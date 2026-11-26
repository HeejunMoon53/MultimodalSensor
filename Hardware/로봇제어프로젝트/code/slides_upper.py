"""상위 제어기 설명 슬라이드: 상태 머신(전이 조건 · 상태별 기준), 동작 예시, 파라미터 표, 대시보드 영상.

값은 supervisor.py · layers.py · params.json 에서 읽는다. 근거가 없는 값은 '(가정)' → 노란 칸.
"""
import numpy as np
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

import paths  # noqa: F401
from build_pptx import (FONT, MATH, MUTED, OUT, STATE_FILL, blk, fmt, get, image, movie, sig, table, text, wire)

TS = 0.01


def _node(s, x, y, w, h, lines, fill):
    b = blk(s, x, y, w, h, lines, 9, fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    p0 = b.text_frame.paragraphs[0]
    for r in p0.runs:
        r.font.bold, r.font.size = True, r.font.size * 1.25
    return b


def _lbl(s, x, y, t, w=1.6, align=PP_ALIGN.CENTER, size=8.5):
    m = t.startswith("$")
    return sig(s, x, y, t.lstrip("$"), size, w, align, italic=m, font=MATH if m else FONT)


def s_upper_fsm(s, P):
    """상태 노드 안 = 그 상태에서 하위로 보내는 기준(법칙) · 하위 모드, 화살표 = 전이 조건."""
    W, H, y1, y2 = 2.7, 1.45, 1.35, 4.3
    xs = dict(OPEN=0.4, APPROACH=4.7, GRASP=9.0)
    _node(s, xs["OPEN"], y1, W, H, ["OPEN", "u = 0 (배기)", "하위: 내부 루프 멈춤"], STATE_FILL["OPEN"])
    _node(s, xs["APPROACH"], y1, W, H, ["APPROACH", "$ε_{ref} = g(d̂)", "$|ε̇_{ref}| ≤ min(v, |g − ε_{ref}| / max(t_c, t_{min}))",
                                        "d ≤ d_{near} 또는 파지 명령: 0.3·v 로 닫기", "하위: 자유 LQG (ε 추종)"], STATE_FILL["APPROACH"])
    _node(s, xs["GRASP"], y1, W, H, ["GRASP", "$F_{ref}: F̂(진입) → F_t", "경사 F_{t} / 0.5 s (인체 0.5·F_{block} / s)",
                                     "하위: F-LQG + RLS (F 추종)"], STATE_FILL["GRASP"])
    _node(s, xs["GRASP"], y2, W, H, ["SAFETY", "u = 0 (배기)", "하위 반사가 1 kHz 로 먼저 배기", "ε 모드로 전환"], STATE_FILL["SAFETY"])
    _node(s, xs["OPEN"], y2, W, H, ["RELEASE", "$ε_{ref} → 0   (0.5·v_0)", "하위: 자유 LQG"], "EFEFEF")
    ym = y1 + 0.5
    # OPEN → APPROACH
    wire(s, [(3.1, ym), (4.7, ym)]); _lbl(s, 3.1, ym - 0.5, "$d̂ < d_{far}", 1.6); _lbl(s, 3.1, ym - 0.3, "또는 파지 명령", 1.6)
    # APPROACH ⇄ GRASP
    wire(s, [(7.4, ym), (9.0, ym)]); _lbl(s, 7.4, ym - 0.5, "접촉 c = 1 이 3번 연속", 1.6); _lbl(s, 7.4, ym - 0.3, "$F_{ref} ← F̂ (무충격)", 1.6)
    wire(s, [(9.0, ym + 0.55), (7.4, ym + 0.55)]); _lbl(s, 7.4, ym + 0.6, "c = 0 이 3번 연속", 1.6); _lbl(s, 7.4, ym + 0.8, "→ ε 모드", 1.6)
    # GRASP ⇄ SAFETY
    wire(s, [(9.8, y1 + H), (9.8, y2)])
    for k, t in enumerate(("$F̂ > F_{max}", "또는 ε_{ref} > ε_{max}", "또는 반사 플래그")):
        _lbl(s, 7.6, y1 + H + 0.25 + k * 0.22, t, 2.1, PP_ALIGN.RIGHT)
    wire(s, [(10.9, y2), (10.9, y1 + H)])
    for k, t in enumerate(("$F̂ ≤ F_t", "그리고 반사 해제", "→ GRASP (F_{ref} 다시 경사)")):
        _lbl(s, 11.0, y1 + H + 0.25 + k * 0.22, t, 2.2, PP_ALIGN.LEFT)
    # release 명령 → RELEASE → OPEN
    wire(s, [(5.4, y1 + H), (5.4, 3.55), (2.4, 3.55), (2.4, y2)])
    _lbl(s, 2.5, 3.25, "release 명령 (어느 상태에서나)", 2.8, PP_ALIGN.LEFT)
    wire(s, [(1.0, y2), (1.0, y1 + H)]); _lbl(s, 1.08, 3.3, "$ε_{ref} = 0", 1.0, PP_ALIGN.LEFT)
    # 입력 · 출력
    blk(s, 3.55, 3.95, 4.95, 2.2, [""], 9, "F7F7F7")
    text(s, 3.65, 3.98, 4.8, 2.7, ["상위 감독기: PC 20 Hz, 손가락마다 1개 (supervisor.py)",
                                   "입력: d̂, ḋ̂ (근접 칼만) · F̂ · c = 게이트 ∨ TENG · 반사 플래그 · 재질 m · 명령",
                                   "출력: 기준 하나 (ε_ref 또는 F_ref) + 모드, F_max → 하위 반사 문턱",
                                   "g(d̂) = ε_pre · sat((d_far − d̂) / (d_far − d_near))   (가까울수록 미리 굽힘)",
                                   "t_c = d̂ / (−ḋ̂): 닿기까지 남은 시간 → 그 안에 모양을 맞추는 속도"], 10.5, font=MATH)
    text(s, 0.4, 6.8, 12.5, 0.6, "노드 = 그 상태에서 하위로 보내는 기준과 하위 모드, 화살표 = 전이 조건. 재질 m 은 시뮬에서 정답 라벨 (판별기 = M1 예정). "
         "근접 추정값은 센서 범위 끝(24 mm)에서 포화하므로 d_far = 24 mm 이면 잡음만으로 APPROACH 에 들어간다 (영상 t ≈ 1 s) → d_far 를 범위 안쪽으로 + 히스테리시스가 개선안.",
         10, color=MUTED)


def s_upper_timeline(s, P):
    image(s, OUT / "upper_timeline.png", 0.3, 1.1, w=10.6)
    text(s, 11.0, 1.2, 2.1, 5.8, ["읽는 법: 위 두 줄이 상위 입력(근접 추정 d, 접촉 c), 셋째 줄이 상태, 맨 아래가 하위로 내려가는 기준 하나.",
                                  "A: 근접 추정이 d_near 아래로 → 천천히 닫음 → 접촉 3회 → GRASP, F_ref 가 F_t 까지 경사. 파지 명령(4.5 s) 전에 이미 GRASP.",
                                  "B: 인체는 힘 추정 편향(+1.5 N)이 목표 0.93 N 보다 커서 반사·SAFETY 가 계속 반복 → 기준이 끊긴다 (센서 한계, 한계 장)."],
         10.5, bullet=True)


def upper_param_rows(P):
    from layers import Reflex
    from supervisor import MATERIAL, N_CONFIRM, Supervisor
    ct, det = P.get("contact", {}), P.get("det", {})
    FB = get(P, "contact.conductor.F_block")
    poles = get(P, "det.lqr.poles")
    tau_in = max(-TS / np.log(abs(complex(*p))) for p in poles) if poles else None
    k_env = get(P, "contact.conductor.k_env")
    sup = Supervisor(F_block=FB or 1.0, Ba0=1.0, v0=det.get("v0") or 1.0, eps_open=0.0, eps_pre=0.3, eps_max=12.0)
    rx = Reflex(1.0, 0.5)
    rows = [["파라미터", "값", "뜻", "정한 근거"],
            ["상위 주기 · 지연", "(가정) 20 Hz · 20 ms", "PC 감독기 실행 간격, UART 지연", "가정. S10 에서 지연 20–200 ms · 두절 비교"],
            ["d_far", f"{sup.d_far:g} mm", "pre-shape 시작 거리", "센서 근접 범위 끝 (0909 데이터 0–24 mm). 포화 문제는 앞 장"],
            ["d_near", f"(가정) {sup.d_near:g} mm", "이보다 가까우면 천천히 닫아 접촉 만들기", "가정"],
            ["ε_open / ε_pre", f"{sup.eps_open:g} / {sup.eps_pre:g} %", "열림 · 근접 끝 굽힘", "ε_pre 작게: 물체가 손끝 사이를 지나가야 함 (S7)"],
            ["ε_max", f"{sup.eps_max:g} %", "굽힘 상한 (SAFETY)", "30 kPa 포화 굽힘 ε(30 kPa) ≈ 12 % (PRBM 보정)"],
            ["v_0", f"(가정) {fmt(det.get('v0'), 3)} %/s", "기준 속도 상한 (재질 배수 곱함)", "가정 (params det.v0)"],
            ["t_min · 닫기 속도", f"(가정) {sup.t_min:g} s · 0.3·v", "t_c 하한 (근접 속도 잡음 방지) · 접촉 만들기 속도", "가정"],
            ["N_confirm", f"{N_CONFIRM} 회 (= {N_CONFIRM * 50} ms)", "접촉 판정 연속 횟수", "게이트 잡음으로 GRASP 오진입 방지 (상위 주기 × 3)"],
            ["F_block", f"{fmt(FB, 3)} N", "F_t · F_max 의 기준 힘", "S8 시뮬 차단력 (도체 r15, 30 kPa)"],
            ["F_ref 경사", f"(가정) F_t / {sup.t_ramp:g} s, 인체 0.5·F_block / s", "힘 기준 증가 속도", "가정 (인체는 dF/dt 상한)"],
            ["B_a0 (비교용 A)", f"4·τ_in·k_env = {fmt(tau_in and k_env and 4 * tau_in * k_env, 3)}",
             "어드미턴스 댐퍼", f"내부 루프 시정수 τ_in = {fmt(tau_in, 3)} s 보다 4배 느리게 (루프 분리)"],
            ["반사 n_on / n_off / F_clr", f"{rx.n_on} / {rx.n_off} 샘플 / F_t", "힘 추정 > F_max 연속 → 배기 래치, 해제 조건", "1 kHz 잡음 한 샘플로는 안 튐 (layers.Reflex)"]]
    mats = [["재질", "F_t (×F_block)", "F_max (×F_block)", "v 배수", "F_t [N]", "F_max [N]"]]
    for m, lab in (("conductor", "도체"), ("dielectric", "유전체"), ("human", "인체")):
        M = MATERIAL[m]
        mats.append([lab, f"(가정) {M['Ft']}", f"(가정) {M['Fmax']}", f"(가정) {M['v']}", fmt(FB and M["Ft"] * FB, 3), fmt(FB and M["Fmax"] * FB, 3)])
    return rows, mats


def s_upper_params(s, P):
    rows, mats = upper_param_rows(P)
    table(s, 0.4, 1.12, 12.5, rows, [2.2, 2.9, 3.4, 4.0], 9.5, 0.36)
    table(s, 0.4, 5.95, 7.4, mats, [1.0, 1.35, 1.45, 1.0, 1.2, 1.4], 9, 0.26)
    text(s, 8.0, 5.95, 4.9, 1.3, ["노란 칸 = 근거 없는 가정값. 재질 배수는 '인체 < 유전체 < 도체' 순서만 의도, 크기는 B단계 R1·R6 실측으로 정한다.",
                                  "F_max 는 하위 반사 문턱으로도 내려간다."], 9.5, bullet=True)


def s_videos(s, P):
    for k, (key, lab) in enumerate((("A", "A 망치 받기 (도체)"), ("B", "B 팔 오잡기 (인체)"))):
        y = 1.12 + k * 3.05
        movie(s, OUT / f"V_{key}.mp4", OUT / f"V_{key}_poster.png", 0.35, y, 7.9, 2.96)
    r = get(P, "results_video") or {}
    A, B = r.get("A", {}), r.get("B", {})
    table(s, 8.45, 1.12, 4.5, [["A 망치 받기", "값"], ["목표 F_t / F_max [N]", fmt(A.get("F_t") and [A["F_t"], A["F_max"]], 3)],
                               ["유지 F 손 떼기 전 / 후 [N]", fmt(A.get("F_hold_before") and [A["F_hold_before"], A["F_hold_after"]], 3)],
                               ["파지 명령 후 최대 F [N]", fmt(A.get("F_peak_grasp"), 3)],
                               ["손 뗀 뒤 두 손가락 접촉 [%]", fmt(A.get("both_contact_after_pct"), 3)]], [3.0, 1.5], 9, 0.28)
    table(s, 8.45, 2.75, 4.5, [["B 팔 오잡기", "값"], ["급이동 → 반사 배기 [s]", fmt(B.get("t_trip_after_jerk_s"), 2)],
                               ["급이동 뒤 최대 F [N] (F_max)", fmt(B.get("F_peak_jerk") and [B["F_peak_jerk"], B["F_max"]], 3)],
                               ["F_max 초과 시간 [s]", fmt(B.get("t_over_s"), 2)], ["반사 배기 횟수", fmt(B.get("n_trips"))],
                               ["마지막 상태", fmt(B.get("final_state"))]], [3.0, 1.5], 9, 0.28)
    text(s, 8.45, 4.55, 4.5, 2.7, ["오른쪽 그래프: TDM 원신호(ΔL 주황 · ΔR 초록 · TENG 파랑) → MoE 추정(d, ε, F) → 기준 → 입력 u, 맨 위 띠 = 상위 상태.",
                                   "A 하중 이전은 근사: 물체가 3 mm 처지고 손 소품만 물러남 (무게 · 미끄럼 없음). 자유 물체 모델은 다음 단계.",
                                   "A 유지 중 u 가 0–30 kPa 로 크게 흔들린다 (σ ≈ 5 kPa, S7 · S10 과 같음): 힘 추정 잡음에 F-LQG 가 반응.",
                                   "B 급이동 전부터 반사가 반복: 인체 힘 추정 편향 (센서 한계). 첫 피크는 수동 충돌.",
                                   "release 는 시나리오 스크립트 명령 (7.8 s)."], 9, bullet=True)
