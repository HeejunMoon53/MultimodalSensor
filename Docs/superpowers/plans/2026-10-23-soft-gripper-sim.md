# 소프트 그리퍼 + 단일 전극 센서 제어 시뮬레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 3지 TPU 소프트 그리퍼(MuJoCo 3D) + 손가락 안쪽 단일 전극 센서 → 실제 v4 Gate-MoE → 게이트 기반 위치/admittance 제어 폐루프 시뮬레이션과 국문 A–Z 보고서를 만든다.

**Architecture:** Python 단일 프로세스. MuJoCo(0.25 ms)가 손가락·물체·접촉을 적분하고, 1 ms마다 센서 순방향 모델(0909 실측 곡면) → TDM 노이즈 → numpy로 이식한 v4 MoE → 재질 판별 → 제어기 → 액추에이터(텐던|공압) 토크를 `qfrc_applied`로 넣는다. 실험 러너가 시나리오 E1~E7을 돌려 csv/png/mp4와 docx를 만든다.

**Tech Stack:** Python 3.13 (`C:/ml_env/Scripts/python.exe`), mujoco, numpy, scipy, pandas, scikit-learn, matplotlib, imageio + imageio-ffmpeg, python-docx, pytest.

**Spec:** `Docs/superpowers/specs/2026-10-23-soft-gripper-sim-design.md`

## Global Constraints

- 모든 명령은 `C:/ml_env/Scripts/python.exe` 사용. 테스트: `C:/ml_env/Scripts/python.exe -m pytest sim_gripper/tests -q` (repo 루트에서).
- 코드 위치 `sim_gripper/`, 산출물 `sim_gripper/out/` (git 제외: `sim_gripper/out/` 를 `.gitignore`에 추가).
- 단위: MuJoCo 내부는 SI(m, N, rad). 센서·제어 인터페이스는 ε[%], d[mm], F[N], ΔL·ΔR[%].
- 주기: 물리 `dt = 0.00025 s`, 센서·MoE·제어 `Ts = 0.001 s` (물리 4 서브스텝).
- 그래프 색: ΔL `#FF8C00`, ΔR `#2CA02C`, V `#1F77B4` (CLAUDE.md).
- v4 모델: `nn_decoupling/test0909_realtime/new/stm32_deploy_moe_v4/models.pkl` (dict: gate, expert_a, expert_b, sc_gate, sc_a, sc_b, gate_cols, feature_cols, force_offset). 읽기 전용.
- 펌웨어 동작 그대로: 게이트 입력 (ΔL, ΔR)만, threshold 0.5, `EMA_ALPHA = 0.00098716675`, 게이트 판단이 바뀐 **그 사이클에** EMA를 원본값으로 리셋, 첫 호출도 리셋. 출력 클램프 strain [−2, 32], dist [−1.7, 26.09], force [−2.347, 15.69].
- 프리스트레치 ε₀ = 15 %, h = 3 mm, 센서 구간 = 손가락 관절 index 1, 2 (길이 40 mm).
- 재질 상수 `K_MAT = {"conductor": 1.0, "dielectric": -0.1}`.
- Material Lookup: conductor (F_t 4.0 N, F_max 8.0 N), dielectric (1.5 N, 3.0 N), unknown → dielectric 값.
- 계란 파손 임계 3.5 N.
- 커밋은 태스크마다 로컬 커밋, 메시지 국문 한 줄 + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. push는 전체 완료 후 사용자에게 물어본다.
- 보고서·그래프의 모든 수치는 "시뮬레이션 결과"로 표기, M7은 "시뮬레이션 내 방법론 시연, 실물 근거 아님" 문구 필수.

## Review Focus

1. 유전체 잔차(+0.3~2 %)가 ε̂ 추정오차(1~2 %p → ΔL 0.7~1.4 %)에 묻혀 재질을 오판 → 연속 지속 조건으로 막는다 (Task 4 `test_strain_error_does_not_flip_material`).
2. 접촉 경계에서 게이트 깜빡임(실측 test2에서 87 %) → 제어 출력이 튐 → u 변화가 속도 제한 이하 (Task 7 `test_gate_flicker_bounded`).
3. 과굽힘으로 ε가 0~30 % 밖 → 순방향 클립, Safety 동작 (Task 2 `test_strain_clip`, Task 7 `test_safety_on_eps_out_of_range`).
4. OpenGL 없는 환경에서 렌더 실패 → 시뮬레이션은 끝까지 돌고 영상만 생략 (Task 9 `test_run_without_video_when_render_fails`).
5. 물체가 빠지거나 접촉이 안 됨 → GRASP에서 영원히 대기 → 타임아웃 후 RELEASE + 실패 플래그 (Task 7 `test_grasp_timeout_releases`).

---

### Task 1: 환경 설정 + v4 MoE numpy 이식 (M3)

**Files:**
- Create: `sim_gripper/__init__.py`, `sim_gripper/perception/__init__.py`, `sim_gripper/perception/moe.py`, `sim_gripper/tests/__init__.py`, `sim_gripper/tests/conftest.py`, `sim_gripper/tests/test_moe.py`
- Modify: `.gitignore` (+ `sim_gripper/out/`)

**Interfaces:**
- Produces:
  - `DEFAULT_PKL: Path`, `EMA_ALPHA = 0.00098716675`
  - `mlp_forward(mlp, x: np.ndarray) -> np.ndarray` — sklearn MLP 가중치로 numpy 순전파. 은닉 tanh, 회귀는 항등 출력 (n,2), 이진 분류는 sigmoid 출력 (n,) = P(class 1).
  - `@dataclass MoeOut: strain_pct: float; value: float; contact: int; gate_proba: float` (value = contact 0이면 dist_mm, 1이면 force_N)
  - `class MoE: __init__(self, pkl_path: Path = DEFAULT_PKL, models: dict | None = None)`, `reset() -> None`, `step(dL: float, dR: float, dt_s: float = 0.001) -> MoeOut`. dt_s≠0.001이면 α = 1 − (1 − EMA_ALPHA)^(dt_s/0.001).
  - `MoE.models: dict` (fine-tune 실험이 교체 가능)

- [ ] **Step 1: 의존성 설치**
  Run: `C:/ml_env/Scripts/python.exe -m pip install mujoco pytest imageio imageio-ffmpeg`
  Expected: 설치 성공, `python -c "import mujoco; print(mujoco.__version__)"` ≥ 3.1.

- [ ] **Step 2: 실패 테스트 작성** (`test_moe.py`)
```python
def test_mlp_forward_matches_sklearn(models):
    x = np.random.default_rng(0).normal(size=(200, 4))
    assert np.allclose(mlp_forward(models["expert_a"], x), models["expert_a"].predict(x), atol=1e-9)
    xg = x[:, :2]
    assert np.allclose(mlp_forward(models["gate"], xg), models["gate"].predict_proba(xg)[:, 1], atol=1e-9)

def test_gate_replay_matches_board():
    # moe_monitor_20260910_010437_test.csv, mode ∈ {0,1} 행만
    agree = ...  # MoE().step(dL_pct, dR_pct, dt_s=행 간 Δt).contact == mode
    assert agree.mean() >= 0.99

def test_expert_strain_tracks_board():
    # 같은 재생, strain_pct 출력 vs 보드 strain_pct
    assert r2(board_strain, sim_strain) >= 0.95

def test_ema_reset_on_gate_change():
    # 같은 사이클에 리셋: 비접촉 다수 스텝 후 접촉 입력 첫 스텝의 내부 EMA == 그 스텝 원본값
```
  `conftest.py`: repo 루트를 `sys.path`에 추가, `models` fixture(pickle 로드).

- [ ] **Step 3: 실패 확인** — `pytest sim_gripper/tests/test_moe.py -q` → ImportError.

- [ ] **Step 4: `perception/moe.py` 구현** — 펌웨어 `moe_inference.c` 순서 그대로(게이트 → EMA 리셋/블렌드 → 전문가), 스케일러는 `(x-mean_)/scale_`, 클램프 Global Constraints 값.

- [ ] **Step 5: 통과 확인** — 4개 PASS.

- [ ] **Step 6: Commit** — `"시뮬: v4 Gate-MoE numpy 이식 및 보드 로그 재생 검증"`

---

### Task 2: 센서 순방향 모델 + TENG (M1)

**Files:**
- Create: `sim_gripper/sensor/__init__.py`, `sim_gripper/sensor/build_tables.py`, `sim_gripper/sensor/forward.py`, `sim_gripper/sensor/tables.npz` (생성물, 커밋함), `sim_gripper/tests/test_forward.py`

**Interfaces:**
- Consumes: `nn_decoupling/test0909_realtime/new/plot_new_training_data.py` 의 `load()`, `grid()` (import만, 수정 금지).
- Produces:
  - `build_tables(out_path: Path) -> None` — npz 키: `eps` (0..30 step 0.5), `d` (0..24 step 0.5), `F` (0..12 step 0.25), `dL_eps(eps)`, `dR_eps(eps)`, `dL_prox(eps,d)`, `dL_F(eps,F)`, `dR_F(eps,F)`. 근거: ΔL_ε/ΔR_ε = 214746 prox≈24 mm 슬라이스, ΔL_prox = 근접 곡면(214746+222022, mode 0) − 곡면(ε, 24), ΔL_F/ΔR_F = 압력 곡면(220210, mode 1) − 곡면(ε, F=0). 격자화는 기존 `grid()`(bin 평균 + NaN-가중 가우시안) 사용, 1D는 `poly`/bin 평균.
  - `@dataclass DomainShift: d_eps: float = 0.0; gamma: float = 0.0; scale: float = 1.0`
  - `class SensorForward: __init__(self, tables_path: Path = DEFAULT_TABLES)`
    - `strain_from_curvature(kappa_bar_per_mm: float, eps0: float = 15.0, h_mm: float = 3.0) -> float` = clip(ε₀ − 100·h·κ̄, 0, 30)
    - `dL_eps(eps: float) -> float`
    - `signals(eps: float, d_mm: float, F_N: float, material: str, shift: DomainShift | None = None, kappa_bar_per_mm: float = 0.0) -> tuple[float, float]` → (ΔL, ΔR). 시프트: ε' = ε + d_eps, ΔL' = scale·ΔL + gamma·100·h·κ̄, ΔR' = scale·ΔR. d는 [0, 24]로, F는 [0, 12]로 클립, d > 24는 근접항 0.
  - `class TengModel: __init__(self, tau_s: float = 0.05, gain: float = 1.0)`, `step(F_N: float, dt_s: float) -> float` — τ·V̇ + V = g·Ḟ 후진오일러, `reset()`.

- [ ] **Step 1: 실패 테스트** (`test_forward.py`, tables 생성 후 사용)
```python
def test_strain_only(fwd):      # ε=30, d=24, F=0, conductor
    dL, dR = fwd.signals(30, 24, 0, "conductor"); assert abs(dL-20.0)<1.5 and abs(dR-20.9)<1.5
def test_conductor_near(fwd):   # ε=0, d=1
    dL, dR = fwd.signals(0, 1, 0, "conductor"); assert abs(dL+22)<2.5 and abs(dR)<0.5
def test_dielectric_near(fwd):
    dL, _ = fwd.signals(0, 1, 0, "dielectric"); assert 1.5 < dL < 3.0
def test_pressure(fwd):         # ε=0, d=0, F=10
    _, dR = fwd.signals(0, 0, 10, "conductor"); assert abs(dR-20)<4
def test_strain_clip(fwd):
    assert fwd.strain_from_curvature(1.0) == 0.0 and fwd.strain_from_curvature(-1.0) == 30.0
def test_teng_sign():
    # F 0→3 N 계단 → 양의 피크, 3→0 → 음의 피크, 0.5 s 후 |V| < 5 % 피크
```

- [ ] **Step 2: 실패 확인** → ImportError.
- [ ] **Step 3: `build_tables.py` 구현 후 1회 실행해 `tables.npz` 생성**
  Run: `C:/ml_env/Scripts/python.exe -m sim_gripper.sensor.build_tables`
- [ ] **Step 4: `forward.py` 구현** (`RegularGridInterpolator`, 2D는 linear, 1D는 `np.interp`).
- [ ] **Step 5: 통과 확인** — 6 PASS. 기준값 실패 시 tables 생성 로직(슬라이스 선택)부터 점검, 허용오차는 바꾸지 않는다.
- [ ] **Step 6: Commit** — `"시뮬: 0909 실측 기반 센서 순방향 모델과 TENG 모델"`

---

### Task 3: TDM 샘플러 (M2)

**Files:** Create `sim_gripper/sensor/tdm.py`, `sim_gripper/tests/test_tdm.py`

**Interfaces:**
- Produces:
  - `noise_from_data() -> tuple[float, float]` — 세션 214746 원시 `dL_pct`, `dR_pct`의 std(diff(x))/√2.
  - `class TdmSampler: __init__(self, sigma_L: float, sigma_R: float, seed: int = 0)`, `sample(dL: float, dR: float) -> tuple[float, float]`.

- [ ] **Step 1: 테스트** — `test_noise_reproducible` (같은 seed 동일 시퀀스), `test_noise_level` (10k 샘플 std가 σ의 ±5 %), `test_noise_from_data_positive` (0 < σ < 1 %).
- [ ] **Step 2: 실패 확인 → Step 3: 구현 → Step 4: PASS**
- [ ] **Step 5: Commit** — `"시뮬: TDM 샘플러와 실측 노이즈 추정"`

---

### Task 4: 재질 판별 (M4)

**Files:** Create `sim_gripper/perception/material.py`, `sim_gripper/tests/test_material.py`

**Interfaces:**
- Consumes: `SensorForward.dL_eps`
- Produces: `class MaterialClassifier: __init__(self, fwd: SensorForward, theta: float = 0.5, persist_steps: int = 50)`, `update(dL_meas: float, eps_hat: float, contact: int) -> str` ∈ {"conductor", "dielectric", "unknown"}, `reset()`.
  규칙: r = dL_meas − fwd.dL_eps(eps_hat). r < −θ가 연속 persist_steps 이상 → conductor, r > +θ 연속 → dielectric, 그 외 이전 판단 유지(초기 unknown). contact가 처음 1이 된 순간의 판단을 래치(이후 고정), reset()으로만 해제.

- [ ] **Step 1: 테스트**
```python
def test_conductor_approach(): # fwd.signals로 d 20→2 mm 접근 시퀀스 → "conductor"
def test_dielectric_approach(): # 같은 시퀀스 dielectric → "dielectric"
def test_far_is_unknown():      # d=24 고정 → "unknown"
def test_latched_after_contact():# 접촉 후 반대 부호 입력 100 스텝 → 판단 유지
def test_strain_error_does_not_flip_material():
    # dielectric 접근 중 eps_hat에 ±1.5 %p 1 kHz 무작위 오차 주입 → 결과 != "conductor"
```
- [ ] **Step 2~4: 실패 → 구현 → PASS** (실패 시 θ/persist만 조정 가능, 조정값을 docstring에 기록)
- [ ] **Step 5: Commit** — `"시뮬: ΔL 잔차 부호 기반 재질 판별"`

---

### Task 5: 액추에이터 (M6)

**Files:** Create `sim_gripper/actuators/__init__.py`, `tendon.py`, `pneumatic.py`, `sim_gripper/tests/test_actuators.py`

**Interfaces:**
- Produces (공통 `step(u: float, q: np.ndarray, dt: float) -> np.ndarray` (관절 토크 N·m, shape (4,)), `reset()`):
  - `TendonActuator(r_j=0.006, r_p=0.01, k_t=2000.0, theta_max=3.0, tau_m=0.02, omega_max=10.0)` — θ̇ₘ = sat((u·θ_max − θₘ)/τₘ, ±ω_max); T = k_t·max(0, r_p·θₘ − Σ r_j·qⱼ); τⱼ = r_j·T.
  - `PneumaticActuator(P_max=60e3, tau_p=0.15, Pdot_max=400e3, alpha=1.0e-5, beta=0.3)` — Ṗ = sat((u·P_max − P)/τ_p, ±Pdot_max); τⱼ = α·P·(1 − β·qⱼ), 음수면 0.
  - `make_actuator(kind: str) -> TendonActuator | PneumaticActuator` (kind ∈ {"tendon", "pneumatic"})

- [ ] **Step 1: 테스트** — `test_tendon_slack_zero` (u=0 → τ=0), `test_tendon_time_constant` (작은 계단 u=0.05에서 θₘ가 t=τₘ에 63±5 %), `test_pneumatic_time_constant` (u=0.05), `test_pneumatic_rate_limit` (u=1 계단에서 |Ṗ| ≤ Pdot_max), `test_pneumatic_efficiency_drops_with_q`.
- [ ] **Step 2~4: 실패 → 구현 → PASS**
- [ ] **Step 5: Commit** — `"시뮬: 텐던·공압 액추에이터 모델"`

---

### Task 6: MuJoCo 그리퍼·물체 모델 (M0)

**Files:** Create `sim_gripper/model/__init__.py`, `sim_gripper/model/gripper.py`, `sim_gripper/tests/test_gripper.py`

**Interfaces:**
- Produces:
  - `@dataclass FingerParams: L_mm=80.0, w_mm=20.0, t_mm=6.0, E_Pa=26e6, n_joints=4, zeta=0.3` + `joint_stiffness() -> float` = E·w·t³/12 / (L/n) (SI).
  - `@dataclass ObjectSpec: name: str; shape: str ("cylinder"|"capsule"|"sphere"); size: tuple; mass_kg: float; material: str; fragile_F_N: float | None = None; soft: bool = False`
  - `build_mjcf(fp: FingerParams, obj: ObjectSpec) -> str` — 베이스(수직 slide 관절 "lift" + position 액추에이터) 아래 120° 간격 손가락 3개, 각 손가락 hinge 4개(stiffness=joint_stiffness, damping from ζ), 세그먼트 박스 geom, 관절 1·2 세그먼트 안쪽면에 pad geom `pad_{i}_{1,2}`. 물체는 테이블 위, soft면 `solref="0.02 1"`, 아니면 기본. timestep 0.00025.
  - `class GripperSim: __init__(self, fp: FingerParams, obj: ObjectSpec)`
    - `step(tau: np.ndarray (3,4), lift_target_m: float) -> None` (qfrc_applied 설정 후 mj_step 1회)
    - `joint_angles() -> np.ndarray (3,4)`, `kappa_bar_per_mm() -> np.ndarray (3,)` = (q[:,1]+q[:,2]) / 40
    - `pad_distance_mm() -> np.ndarray (3,)` — `mj_geomDistance`(pad 두 개 중 최소, cutoff 0.03 m, 그 이상 24 이상값), 접촉 시 0.
    - `pad_force_N() -> np.ndarray (3,)` — pad geom이 물체와 맺은 접촉 법선력 합(`mj_contactForce`).
    - `object_height_m() -> float`, `apply_object_force(f_xyz: np.ndarray) -> None`, `object_broken: bool` (fragile_F_N이 있고 3지 합력 > 임계 시 True, 래치)
    - `render_frame(width=640, height=480) -> np.ndarray | None` (렌더 예외 시 None)

- [ ] **Step 1: 테스트**
```python
def test_model_loads():          # mujoco.MjModel.from_xml_string 성공, hinge 12개
def test_joint_stiffness():      # FingerParams().joint_stiffness() ≈ 0.47 ± 0.05
def test_distance_decreases():   # 손가락 닫는 토크 → pad_distance_mm 감소
def test_contact_force_positive():# 금속 원통, 닫는 토크 1 s → 3지 모두 pad_force_N > 0
def test_egg_breaks():           # fragile 3.5 N 물체, 큰 토크 → object_broken True
```
- [ ] **Step 2~4: 실패 → 구현 → PASS**
- [ ] **Step 5: Commit** — `"시뮬: MuJoCo 3지 PRBM 그리퍼와 물체 모델"`

---

### Task 7: 제어기 (M5)

**Files:** Create `sim_gripper/control/__init__.py`, `sim_gripper/control/controller.py`, `sim_gripper/tests/test_controller.py`

**Interfaces:**
- Consumes: `MoeOut` (Task 1)
- Produces:
  - `MATERIAL_TABLE = {"conductor": (4.0, 8.0), "dielectric": (1.5, 3.0)}` (F_t, F_max), unknown → dielectric.
  - `@dataclass CtrlParams: u_open=0.0, u_pre=0.35, d0_mm=20.0, d1_mm=3.0, u_rate_max=0.8, B_a=2.0, F_dead=0.1, Fdot_max=50.0, eps_range=(0.0, 30.0), grasp_timeout_s=3.0`
  - `class FingerController: __init__(self, p: CtrlParams)`, `step(m: MoeOut, material: str, phase: str, dt: float) -> float` (u ∈ [0,1]), `reset()`, 속성 `safety_trip: bool`.
    - phase "OPEN"/"RELEASE": u → u_open (속도 제한).
    - "APPROACH": contact 0이면 pre-shape 식, contact 1이면 admittance.
    - "GRASP"/"HOLD": admittance u += (dt/B_a)·(F_t − F̂) (|F_t − F̂| ≤ F_dead면 0). 
    - Safety: F̂ > F_max 또는 dF̂/dt > Fdot_max 또는 ε̂ ∉ eps_range → safety_trip, u를 2·u_rate_max로 감소, F̂ < 0.5·F_max 되면 해제.
    - contact 값이 바뀐 스텝에 admittance 내부 상태(이전 F̂, 미분값) 리셋.
    - 모든 phase에서 |Δu| ≤ u_rate_max·dt (safety는 2배).
  - `class GraspSupervisor: __init__(self, p: CtrlParams)`, `update(t: float, contacts: list[int], cmd: str | None) -> str`, 속성 `phase`, `failed: bool`. cmd ∈ {"approach", "lift", "release"}. APPROACH→GRASP: 3지 모두 contact; GRASP 진입 대기 > grasp_timeout_s → RELEASE + failed=True; "lift" → HOLD; "release" → RELEASE.

- [ ] **Step 1: 테스트** — `test_open_goes_to_u_open`, `test_preshape_monotonic_bounded` (d̂ 20→3 → u 단조 증가, ≤ u_pre), `test_admittance_increment` (F̂ = F_t − 1 → Δu = dt/B_a), `test_safety_on_force`, `test_safety_on_eps_out_of_range`, `test_gate_flicker_bounded` (contact 0/1 교대 1000 스텝 → 모든 |Δu| ≤ u_rate_max·dt·2), `test_unknown_uses_dielectric`, `test_grasp_timeout_releases`.
- [ ] **Step 2~4: 실패 → 구현 → PASS**
- [ ] **Step 5: Commit** — `"시뮬: 게이트 기반 상태 머신·admittance·안전 계층 제어기"`

---

### Task 8: 폐루프 + 시나리오 + 통합 테스트

**Files:** Create `sim_gripper/sim/__init__.py`, `sim_gripper/sim/scenarios.py`, `sim_gripper/sim/loop.py`, `sim_gripper/tests/test_integration.py`

**Interfaces:**
- Consumes: Task 1~7 전부.
- Produces:
  - `@dataclass Scenario: name: str; obj: ObjectSpec; t_end: float; events: list[tuple[float, str]]; disturbance: tuple[float, float, tuple[float,float,float]] | None = None`
  - `SCENARIOS: dict[str, Scenario]` — 키 `E1_metal`(원통 r 25 mm, 0.2 kg, conductor), `E2_hand`(캡슐 r 20 mm, dielectric), `E2_egg`(구 r 22 mm, 0.06 kg, dielectric, fragile 3.5), `E3_sponge`(원통 r 25, soft, dielectric), `E3_small`(원통 r 15, conductor), `E3_large`(원통 r 35, conductor), `E4_disturb`(E1 + t 6~7 s 수평 3 N). 공통 이벤트: (0.5, "approach"), (4.0, "lift"), (8.0, "release"), t_end 10 s.
  - `run(scenario: Scenario, actuator: str = "tendon", sensor_mode: str = "pipeline", shift: DomainShift | None = None, moe_models: dict | None = None, record_video: bool = False, seed: int = 0) -> tuple[pd.DataFrame, list[np.ndarray] | None]`
    - 로그 1 kHz, 손가락 i∈{0,1,2}별 열: `t, phase, eps_true_i, d_true_i, F_true_i, dL_i, dR_i, V_i, eps_hat_i, value_i, contact_i, gate_proba_i, material_i, u_i, safety_i`, 공통 `obj_z, broken, failed`.
    - sensor_mode "ideal": MoeOut을 참값 + TDM 노이즈 크기의 가우시안으로 대체(재질은 참값).
    - 영상: record_video면 33 ms마다 `render_frame`, None이면 영상 없이 진행.

- [ ] **Step 1: 테스트** — `test_e1_lifts_object` (E1_metal 텐던: t=7 s에 obj_z − 초기 ≥ 0.02 m, failed False), `test_e2_egg_not_broken` (E2_egg: broken False), `test_e2_hand_low_force` (HOLD 구간 F_true 평균 < 3.0 N).
- [ ] **Step 2~4: 실패 → 구현 → PASS** (실패 시 CtrlParams·액추에이터 파라미터 조정 허용, 조정 내역을 보고서 파라미터 표에 반영)
- [ ] **Step 5: Commit** — `"시뮬: 폐루프 실행기와 시나리오, 통합 테스트"`

---

### Task 9: 실험 E1~E6 + 시각화 (M8)

**Files:** Create `sim_gripper/viz/__init__.py`, `sim_gripper/viz/plots.py`, `sim_gripper/viz/render.py`, `sim_gripper/experiments/__init__.py`, `sim_gripper/experiments/run_all.py`, `sim_gripper/tests/test_experiments.py`

**Interfaces:**
- Produces:
  - `compute_metrics(df: pd.DataFrame) -> dict` — `force_rmse` (HOLD 구간 F_true vs F_t), `max_force`, `overshoot_pct`, `settle_s` (±10 % 진입), `success` (리프트 ≥ 2 cm & not failed & not broken), `gate_acc` (contact vs F_true>0.05), `strain_r2`, `material_acc`.
  - `plot_timeline(df: pd.DataFrame, finger: int, path: Path) -> None` — 6패널: ε(참/추정), d(참/추정), F(참/추정, F_t/F_max 선), ΔL·ΔR, V, phase·contact·material.
  - `plot_actuator_compare(results: dict[str, pd.DataFrame], path: Path) -> None`
  - `save_mp4(frames: list[np.ndarray], path: Path, fps: int = 30) -> None`
  - `run_all(out_dir: Path) -> dict` — E1~E4 × {tendon, pneumatic} + E6(E1·E2_hand ideal vs pipeline). `out_dir/metrics.json`, `timeline_<scenario>_<act>.png`, `compare_actuators.png`, `ideal_vs_pipeline.png`, `E1_metal_tendon.mp4`.

- [ ] **Step 1: 테스트** — `test_metrics_on_synthetic_df` (손으로 만든 df에서 force_rmse·success 기대값), `test_run_without_video_when_render_fails` (render_frame를 None 반환하게 monkeypatch → run 정상 완료, 영상 None).
- [ ] **Step 2~4: 실패 → 구현 → PASS**
- [ ] **Step 5: 실행** — `C:/ml_env/Scripts/python.exe -m sim_gripper.experiments.run_all` → out/에 위 파일 생성, metrics.json에 E1_metal_tendon success true.
- [ ] **Step 6: Commit** — `"시뮬: 실험 E1~E6 러너와 그래프·영상"`

---

### Task 10: 도메인 시프트 + fine-tune 실험 (M7)

**Files:** Create `sim_gripper/experiments/domain_shift.py`, `sim_gripper/tests/test_domain_shift.py`

**Interfaces:**
- Consumes: `run(..., shift=, moe_models=)`, `DomainShift`, `MoE.models`
- Produces:
  - `DEFAULT_SHIFT = DomainShift(d_eps=3.0, gamma=0.2, scale=1.1)`
  - `collect_sim_data(shift: DomainShift, n_samples: int, seed: int) -> pd.DataFrame` — 시나리오 E1·E2_hand·E3_small 실행, 100 Hz로 다운샘플, 열 `dL, dR, dL_ema, dR_ema, strain, dist, force, contact` (EMA는 펌웨어 α로 재계산).
  - `adapt(method: str, base: dict, data: pd.DataFrame, flat: pd.DataFrame | None = None) -> dict` — method ∈ {"recal", "finetune", "mixed", "scratch"}:
    - recal: 스케일러만 data로 재적합 + 전문가 출력에 선형 보정(LinearRegression)
    - finetune: deepcopy, `warm_start=True, learning_rate_init=1e-4, max_iter=200, early_stopping=False`, 기존 스케일러로 fit
    - mixed: finetune + 0909 원본 데이터 동량 혼합
    - scratch: 같은 hidden 구조 새 모델, 새 스케일러
  - `run_domain_shift(out_dir: Path, n_list=(500, 2000, 8000, 20000)) -> dict` — 시프트 없는 v4, 시프트 v4, 4방법 × n_list의 루프 내 strain/dist/force R², 0909 test 셋 성능(망각). `out_dir/domain_shift.json`, `domain_shift_recovery.png`.

- [ ] **Step 1: 테스트** — `test_shift_degrades_v4` (시프트 데이터에서 v4 strain R² < 비시프트 R²), `test_finetune_recovers` (n=8000 finetune strain R² > 시프트 v4 R²), `test_adapt_keeps_architecture` (finetune 후 hidden_layer_sizes 및 모든 coefs_/intercepts_ shape 동일 — 총 1,413 파라미터 유지).
- [ ] **Step 2~4: 실패 → 구현 → PASS**
- [ ] **Step 5: 실행** → json·png 생성
- [ ] **Step 6: Commit** — `"시뮬: 장착 도메인 시프트와 fine-tune 비교 실험"`

---

### Task 11: A–Z 보고서 (docx)

**Files:** Create `sim_gripper/report/__init__.py`, `sim_gripper/report/build_report.py`, `sim_gripper/tests/test_report.py`

**Interfaces:**
- Consumes: `out/metrics.json`, `out/domain_shift.json`, out/ png들, 각 모듈 파라미터 dataclass 기본값(하드코딩 금지, import해서 표에 채움).
- Produces: `build_report(out_dir: Path) -> Path` → `out_dir/소프트그리퍼_시뮬레이션_보고서.docx`.
  장 구성(제목 고정): 1 개요와 목적 · 2 시스템 구조(Fig.1(b) 대응) · 3 M0 손가락 기구 · 4 M1 센서 순방향 모델 · 5 M2 TDM · 6 M3 Gate-MoE · 7 M4 재질 판별 · 8 M5 제어기 · 9 M6 액추에이터 · 10 실험 E1~E6 결과 · 11 M7 도메인 시프트와 fine-tune · 12 한계와 향후 과제 · 부록 A 파라미터 표 · 부록 B 기호표.
  각 모듈 장: 개념 → 수식 → 파라미터 → 검증(해당 단위테스트 근거) → 한계. 11장 첫 문단에 "시뮬레이션 내 방법론 시연, 실물 근거 아님".

- [ ] **Step 1: 테스트** — `test_report_has_all_chapters` (docx 제목 목록에 14개 장 포함), `test_report_has_disclaimer` (11장 첫 문단에 문구 포함), `test_report_numbers_from_metrics` (보고서의 E1 force_rmse 문자열 == metrics.json 값 포맷).
- [ ] **Step 2~4: 실패 → 구현 → PASS**
- [ ] **Step 5: 생성** — `C:/ml_env/Scripts/python.exe -m sim_gripper.report.build_report`
- [ ] **Step 6: Commit** — `"시뮬: A-Z 보고서 생성기"`
