# MEC799 로봇제어 기말 프로젝트 — PneuNet 2지 센서 되먹임 제어

- 스펙: `Docs/superpowers/specs/2026-11-19-robot-control-project-design.md`
- 계획: `Docs/superpowers/plans/2026-11-19-robot-control-project.md`
- 제출물: `MEC799_Project_PneuNet.pptx` (블록도·표는 PPT 도형이라 직접 고칠 수 있다. 노란 칸 = 가정값)
- 모든 수치는 **시뮬레이션**(A단계)이다. 실물 값이 아니다.

## 실행 순서 (저장소 루트에서, `C:/ml_env/Scripts/python.exe`)

| 순서 | 명령 | 하는 일 | 결과 |
|---|---|---|---|
| 0 | `code/s0_spike.py` | flex 손가락 보정·판정 (S0) | `params.json["plant"]["flex_S0"]`, `out/S0_calib.png` |
| 1 | `code/sysid.py` | S1 정적 맵·센서 장착 보정, S2 계단, S3 PRBS·처프 식별 | `params["sysid"]`, `params["sensor_cal"]`, `out/sysid_*` |
| 2 | `code/analysis.py` | 물리 모델 피팅, 이산화, 고유값, Lyapunov, 가제어·가관측 | `params["model"]`, `out/analysis_poles_obsv.png` |
| 3 | `code/run_compare.py S4` | 정지 잡음 (칼만 V) | `params["noise"]` |
| 4 | `code/design_det.py` | 극배치, 관측기, LQR | `params["det"]` |
| 5 | `code/design_stoch.py` | 칼만 (W, V) | `params["stoch"]` |
| 6 | `code/design_dob.py` | DOB τ_q 후보·강건 조건 | `params["dob"]` |
| 7 | `code/run_compare.py S8` | 접촉 강성 k_eq·k_env (재질 3 + 위치·크기 6), 힘 보정, V_F | `params["contact"]`, `out/S8_keq.png` |
| 8 | `code/design_contact.py` | 접촉 모드 가관측성, 접촉용 LQR 격자 (스펙 12절) | `params["contact_design"]`, `out/contact_obsv.png` |
| 9 | `code/run_compare.py S5 S6 S9 S7 R` | 제어기 비교, DOB 강건성, 힘 유지 비교(S9), 파지 영상(하이브리드 C), 실시간 보기 `code/live_view.py`, 모델 렌더 | `out/S5_*`, `out/S6_*`, `out/S9_*`, `out/S7_*.mp4`, `params["results_*"]` |
| 10 | `code/run_hri.py S10 S11` | 상·하위 계층: 하위 반사 안전 vs 상위 지연·두절(S10), 시나리오 2 인체 상호작용(S11) | `out/S10*`, `out/S11*`, `params["results_s10", "results_s11"]` |
| 11 | `code/build_pptx.py` | PPT 생성 (30장) | `MEC799_Project_PneuNet.pptx` |

테스트: `C:/ml_env/Scripts/python.exe -m pytest Hardware/로봇제어프로젝트/code/tests -q`

## 플랜트 (A단계)

- 손가락: S0에서 MuJoCo flex(사면체 유한요소, 방 내벽 압력)가 300° 대변형에서 좌굴(비단조)해, 스펙 2.2 대체안인 **PRBM**(관절 9개)을 쓴다.
  - 굽힘 보정: 30 kPa → 300°
  - 방 부풂: self-collision flex 결과의 V(p)로 공압 용량과 화면의 방 크기에 반영
- ITV: 지연, 데드밴드 0.3 kPa(처음 열릴 때 튐), 1 kPa 계단, 포화 30 kPa
- 튜브·방: C(p)ṗ_c = (p − p_c)/R_t
- 센서: 0909 순방향 모델 → TDM 잡음 → v4 MoE → 장착 보정(ε, F)
- 물체: 도체 = 강체, 유전체·인체 = 스프링 패드 (k_obj 2.0 / 0.7 N/mm, 가정값)

## 제어 (스펙 12절)

- 상태 x = [p, ε_f]는 두 모드 공통이고, 출력만 모드에 따라 바뀐다. 입력은 손가락마다 ITV 하나다.
- 자유 모드는 LQG로 ε를 추종한다. 접촉 모드는 F를 추종한다: 적분 대상은 F_ref − F̂이고, k_eq 격자의 LQR을 보간하며, RLS로 k̂_eq를 추정하고, DOB를 더한다.
- 두 모드 사이 전환은 무충격이다. 코드: `design_contact.py`, `run_compare.Hybrid`.

## 상·하위 계층 (스펙 13절)

- 상위(PC, 20 Hz + 통신 지연, 가정값): 시나리오·재질·상태 머신·기준. 하위(STM32 + TDM): 내부 루프 100 Hz, 반사 안전 1 kHz (`layers.Reflex`, `Plant.reflex`).
- 반사는 TDM 샘플마다 F̂ > F_max 3 샘플 연속이면 ITV 배기를 래치한다. 상위에는 반사 플래그로 알린다 (감독기 SAFETY).
- 시나리오 1 = 도체 파지(S7), 시나리오 2 = 인체 상호작용(S11: 힘 유지 vs 어드미턴스 따라가기).

## B단계 (실물)에서 바꿀 곳

- `sysid.run_experiments(plant_factory)`의 `plant_factory`를 실물 래퍼로 바꾼다. 래퍼는 `step(u) → Obs`이고 ITV 보드와 TDM 보드를 쓴다.
- 이후 2–8단계를 그대로 다시 돌리면 `params.json`과 PPT 게인 표가 실측값으로 바뀐다.
- 실측 계획 R1–R8은 PPT 25번 슬라이드에 있다.
