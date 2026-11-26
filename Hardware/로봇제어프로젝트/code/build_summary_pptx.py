"""두괄식 요약 PPT: 장마다 결론 한 줄을 맨 위에, 그 아래 근거 그림 · 수치. 모든 수치는 시뮬레이션 결과 파일에서 읽는다.

실행: C:/ml_env/Scripts/python.exe Hardware/로봇제어프로젝트/code/build_summary_pptx.py → MEC799_Summary_두괄식.pptx
근거 파일: params.json (results_*), out/S6_metrics.csv, out/S9_metrics.csv, out/*.png, out/V_*.mp4
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.util import Inches, Pt

import paths  # noqa: F401
from build_pptx import ACCENT, MUTED, box, fmt, get, image, movie, read_csv, table, text
from paths import OUT, PROJECT, load_params

S10_KEYS = dict(up20="상위 배기 · 지연 20 ms", up200="상위 배기 · 지연 200 ms", drop="상위 배기 · 통신 두절",
                reflex="하위 반사 1 kHz", reflex_drop="하위 반사 1 kHz · 통신 두절")


def _csv(name):
    rows = read_csv(OUT / name)
    h = rows[0]
    return {r[0]: dict(zip(h[1:], map(float, r[1:]))) for r in rows[1:]}


def evidence(P=None):
    """결론마다 쓰는 수치 (모두 결과 파일에서 계산)."""
    P = load_params() if P is None else P
    s6, s9 = _csv("S6_metrics.csv"), _csv("S9_metrics.csv")
    pert = list(dict.fromkeys(k.split(" | ")[0] for k in s6))
    scen = list(dict.fromkeys(k.split(" | ")[0] for k in s9))
    ctrl = list(dict.fromkeys(k.split(" | ")[1] for k in s9))   # A 어드미턴스, B F-LQG, ...
    rmse = lambda sc, c: s9[f"{sc} | {c}"]["rmse_hold"]
    r10 = get(P, "results_s10") or {}
    return dict(
        obsv=get(P, "model.rank_obsv") or {},
        s6=s6, s6_pert=pert,
        s6_fb={p: s6[f"{p} | 없음"]["rmse_improve_pct"] for p in pert},          # LQG vs 개루프 FF [%] (+ = 오차 감소)
        s6_dob={p: s6[f"{p} | DOB"]["dob_vs_lqg_pct"] for p in pert},           # DOB vs LQG [%]
        s9_rows={sc: (rmse(sc, ctrl[0]), rmse(sc, ctrl[1])) for sc in scen},
        s9={sc: 100 * (rmse(sc, ctrl[1]) - rmse(sc, ctrl[0])) / rmse(sc, ctrl[0]) for sc in scen},   # B vs A [%] (− = 감소)
        s10={k: r10.get(f"human | {v}", {}).get("impulse_over_Ns") for k, v in S10_KEYS.items()},
        s10_peak={k: r10.get(f"human | {v}", {}).get("F_peak") for k, v in S10_KEYS.items()},
        video=get(P, "results_video") or {})


def _fit(s, path, x, y, w, h):
    """그림을 (w, h) 상자 안에 비율 유지로 넣고 가운데 정렬."""
    from PIL import Image
    if Path(path).exists():
        iw, ih = Image.open(path).size
        if iw / ih > w / h:
            return image(s, path, x, y + (h - w * ih / iw) / 2, w=w)
        return image(s, path, x + (w - h * iw / ih) / 2, y, h=h)
    return image(s, path, x, y, w=w, h=h)


def head(s, n, claim, why=None):
    """첫 텍스트 = '결론 n. 주장' (두괄식). 아래 한 줄 = 왜 중요한가."""
    text(s, 0.45, 0.25, 12.4, 0.9, f"결론 {n}. {claim}", 22, True)
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.5), Inches(1.2), Inches(12.8), Inches(1.2))
    ln.line.color.rgb, ln.line.width = ACCENT, Pt(1.5)
    if why:
        text(s, 0.5, 1.27, 12.3, 0.45, why, 13, color=ACCENT)


def foot(s, t):
    text(s, 0.5, 7.05, 12.3, 0.35, "근거 (시뮬레이션): " + t, 9.5, color=MUTED)


def pct(v):
    return f"{v:+.0f} %"


def build(out_path=PROJECT / "MEC799_Summary_두괄식.pptx", P=None):
    P = load_params() if P is None else P
    E = evidence(P)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    new = lambda: prs.slides.add_slide(blank)

    fb_bad = {p: v for p, v in E["s6_fb"].items() if p.startswith("강성")}
    s9_good = {k: v for k, v in E["s9"].items() if not k.startswith("인체")}
    s9_h = next((v for k, v in E["s9"].items() if k.startswith("인체")), None)
    i10 = E["s10"]
    red10 = lambda a, b: 100 * (i10[b] - i10[a]) / i10[a] if i10.get(a) and i10.get(b) is not None else None
    vA, vB = E["video"].get("A", {}), E["video"].get("B", {})
    claims = [
        ("손가락에 넣은 센서가 있어야 굽힘을 되먹임할 수 있다",
         f"압력만 재면 가관측 랭크 {fmt(E['obsv'].get('p'))}/2, 센서 ε 를 더하면 {fmt(E['obsv'].get('eps'))}/2"),
        ("모델이 ±30 % 틀려도 센서 되먹임(LQG)이 굽힘 오차를 크게 줄인다",
         "강성 ±30 %: 개루프 대비 RMSE " + " · ".join(pct(-v) for v in fb_bad.values()) + f" (공칭에선 개루프가 나음, DOB 이득은 작음)"),
        ("접촉 후에는 굽힘이 아니라 힘을 직접 추종해야 한다",
         "유지 힘 RMSE " + " · ".join(pct(v) for v in s9_good.values()) + " (도체 · 유전체, 어드미턴스 대비)"),
        ("상위 제어기는 상태 머신 하나로, 기준 하나만 하위로 내린다",
         "OPEN → APPROACH(ε_ref = g(d)) → GRASP(F_ref 경사) · SAFETY(배기) · RELEASE"),
        ("안전 동작은 하위 1 kHz 반사로 해야 한다",
         f"인체 지령 폭주: F_max 초과 충격량 상위(지연 20 ms) 대비 {pct(red10('up20', 'reflex')) if red10('up20', 'reflex') is not None else '?'}, "
         f"통신 두절 대비 {pct(red10('drop', 'reflex_drop')) if red10('drop', 'reflex_drop') is not None else '?'}"),
        ("시나리오: 망치 받기는 유지, 팔 오잡기는 반사로 놓지만 인체 힘 추정이 병목",
         f"A 손 뗀 뒤 두 손가락 접촉 {fmt(vA.get('both_contact_after_pct'), 3)} %, B 급이동 → 배기 {fmt(vB.get('t_trip_after_jerk_s'), 2)} s"),
    ]

    # 1 표지
    s = new()
    text(s, 0.8, 2.2, 11.7, 1.0, "PneuNet 2지 센서 되먹임 제어 — 요약", 36, True)
    text(s, 0.8, 3.3, 11.7, 0.6, "결론 먼저, 근거는 아래. 자세한 유도 · 표는 본 발표 자료 (MEC799_Project_PneuNet.pptx)", 16, color=MUTED)
    text(s, 0.8, 5.6, 11.7, 0.8, ["[MEC799] Robot Control — Final Project", "문희준 · BioRobotics & Control Lab, 고려대학교 기계공학과"], 14)

    # 2 한 장 요약
    s = new()
    text(s, 0.45, 0.25, 12.4, 0.7, "한 장 요약: 결론 6개", 26, True)
    for k, (c, num) in enumerate(claims):
        y = 1.15 + k * 0.92
        box(s, 0.5, y, 0.55, 0.75, str(k + 1), "DCE6F2", 18, True)
        text(s, 1.2, y - 0.02, 11.6, 0.4, c, 16, True)
        text(s, 1.2, y + 0.36, 11.6, 0.4, num, 12, color=MUTED)
    text(s, 0.5, 6.85, 12.3, 0.5, "모든 수치는 시뮬레이션(A단계: MuJoCo PRBM 손가락 + ITV · 센서 비이상성). 실물 값이 아니다.", 11, color=MUTED)

    # 결론 1 가관측성
    s = new(); head(s, 1, claims[0][0], "공압 손가락의 굽힘은 압력만으로는 보이지 않는다 → 매립 센서의 제어 이론적 필요성")
    _fit(s, OUT / "analysis_poles_obsv.png", 0.5, 1.85, 12.3, 4.3)
    text(s, 0.5, 6.2, 12.3, 0.8, [claims[0][1] + " (2상태 x = [p, ε]).",
                                  "→ 굽힘 추종 · 칼만 필터 · 접촉 힘 추정 모두 이 센서 신호 위에 선다."], 13, bullet=True)
    foot(s, "params.json model.rank_obsv, out/analysis_poles_obsv.png")

    # 결론 2 되먹임 강건성
    s = new(); head(s, 2, claims[1][0], "개루프 맵은 모델이 맞을 때만 좋다. 실물은 강성 · 하중이 바뀐다.")
    _fit(s, OUT / "S6_dob.png", 0.4, 1.85, 7.6, 3.4)
    rows = [["섭동", "개루프 RMSE", "LQG RMSE", "LQG vs 개루프", "DOB vs LQG"]]
    for p in E["s6_pert"]:
        rows.append([p, f"{E['s6'][p + ' | FF']['rmse']:.2f}", f"{E['s6'][p + ' | 없음']['rmse']:.2f}", pct(-E["s6_fb"][p]), pct(-E["s6_dob"][p])])
    table(s, 8.2, 1.85, 4.7, rows, [1.4, 0.85, 0.8, 0.85, 0.8], 9, 0.3)
    dob = list(E["s6_dob"].values())
    text(s, 0.5, 5.4, 12.3, 1.6, [f"강성 ±30 % 에서 개루프 RMSE 는 {E['s6']['강성 +30 % | FF']['rmse']:.2f} · {E['s6']['강성 −30 % | FF']['rmse']:.2f} % 로 커지지만 LQG 는 1 % 아래로 유지.",
                                  f"공칭(모델 정확)에선 개루프 맵이 더 낫다 (LQG {pct(-E['s6_fb']['공칭'])}): 센서 잡음 σ ≈ 0.4 % 를 되먹임하기 때문. 숨기지 않고 보고.",
                                  f"DOB 추가 효과는 {min(-v for v in dob):+.0f} ~ {max(-v for v in dob):+.0f} % (− = 오차 감소) 로 작고 일관되지 않다 → 핵심은 적분 서보 + 센서 되먹임."], 12, bullet=True)
    foot(s, "out/S6_metrics.csv (RMSE [%], 표의 − = 오차 감소)")

    # 결론 3 힘 직접 추종
    s = new(); head(s, 3, claims[2][0], "물체를 쥐면 굽힘 ε 는 거의 막힌다(g = 0.28–0.48). 힘 F 가 실제 출력이 된다.")
    _fit(s, OUT / "S9_force.png", 0.4, 1.85, 6.2, 5.1)
    rows = [["물체", "어드미턴스 RMSE [N]", "힘 직접 추종 [N]", "변화"]]
    for sc, (a, b) in E["s9_rows"].items():
        rows.append([sc, f"{a:.3g}", f"{b:.3g}", pct(E["s9"][sc])])
    table(s, 6.8, 1.85, 6.1, rows, [2.4, 1.4, 1.3, 1.0], 10, 0.34)
    text(s, 6.8, 3.75, 6.1, 3.2, ["같은 상태 [p, ε_f] 와 모델에서 출력만 F 로 바꿔 적분 서보(F-LQG)를 설계.",
                                  "k_eq(힘/굽힘)는 쥔 위치 · 크기로 약 2배 바뀐다 → RLS 게인 스케줄은 k_eq 가 공칭과 다를 때만 이득.",
                                  f"인체는 실패 ({pct(s9_h) if s9_h is not None else '?'}): 힘 추정 편향 (+1.5 N) 이 목표 0.93 N 보다 크다 → 센서 정확도가 먼저."], 12, bullet=True)
    foot(s, "out/S9_metrics.csv (유지 구간 정답 F 기준), 어드미턴스 = 기존 A, 힘 직접 추종 = B")

    # 결론 4 상위 제어기
    s = new(); head(s, 4, claims[3][0], "상위는 '언제 무엇을' 정하고, 하위는 '그 기준을 정확히' 따른다.")
    _fit(s, OUT / "upper_timeline.png", 0.3, 1.8, 9.5, 5.2)
    text(s, 9.95, 1.85, 3.0, 5.1, ["입력: 근접 d · 접촉 c (게이트 ∨ TENG) · 힘 · 반사 플래그 · 재질 · 명령.",
                                   "APPROACH: ε_ref = g(d), 닿기 전 남은 시간 t_c 안에 모양 맞춤.",
                                   "GRASP: 접촉 3회 연속 → F_ref 를 지금 힘에서 F_t 까지 경사 (무충격).",
                                   "SAFETY: 힘 > F_max → 배기. 재질은 지금 정답 라벨 (판별기 M1).",
                                   "주기 20 Hz, 파라미터 대부분은 가정값 (본 자료 표)."], 11.5, bullet=True)
    foot(s, "out/upper_timeline.png (영상 A · B 기록), supervisor.py")

    # 결론 5 하위 반사
    s = new(); head(s, 5, claims[4][0], "구동기가 힘을 만드는 고장은 감지 지연만큼 힘이 계속 오른다. 반사는 TDM 샘플마다 본다.")
    _fit(s, OUT / "S10.png", 0.4, 1.8, 12.5, 3.35)
    rows = [["인체 · 지령 폭주", "최대 F [N]", "초과 충격량 [N·s]"]]
    for k in ("up20", "up200", "drop", "reflex", "reflex_drop"):
        rows.append([S10_KEYS[k], fmt(E["s10_peak"][k], 3), fmt(i10[k], 2)])
    table(s, 0.5, 5.25, 6.6, rows, [3.2, 1.5, 1.9], 10, 0.29)
    text(s, 7.3, 5.25, 5.6, 1.8, ["상위 지연 20 ms 는 ITV 지연과 비슷해 차이가 작다. 100 ms 이상 · 두절에서 차이가 커진다.",
                                  "손이 갑자기 움직일 때의 첫 피크는 수동 충돌이라 어떤 제어로도 못 줄인다.",
                                  "→ 안전 동작 = 배기, 실행 = 하위. 문턱 F_max 는 상위가 재질로 정해 내려보낸다."], 11.5, bullet=True)
    foot(s, "params.json results_s10, out/S10.png")

    # 결론 6 시나리오 영상
    s = new(); head(s, 6, claims[5][0], "영상 오른쪽 = TDM 원신호(ΔL · ΔR · TENG) → 추정 → 기준 → 입력 u, 맨 위 띠 = 상위 상태")
    for k, key in enumerate("AB"):
        movie(s, OUT / f"V_{key}.mp4", OUT / f"V_{key}_poster.png", 0.4 + k * 6.3, 1.85, 6.15, 2.31)
    table(s, 0.4, 4.3, 6.15, [["A 망치 받기 (도체)", "값"],
                              ["유지 F 손 떼기 전 / 후 [N]", fmt(vA.get("F_hold_before") and [vA["F_hold_before"], vA["F_hold_after"]], 3)],
                              ["목표 F_t / F_max [N]", fmt(vA.get("F_t") and [vA["F_t"], vA["F_max"]], 3)],
                              ["손 뗀 뒤 두 손가락 접촉 [%]", fmt(vA.get("both_contact_after_pct"), 3)]], [4.0, 2.15], 10, 0.3)
    table(s, 6.7, 4.3, 6.2, [["B 팔 오잡기 (인체)", "값"], ["급이동 → 반사 배기 [s]", fmt(vB.get("t_trip_after_jerk_s"), 2)],
                             ["F_max 초과 시간 [s]", fmt(vB.get("t_over_s"), 2)], ["반사 배기 횟수 · 마지막 상태", fmt(vB.get("n_trips") is not None and f"{vB['n_trips']} · {vB.get('final_state')}")]],
          [4.0, 2.2], 10, 0.3)
    text(s, 0.4, 5.65, 12.5, 1.4, ["A 하중 이전은 근사 (물체 3 mm 처짐, 손 소품만 물러남) → 다음 단계에서 자유 물체(무게 · 마찰)로.",
                                   "B 는 급이동 전부터 반사 · SAFETY 가 반복된다: 인체 힘 추정 편향이 목표 힘보다 크다 (결론 3 과 같은 원인)."], 12, bullet=True)
    foot(s, "out/V_A.mp4, out/V_B.mp4, params.json results_video")

    # 한계와 다음 단계
    s = new()
    text(s, 0.45, 0.25, 12.4, 0.7, "한계와 다음 단계", 26, True)
    text(s, 0.5, 1.2, 12.3, 5.8, ["힘 추정 편향(MoE)이 가장 큰 병목: 도체 유지 힘이 목표보다 크고, 인체는 목표 힘(0.93 N)보다 오차(+1.5 N)가 커서 파지 · 상호작용 실패 → 실물 R1 · R6 보정이 먼저.",
                                  "유지 중 입력 u 가 0–30 kPa 로 흔들린다 (σ ≈ 5 kPa): 힘 추정 잡음에 반응 → 측정 필터 · Bryson δF 재조정.",
                                  "망치 받기의 하중 이전은 근사 → (b) 손을 떼면 망치를 자유 물체(질량 · 중력 · 패드 마찰)로 바꿔 미끄럼 · 낙하와 F_t ≥ mg/(2μ) 확인.",
                                  "상위 d_far = 센서 근접 범위 끝(24 mm) → 포화 잡음으로 APPROACH 진입. d_far 를 안쪽으로 + 히스테리시스.",
                                  "재질은 정답 라벨 → 판별기(M1). DOB 는 2지 파지에서 입력 진동 → 원인 분석 전까지 제외.",
                                  "실물 B단계 R1–R8 → 같은 스크립트로 params.json 과 두 PPT 를 다시 생성."], 15, bullet=True)

    out_path = Path(out_path)
    prs.save(out_path)
    return out_path


if __name__ == "__main__":
    print(build())
