"""논문 개념 그림 (Fig. 1 후보, 2안): 사람 촉각·신경 체계에서 영감 + 그 이상.

공통 왼쪽 패널 a (a+b 통합): 피부 블록 ↔ 센서 블록, 감각 대응표 (근접 · 재질 = beyond human).
오른쪽 패널 b:
  1안 — 인체 한 장 위에 신경 계층을 얹고, 부위마다 이 연구 내용을 지시선으로 대입 (하나로 이어진 그림)
  2안 — 왼쪽 사람 ↔ 오른쪽 소프트 그리퍼, 가운데 대응 쌍을 대칭으로
사람 그림: Servier Medical Art (CC BY 4.0, assets/servier/SOURCE.txt). 센서 블록 · 그리퍼: Blender 렌더
(render_sensor_cube.py · render_gripper.py, not to scale). MCU 보드: 세미나 PCB 렌더.
글자는 모두 따로 둔 텍스트 상자 (편집용). 실행: python Paper/concept_fig/build_concept_fig.py → Fig_BioInspired_Concept.pptx
"""
from pathlib import Path

import numpy as np
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "Fig_BioInspired_Concept.pptx"
A = HERE / "assets"
SV = A / "servier"
CROP = A / "crops"

FONT = "Arial"
INK, MUTED, EDGE = "222222", "666666", "8C8C8C"
AFF, EFF = "1F77B4", "C0392B"                                  # 구심 (감각) · 원심 (운동)
HUMAN_BG, WORK_BG, BEYOND_BG = "FBF1EA", "EEF3F8", "FFF6D6"
LEAD = "7A7A7A"


def rgb(h):
    return RGBColor.from_string(h)


# ---------------- 이미지 준비 ----------------
def prep():
    CROP.mkdir(parents=True, exist_ok=True)
    src = Image.open(ROOT / "Paper/figures/seminar_pcb.png")
    W, H = src.size
    px = np.array(src.crop((int(0.06 * W), int(0.04 * H), W, int(0.76 * H))).convert("RGBA"))
    px[px[..., :3].min(axis=2) > 242, 3] = 0                                # 흰 배경 → 투명
    Image.fromarray(px).save(CROP / "pcb.png")
    clean_body(Image.open(SV / "Systeme_nerveux.png").crop((0, 0, 501, BODY_H))).save(CROP / "body.png")   # 머리 – 허벅지


def clean_body(im, fill=(222, 232, 240), edge=(70, 110, 150), fade=110):
    """신경계 인체를 도식형으로: 피부 → 단색, 안쪽 선 (젖꼭지 · 배꼽 · 얼굴 · 사타구니) 제거, 바깥 윤곽만, 아랫단은 흐리게.
    신경 (노랑) · 뇌 (회색) · 소뇌 (보라) 는 원래 색 그대로."""
    from scipy import ndimage
    a = np.array(im.convert("RGBA")).astype(int)
    r, g, b, al = (a[..., i] for i in range(4))
    body = al > 0
    nerve = (r > 190) & (g > 120) & (g < 225) & (b < 120)
    brain_box = np.zeros_like(body); brain_box[12:120, 188:316] = True                  # 대뇌 영역
    cereb_box = np.zeros_like(body); cereb_box[85:120, 195:260] = True                  # 소뇌 영역 (보라: 눈썹과 색이 비슷해 좁게)
    brain = body & ~nerve & ((brain_box & (b >= r - 2) & (r > 120)) | (cereb_box & (r > g + 15) & (b > g + 5) & (r < 230)))
    rim = body & ndimage.binary_dilation(~body, iterations=4)                          # 바깥 윤곽 띠
    out = np.zeros_like(a)
    out[body] = (*fill, 255)
    out[rim] = (*edge, 255)
    dark = a[..., :3].max(axis=2) < 140
    eye = np.zeros_like(body); eye[60:110, 296:340] = True                             # 눈 · 눈썹 선은 지움
    keep = (nerve | brain | (brain_box & dark & ~eye)) & ~rim                                # 뇌 주름 윤곽선은 남김
    out[keep] = a[keep]
    h = out.shape[0]
    out[h - fade:, :, 3] = (out[h - fade:, :, 3] * np.linspace(1, 0, fade)[:, None]).astype(int)   # 잘린 아랫단 흐리게
    return Image.fromarray(out.astype(np.uint8))


def place(s, path, x, y, w=None, h=None, trim=True):
    """투명 여백을 잘라 놓고 (trim), 놓인 상자 (x, y, w, h) 를 돌려준다 (w 또는 h 하나만 주면 비율 유지)."""
    im = Image.open(path)
    if trim and im.mode == "RGBA":
        bb = im.getchannel("A").getbbox()
        if bb and bb != (0, 0, *im.size):
            p = CROP / ("t_" + Path(path).name)
            im = im.crop(bb); im.save(p); path = p
    if w is None:
        w = h * im.width / im.height
    if h is None:
        h = w * im.height / im.width
    s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    return x, y, w, h


def at(box_, fx, fy):
    x, y, w, h = box_
    return x + fx * w, y + fy * h


# ---------------- 도형 · 글자 ----------------
def shape(s, kind, x, y, w, h, fill=None, line_=EDGE, lw=0.75, dash=False):
    sh = s.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    else:
        sh.fill.background()
    if line_:
        sh.line.color.rgb = rgb(line_); sh.line.width = Pt(lw)
        if dash:
            sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def text(s, x, y, w, h, runs, size=9, color=INK, bold=False, align=PP_ALIGN.LEFT, italic=False, anchor=MSO_ANCHOR.TOP):
    """runs: 문자열 또는 [(글자, {size, bold, color, italic, sub})...] 의 줄 목록."""
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = anchor
    for i, ln in enumerate(runs if isinstance(runs, list) else [runs]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        for t, o in ([(ln, {})] if isinstance(ln, str) else ln):
            r = p.add_run(); r.text = t
            f = r.font
            f.name, f.size = FONT, Pt(o.get("size", size))
            f.bold, f.italic = o.get("bold", bold), o.get("italic", italic)
            f.color.rgb = rgb(o.get("color", color))
            if o.get("sub"):
                r._r.get_or_add_rPr().set("baseline", "-25000")
    return tf


def line(s, pts, color=EDGE, lw=1.0, head=False, dash=False):
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(pts[:-1], pts[1:])):
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = rgb(color); c.line.width = Pt(lw)
        if dash:
            c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if head and i == len(pts) - 2:
            etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd"), type="triangle", w="med", len="med")


def dot(s, x, y, c=LEAD, r=0.035):
    shape(s, MSO_SHAPE.OVAL, x - r, y - r, 2 * r, 2 * r, c, None)


def leader(s, p, q, c=LEAD):
    """부위 점 p → 글자 q (점 + 선)."""
    dot(s, *p, c); line(s, [p, q], c, 0.75)


def panel_label(s, x, y, letter, title_):
    text(s, x, y, 7.0, 0.3, [[(letter + "  ", {"bold": True, "size": 13}), (title_, {"bold": True, "size": 11})]])


def tag(s, x, y, w, t, fill):
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.22, fill, None)
    text(s, x, y + 0.01, w, 0.2, t, 8, INK, True, PP_ALIGN.CENTER)


def field(s, x, y, w, h):
    for k in range(2):
        shape(s, MSO_SHAPE.OVAL, x - 0.07 - k * 0.09, y - 0.06 - k * 0.07, w + 0.14 + k * 0.18, h + 0.12 + k * 0.14, None, "7F8C8D", 0.6, dash=True)


# ---------------- a. 피부 ↔ 센서 + 감각 대응 ----------------
def panel_a(s):
    panel_label(s, 0.25, 0.2, "a", "Soft and multimodal, like skin — and beyond")
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.25, 0.6, 2.72, 2.45, HUMAN_BG, None)
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 3.05, 0.6, 2.72, 2.45, WORK_BG, None)
    tag(s, 0.33, 0.67, 0.7, "Human", "F2C9AE"); tag(s, 3.13, 0.67, 0.85, "This work", "C9DAEC")
    sk = place(s, SV / "Integumentary-system.png", 0.42, 1.0, w=2.0)
    for (fx, fy), t, ty in (((0.97, 0.38), "Epidermis", 1.15), ((0.97, 0.62), "Dermis", 1.55), ((0.80, 0.80), "Mechano-\nreceptors", 1.95),
                            ((0.95, 0.90), "Subcutis", 2.45)):
        leader(s, at(sk, fx, fy), (2.48, ty + 0.08))
        text(s, 2.5, ty - 0.02, 0.48, 0.4, t.split("\n"), 6.5, INK)
    cb = place(s, A / "sensor_cube.png", 3.15, 1.02, w=1.95)
    for (fx, fy), t, ty in (((0.92, 0.12), "Two-wire lead", 0.98), ((0.75, 0.32), "Cover silicone\n+ bumps", 1.38),   # 점 높이 순 → 교차 없음
                            ((0.20, 0.42), "EGaIn spiral\n(DIW)", 1.88), ((0.32, 0.80), "Base silicone", 2.4)):
        leader(s, at(cb, fx, fy), (5.12, ty + 0.08))
        text(s, 5.14, ty - 0.02, 0.62, 0.4, t.split("\n"), 6.5, INK)
    text(s, 0.33, 2.7, 2.56, 0.3, "Compliant, stretchable, receptor-rich", 7.5, MUTED, align=PP_ALIGN.CENTER, italic=True)
    text(s, 3.13, 2.7, 2.56, 0.3, [[("Stretchable single electrode, ", {}), ("ε", {"italic": True}), (" up to 30 % (not to scale)", {})]],
         7.5, MUTED, align=PP_ALIGN.CENTER, italic=True)
    # 감각 대응표
    X0, W = 0.25, 5.52
    cols = [("Human", 1.75), ("Modality", 1.35), ("This work", 2.42)]
    y0, rh = 3.15, 0.7
    x = X0
    for name, w in cols:
        text(s, x, y0, w, 0.22, name, 8.5, INK, True, PP_ALIGN.CENTER); x += w
    line(s, [(X0, y0 + 0.26), (X0 + W, y0 + 0.26)], EDGE, 0.75)
    # 이 연구 열: 장면 렌더 + "→ 쓰임새" (감각별 색) + 한 줄 설명 (세미나 S05 형식, 신호 기호 없이)
    G = lambda n: A / f"{n}.png"
    rows = [("Bras.png", "muscle spindle", "Proprioception", "stretch", [G("gripper")], "3A9A5B", "self-shape awareness", "finger bending, body state"),
            ("Main.png", "Merkel, Ruffini", "Pressure", "force", [G("grip_egg")], "E8731A", "force-feedback grasp", "grip force on fragile objects"),
            ("Integumentary-system-1.png", "Meissner, Pacinian", "Touch", "contact", [G("grip_touch")], "1E8A8A", "contact detection", "contact onset and release"),
            ("poisson.png", "electric fish: electrolocation", "Proximity", "pre-contact", [G("grip_near")], "1F77B4", "pre-grasp, collision avoidance",
             "detects objects before contact"),
            ("poisson.png", "electric fish: impedance sensing", "Material", "conductor / dielectric", [G("grip_near"), SV / "Main.png"], "7B3F98",
             "human / conductor discrimination", "tells a hand from a metal object")]
    ys = y0 + 0.32
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, X0 - 0.03, ys + 3 * rh - 0.03, W + 0.06, 2 * rh, BEYOND_BG, None)
    text(s, X0 + W - 1.2, ys + 3 * rh - 0.01, 1.18, 0.18, "beyond human", 7, "B7950B", True, PP_ALIGN.RIGHT, italic=True)
    for i, (img, note, m, m2, pics, col, use, desc) in enumerate(rows):
        y = ys + i * rh
        if img == "poisson.png":
            field(s, X0 + 0.12, y + 0.17, 0.5, 0.17)
            place(s, SV / img, X0 + 0.12, y + 0.17, w=0.5)
            text(s, X0 + 0.75, y + 0.06, 1.0, 0.2, "human: —", 7, MUTED)
            text(s, X0 + 0.75, y + 0.24, 1.0, 0.4, note, 6.5, MUTED, italic=True)
        else:
            im = Image.open(SV / img)
            if im.width / im.height > 1.1:                                   # 넓은 그림 (팔 · 피부) 은 폭 0.66 에 맞춤
                place(s, SV / img, X0 + 0.05, y + (0.25 if img == "Bras.png" else 0.1), w=0.66)
            else:
                place(s, SV / img, X0 + 0.1, y + 0.06, h=0.56)
            text(s, X0 + 0.75, y + 0.22, 1.0, 0.3, note, 7, MUTED, italic=True)
        mx = X0 + cols[0][1]
        text(s, mx, y + 0.12, cols[1][1], 0.45, [[(m, {"bold": True})], [(m2, {"color": MUTED, "size": 6.5})]], 8, INK, align=PP_ALIGN.CENTER)
        wx = mx + cols[1][1] + 0.05
        for q in pics:                                                        # 렌더 (시뮬레이션 그림) — 높이 0.6 에 맞춤
            wx = sum(place(s, q, wx, y + 0.05, h=0.6)[::2]) + 0.04
        text(s, wx, y + 0.1, X0 + W - wx, 0.5, [[("→ " + use, {"bold": True, "color": col, "size": 7.5})], [(desc, {"color": MUTED, "size": 7})]], 7.5)
        if i < len(rows) - 1:
            line(s, [(X0, y + rh), (X0 + W, y + rh)], "DDDDDD", 0.5)
    text(s, X0, ys + 5 * rh + 0.04, W, 0.3, "All five modalities from one two-wire soft electrode, every 1 ms", 7.5, INK, align=PP_ALIGN.CENTER)


# ---------------- b 공통: 신경계 인체 (Servier Systeme_nerveux, 앞모습) ----------------
BODY_H = 900                       # 머리 – 허벅지까지 자름 [px]
PX = dict(brain=(255, 45), cerebellum=(222, 105), spine=(248, 350), arm=(410, 330), nerve=(432, 540), hand=(462, 705))
# 화면 오른쪽 팔: 손 → 아래팔 → 위팔 → 어깨 → 상완신경총 → 척수 → 뇌간 (그림 속 신경을 따라감)
ROUTE = [(455, 700), (440, 640), (430, 540), (420, 450), (400, 330), (370, 230), (300, 200), (250, 190), (247, 130), (250, 98)]


def human(s, x0, y0, h):
    """신경계 인체. 반환: 픽셀 → 인치 함수."""
    place(s, CROP / "body.png", x0, y0, h=h, trim=False)                     # 픽셀 좌표 그대로 (PX 와 맞춤)
    k = h / BODY_H
    return lambda px, py: (x0 + px * k, y0 + py * k)


def nerve_path(s, f, d=0.0, color=AFF, head_up=True):
    """손 → 말초신경 → 척수 → 뇌 (구심) 또는 반대 (원심). d = 신경에서 비켜 그리는 거리 [in]."""
    pts = [(x + d, y + d * 0.6) for x, y in (f(*q) for q in ROUTE)]
    line(s, pts if head_up else pts[::-1], color, 1.3, head=True)


def box(s, x, y, w, h, title_, sub, body, img=None, img_w=0.62):
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, WORK_BG, None)
    tx = x + 0.06
    if img:
        b = place(s, img, x + 0.05, y + 0.08, w=img_w)
        tx = x + b[2] + 0.1
    text(s, tx, y + 0.04, x + w - tx - 0.04, 0.22, [[(title_, {"bold": True, "size": 8.5})]])
    text(s, tx, y + 0.27, x + w - tx - 0.04, 0.2, sub, 7, "8E5A2B", italic=True)
    text(s, tx, y + 0.45, x + w - tx - 0.04, h - 0.47, body, 7, MUTED)


# ---------------- b 1안: 인체 위에 ----------------
def panel_b1(s):
    panel_label(s, 6.0, 0.2, "b", "A nervous-system-like hierarchy on one body (option 1)")
    f = human(s, 8.3, 1.05, 5.2)
    nerve_path(s, f, -0.05, AFF, True); nerve_path(s, f, 0.05, EFF, False)
    text(s, *f(180, 910), 1.4, 0.2, [[("▲ afferent  ", {"color": AFF, "bold": True}), ("▼ efferent", {"color": EFF, "bold": True})]], 7)
    left = [("brain", 0.95, "Cerebrum → upper controller", "PC", "material recognition, grasp state machine, references (d, v, F_ref)", None),
            ("cerebellum", 2.1, "Cerebellum → inner loop", "MCU, 100 Hz", "Kalman-LQG prediction + RLS adaptive gain schedule", CROP / "pcb.png"),
            ("spine", 3.3, "Spinal cord → edge layer", "MCU, 1 kHz", "TDM sensing, Edge-AI decoupling (Gate-MoE), safety reflex: vent when force > F_max",
             CROP / "pcb.png")]
    right = [("arm", 2.5, "Muscle → actuator", "PneuNet + ITV", "chamber pressure bends the soft finger", A / "gripper.png"),
             ("nerve", 3.75, "Nerve → two-wire lead", "single electrode", "L, R_DC, V_TENG share two wires, separated in time (TDM)", None),
             ("hand", 5.05, "Skin → soft sensor", "EGaIn spiral", "strain, force, contact + proximity, material", A / "sensor_cube.png")]
    for key, y, t, sub, body, img in left:
        box(s, 5.95, y, 2.3, 1.02, t, sub, body, img)
        leader(s, f(*PX[key]), (8.25, y + 0.5))
    for key, y, t, sub, body, img in right:
        box(s, 11.2, y, 2.05, 1.1, t, sub, body, img)
        leader(s, f(*PX[key]), (11.2, y + 0.55))
    # 척수 반사 고리: 팔 (구심) → 척수 → 팔 (원심), 뇌를 거치지 않음
    line(s, [f(372, 262), f(310, 250), f(256, 240)], AFF, 1.0, head=True, dash=True)
    line(s, [f(256, 222), f(320, 222), f(385, 246)], EFF, 1.0, head=True, dash=True)
    p = f(335, 150)                                                         # 오른쪽 어깨 위 빈 곳
    text(s, p[0], p[1], 1.1, 0.4, ["spinal reflex ≈", "1 kHz safety reflex"], 7, EFF, True, PP_ALIGN.LEFT, italic=True)


# ---------------- b 2안: 사람 ↔ 그리퍼 대칭 ----------------
def panel_b2(s):
    panel_label(s, 6.0, 0.2, "b", "Human and soft gripper, part by part (option 2)")
    tag(s, 6.15, 0.62, 0.7, "Human", "F2C9AE"); tag(s, 12.25, 0.62, 0.85, "This work", "C9DAEC")
    f = human(s, 6.1, 1.0, 4.7)
    nerve_path(s, f, -0.04, AFF, True); nerve_path(s, f, 0.04, EFF, False)
    # 오른쪽: PC → MCU 보드 → 그리퍼 (위에서 아래, 사람의 뇌 → 척수 → 팔과 같은 순서)
    shape(s, MSO_SHAPE.RECTANGLE, 12.0, 1.0, 0.75, 0.5, "D6EAF8", "34495E", 0.75)
    shape(s, MSO_SHAPE.TRAPEZOID, 12.25, 1.5, 0.25, 0.1, "34495E", None)
    pcb = place(s, CROP / "pcb.png", 11.85, 1.85, w=1.05)
    g = place(s, A / "gripper.png", 11.4, 3.6, w=1.85)
    line(s, [(12.37, 1.62), (12.37, 1.85)], "34495E", 1.0)                   # PC – 보드 (UART)
    line(s, [at(pcb, 0.5, 1.0), at(g, 0.5, 0.2)], "B07A2A", 1.0)            # 보드 – 센서 리드
    pairs = [("brain", (12.0, 1.25), "Cerebrum", "perception, decision", "Upper controller (PC)", "material, state machine, references"),
             ("cerebellum", at(pcb, 0.1, 0.35), "Cerebellum", "coordination, prediction", "Inner loop (MCU, 100 Hz)", "Kalman-LQG + RLS"),
             ("spine", at(pcb, 0.1, 0.7), "Spinal cord", "relay, spinal reflex", "Edge layer (MCU, 1 kHz)", "TDM, Edge-AI, safety reflex"),
             ("arm", at(g, 0.08, 0.48), "Muscle", "contraction", "Pneumatic chambers", "PneuNet + ITV"),
             ("nerve", at(g, 0.745, 0.42), "Sensory nerve", "afferent fibres", "Two-wire lead", "TDM single electrode"),
             ("hand", at(g, 0.66, 0.7), "Skin receptors", "touch, stretch", "Soft sensor", "L, R_DC, V_TENG")]
    ys = [1.05, 2.0, 2.85, 4.0, 4.95, 5.9]
    for (key, q, hn, hf, wn, wf), y in zip(pairs, ys):
        text(s, 8.8, y, 1.0, 0.45, [[(hn, {"bold": True})], [(hf, {"color": MUTED, "size": 6.5})]], 8, INK, align=PP_ALIGN.RIGHT)
        text(s, 9.81, y + 0.05, 0.22, 0.3, "≈", 12, MUTED, align=PP_ALIGN.CENTER)
        text(s, 10.05, y, 1.32, 0.45, [[(wn, {"bold": True})], [(wf, {"color": MUTED, "size": 6.5})]], 8, INK)
        leader(s, f(*PX[key]), (8.8, y + 0.16))
        leader(s, q, (11.3, y + 0.16))
    text(s, 6.6, 5.8, 4.0, 0.2, [[("▲ afferent  ", {"color": AFF, "bold": True}), ("▼ efferent", {"color": EFF, "bold": True})]], 7)


def footer(s):
    text(s, 0.25, 7.18, 12.9, 0.26, "Sensor and signals: measured. Control layers: simulation (MuJoCo). Sensor block and gripper: renders, not to scale. "
         "Human illustrations adapted from Servier Medical Art (CC BY 4.0).", 7, MUTED, italic=True)


def main():
    prep()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for pb in (panel_b1, panel_b2):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        panel_a(s); pb(s); footer(s)
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print(main())
