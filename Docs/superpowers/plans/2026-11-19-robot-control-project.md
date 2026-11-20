# MEC799 PneuNet 2지 센서 되먹임 제어 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MuJoCo flex PneuNet 2지 플랜트(비이상성 포함)를 만들고, 그 위에 시스템 식별 → 상태공간 해석 → 극배치·관측기·LQR → 칼만·LQG → DOB → 상위 루프(근접·속도·어드미턴스·재질)를 구현해 그림·지표·편집 가능한 PPT를 낸다.

**Architecture:** `code/`의 모듈은 각자 한 책임을 맡는다.
- 플랜트: `finger_flex` + `pneumatics` + `plant`
- 설계: `sysid` → `analysis` → `design_*`. 설계는 **식별 모델만** 보고, 플랜트 내부 파라미터를 보지 않는다.
- 실행·보고: `supervisor` + `run_compare` + `build_pptx`
- 모든 설계 결과는 `params.json`에 쓰고 읽는다.

**Tech Stack:** Python (`C:/ml_env/Scripts/python.exe`), MuJoCo 3.17 flexcomp, numpy, scipy (signal, linalg), python-pptx 1.0.2, imageio, pytest. 기존 `sim_gripper.sensor`·`sim_gripper.perception` 재사용. `control`·`gmsh`는 설치되어 있지 않다. 설치하지 않고 scipy와 직접 구현으로 해결한다.

**Spec:** `Docs/superpowers/specs/2026-11-19-robot-control-project-design.md`

## Global Constraints

- 코드 위치: `Hardware/로봇제어프로젝트/code/`, 테스트 `code/tests/`, 출력 `Hardware/로봇제어프로젝트/out/`
- 실행 위치: 저장소 루트. `code/`는 `sys.path`로 넣는다. `conftest.py`가 `code/`와 저장소 루트를 경로에 추가한다.
- 단위: 압력 kPa, 변형률 ε는 % (MoE와 같음), 힘 N, 거리 mm, 시간 s. 제어 주기 **Ts = 0.01 s**, MuJoCo 스텝은 Task 1에서 정한다(≤ 1 ms).
- 압력 범위 **0–30 kPa**(지령 상한 30, ITV F_2 50). 보정 목표: **30 kPa에서 끝단 굽힘 약 300°**.
- ITV: 감도 **1 kPa** 계단, 데드밴드 **0.3 kPa**(처음 열릴 때 튐 포함), 1차 지연 τ_v, 순수 지연 θ_v. 초깃값은 가정값이고 `params.json["plant"]`에 둔다.
- 재질은 `"conductor" | "human" | "dielectric"` 세 가지만 쓴다.
- 재질표는 F_block 비율로 둔다. 도체 (0.5, 0.8), 유전체 (0.35, 0.6), 인체 (0.15, 0.3). B_a 배수는 1 / 1.5 / 3, v_max 배수는 1 / 0.7 / 0.4.
- 손가락 기하는 `Hardware/pneunet_gripper/build_cad.py`의 `PP` 기본값을 import해서 쓴다. 복사하지 않는다. 비신장층(종이)은 없고, 몸체·바닥층 모두 DS30이다.
- 모든 그림·PPT 수치 옆에 "시뮬레이션"을 표시한다. 미정·가정값은 PPT에서 노란 칸(`FFF2CC`)으로 둔다.
- 플롯 색: 인덕턴스 L `#FF8C00`, 저항 R `#2CA02C`, TENG `#1F77B4` (CLAUDE.md). 그 밖의 신호는 자유롭게 정한다.
- 커밋: CLAUDE.md 규칙에 따라 **작업 중에는 커밋하지 않는다**. 전체가 끝나면 사용자에게 묻는다. ledger의 커밋 범위 칸은 `uncommitted`로 둔다.
- 같은 시드는 같은 결과를 내야 한다(MuJoCo는 결정적, 잡음은 `np.random.default_rng(seed)`).

## Review Focus

1. 지령 u가 음수, NaN, 30 kPa 초과일 때 플랜트는 포화로 처리하고, 예외나 NaN 상태를 만들지 않아야 한다 → Task 2 `test_itv_bad_input`.
2. flex가 발산하면(정점 속도 NaN 또는 끝단 이동 > 200 mm/스텝) `plant.step`은 조용히 진행하지 말고 `PlantDiverged`를 던져야 한다 → Task 3 `test_divergence_raises`.
3. 식별 데이터가 상수 입력(가진 부족)이면 `arx_ls`는 특이 행렬로 엉터리 계수를 내지 말고 `ValueError`를 던져야 한다 → Task 4 `test_arx_rejects_unexciting_input`.
4. 극배치 대상 극이 중복이거나 |z| ≥ 1이면 경고 없이 불안정 게인을 내지 말아야 한다. 중복 극은 Ackermann으로 처리하고, |z| ≥ 1은 `ValueError` → Task 6 `test_place_rejects_unstable_target`.
5. 접촉이 없는데 F̂가 잡음으로 튀는 경우, 상위 루프가 GRASP로 넘어가 손가락을 조이면 안 된다. 게이트 = 접촉이 연속 3 샘플일 때만 전이한다 → Task 9 `test_no_grasp_on_force_noise`.

---

### Task 1: flex 손가락 + 스파이크 S0 (보정·결정)

**Files:**
- Create: `Hardware/로봇제어프로젝트/code/finger_flex.py`, `code/s0_spike.py`, `code/conftest.py`, `code/params.json`
- Test: `code/tests/test_finger_flex.py`

**Interfaces:**
- Produces:
  - `FlexFinger(young_pa: float = 1.0e6, poisson: float = 0.45, sensor_z_mm: float = 2.0, res: str = "coarse")`
  - `.mjcf(name: str, pos: tuple, quat: tuple) -> str`: `<worldbody>` 안에 넣을 XML 조각
  - `.attach(model, data, name)`: 정점 id와 방 내벽 면 목록을 찾는다
  - `.apply_pressure(data, p_kpa: float)`: 방 내벽 면에 f = p·A·n을 정점에 나눠 `xfrc_applied`로 건다
  - `.chamber_volume(data) -> float` [mm³]
  - `.sensor_strain(data) -> float` [%]: 센서 선 길이 변화
  - `.tip_angle(data) -> float` [deg]: 뿌리 접선 대비 끝 접선, 누적 각이라 300°까지 표현
  - `build_single(finger) -> (MjModel, MjData)`
  - `params.json["plant"]`: `{"young_pa", "poisson", "sensor_z_mm", "dt_sim", "model": "flex"|"prbm", "V_of_p": [[p, V], ...]}`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_rest_at_zero_pressure():
    f = FlexFinger(); m, d = build_single(f)
    for _ in range(500): f.apply_pressure(d, 0.0); mujoco.mj_step(m, d)
    assert abs(f.tip_angle(d)) < 2.0

def test_bends_and_inflates_monotonic():
    f = FlexFinger(); m, d = build_single(f)
    ang, vol = [], []
    for p in (0, 10, 20):
        settle(f, m, d, p, 1.0)          # tests/helpers: p를 1 s 유지
        ang.append(f.tip_angle(d)); vol.append(f.chamber_volume(d))
    assert ang[0] < ang[1] < ang[2] and vol[0] < vol[1] < vol[2]
```

- [ ] **Step 2: 실행해서 실패 확인**
  - Run: `C:/ml_env/Scripts/python.exe -m pytest Hardware/로봇제어프로젝트/code/tests/test_finger_flex.py -q`
  - Expected: FAIL (`ModuleNotFoundError: finger_flex`)

- [ ] **Step 3: `finger_flex.py` 구현**
  - **메시:** gmsh가 없으므로 직선 격자 육면체를 만든다.
    - x 분할점은 PP의 경계를 그대로 쓴다: 뿌리 15, 방 블록 8 안의 벽 t_in 1.5, 틈 2, 끝벽 +2.
    - y 분할: 옆벽 2 / 안 / 옆벽 2. `res="coarse"`면 안쪽을 2칸으로 나눈다.
    - z 분할: 바닥층 t_base 4(센서 깊이 `sensor_z_mm` 경계 포함) / 받침대 3 / 방 / 윗벽 2.
    - 방 내부 칸은 빈칸으로 둔다. 9개 방은 공기 채널로 이어진다고 보고, 압력은 모두 같다.
    - 각 육면체를 사면체 5개로 나눈다(인접 칸끼리 대각선 방향이 맞게 교대).
  - **MJCF:** `flexcomp type="direct" dim="3"`에 `point`와 `element` 속성을 쓴다. `<elasticity young poisson damping>`, `<contact>`는 켠다.
  - **뿌리 고정:** x < 15 mm 정점을 `pin`으로 고정한다.
  - **둥근 모서리(R_top, r_cav):** 생략한다. 생략은 shortcut 주석으로 남긴다.

- [ ] **Step 4: 테스트 통과 확인**
  - Run: Step 2 명령
  - Expected: 2 passed

- [ ] **Step 5: `s0_spike.py` 실행 — 보정과 결정**
  - young을 이분 탐색해서 30 kPa 정상 상태 tip_angle을 300 ± 15°에 맞춘다.
  - 기록할 값:
    - p = 0..30(5 kPa 간격)의 각도, V, ε. ε는 `sensor_z_mm ∈ {0.5, 2.0, 3.5}` 세 깊이에서 잰다.
    - 1초 시뮬에 걸린 벽시계 시간
  - 판정:
    - 발산 없음, 1 s 시뮬 ≤ 20 s 벽시계 → `"model": "flex"`
    - 아니면 `"model": "prbm"`으로 정하고 Task 1b를 수행한다
  - ε 부호:
    - 30 kPa에서 ε < 0이면 `params.json["plant"]["eps_prestrain"]`에 −min(ε) + 1 %를 넣는다. 센서를 미리 늘린 상태로 매설하는 가정이고, 기존 `SensorForward.eps0`와 같은 방식이다.
    - 이 결정은 ledger에 Ruling으로 남긴다.
  - 그림: `out/S0_calib.png`(각도·V·ε vs p)
  - Expected: `params.json["plant"]`이 채워지고, 터미널에 판정 한 줄이 출력된다.

### Task 1b (조건부: S0 판정이 prbm일 때만): PRBM 대체

**Files:** Create `code/finger_prbm.py`, Test `code/tests/test_finger_prbm.py`
- Produces: `FlexFinger`와 같은 메서드 이름·반환을 가진 `PrbmFinger`. plant는 `params["plant"]["model"]`로 둘 중 하나를 고른다.
- 관절 9개(방마다 하나). 관절 토크는 τ(p, q) 표로 정하고, 표는 S0 flex 정적 결과(굽힘 시작 전 단계까지라도)와 300° 점으로 맞춘다. V(p)는 S0 표를 쓴다. 센서 ε는 곡률 × sensor_z로 계산한다.
- 테스트: Task 1의 두 테스트를 `PrbmFinger`로 그대로 돌린다(같은 이름의 파라미터화 테스트).

### Task 2: ITV + 튜브·방 공압 모델

**Files:** Create `code/pneumatics.py`, Test `code/tests/test_pneumatics.py`

**Interfaces:**
- Produces:
  - `Itv(tau_v=0.05, theta_v=0.01, p_db=0.3, quant=1.0, p_max=30.0, rate_max=200.0, mon_sigma=0.05, seed=0, ideal=False)`
    - `.step(u_kpa: float, dt: float) -> float` (출력 압력 p)
    - `.monitor() -> float` (p_mon, 잡음 포함)
    - `.reset()`
  - `Line(R_t=2.0e-3, kappa=1.0)`
    - `.step(p: float, V_mm3: float, dVdp: float, dt: float) -> float` (방 압력 p_c)
    - 식: C·ṗ_c = (p − p_c)/R_t, C = dV/dp + V/(κ·(p_c + 101.3))
    - 단위는 kPa·mm³로 쓰고, R_t 단위를 docstring에 적는다.
  - `ideal=True`: 지연·데드밴드·계단·잡음을 모두 끈다(1차 지연만 남김). 과제 1절 "켜고 끄기"용이다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_quantized_and_deadband():
    itv = Itv(seed=0, mon_sigma=0.0)
    assert run_to_steady(itv, 0.2) == 0.0                    # 데드밴드
    assert run_to_steady(itv, 12.4) == pytest.approx(12.0)   # 1 kPa 계단
def test_ideal_is_first_order():
    itv = Itv(ideal=True); y = [itv.step(10.0, 1e-3) for _ in range(50)]
    assert y[-1] == pytest.approx(10*(1-np.exp(-0.05/0.05)), rel=0.02)
def test_itv_bad_input():
    itv = Itv()
    for u in (-5.0, float("nan"), 99.0): p = itv.step(u, 1e-3); assert np.isfinite(p) and 0 <= p <= 30
def test_line_settles_to_supply():
    ln = Line(); pc = [ln.step(20.0, 5e4, 2e3, 1e-3) for _ in range(5000)]
    assert pc[-1] == pytest.approx(20.0, abs=0.1)
```

- [ ] **Step 2: 실행해서 실패 확인**
  - Run: `... -m pytest .../tests/test_pneumatics.py -q`
  - Expected: FAIL (import)

- [ ] **Step 3: 구현**
  - NaN은 0으로 처리한다.
  - 순수 지연은 ring buffer로 구현한다.
  - 데드밴드는 목표 < p_db면 0으로 둔다. 처음 열릴 때 튐은 목표가 0에서 처음 넘어갈 때 1회 +quant를 오버슈트한 뒤 1차로 복귀하는 것으로 모델링한다.
  - 1 kPa 계단: 출력은 round(목표/quant)·quant를 1차로 따라간다.

- [ ] **Step 4: 테스트 통과 확인**
  - Expected: 4 passed

### Task 3: 2지 플랜트 래퍼

**Files:** Create `code/plant.py`, Test `code/tests/test_plant.py`

**Interfaces:**
- Consumes: `FlexFinger`(또는 `PrbmFinger`), `Itv`, `Line`, `sim_gripper.sensor.forward.SensorForward`, `sim_gripper.sensor.tdm.TdmSampler, noise_from_data`, `sim_gripper.perception.moe.MoE`
- Produces:
  - `Scenario(material: str = "conductor", obj_kind: str = "cylinder", obj_radius_mm=20.0, obj_start_mm=(0, 0, 120), obj_path=None, tip_load_N=0.0, young_scale=1.0, tau_v_scale=1.0, R_t_scale=1.0)`
    - `obj_path(t) -> (x, y, z)`: 움직이는 손(인체)용
  - `Plant(scn: Scenario, seed=0, nonideal=True, params_path=PARAMS)`
    - `.step(u: np.ndarray[2]) -> Obs`: Ts = 0.01 동안 MuJoCo 여러 스텝
    - `.truth() -> Truth`
    - `.t`
    - `.frames(cam="front") -> np.ndarray`
  - `Obs(p_mon[2], eps_hat[2], val_hat[2], contact[2], gate_p[2])`
    - `val_hat`: MoE 출력. 비접촉이면 d[mm], 접촉이면 F[N]
  - `Truth(p[2], p_c[2], eps[2], eps_dot[2], d_mm[2], F_N[2], tip_deg[2])`
  - `class PlantDiverged(RuntimeError)`
- 센서 체인: 손가락마다 다음을 거친다.
  - ε_meas = eps + eps_prestrain
  - → `SensorForward.signals(ε_meas, d, F, material)`
  - → `TdmSampler`: 1 kHz 샘플 10개를 MoE에 넣고, 마지막 출력을 쓴다
  - `nonideal=False`면 Obs에 진짜 ε, d, F를 넣고 MoE·잡음을 건너뛴다.
- 인체·유전체의 `K_MAT`: forward.py에는 conductor와 dielectric만 있다. 인체는 conductor 값(1.0)으로 둔다. shortcut 주석으로 남기고, B단계 R1에서 교체한다.
- 접촉 힘 F: 센서 구간 정점과 물체 사이 MuJoCo 접촉력 법선 성분의 합이다.
- 거리 d: 센서 중심에서 물체 표면까지다. 24 mm 이상이면 근접 신호 없음.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_deterministic_same_seed():
    a, b = Plant(Scenario(), seed=3), Plant(Scenario(), seed=3)
    for _ in range(30): oa, ob = a.step(np.array([10., 10.])), b.step(np.array([10., 10.]))
    assert np.allclose(oa.eps_hat, ob.eps_hat) and np.allclose(oa.p_mon, ob.p_mon)
def test_ideal_returns_truth():
    pl = Plant(Scenario(), nonideal=False)
    for _ in range(50): o = pl.step(np.array([15., 15.]))
    assert np.allclose(o.eps_hat, pl.truth().eps)
def test_contact_force_when_closing_on_object():
    pl = Plant(Scenario(obj_start_mm=(0, 0, 60)), nonideal=False)
    for _ in range(300): o = pl.step(np.array([30., 30.]))
    assert pl.truth().F_N.max() > 0.05
def test_divergence_raises():
    pl = Plant(Scenario(young_scale=1e-4))
    with pytest.raises(PlantDiverged):
        for _ in range(200): pl.step(np.array([30., 30.]))
```

- [ ] **Step 2: 실행해서 실패 확인**
  - Expected: FAIL (import)

- [ ] **Step 3: 구현**
  - 두 손가락은 x축 ±r_in(25 mm)에 바닥층이 서로 마주 보게 놓는다.
  - 물체는 mocap 바디로 만들고, `obj_path`가 있으면 매 스텝 위치를 바꾼다.
  - 매 MuJoCo 스텝마다 Itv → Line(V, dV/dp는 `chamber_volume` 수치미분) → `apply_pressure(p_c)` → `mj_step` 순서로 진행한다.
  - 발산 판정은 Review Focus 2를 따른다.

- [ ] **Step 4: 테스트 통과 확인**
  - Expected: 4 passed

### Task 4: 시스템 식별 (S1–S3)

**Files:** Create `code/sysid.py`, Test `code/tests/test_sysid.py`

**Interfaces:**
- Produces:
  - `prbs(n: int, bits: int, amp: float, seed: int) -> np.ndarray`
  - `chirp(t: np.ndarray, f0=0.05, f1=5.0, amp=3.0) -> np.ndarray`
  - `arx_ls(y, u, na: int, nb: int, nk: int = 1) -> (a: np.ndarray, b: np.ndarray)`: 강의 식 θ̂ = (ΦᵀΦ)⁻¹ΦᵀY, `np.linalg.lstsq`로 계산
  - `simulate_arx(a, b, nk, u, y0) -> np.ndarray`
  - `fit_pct(y, yhat) -> float`
  - `aic(y, yhat, n_par) -> float`
  - `select_order(y_id, u_id, y_val, u_val, max_order=4) -> dict`
  - `d2c_zoh(numz, denz, Ts) -> (nums, dens)`: 상태공간 → `scipy.linalg.logm`
  - `run_experiments(plant_factory) -> dict`: S1, S2, S3를 돌리고 CSV를 `out/`에 저장한다. 동작점은 p₀ = 15 kPa, 가진은 ±3 kPa다.
  - `main()`: `params.json["sysid"] = {"G_eps": {"num_z", "den_z", "num_s", "den_s"}, "G_p": {...}, "order": [na, nb, nk], "fit_val_pct", "p0", "eps0"}`
  - 그림: `out/sysid_*.png`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_arx_recovers_known_model():
    a_true, b_true = np.array([-1.5, 0.7]), np.array([0.1, 0.05])
    u = prbs(4000, 7, 1.0, 0); y = simulate_arx(a_true, b_true, 1, u, np.zeros(2))
    a, b = arx_ls(y + 1e-4*np.random.default_rng(0).normal(size=y.size), u, 2, 2, 1)
    assert np.allclose(a, a_true, atol=1e-2) and np.allclose(b, b_true, atol=1e-2)
def test_arx_rejects_unexciting_input():
    with pytest.raises(ValueError): arx_ls(np.ones(500), np.ones(500), 2, 2, 1)
def test_d2c_roundtrip():
    nums, dens = [2.0], [1.0, 3.0, 2.0]; numz, denz = c2d_tf(nums, dens, 0.01)
    n2, d2 = d2c_zoh(numz, denz, 0.01); assert np.allclose(np.poly1d(d2).r, np.poly1d(dens).r, atol=1e-6)
```
(`c2d_tf`는 `scipy.signal.cont2discrete` 래퍼다. 같은 파일에 둔다.)

- [ ] **Step 2: 실행해서 실패 확인**
  - Expected: FAIL (import)

- [ ] **Step 3: 구현**
  - `arx_ls`: cond(Φ) > 1e10이면 `ValueError`를 던진다.

- [ ] **Step 4: 테스트 통과 확인**
  - Expected: 3 passed

- [ ] **Step 5: 실제 식별 실행**
  - Run: `C:/ml_env/Scripts/python.exe Hardware/로봇제어프로젝트/code/sysid.py`
  - Expected: `params.json["sysid"]`가 채워지고, 터미널에 `fit_val_pct`가 출력된다.
  - 80 % 미만이면 스펙 9절대로 차수·동작점 변경을 기록하고 진행한다.

### Task 5: 상태공간 해석

**Files:** Create `code/analysis.py`, Test `code/tests/test_analysis.py`

**Interfaces:**
- Consumes: `params["sysid"]`
- Produces:
  - `physical_ss(tau_v, K_f, wn, zeta) -> (A, B, C)`: 스펙 11.2의 3×3 형태, C = [[1,0,0],[0,1,0]]
  - `fit_physical(sysid: dict) -> dict`: G_p에서 τ_v, G_ε/G_p에서 K_f·ω_n·ζ를 구한다. 식별 차수가 다르면 가장 가까운 2차로 근사하고 ledger에 Ruling을 남긴다.
  - `ctrb_canonical(num, den) -> (A, B, C)`
  - `similarity(A1, A2) -> Q`
  - `c2d(A, B, Ts) -> (Ad, Bd)`: `scipy.linalg.expm` 확대행렬 방식
  - `dlyap(A, Q) -> P`: `scipy.linalg.solve_discrete_lyapunov`
  - `is_pd(P) -> bool`
  - `ctrb(A, B)`, `obsv(A, C)`, `rank`
  - `gramian_obsv(A, C, N=500) -> W`
  - `kalman_decomp(A, B, C) -> dict`
  - `main()`: `params["model"] = {"A","B","C","Ad","Bd","Ts","eig_c","eig_d","lyap_P","rank_ctrb","rank_obsv": {"p": r, "eps": r, "both": r}, "gram_min_sv": {...}}`
  - 그림: `out/analysis_*.png`(극 지도, 가관측 그래미안 특이값 막대)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_pressure_only_is_unobservable():
    A, B, C = physical_ss(0.05, 2.0, 15.0, 0.4)
    assert rank(obsv(A, C[:1])) == 1 and rank(obsv(A, C[1:2])) == 3 and rank(ctrb(A, B)) == 3
def test_dlyap_pd_iff_stable():
    Ad, _ = c2d(*physical_ss(0.05, 2.0, 15.0, 0.4)[:2], 0.01)
    assert is_pd(dlyap(Ad.T, np.eye(3))) and np.all(abs(np.linalg.eigvals(Ad)) < 1)
def test_similarity_preserves_eigs():
    A1, *_ = ctrb_canonical([2.0], [1, 3, 2]); A2 = np.array([[-1, 0], [0, -2.]])
    Q = similarity(A1, A2); assert np.allclose(np.linalg.inv(Q) @ A1 @ Q, A2, atol=1e-8)
```

- [ ] **Step 2: 실행해서 실패 확인 → Step 3: 구현 → Step 4: 통과(3 passed) → Step 5: `analysis.py` 실행**
  - Expected: `params["model"]`이 채워진다.

### Task 6: 결정론적 제어 (극배치·관측기·LQR)

**Files:** Create `code/design_det.py`, Test `code/tests/test_design_det.py`

**Interfaces:**
- Consumes: `params["model"]` (Ad, Bd, C, Ts)
- Produces:
  - `augment_integral(Ad, Bd, C_eps) -> (Aa, Ba, Ga)`: 스펙 11.3 확대식
  - `acker(A, B, poles_z) -> K`: 강의 Ackermann 공식, 단일 입력. 검증은 `scipy.signal.place_poles`와 대조한다.
  - `poles_from_spec(zeta, wn, Ts, extra: list[float]) -> np.ndarray`
  - `observer_gain(A, C, poles_z) -> L`: 쌍대
  - `dlqr(A, B, Q, R) -> (K, P)`: `scipy.linalg.solve_discrete_are`
  - `bryson(x_max: list, u_max: float) -> (Q, R)`
  - `margins(A, B, K, Ts) -> (gm_db, pm_deg)`: L(z) = K(zI−A)⁻¹B를 단위원에서 계산
  - `class StateFeedback(K, KI, L|None, mode="apriori"|"aposteriori")`
    - `.reset()`
    - `.u(y: np.ndarray, r: float) -> float`
  - `main()`: `params["det"] = {"pp": {"poles","K","KI"}, "obs": {"poles","L"}, "lqr": {"Q","R","K","KI","P","gm_db","pm_deg"}}`
- 설계값:
  - 극배치: ζ = 0.8, ω_n = 개루프 손가락 ω_n × 1.5, 나머지 극은 그 3배 빠르게
  - 관측기 극: 제어기 극보다 4배 빠르게 (z = e^{4sTs})
  - Bryson: ε 오차 0.5 %, ε̇ v_max(기준), p 30 kPa, x_I 0.5 %·1 s, u 30 kPa

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_acker_places_poles():
    Ad, Bd = c2d(*physical_ss(0.05, 2.0, 15.0, 0.4)[:2], 0.01); z = np.array([0.9, 0.85, 0.8])
    K = acker(Ad, Bd, z); assert np.allclose(np.sort(np.linalg.eigvals(Ad - Bd @ K)), np.sort(z), atol=1e-6)
def test_dlqr_satisfies_dare():
    K, P = dlqr(Ad, Bd, np.eye(3), np.eye(1))
    rhs = Ad.T@P@Ad - Ad.T@P@Bd@np.linalg.inv(np.eye(1)+Bd.T@P@Bd)@Bd.T@P@Ad + np.eye(3)
    assert np.allclose(P, rhs, atol=1e-8)
def test_separation_principle():   # 폐루프 고유값 = eig(A−BK) ∪ eig(A−LC)
    ...
def test_place_rejects_unstable_target():
    with pytest.raises(ValueError): acker(Ad, Bd, [1.05, 0.9, 0.8])
```
(`test_separation_principle`: 6×6 폐루프 [[A, −BK],[LC, A−LC−BK]]의 고유값이 두 집합의 합과 같은지 `np.allclose(sorted)`로 확인한다.)

- [ ] **Step 2–4: 실패 확인 → 구현 → 4 passed**

- [ ] **Step 5: `design_det.py` 실행**
  - Expected: `params["det"]`이 채워지고, 터미널에 gm_db와 pm_deg가 출력된다.

### Task 7: 칼만·LQG (+ d, ḋ 칼만)

**Files:** Create `code/design_stoch.py`, Test `code/tests/test_design_stoch.py`

**Interfaces:**
- Consumes: `params["model"]`, `params["det"]["lqr"]`
- Produces:
  - `class Kalman(Ad, Bd, C, Bw, W, V, x0, M0)`
    - `.update(y) -> x_post`: 강의 (KF) 측정 갱신, Z 저장
    - `.predict(u)`: 시간 갱신, M 저장
    - `.x_post`, `.M`, `.Z`
  - `steady_kalman(Ad, C, Bw, W, V) -> (Kf, M)`: 쌍대 DARE
  - `class Lqg(K, KI, kalman)`: `.reset()`, `.u(y, r) -> float`
  - `class RangeKF(Ts, q_acc, r_d)`: 상태 [d, ḋ] 등속 모델. `.step(d_meas) -> (d, d_dot)`
  - `noise_from_S4(csv) -> V`: S4는 `run_compare`가 아니라 이 모듈의 `measure_noise(plant_factory)`가 수행한다
  - `main()`: `params["stoch"] = {"V", "W", "Bw", "Kf", "M", "W_sweep": [...]}`
- W 시작값: 식별 잔차 분산을 B_w = I 기준으로 상태에 배분한다. 그다음 W/V 비율 {0.1, 1, 10}× 스윕 결과를 저장한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_steady_kalman_satisfies_dual_dare(): ...      # M = A(M − MCᵀ(CMCᵀ+V)⁻¹CM)Aᵀ + BwWBwᵀ, atol 1e-8
def test_kalman_reduces_estimation_error():           # 잡음 있는 시뮬에서 RMSE(x̂_KF) < RMSE(관측기 극 4배) for ε̇
    ...
def test_range_kf_tracks_constant_velocity():
    kf = RangeKF(0.01, 50.0, 0.5); rng = np.random.default_rng(0)
    for k in range(300): d, v = kf.step(80 - 20*k*0.01 + 0.5*rng.normal())
    assert v == pytest.approx(-20, abs=2)
```

- [ ] **Step 2–4: 실패 확인 → 구현 → 3 passed → Step 5: 실행**
  - Expected: `params["stoch"]`이 채워진다.

### Task 8: DOB

**Files:** Create `code/design_dob.py`, Test `code/tests/test_design_dob.py`

**Interfaces:**
- Consumes: `params["sysid"]["G_eps"]`(공칭 P_n, 연속), `params["model"]["Ts"]`
- Produces:
  - `q_filter(tau_q, r) -> (num_s, den_s)`
  - `class Dob(Pn_num_s, Pn_den_s, tau_q, Ts, delay_steps=1)`
    - `.reset()`
    - `.correct(u_c: float, y_eps: float) -> float`: 반환값은 실제로 낼 u
    - 내부에서 Q와 Q·P_n⁻¹을 ZOH 이산화하고, u 경로에 delay_steps 지연을 둔다.
  - `robust_bound(Pn, P_true_list, tau_q) -> (ok: bool, worst: float)`: max_ω |QΔ|
  - `main()`: `params["dob"] = {"tau_q_list": [3개 이상], "tau_q": 선택값, "r", "robust": {...}}`
- r은 P_n의 상대 차수 이상으로 잡는다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_dob_transparent_on_nominal():
    # 공칭 플랜트(이산 P_n) + 외란 0에서 DOB 유무의 출력 차이 < 1e-6
    ...
def test_dob_rejects_constant_input_disturbance():
    # 공칭 플랜트 + 입력 외란 계단 2 kPa, LQR 폐루프. DOB 있으면 정상상태 오차 < 없을 때의 10 %
    ...
def test_q_filter_proper():
    num, den = q_filter(0.05, 2); assert len(den) - len(num) == 2
```

- [ ] **Step 2–4: 실패 확인 → 구현 → 3 passed → Step 5: 실행**
  - Expected: `params["dob"]`이 채워진다.

### Task 9: 상위 루프 상태 머신

**Files:** Create `code/supervisor.py`, Test `code/tests/test_supervisor.py`

**Interfaces:**
- Consumes: `RangeKF`(Task 7), 재질표(Global Constraints)
- Produces:
  - `MATERIAL = {"conductor": dict(Ft=0.5, Fmax=0.8, Ba=1.0, v=1.0), "dielectric": dict(Ft=0.35, Fmax=0.6, Ba=1.5, v=0.7), "human": dict(Ft=0.15, Fmax=0.3, Ba=3.0, v=0.4)}`: F 항목은 F_block 배수, Ba·v는 기준 배수
  - `class Supervisor(F_block, Ba0, v0, eps_open, eps_pre, d_far=24.0, d_near=5.0, eps_max, Ts=0.01, t_min=0.2, dFdt_max_human)`
    - `.reset()`
    - `.step(obs_finger: dict(d_hat, F_hat, contact), material: str, cmd: "grasp"|"release") -> float` (ε_ref)
    - `.state` ∈ {OPEN, APPROACH, CONTACT, GRASP, SAFETY, RELEASE}
- 규칙은 스펙 4절, 4.1절, 11.8절을 그대로 따른다.
  - 근접 스케줄(sat 선형)
  - ε̇_ref = (g(d̂) − ε_ref)/max(t_c, t_min), 그 위에 |ε̇_ref| ≤ v_max(재질) 제한
  - 어드미턴스 ε_ref += (Ts/B_a)(F_t − F̂)·F_block 정규화, 데드존 δF = 0.02 F_block
  - 게이트 접촉 연속 3 샘플일 때 CONTACT→GRASP로 전이한다
  - F̂ > F_max면 SAFETY: ε_ref를 v_max로 감소
  - 인체면 dF/dt 상한을 둔다
- Ba0 결정: 내부 루프 폐루프 지배 시정수 τ_in(`params["det"]["lqr"]` 극에서 계산)과 S8의 k_env로 B_a0 = 4·τ_in·k_env를 정한다(스펙 11.8의 3–5배 규칙 중간값).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_approach_rate_limited():           # d̂ 계단 24→5 mm에서 |Δε_ref| ≤ v·Ts 매 스텝
def test_admittance_converges_first_order_env():  # F = k_env·(ε_ref − ε_c) 가상 환경에서 F → Ft·F_block (±δF), 재질 3종
def test_human_never_exceeds_fmax():         # 같은 가상 환경 + k_env 2배 계단에서 max F ≤ Fmax·F_block
def test_no_grasp_on_force_noise():          # contact가 1샘플씩 0/1 깜박이면 state ∉ {GRASP}
```

- [ ] **Step 2–4: 실패 확인 → 구현 → 4 passed**

### Task 10: 비교 실험·지표·그림·영상 (S4–S8)

**Files:** Create `code/run_compare.py`, `code/metrics.py`, Test `code/tests/test_metrics.py`

**Interfaces:**
- Consumes: Task 3, 6, 7, 8, 9의 모든 Produces, `params.json`
- Produces:
  - `metrics.step_metrics(t, y, r) -> dict(rise_s, overshoot_pct, settle_s, ess)`
  - `metrics.effort(u) -> dict(sum_u2, sum_du)`
  - `metrics.rmse(a, b)`
  - `run_compare.main(which: list[str] = ["S4","S5","S6","S7","S8"])`
- 실험 내용:
  - S8 (먼저 실행): F_block, k_env를 재질별로 구해 `params["contact"]`에 쓴다. 재질은 플랜트 `Scenario.material`로 바꾼다.
  - S5: 제어기 7종(PP, PP+Obs, LQR+Obs, LQG, LQG+DOB(τ_q 3개))을 같은 기준(계단 + 사다리꼴 + 사인)으로 비교하고 `out/S5_metrics.csv`에 저장한다.
  - S6: 섭동 4종 × {LQG, LQG+DOB}를 돌려 `out/S6_metrics.csv`에 저장한다.
  - S7: 재질 3종 파지와 인체(움직이는 손, `obj_path`)를 돌려 `out/S7_*.mp4`와 스냅샷 png를 만든다.
  - 그림: 각 실험에서 기준/출력, 추정 상태(x̂ vs truth), 입력 u를 시간축으로 그린다(과제 7절).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_step_metrics_on_known_response():   # 1차 τ=0.1 응답 → rise ≈ 0.22 s, overshoot 0, settle ≈ 0.39 s (±2 샘플)
```

- [ ] **Step 2–4: 실패 확인 → 구현 → 1 passed**

- [ ] **Step 5: 전체 실행**
  - Run: `C:/ml_env/Scripts/python.exe Hardware/로봇제어프로젝트/code/run_compare.py`
  - Expected: `out/`에 S5·S6 CSV, 그림, S7 mp4가 생긴다. S7 인체 F 최댓값이 F_max 이하여야 한다(스펙 9절). 넘으면 원인을 기록하고 Supervisor 파라미터를 고친다.

### Task 11: PPT 생성

**Files:** Create `code/build_pptx.py`, `code/slides_text.py`, Test `code/tests/test_build_pptx.py`

**Interfaces:**
- Consumes: `params.json`, `out/*.png|csv`, 스펙 11절 원고(`slides_text.py`에 슬라이드별 문자열로 옮긴다)
- Produces:
  - `build(out_path=PROJECT/"MEC799_Project_PneuNet.pptx") -> Path`
  - 22장, 구성은 스펙 8절 목록 순서다.
- 블록도(4번 제어 구조, 4번 플랜트 모델)는 `add_shape` 사각형·화살표 커넥터·텍스트로 그린다. 이미지가 아니다.
- 강의 대응표·게인 표·실험 표는 PPT 표로 넣는다.
- `params.json`에 없는 값과 가정값 셀은 배경을 `FFF2CC`로 칠한다.
- 수치가 있는 슬라이드 제목 옆에 "(시뮬레이션)"을 붙인다.
- 16:9, 한글 폰트는 맑은 고딕이다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_deck_has_22_slides_and_editable_diagram(tmp_path):
    p = build(tmp_path/"d.pptx"); prs = Presentation(p)
    assert len(prs.slides) == 22
    s5 = prs.slides[4]; assert sum(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE for sh in s5.shapes) >= 8
def test_gain_table_from_params(tmp_path):   # 20번 슬라이드 표에 params["det"]["lqr"]["K"] 첫 값이 문자열로 들어 있다
def test_missing_value_cell_is_yellow(tmp_path):  # params에서 키 하나를 지우고 빌드 → 해당 셀 fill = FFF2CC
```

- [ ] **Step 2–4: 실패 확인 → 구현 → 3 passed**

- [ ] **Step 5: 생성 후 확인**
  - Run: `C:/ml_env/Scripts/python.exe Hardware/로봇제어프로젝트/code/build_pptx.py`
  - PowerPoint COM으로 PNG 내보내기를 해서 블록도 겹침·글자 넘침을 눈으로 확인한다(`out/pptx_check/`).
  - Expected: 22장 파일이 생기고, 겹침이 없다.

### Task 12: 마무리

- [ ] 전체 테스트: `C:/ml_env/Scripts/python.exe -m pytest Hardware/로봇제어프로젝트/code/tests -q` → 모두 통과
- [ ] `Hardware/로봇제어프로젝트/README.md` 작성
  - 실행 순서: s0_spike → sysid → analysis → design_det → design_stoch → design_dob → run_compare → build_pptx
  - B단계에서 실측 데이터로 바꾸는 위치: `params.json`, `sysid.run_experiments`의 플랜트 팩토리를 실물 래퍼로 교체
- [ ] `Docs/plan/연구계획.md` 6절 결정 기록에 S0 판정(flex/prbm, ε 프리스트레인)을 날짜와 함께 남긴다.
- [ ] 사용자에게 커밋 여부를 묻는다(CLAUDE.md 규칙).
