# 60A 벨로즈 손가락 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 논문(Meitani & Nisar 2025) 60A TPU 벨로즈 손가락의 출력용 STL과, 그 형상·거동을 반영한 MuJoCo 손가락을 기존 시뮬에 추가한다.

**Architecture:**
- CAD는 build123d 파라미터 스크립트로 만든다.
- 시뮬은 8관절 PRBM(precurve springref) + 공압 데드존 모델로 구성하고, Fig.9·Fig.7에 보정한다.
- 기존 판형 손가락은 옵션으로 유지한다.

**Tech Stack:** Python 3.13 (C:/ml_env), build123d 0.13, MuJoCo 3.17, pytest

**Spec:** Docs/superpowers/specs/2026-10-26-bellows-60a-finger-design.md

## Global Constraints
- 테스트: `C:/ml_env/Scripts/python.exe -m pytest sim_gripper/tests -q`. 기존 테스트 전부 유지.
- 그래프 색: L `#FF8C00`, R `#2CA02C`, TENG `#1F77B4`.
- 커밋 메시지 한글 + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- 논문 수치는 스펙 2절 값 그대로. 추정치는 스펙 3절 값.

## Review Focus
1. 판형 손가락 경로 회귀 (SENSOR_SEGS·BASE_R/Z 전역 → 파라미터화하면서 기존 값이 바뀌면 안 됨) → 기존 test_gripper/test_integration 유지.
2. P₀ 데드존이 기존 공압 기본값을 바꾸면 안 됨 → P₀ 기본 0, test_actuators 유지.
3. precurve 손가락이 테이블·물체를 뚫거나 초기 상태에서 이미 접촉 → 초기 pad 거리 > 0 테스트.
4. CAD 공동이 바깥으로 뚫리거나 솔리드가 여러 조각 → 단일 솔리드·부피 감소 테스트.
5. 보정값이 측정 정의와 다름 (Fig. 9 = precurve 제외 각) → 보정 테스트가 같은 정의 사용.

---

### Task B1: CAD 손가락·베이스
**Files:**
- Create: `sim_gripper/cad/__init__.py`, `sim_gripper/cad/finger.py`, `sim_gripper/cad/base.py`, `sim_gripper/cad/export.py`
- Test: `sim_gripper/tests/test_cad.py`

**Interfaces:**
- Produces:
  - `@dataclass FingerCAD(arc_len=105.0, depth=32.0, n_bellows=8, precurve_deg=41.0, backbone_t=3.0, bellow_h=14.0, bellow_t=6.43, wall=2.5, root_len=8.0, inlet_d=4.0, inlet_z=3.0, groove_w=22.0, groove_d=0.5, groove_n=3)`
    - `rho()` = arc_len / precurve(rad)
  - `make_finger(p) -> build123d.Part`
  - `make_base(R=66.0, ...) -> Part`
  - `export_all(out_dir) -> dict[str, Path]`
- [ ] 테스트:
  - `test_finger_is_single_valid_solid`
  - `test_finger_depth_and_chord`
  - `test_finger_is_hollow` (부피 < 외곽 솔리드 부피 × 0.8)
  - `test_export_writes_stl`
- [ ] RED → 구현 → GREEN → Commit `"CAD: 60A 벨로즈 손가락·3지 베이스 파라미터 모델"`

### Task B2: 공압 데드존 + 60A 프리셋
**Files:** Modify `sim_gripper/actuators/pneumatic.py`, `__init__.py`; Test `test_actuators.py`
**Interfaces:**
- `PneumaticActuator(..., P0=0.0)`
- `make_actuator(kind)` with kind ∈ {"tendon", "pneumatic", "pneumatic60a"}
- [ ] 테스트:
  - `test_pneumatic_deadzone` (P < P₀ → τ = 0)
  - `test_make_pneumatic60a_preset` (P_max 200e3, P0 62e3)
- [ ] RED → 구현 → GREEN → Commit `"시뮬: 공압 데드존과 60A 프리셋"`

### Task B3: 벨로즈 MJCF + 보정
**Files:** Modify `sim_gripper/model/gripper.py`; Create `sim_gripper/model/calibrate_bellows.py`; Test `test_bellows.py`
**Interfaces:**
- `@dataclass BellowsParams`
  - 필드: `arc_len_mm=105, depth_mm=32, n_joints=8, precurve_deg=41, backbone_mm=3, bellow_h_mm=14, k_joint` (보정값), `zeta=0.3, base_R=0.066, sensor_segs=(5,6,7), h_sensor_mm=0.5`
  - 메서드: `seg_m()`, `base_z()`
- `FingerParams`도 `base_R`, `base_z()`, `sensor_segs`, `h_sensor_mm=3.0`를 제공 (값은 기존과 동일).
- `GripperSim(fp, obj)`는 두 종류 모두 지원. `kappa_bar_per_mm` = 센서 세그먼트 q 합 / (len·seg_mm).
- `calibrate()`: 자유 굽힘·차단력 측정 → 표 출력.
- [ ] 테스트:
  - `test_bellows_model_loads` (hinge 24)
  - `test_bellows_open_no_contact`
  - `test_free_bending_matches_fig9` (100/150/200 kPa, ±6°)
  - `test_blocked_force_200kpa` (6.28 ± 1.0 N)
- [ ] RED → 구현·보정 → GREEN (+ 전체 회귀) → Commit `"시뮬: 60A 벨로즈 손가락 PRBM과 논문 기반 보정"`

### Task B4: 루프·시나리오 통합
**Files:** Modify `sim/loop.py`, `sim/scenarios.py`; Test `test_integration.py`
**Interfaces:**
- `FINGERS = {"flat": FingerParams, "bellows60a": BellowsParams}`
- `run(..., finger="flat")`
  - finger가 bellows면 `actuator` 기본값 "pneumatic60a"
  - `SensorForward(h_mm=fp.h_sensor_mm)`
- `SCENARIOS["E5_spool"]` 추가
- [ ] 테스트:
  - `test_bellows_e1_lifts`
  - `test_bellows_egg_not_broken`
- [ ] Commit `"시뮬: 벨로즈 손가락 폐루프 통합과 스풀 시나리오"`

### Task B5: 실험·보고서·패널
**Files:** Modify `experiments/run_all.py`, `report/build_report.py`, `panel.py`, `viewer.py`; Test `test_report.py`
**Interfaces:**
- `run_all`에 `finger` 그리드 추가 (`<scen>_<act>` 키 유지, 벨로즈는 `bellows60a_<scen>`)
- `plot_finger_compare` 추가
- 보고서 `CHAPTERS`에 "부록 C. 60A 벨로즈 그리퍼" 추가 (15개 장)
- 패널·뷰어에 `--finger` 옵션
- [ ] 테스트:
  - `test_report_has_all_chapters` (15개)
  - `test_report_has_bellows_calibration_table`
- [ ] 실행 → Commit `"시뮬: 벨로즈 실험·보고서 부록·패널 손가락 선택"`
