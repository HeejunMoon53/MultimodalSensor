# 논문 Figure 세트 (제어 구조·모달리티·Edge-AI 장점) — 스펙 + 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** 제어 구조가 센서 다중 모달리티를 어떻게 쓰는지, Embedded AI가 왜 필요한지를 보여주는 논문용 Figure 세트와 구성 가이드(docx)를 만든다.

**사용자 결정 (2026-10-26):**
- 메인 추정기: 그리퍼 보정 MoE (v4와 같은 1,413 파라미터 구조, 시뮬 그리퍼 데이터로 mixed fine-tune). v4 원본은 ablation.
- Edge-AI 근거 실험: (a) 지연 비교, (b) 해석적 역산 vs MoE, (c) 연산·메모리 예산, (d) 모달리티 ablation — 모두.
- 형식: 고해상도 PNG(300 dpi)+SVG + 구성 가이드 docx.

**Architecture:**
- 그림 생성은 `sim_gripper/paper/`에서 한다.
- 메인 손가락은 60A 벨로즈(논문 기반 실설계)로 한다.
- 실측 근거: 보드 로그 `latency_us` 중앙값 261 µs(STM32G473 @170 MHz), X-CUBE-AI 리포트(전문가 MACC 1,154, 가중치 2.63 KiB, RAM 160 B).

**Spec:** 이 문서(1~3절) + 선행 스펙 2개.

## 1. Figure 목록 (최종 산출: `sim_gripper/out/paper_figs/`)
| # | 파일 | 메시지 |
|---|---|---|
| F1 | fig1_architecture | 센서 → TDM → Gate-MoE(+TENG 융합·재질) → 상태 머신 제어 → 액추에이터 전체 알고리즘 블록도 (1 kHz 온보드) |
| F2 | fig2_timing_budget | 1 ms TDM 주기 타이밍(측정 슬롯·추론 261 µs·제어·유휴) + 모델 예산표 |
| F3 | fig3_state_machine | 상태 머신과 각 전이·제어 법칙을 어떤 모달리티가 구동하는지 |
| F4 | fig4_grasp_timeline | 한 번의 파지에서 다섯 모달리티 + 제어 출력 타임라인 (벨로즈, 금속) |
| F5 | fig5_material_adaptive | 금속·손·계란: 재질 판별 → 목표 힘 자동 선택, 계란 무파손 |
| F6 | fig6_latency | 센서→제어 지연 0~100 ms: 최대 힘·과하중·계란 파손·안전 반응 |
| F7 | fig7_analytic_vs_moe | 경험식 역산(뉴턴)의 발산 영역 vs MoE 오차 지도 (ε–d 평면) |
| F8 | fig8_ablation | 근접·재질·TENG·안전 계층을 하나씩 뺐을 때 성능 |
| F9 | fig9_adaptation | 장착 시프트 적응 회복 곡선 (기존 domain_shift.json) |

## 2. 구현 결정
- **지연 모델:** 센서 처리 결과(MoeOut, 재질, 접촉)를 `latency_ms`만큼 FIFO로 늦춰 제어기에 전달한다.
  - 물리·액추에이터는 그대로 둔다.
  - PC 경유 시스템(USB 스트리밍 + PC 추론 + 명령 회신)을 대표한다.
- **Ablation:**
  - `proximity`: 비접촉 d̂를 30 mm로 고정 → 근접 스케줄 없이 고속 접근.
  - `material`: 재질을 항상 도체로 둔다 → 고정 목표 힘 4 N.
  - `teng`: contact_hint = 0.
  - `safety`: `CtrlParams.safety=False`.
- **해석적 역산:**
  - CLAUDE.md의 경험식을 사용한다: ΔR = α₁ε + α₂ε², ΔL = β₁ε + β₂/(d+d₀)^k + β₃·ε/(d+d₀)^k + c.
  - 순방향 표(도체)에 curve_fit한다.
  - (ΔL, ΔR) → (ε, d)는 2D 뉴턴법으로 푼다 (최대 30회). 다음 경우를 발산으로 판정한다: 비수렴, 범위 이탈(ε ∉ [−5, 40], d ∉ [−2, 40]), 야코비안 특이(|det| < 1e−9).
  - MoE와 같은 노이즈 입력을 쓴다.
- **보정 MoE:**
  - `experiments/calibrated.py: make_gripper_moe(n=20000, seed=0) -> dict`
  - 벨로즈 시나리오(E1, E2_hand, E3_small, E2_egg) 시뮬 데이터를 사용한다 (시프트 없음).
  - mixed fine-tune, 전문가만 적응한다.
  - `out/moe_gripper.pkl`에 캐시한다.
- 색: L `#FF8C00`, R `#2CA02C`, TENG `#1F77B4`, 참값 `#333333`, 추정 `#7B4FBF`.

## 3. 검증
- 보정 MoE: 구조·파라미터 수 1,413 유지. 벨로즈 E1 폐루프 force_rmse가 v4보다 작다.
- 지연: latency 0 vs 100 ms에서 계란 시나리오 최대 힘이 증가한다.
- 해석적 역산: 적합 R² > 0.9. 근접 극한(d < 2 mm)에서 발산률이 중간 영역보다 크다.
- 그림 9개 PNG + SVG 생성, 가이드 docx에 9개 Figure 절이 있다.

---

### Task P1: 그리퍼 보정 MoE
- Create: `sim_gripper/experiments/calibrated.py`
- Test: `sim_gripper/tests/test_calibrated.py`
  - `test_calibrated_keeps_architecture`
  - `test_calibrated_improves_bellows_force`
- Commit: `"시뮬: 그리퍼 보정 MoE(같은 구조 mixed fine-tune)"`

### Task P2: 지연·ablation 옵션
- Modify: `sim/loop.py` (`latency_ms=0`, `ablate=()`), `control/controller.py` (`CtrlParams.safety=True`)
- Test: `test_loop_options.py`
  - `test_latency_delays_controller_input`
  - `test_ablate_material_uses_conductor`
  - `test_safety_flag_disables_trip`
- Commit: `"시뮬: 센서-제어 지연과 모달리티 ablation 옵션"`

### Task P3: 해석적 역산 기준선
- Create: `sim_gripper/perception/analytic.py`
  - `fit_empirical(fwd) -> params`
  - `invert(params, dL, dR, x0) -> (eps, d, ok)`
- Test: `test_analytic.py`
  - `test_fit_quality`
  - `test_inverts_midrange`
  - `test_divergence_higher_near_contact`
- Commit: `"시뮬: 경험식 해석적 역산 기준선"`

### Task P4: Figure 생성기
- Create: `sim_gripper/paper/__init__.py`, `diagrams.py` (F1–F3), `figures.py` (F4–F9 + `make_all(out_dir)`)
- Test: `test_paper_figs.py` (다이어그램 3개 생성, `make_all` 파일 목록)
- Commit: `"논문 Figure: 알고리즘·타이밍·상태머신 다이어그램과 실험 그림"`

### Task P5: 구성 가이드 docx
- Create: `sim_gripper/paper/guide.py` → `out/paper_figs/논문_Figure_구성가이드.docx`
  - 권장 논문 구조
  - 각 Figure: 메시지·패널 구성·데이터 출처·캡션(국/영)·본문 단락·실물 실험 대응
  - 표: 모델 예산, 핵심 수치
- Test: `test_guide_has_all_figures`
- Commit: `"논문 Figure 구성 가이드 생성기"`
