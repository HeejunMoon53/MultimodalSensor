"""시나리오 그림: 적응형 소프트 그리퍼 (PneuNet 2지 + 단일 소프트 전극).

흐름: ① 탐지 → ② 식별 (접촉 전) → 분기
  A. 망치 넘겨받기 (사람 → 그리퍼): 내밂 → 강철 머리 접촉 → 하중 이양 (F → F_ref) → 사람이 놓음
  B. 팔을 잘못 잡음: 인체 식별 → 천천히 닫힘 → 부드러운 접촉 (F ≤ F_safe) → 반사 배기 → 놓기
그림: render_gripper.py 의 시나리오 장면 (assets/scenario/*.png). 파동 · 접촉 표시 · 화살표 · 글자는 PPT 도형 (편집용).
슬라이드 2: 물체 식별 — 닿을 때까지의 손가락 굽힘 (고유감각, R → ε) = 크기 · 형상, 접촉 전 와전류 응답 (L) = 재질. 도체/유전체 × 큼/작음 2×2 + 특징 공간 개념도 (측정값 아님).
실행: python Paper/concept_fig/build_scenario_fig.py → Paper/concept_fig/Fig_Scenario.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

from build_concept_fig import A, CROP, INK, MUTED, at, line, place, shape, text

OUT = Path(__file__).resolve().parent / "Fig_Scenario.pptx"
S = A / "scenario"
NAVY, BLUE, GREEN, ORANGE = "1F3A5F", "2E6DB4", "2E8B57", "E8731A"
BLUE_BG, GREEN_BG, GREY_BG = "EAF2FB", "EBF6EF", "F3F5F8"
STATE = {"OPEN": "9AA5B1", "APPROACH": "2E6DB4", "GRASP": "E8731A", "SAFETY": "C0392B"}


def badge(s, x, y, n, color, r=0.28):
    shape(s, MSO_SHAPE.OVAL, x, y, r, r, color, None)
    text(s, x, y + 0.03, r, r - 0.05, str(n), 9.5, "FFFFFF", True, PP_ALIGN.CENTER)


def chip_w(st):
    return 0.16 + 0.072 * len(st)


def state_chips(s, cx, y, states):
    """가운데 cx 에 상태 칩들을 나란히."""
    x = cx - (sum(chip_w(st) for st in states) + 0.05 * (len(states) - 1)) / 2
    for st in states:
        w = chip_w(st)
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.2, STATE[st], None)
        text(s, x, y + 0.02, w, 0.17, st, 6.5, "FFFFFF", True, PP_ALIGN.CENTER)
        x += w + 0.05


def pic_center(s, img, x, y, w, h):
    """상자 (x, y, w, h) 가운데에 비율 유지로 맞춰 놓고, 놓인 상자를 돌려준다."""
    b = place(s, img, x, y, h=h)
    if b[2] > w:                                                               # 넓으면 폭에 맞춰 다시
        s.shapes._spTree.remove(s.shapes[-1]._element)
        b = place(s, img, x, y, w=w)
    pic = s.shapes[-1]
    dx, dy = (w - b[2]) / 2, (h - b[3]) / 2
    pic.left, pic.top = int(Inches(x + dx)), int(Inches(y + dy))
    return x + dx, y + dy, b[2], b[3]


def card(s, x, y, w, h, n, title, desc, states, color, bg, img, img_h):
    """세로 카드: 번호 + 제목 → 그림 → 설명 → 상태 칩. 그림 상자를 돌려준다."""
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, bg, None)
    badge(s, x + 0.07, y + 0.08, n, color)
    text(s, x + 0.38, y + 0.08, w - 0.42, 0.3, title, 9.5, INK, True)
    b = pic_center(s, S / f"{img}.png", x + 0.06, y + 0.42, w - 0.12, img_h)
    text(s, x + 0.06, y + 0.48 + img_h, w - 0.12, h - img_h - 0.78, desc, 7.5, MUTED, align=PP_ALIGN.CENTER)
    state_chips(s, x + w / 2, y + h - 0.28, states)
    return b


def arrow(s, x1, y1, x2, y2, color=MUTED, lw=2.0):
    line(s, [(x1, y1), (x2, y2)], color, lw, head=True)


def waves(s, cx, cy, color=BLUE, n=3):
    """손가락 끝 아래로 퍼지는 호 (아래쪽 반원 일부)."""
    for k in range(n):
        r = 0.1 + 0.08 * k
        a = shape(s, MSO_SHAPE.ARC, cx - r, cy + 0.05 * k - r, 2 * r, 2 * r, None, color, 1.5)
        a.rotation = 135                                                      # 기본 호 (12 → 3시) 를 아래쪽 (‿) 으로


def burst(s, cx, cy, r=0.2, color=BLUE):
    for dx, dy in ((-1, -0.45), (-1, 0.45), (1, -0.45), (1, 0.45), (-1.15, 0), (1.15, 0)):
        line(s, [(cx + dx * r * 0.75, cy + dy * r * 0.75), (cx + dx * r * 1.25, cy + dy * r * 1.25)], color, 1.5)


def scenario(s, x0, y0, w, h, title, color, bg, steps, overlay):
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x0, y0, w, h, bg, color, 1.0)
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x0 + w / 2 - 1.9, y0 - 0.17, 3.8, 0.34, color, None)
    text(s, x0 + w / 2 - 1.9, y0 - 0.14, 3.8, 0.3, title, 10.5, "FFFFFF", True, PP_ALIGN.CENTER)
    gap, cw = 0.17, (w - 0.2 - 3 * 0.17) / 4
    for j, (t, img, d, sts) in enumerate(steps):
        cx = x0 + 0.1 + j * (cw + gap)
        b = card(s, cx, y0 + 0.28, cw, h - 0.4, j + 1, t, d, sts, color, "FFFFFF", img, 1.75)
        overlay(s, img, b)
        if j < 3:
            arrow(s, cx + cw + 0.01, y0 + 0.28 + 1.3, cx + cw + gap - 0.01, y0 + 0.28 + 1.3, color, 1.75)


def overlay(s, img, b):
    """장면별 표시 (그림 상자 b 기준 비율 좌표)."""
    if img == "a_approach":                                                    # 사람이 망치를 들어 올려 내밂
        arrow(s, *at(b, 0.12, 0.62), *at(b, 0.12, 0.42), BLUE, 2.25)
    elif img == "a_contact":
        burst(s, *at(b, 0.47, 0.45), 0.2, BLUE)
    elif img == "a_grasp":
        burst(s, *at(b, 0.47, 0.45), 0.2, ORANGE)
    elif img == "a_handover":                                                  # 사람 손이 놓고 빠짐
        arrow(s, *at(b, 0.95, 0.72), *at(b, 0.95, 0.95), MUTED, 2.0)
    elif img == "b_slow":
        for sx in (-1, 1):                                                    # 손가락이 안쪽으로 천천히
            p = at(b, 0.45 + sx * 0.3, 0.5)
            arrow(s, p[0], p[1], p[0] - sx * 0.16, p[1], GREEN, 2.0)
    elif img in ("b_contact", "b_interact"):
        burst(s, *at(b, 0.42, 0.55), 0.16, GREEN if img == "b_contact" else "C0392B")
    elif img == "b_release":
        for sx in (-1, 1):
            p = at(b, 0.42 + sx * 0.3, 0.45)
            arrow(s, p[0], p[1], p[0] + sx * 0.16, p[1], GREEN, 2.0)


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 3.9, 0.1, 5.55, 0.46, NAVY, None)
    text(s, 3.9, 0.16, 5.55, 0.36, "Adaptive Soft Gripper Scenario", 18, "FFFFFF", True, PP_ALIGN.CENTER)
    # ① 탐지 → ② 식별 (공통)
    Y0, H = 0.72, 2.3
    b = card(s, 0.3, Y0, 2.2, H, 1, "Detection", "Senses the hammer before contact (proximity, same soft electrode)", ["OPEN"],
             NAVY, GREY_BG, "s_detect", 1.12)
    waves(s, *at(b, 0.5, 0.33), n=2)
    arrow(s, 2.55, Y0 + 1.15, 2.83, Y0 + 1.15, NAVY)
    x2, w2 = 2.88, 3.1
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x2, Y0, w2, H, GREY_BG, None)
    badge(s, x2 + 0.07, Y0 + 0.08, 2, NAVY)
    text(s, x2 + 0.38, Y0 + 0.08, 2.6, 0.3, "Identification", 9.5, INK, True)
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x2 + 0.12, Y0 + 0.42, w2 - 0.24, 1.32, "FFFFFF", "9DB0C3", 0.75)
    line(s, [(x2 + w2 / 2, Y0 + 0.48), (x2 + w2 / 2, Y0 + 1.68)], "9DB0C3", 0.75)
    pic_center(s, S / "s_obj_metal.png", x2 + 0.2, Y0 + 0.48, w2 / 2 - 0.3, 0.95)
    pic_center(s, S / "s_obj_hand.png", x2 + w2 / 2 + 0.1, Y0 + 0.5, w2 / 2 - 0.3, 0.9)
    text(s, x2 + 0.12, Y0 + 1.47, w2 / 2 - 0.12, 0.22, "Hammer (steel head)", 8, INK, True, PP_ALIGN.CENTER)
    text(s, x2 + w2 / 2, Y0 + 1.47, w2 / 2 - 0.12, 0.22, "Human arm", 8, INK, True, PP_ALIGN.CENTER)
    text(s, x2 + 0.06, Y0 + 1.8, w2 - 0.12, 0.3, "Classified before contact by the electrical response", 7.5, MUTED, align=PP_ALIGN.CENTER)
    state_chips(s, x2 + w2 / 2, Y0 + H - 0.28, ["APPROACH"])
    # 오른쪽 위: 한 전극 · 제어 계층
    bx, bw = 6.3, 6.73
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, bx, Y0, bw, H, "FFFFFF", "C9D3DE", 0.75)
    text(s, bx + 0.15, Y0 + 0.1, bw - 0.3, 0.25, "One soft electrode drives every decision (no extra sensors)", 10, INK, True)
    rows = [("Same electrode senses", "proximity · material · contact · force · finger bending"),
            ("Upper controller (PC)", "state machine and references for distance, speed and force"),
            ("Inner loop (MCU, 100 Hz)", "Kalman-LQG + RLS gain schedule: closes the gap, tracks grip force"),
            ("Edge layer (MCU, 1 kHz)", "TDM sensing + Edge-AI decoupling; safety reflex vents the finger if force > F_max")]
    for i, (k, v) in enumerate(rows):
        yy = Y0 + 0.45 + i * 0.4
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, bx + 0.15, yy, 1.8, 0.32, "EEF3F8", None)
        text(s, bx + 0.17, yy + 0.06, 1.76, 0.22, k, 7.5, NAVY, True, PP_ALIGN.CENTER)
        text(s, bx + 2.05, yy + 0.06, bw - 2.2, 0.3, v, 7.5, INK)
    state_chips(s, bx + 1.6, Y0 + H - 0.3, list(STATE))
    text(s, bx + 3.05, Y0 + H - 0.31, 3.5, 0.22, "supervisor states shown on each step", 7, MUTED, italic=True)
    # 분기: 식별 카드 아래 → A (왼쪽) · B (오른쪽)
    sx, sy, by = x2 + w2 / 2, Y0 + H, 3.3
    line(s, [(sx, sy), (sx, by)], NAVY, 2.0)
    line(s, [(sx, by), (3.42, by), (3.42, 3.46)], BLUE, 2.0, head=True)
    line(s, [(sx, by), (9.91, by), (9.91, 3.46)], GREEN, 2.0, head=True)
    text(s, sx - 1.35, by - 0.25, 1.3, 0.22, "metal", 8, BLUE, True, PP_ALIGN.RIGHT, italic=True)
    text(s, sx + 0.08, by - 0.25, 1.3, 0.22, "human", 8, GREEN, True, italic=True)
    # A · B
    YA, HA = 3.63, 3.58
    scenario(s, 0.3, YA, 6.25, HA, "Scenario A. Hammer hand-over (human → gripper)", BLUE, BLUE_BG,
             [("Offer", "a_approach", "Person holds up the hammer; fingers pre-shape by distance", ["APPROACH"]),
              ("Contact", "a_contact", "Both pads touch the steel head", ["GRASP"]),
              ("Load transfer", "a_grasp", "Grip force rises to F_ref while the person still holds", ["GRASP"]),
              ("Hand-over", "a_handover", "Person lets go; the gripper holds the hammer", ["GRASP"])], overlay)
    scenario(s, 6.78, YA, 6.25, HA, "Scenario B. Arm grasped by mistake", GREEN, GREEN_BG,
             [("Arm detected", "b_slow", "Arm between the fingers is identified as human: close slowly", ["APPROACH"]),
              ("Gentle contact", "b_contact", "Soft first touch, F ≤ F_safe", ["GRASP"]),
              ("Safety reflex", "b_interact", "1 kHz reflex vents the fingers if F > F_max", ["SAFETY"]),
              ("Release", "b_release", "Fingers open; the arm is free", ["OPEN"])], overlay)
    text(s, 0.3, 7.27, 12.7, 0.2, "Renders of the PneuNet two-finger gripper with the soft sensor on the bottom layer (illustration, not to scale). "
         "Control behaviour as validated in simulation (MuJoCo).", 7, MUTED, italic=True)
    build_recog(prs)
    prs.save(OUT)
    return OUT


COLOR_L, COLOR_R, DIEL = "FF8C00", "2CA02C", "7B4FA0"        # CLAUDE.md: L 주황 · R 초록. 유전체 = 보라
OBJS = [  # (렌더, 이름, 재질 행, 크기 열, 굽힘 정도, 와전류 정도, 메모) — 정도는 개념 (0–1), 측정값 아님
    ("can", "Metal can", 0, 0, 0.3, 0.85, "strong eddy current"),
    ("rod", "Metal rod", 0, 1, 0.8, 0.45, "smaller metal area"),
    ("block", "Wooden block", 1, 0, 0.3, 0.05, "no eddy current; TENG at contact"),
    ("egg", "Egg", 1, 1, 0.8, 0.05, "fragile: low F_max"),
]


def gauge(s, x, y, w, frac, color, label):
    text(s, x, y, w, 0.18, label, 6.5, MUTED)
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y + 0.19, w, 0.09, "E6EAF0", None)
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y + 0.19, max(w * frac, 0.06), 0.09, color, None)


def build_recog(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 2.4, 0.1, 8.55, 0.46, NAVY, None)
    text(s, 2.4, 0.16, 8.55, 0.36, "Object Recognition: Proprioception + Electrical Property", 18, "FFFFFF", True, PP_ALIGN.CENTER)
    # 위: 4단계 흐름 (글만)
    steps = [("Approach", "Eddy-current response before contact (L) → material: conductor / dielectric", ["APPROACH"], COLOR_L),
             ("Close until contact", "Finger bending when both pads touch (R → ε) → object size (proprioception)", ["GRASP"], COLOR_R),
             ("Squeeze", "Bending vs. pressure after contact → shape cue (round / flat)", ["GRASP"], COLOR_R),
             ("Classify & adapt", "class (material, size, shape) → F_ref, F_max, v_max", ["GRASP"], NAVY)]
    sw, sg, y0, h0 = 2.95, 0.3, 0.75, 1.05
    for j, (t, d, st, c) in enumerate(steps):
        x = 0.3 + j * (sw + sg)
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y0, sw, h0, GREY_BG, None)
        shape(s, MSO_SHAPE.RECTANGLE, x + 0.12, y0 + 0.13, 0.05, 0.22, c, None)
        badge(s, x + 0.25, y0 + 0.1, j + 1, NAVY)
        text(s, x + 0.58, y0 + 0.1, sw - 0.6, 0.28, t, 9.5, INK, True)
        text(s, x + 0.12, y0 + 0.42, sw - 1.1, 0.6, d, 7.5, MUTED)
        state_chips(s, x + sw - 0.5, y0 + h0 - 0.3, st)
        if j < 3:
            arrow(s, x + sw + 0.03, y0 + h0 / 2, x + sw + sg - 0.03, y0 + h0 / 2, NAVY)
    # 왼쪽 아래: 2×2 파지 갤러리
    gx, gy, lw_, cw, ch = 0.3, 2.05, 1.05, 3.27, 2.42
    for k, hd in enumerate(["Large object  ·  small bending", "Small object  ·  large bending"]):
        text(s, gx + lw_ + 0.08 + k * (cw + 0.08), gy, cw, 0.25, hd, 8.5, INK, True, PP_ALIGN.CENTER)
    for r, (nm, sub, c) in enumerate([("Conductor", "metal", BLUE), ("Dielectric", "wood, egg", DIEL)]):
        yy = gy + 0.3 + r * (ch + 0.08)
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, gx, yy, lw_, ch, c, None)
        text(s, gx, yy + ch / 2 - 0.25, lw_, 0.25, nm, 9.5, "FFFFFF", True, PP_ALIGN.CENTER)
        text(s, gx, yy + ch / 2, lw_, 0.22, sub, 7.5, "FFFFFF", align=PP_ALIGN.CENTER, italic=True)
    for key, name, r, c, bend, eddy, note in OBJS:
        x, y = gx + lw_ + 0.08 + c * (cw + 0.08), gy + 0.3 + r * (ch + 0.08)
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, ch, "FFFFFF", "D5DCE4", 0.75)
        pic_center(s, S / f"r_{key}.png", x + 0.14, y + 0.16, 1.45, ch - 0.32)
        tx, tw = x + 1.7, cw - 1.82
        text(s, tx, y + 0.25, tw, 0.28, name, 10, INK, True)
        gauge(s, tx, y + 0.65, tw, bend, COLOR_R, "finger bending at contact (ε)")
        gauge(s, tx, y + 1.1, tw, eddy, COLOR_L, "eddy-current response (L)")
        text(s, tx, y + 1.6, tw, 0.5, note, 7, MUTED, italic=True)
    # 오른쪽 아래: 특징 공간 (개념도)
    fx, fy, fw, fh = 8.2, 2.05, 4.83, 5.0
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, fx, fy, fw, fh, "FFFFFF", "C9D3DE", 0.75)
    text(s, fx + 0.15, fy + 0.08, fw - 0.3, 0.28, "Feature space (schematic)", 10, INK, True)
    ox, oy, ax, ay = fx + 0.7, fy + 4.15, fw - 1.0, 3.55                       # 원점 (왼쪽 아래), 축 길이
    line(s, [(ox, oy), (ox + ax, oy)], INK, 1.25, head=True)
    line(s, [(ox, oy), (ox, oy - ay)], INK, 1.25, head=True)
    text(s, ox, oy + 0.05, ax, 0.4, "finger bending at contact ε (proprioception)  →  smaller object", 7.5, COLOR_R, True, PP_ALIGN.CENTER)
    text(s, ox - 0.55 - ay / 2 + 0.2, oy - ay / 2 - 0.15, ay, 0.3, "eddy-current response (L)  →  conductor", 7.5, COLOR_L, True, PP_ALIGN.CENTER)
    s.shapes[-1].rotation = 270
    line(s, [(ox + ax / 2, oy - 0.05), (ox + ax / 2, oy - ay + 0.1)], "B8C2CE", 1.0, dash=True)
    line(s, [(ox + 0.05, oy - ay * 0.38), (ox + ax - 0.1, oy - ay * 0.38)], "B8C2CE", 1.0, dash=True)
    for key, name, r, c, bend, eddy, note in OBJS:
        cx, cy = ox + ax * (0.25 + 0.5 * c), oy - ay * (0.22 if r else (0.55 + 0.3 * eddy))
        col = BLUE if r == 0 else DIEL
        shape(s, MSO_SHAPE.OVAL, cx - 0.72, cy - 0.5, 1.44, 1.0, None, col, 1.0, dash=True)
        pic_center(s, S / f"o_{key}.png", cx - 0.4, cy - 0.42, 0.8, 0.62)
        text(s, cx - 0.72, cy + 0.2, 1.44, 0.22, name, 7.5, col, True, PP_ALIGN.CENTER)
    text(s, fx + 0.15, fy + fh - 0.42, fw - 0.3, 0.38, "Positions are qualitative, not measured. A human hand is told apart by the TENG pulse at contact (scenario B).",
         7, MUTED, italic=True)
    text(s, 0.3, 7.27, 12.7, 0.2, "Renders of the PneuNet two-finger gripper with the soft sensor on the bottom layer (illustration, not to scale). "
         "Bending (ε) and eddy-current bars are qualitative; the object classifier is planned (M1), not yet validated.", 7, MUTED, italic=True)


if __name__ == "__main__":
    CROP.mkdir(parents=True, exist_ok=True)
    print(build())
