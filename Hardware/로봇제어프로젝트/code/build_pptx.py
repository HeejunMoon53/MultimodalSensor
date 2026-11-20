"""제출용 PPT 생성 (편집 가능): 블록도·표는 PPT 도형, 값은 params.json, 미정·가정값은 노란 칸.

실행: C:/ml_env/Scripts/python.exe Hardware/로봇제어프로젝트/code/build_pptx.py
"""
import csv
import re
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

import paths  # noqa: F401
from paths import OUT, PROJECT, ROOT, load_params
from slides_text import LECTURE_MAP, LIMITS, REAL_PLAN, THEORY

YELLOW = "FFF2CC"
FONT = "맑은 고딕"
INK, MUTED, ACCENT = RGBColor(0x22, 0x22, 0x22), RGBColor(0x66, 0x66, 0x66), RGBColor(0x2B, 0x6C, 0xB0)
CAD = ROOT / "Hardware" / "pneunet_gripper" / "out"


# ---------------- 기본 도구 ----------------
def get(P, path):
    cur = P
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def fmt(v, nd=4):
    if v is None:
        return None
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}g}"
    if isinstance(v, (list, tuple)):
        flat = []
        for x in v:
            flat += x if isinstance(x, (list, tuple)) else [x]
        return "[" + ", ".join(f"{x:.{nd}g}" if isinstance(x, (int, float)) else str(x) for x in flat) + "]"
    return str(v)


def _run(p, text, size, bold=False, color=INK, font=FONT):
    r = p.add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
    r.font.color.rgb = color
    return r


def text(slide, x, y, w, h, lines, size=14, bold=False, color=INK, font=FONT, bullet=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, ln in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        _run(p, ("• " if bullet else "") + ln, size, bold, color, font)
        p.space_after = Pt(4)
    return tb


def title(slide, t, sim=False):
    text(slide, 0.5, 0.3, 12.3, 0.7, t + ("  (시뮬레이션)" if sim else ""), 26, True)
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.5), Inches(1.0), Inches(12.8), Inches(1.0))
    ln.line.color.rgb, ln.line.width = ACCENT, Pt(1.5)


def box(slide, x, y, w, h, t, fill="FFFFFF", size=12, bold=False, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = RGBColor.from_string(fill)
    s.line.color.rgb, s.line.width = RGBColor(0x44, 0x44, 0x44), Pt(1)
    tf = s.text_frame; tf.word_wrap = True
    for i, ln in enumerate(t.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        _run(p, ln, size, bold)
    return s


def arrow(slide, x1, y1, x2, y2, label=None):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb, c.line.width = RGBColor(0x33, 0x33, 0x33), Pt(1.5)
    ln = c.line._get_or_add_ln()
    ln.append(etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", type="triangle"))
    if label:
        text(slide, (x1 + x2) / 2 - 0.6, (y1 + y2) / 2 - 0.32, 1.2, 0.3, label, 10, color=MUTED)
    return c


def table(slide, x, y, w, rows, widths=None, size=11, row_h=0.32):
    nr, nc = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr)).table
    if widths:
        for j, cw in enumerate(widths):
            gt.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = gt.cell(i, j)
            c.text = "?" if v is None else str(v)
            p = c.text_frame.paragraphs[0]
            for r in p.runs:
                r.font.size, r.font.name, r.font.bold = Pt(size), FONT, (i == 0)
            if v is None or (isinstance(v, str) and v.startswith("(가정)")):
                c.fill.solid(); c.fill.fore_color.rgb = RGBColor.from_string(YELLOW)
                for r in p.runs:
                    r.font.color.rgb = INK
    return gt


def image(slide, path, x, y, w=None, h=None, caption=None):
    path = Path(path)
    if path.exists():
        pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    else:
        pic = box(slide, x, y, w or 4, h or 3, f"그림 없음\n{path.name}\n(스크립트 실행 후 다시 생성)", YELLOW, 11)
    if caption:
        bottom = Emu(pic.top + pic.height).inches
        text(slide, x, bottom + 0.02, (w or Emu(pic.width).inches), 0.3, caption, 10, color=MUTED)
    return pic


def movie(slide, path, poster, x, y, w, h):
    path = Path(path)
    if not path.exists():
        return box(slide, x, y, w, h, f"영상 없음\n{path.name}", YELLOW, 11)
    return slide.shapes.add_movie(str(path), Inches(x), Inches(y), Inches(w), Inches(h),
                                  poster_frame_image=str(poster) if Path(poster).exists() else None, mime_type="video/mp4")


def gs_text(ph, out):
    if not ph:
        return None
    G = f"{ph['K_p']:.3g}/({ph['tau_v']:.3g}s+1)"
    if out == "eps":
        G = f"{ph['K_p'] * ph['K_f']:.3g}/(({ph['tau_v']:.3g}s+1)({ph['tau_f']:.3g}s+1))" if ph.get("order") == 2 else G + f"·{ph['K_f']:.3g}ω²/(s²+2ζωs+ω²)"
        return G + f"·e^(−{ph['theta_e'] * 1e3:.0f}ms·s)"
    return G + f"·e^(−{ph['theta_p'] * 1e3:.0f}ms·s)"


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return None
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def metrics_rows(rows, keys, labels, nd=3):
    if rows is None:
        return [["제어기", *labels], ["(실험 전)", *[None] * len(labels)]]
    head, body = rows[0], rows[1:]
    idx = [head.index(k) for k in keys]
    return [["조건 / 제어기", *labels]] + [[r[0], *[f"{float(r[i]):.{nd}g}" for i in idx]] for r in body]


# ---------------- 논문 그림형 블록도 도구 ----------------
MATH = "Cambria Math"
LINE = RGBColor(0x2A, 0x2A, 0x2A)
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _rich(p, t, size, color=INK, font=MATH, italic=True):
    """'_x' 또는 '_{abc}' → 아래첨자 run."""
    for part in re.split(r"(_\{[^}]*\}|_\w)", t):
        if not part:
            continue
        sub = part.startswith("_")
        r = _run(p, part.strip("_{}") if sub else part, size, color=color, font=font)
        r.font.italic = italic
        if sub:
            r.font._rPr.set("baseline", "-25000")


def wire(s, pts, head=True, dash=False, w=1.25):
    """직교 배선: 꺾인 점 목록, 화살촉은 마지막 구간에만."""
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(a[0]), Inches(a[1]), Inches(b[0]), Inches(b[1]))
        c.line.color.rgb, c.line.width = LINE, Pt(w)
        if dash:
            c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if head and i == len(pts) - 2:
            etree.SubElement(c.line._get_or_add_ln(), _A + "tailEnd", type="triangle", w="med", len="med")


def dot(s, x, y, r=0.04):
    d = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - r), Inches(y - r), Inches(2 * r), Inches(2 * r))
    d.fill.solid(); d.fill.fore_color.rgb = LINE; d.line.fill.background()


def sig(s, x, y, t, size=11, w=1.2, align=PP_ALIGN.LEFT, color=INK, italic=True, font=MATH):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.26))
    tf = tb.text_frame; tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = align
    _rich(p, t, size, color, font, italic)
    return tb


def blk(s, x, y, w, h, lines, size=10, fill="FFFFFF", edge=LINE, shape=MSO_SHAPE.RECTANGLE, color=INK):
    """블록: '$'로 시작하는 줄은 수식 글꼴(기울임)."""
    b = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = RGBColor.from_string(fill)
    b.line.color.rgb, b.line.width = edge, Pt(1)
    tf = b.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.03); tf.margin_top = tf.margin_bottom = Inches(0.01)
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        m = ln.startswith("$")
        _rich(p, ln.lstrip("$"), size, color, MATH if m else FONT, m)
    return b


def sumj(s, cx, cy, signs, r=0.14):
    """합산점: signs = {'l'|'r'|'t'|'b': '+'/'−'} 입력 방향 옆에 부호."""
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - r), Inches(cy - r), Inches(2 * r), Inches(2 * r))
    c.fill.solid(); c.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    c.line.color.rgb, c.line.width = LINE, Pt(1)
    off = {"l": (-r - 0.17, -r - 0.2), "t": (r - 0.02, -r - 0.2), "b": (r - 0.02, r - 0.06), "r": (r + 0.03, -r - 0.2)}
    for k, sg in signs.items():
        sig(s, cx + off[k][0], cy + off[k][1], sg, 11, 0.2, italic=False)


def panel(s, x, y, w, h, label, fill, edge):
    p = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    p.fill.solid(); p.fill.fore_color.rgb = RGBColor.from_string(fill)
    p.line.color.rgb, p.line.width = RGBColor.from_string(edge), Pt(1.25)
    p.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    sig(s, x + 0.1, y + 0.07, label, 11, w - 0.2, color=RGBColor.from_string(edge), italic=False, font=FONT).text_frame.paragraphs[0].runs[0].font.bold = True


def s_control_fig(s, P):
    """계층형 제어 블록도. 배치 관례: 감독기(상위) | 내부 루프 | 플랜트 3패널 점선 구획,
    DOB는 Q-필터 표준형 d̂ = Q[P_n⁻¹y − u] (Chen et al., IEEE TIE 2016 개관 그림 관례)."""
    Y = 3.85  # 주 신호선 높이
    panel(s, 0.35, 1.2, 3.1, 5.05, "(a) 상위 감독기  [4.2 · 11.8절]", "FFF5EA", "B5762A")
    panel(s, 3.6, 1.2, 6.4, 5.05, "(b) 내부 루프: 적분 LQR + 칼만 + DOB  [과제 4–6절]", "EEF3FA", "3C6AA8")
    panel(s, 10.15, 1.2, 2.85, 5.05, "(c) 플랜트  (시뮬레이션)", "F3F3F3", "6B6B6B")

    # (a) 상태 머신
    for x, w, t in ((0.55, 0.8, "OPEN"), (1.5, 1.0, "APPROACH"), (2.65, 0.7, "GRASP")):
        blk(s, x, 1.7, w, 0.32, [t], 8, "FFFFFF", shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    for x, t in ((0.55, "RELEASE"), (2.65, "SAFETY")):
        blk(s, x, 2.3, 0.8 if t == "RELEASE" else 0.7, 0.32, [t], 8, "FBE3E3" if t == "SAFETY" else "FFFFFF", shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    wire(s, [(1.35, 1.86), (1.5, 1.86)]); wire(s, [(2.5, 1.86), (2.65, 1.86)])
    wire(s, [(2.9, 2.02), (2.9, 2.3)]); wire(s, [(3.1, 2.3), (3.1, 2.02)]); wire(s, [(0.95, 2.3), (0.95, 2.02)])
    sig(s, 1.42, 2.36, "release 명령 → RELEASE", 7, 1.2, color=MUTED, italic=False, font=FONT)
    # (a) 기준 생성 블록 + 상태 선택기
    for yy, ln in ((2.95, ["근접 스케줄 (APPROACH)", "$ε_{ref} = g(d̂)"]),
                   (3.6, ["속도 제한", "$|ε̇_{ref}| ≤ v_{max},  t_c = d̂/(−ḋ̂)"]),
                   (4.25, ["어드미턴스 (GRASP)", "$B_a ε̇_{ref} = F_t − F̂"])):
        blk(s, 0.55, yy, 2.3, 0.5, ln, 9)
        wire(s, [(2.85, yy + 0.25), (3.0, yy + 0.25)])
    blk(s, 3.0, 2.95, 0.22, 1.8, [""], 8, "3A3A3A")
    wire(s, [(3.1, 2.62), (3.1, 2.95)], dash=True)
    blk(s, 0.55, 5.05, 2.67, 0.8, ["재질 m ∈ {도체, 인체, 유전체}", "→ F_t, F_{max}, B_a, v_{max} (가정값)"], 9, YELLOW)
    wire(s, [(1.7, 5.05), (1.7, 4.75)])

    # (b) 내부 루프
    lq, st, dob = get(P, "det.lqr") or {}, get(P, "stoch") or {}, get(P, "dob") or {}
    wire(s, [(3.22, Y), (4.06, Y)]); sig(s, 3.38, Y - 0.3, "ε_{ref}", 11, 0.6)
    dot(s, 3.85, Y)
    sumj(s, 4.2, Y, {"l": "+", "b": "−"})
    wire(s, [(3.85, Y), (3.85, 2.97), (5.0, 2.97)])
    blk(s, 5.0, 2.75, 1.1, 0.45, ["$N_u + K N_x"], 11)
    sig(s, 5.0, 2.5, "기준 피드포워드", 8, 1.1, PP_ALIGN.CENTER, MUTED, False, FONT)
    wire(s, [(6.1, 2.97), (6.45, 2.97), (6.45, Y - 0.14)])
    wire(s, [(4.34, Y), (4.5, Y)]); sig(s, 4.36, Y - 0.27, "e", 10, 0.2)
    blk(s, 4.5, Y - 0.25, 0.6, 0.5, ["$1/(z−1)"], 10)
    wire(s, [(5.1, Y), (5.4, Y)]); sig(s, 5.12, Y - 0.27, "x_I", 10, 0.3)
    blk(s, 5.4, Y - 0.22, 0.55, 0.44, ["$K_I"], 12)
    sig(s, 5.2, Y + 0.25, f"= {fmt(lq.get('KI'), 3)}", 8, 1.0, PP_ALIGN.CENTER, MUTED, False)
    wire(s, [(5.95, Y), (6.31, Y)])
    sumj(s, 6.45, Y, {"t": "+", "l": "−", "b": "−"})
    wire(s, [(6.59, Y), (8.81, Y)]); sig(s, 7.5, Y - 0.27, "u_c", 11, 0.4)
    sumj(s, 8.95, Y, {"l": "+", "b": "−"})
    wire(s, [(9.09, Y), (10.35, Y)]); sig(s, 9.85, Y - 0.27, "u", 11, 0.3)
    dot(s, 9.7, Y); wire(s, [(9.7, Y), (9.7, 4.67), (9.45, 4.67)])
    blk(s, 8.3, 4.4, 1.15, 0.7, ["DOB", "$Q(z)[P_n⁻¹y − u]", f"$τ_q = {fmt(dob.get('tau_q'), 2)} s"], 8)
    wire(s, [(8.95, 4.4), (8.95, Y + 0.14)]); sig(s, 8.68, 4.08, "d̂", 11, 0.3)
    blk(s, 5.4, 4.45, 0.55, 0.44, ["$K"], 12)
    sig(s, 4.3, 4.56, f"= {fmt(lq.get('K'), 3)}", 8, 1.05, PP_ALIGN.RIGHT, MUTED, False)
    wire(s, [(5.95, 4.67), (6.45, 4.67), (6.45, Y + 0.14)])
    blk(s, 6.6, 5.1, 1.4, 0.55, ["칼만 필터", "$x̂ = [p̂, ε̂]"], 9)
    wire(s, [(6.6, 5.37), (5.675, 5.37), (5.675, 4.89)]); sig(s, 5.75, 5.12, "x̂", 11, 0.3)
    wire(s, [(7.3, 4.8), (7.3, 5.1)]); sig(s, 7.12, 4.72, "u", 10, 0.2)
    sig(s, 4.3, 1.55, f"LQR (Bryson) · GM {fmt(lq.get('gm_db'), 3)} dB · PM {fmt(lq.get('pm_deg'), 3)}° · T_s = 10 ms", 8, 5.5, color=MUTED, italic=False)

    # (c) 플랜트
    blk(s, 10.35, Y - 0.3, 0.9, 0.6, ["ITV + 튜브", "지연·데드밴드"], 8)
    wire(s, [(11.25, Y), (11.5, Y)]); sig(s, 11.28, Y - 0.27, "p", 11, 0.2)
    fb = blk(s, 11.5, 2.55, 1.35, 1.9, [""], 8)
    fb.text_frame.vertical_anchor = MSO_ANCHOR.BOTTOM
    _run(fb.text_frame.paragraphs[0], "PneuNet 2지 (PRBM)", 8)
    if (OUT / "model_render.png").exists():  # 15 kPa 가운데 칸만 잘라 삽입
        from PIL import Image
        inset = OUT / "fig_finger_inset.png"
        Image.open(OUT / "model_render.png").crop((830, 80, 1090, 250)).save(inset)
        s.shapes.add_picture(str(inset), Inches(11.56), Inches(2.65), Inches(1.23))
        sig(s, 11.5, 3.5, "MuJoCo, p = 15 kPa", 7, 1.35, PP_ALIGN.CENTER, MUTED, False, FONT)
    wire(s, [(12.6, 1.7), (12.6, 2.55)]); sig(s, 10.95, 1.72, "외란 τ_d (하중·접촉)", 9, 1.6, PP_ALIGN.RIGHT, italic=False)
    blk(s, 11.3, 4.85, 1.55, 0.7, ["센서 (DS30 + EGaIn)", "TDM L·R·V → v4 MoE"], 8, "EAF3E4")
    wire(s, [(12.175, 4.45), (12.175, 4.85)]); sig(s, 12.22, 4.5, "ε, d, F", 9, 0.7)
    # 측정 버스 y = [p, ε̂]
    wire(s, [(11.7, 5.55), (11.7, 5.95), (4.2, 5.95), (4.2, Y + 0.14)]); sig(s, 4.25, 5.35, "ε̂", 11, 0.3)
    wire(s, [(10.8, Y + 0.3), (10.8, 5.95)], head=False); dot(s, 10.8, 5.95); sig(s, 10.85, 5.0, "p", 11, 0.2)
    for x, y2 in ((7.3, 5.65), (8.875, 5.1)):
        dot(s, x, 5.95); wire(s, [(x, 5.95), (x, y2)])
    sig(s, 9.15, 5.98, "y = [p, ε̂]", 10, 1.0)
    # 감독기 버스 d̂, F̂, 접촉
    wire(s, [(12.85, 5.2), (13.15, 5.2), (13.15, 6.6), (0.2, 6.6), (0.2, 1.86), (0.55, 1.86)])
    for yy in (3.2, 3.85, 4.5):
        dot(s, 0.2, yy); wire(s, [(0.2, yy), (0.55, yy)])
    sig(s, 4.0, 6.33, "d̂, ḋ̂, F̂, 접촉 c = gate ∨ TENG", 10, 4.0)
    cap = s.shapes.add_textbox(Inches(0.35), Inches(6.72), Inches(12.65), Inches(0.7)).text_frame
    cap.word_wrap = True
    _rich(cap.paragraphs[0], "그림 5. 계층형 제어 구조. (a) 상태 머신이 근접 스케줄·속도 제한·어드미턴스 중 하나를 골라 ε_{ref}를 만든다 "
          "(GRASP→SAFETY: F̂ > F_{max} 또는 ε > ε_{max}). (b) u = −K(x̂ − N_x ε_{ref}) + N_u ε_{ref} − K_I x_I − d̂, 포화 시 조건부 적분. "
          "(c) 손가락 두 개에 같은 게인. 노란 칸 = 가정값, 수치는 params.json에서 자동 기입.", 10, MUTED, MATH, False)


# ---------------- 슬라이드 ----------------
def s_theory(prs, key):
    T = THEORY[key]
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, T["title"])
    text(s, 0.5, 1.15, 12.3, 0.6, "질문: " + T["q"], 15, True, ACCENT)
    eqb = box(s, 0.5, 1.85, 6.4, 3.9, "", "F5F7FA", 13, shape=MSO_SHAPE.RECTANGLE)
    tf = eqb.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.LEFT
    _run(tf.paragraphs[0], "핵심 식", 13, True, MUTED)
    for ln in T["eq"]:
        p = tf.add_paragraph(); p.alignment = PP_ALIGN.LEFT; p.space_before = Pt(6)
        _run(p, ln, 15, font="Cambria Math")
    text(s, 7.1, 1.85, 5.8, 0.4, "쉬운 설명", 14, True)
    text(s, 7.1, 2.25, 5.8, 2.4, T["easy"], 13, bullet=True)
    text(s, 7.1, 4.55, 5.8, 0.4, "우리 시스템에서", 14, True)
    text(s, 7.1, 4.95, 5.8, 1.6, T["ours"], 12)
    text(s, 0.5, 6.85, 12.3, 0.4, "출처: " + T["src"], 11, color=MUTED)


def build(out_path=PROJECT / "MEC799_Project_PneuNet.pptx", params=None):
    P = load_params() if params is None else params
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]

    # 1 표지
    s = prs.slides.add_slide(blank)
    text(s, 0.8, 2.0, 11.7, 1.2, "PneuNet 2지 소프트 그리퍼의 센서 되먹임 제어", 36, True)
    text(s, 0.8, 3.2, 11.7, 0.8, "단일 전극 멀티모달 센서(인장·근접·힘) 기반 식별 · LQR · LQG · DOB · 상위 어드미턴스", 18, color=MUTED)
    text(s, 0.8, 5.6, 11.7, 0.8, ["[MEC799] Robot Control — Final Project", "문희준 · BioRobotics & Control Lab, 고려대학교 기계공학과"], 14)
    image(s, CAD / "preview_assembly.png", 9.3, 3.9, h=2.2)

    # 2 연구 질문
    s = prs.slides.add_slide(blank); title(s, "연구 질문과 목표")
    text(s, 0.5, 1.2, 12.3, 1.0, "질문: 손가락에 매립한 단일 전극 센서 하나(ε·d·F)만으로 공압 손가락을 정밀하게 되먹임 제어하고, "
         "물체(도체·인체·유전체)에 따라 안전하게 쥘 수 있는가?", 16, True, ACCENT)
    table(s, 0.5, 2.4, 12.3, [["목표", "지표", "목표값"],
                              ["ε 추종", "검증 적합도 / 추종 RMSE", "fit ≥ 80 % / 개루프 대비 RMSE 감소"],
                              ["과도 응답", "오버슈트 · 정착시간(2 %)", "(가정) ≤ 10 % · ≤ 1 s"],
                              ["강건성", "섭동 시 RMSE (DOB 유무)", "DOB로 RMSE 감소"],
                              ["안전 파지", "접촉 힘 최댓값", "재질별 F_max 이하 (인체 최우선)"]], [2.5, 4.8, 5.0], 14, 0.45)
    text(s, 0.5, 5.0, 12.3, 1.5, ["A단계(지금): MuJoCo 유한요소 손가락 + ITV·센서 비이상성 = 실제 플랜트로 간주",
                                  "B단계(실물 수정 후): 실물 센서 L·R·V 디커플링 후 같은 스크립트로 실측 재계산"], 14, bullet=True)

    # 3 시스템
    s = prs.slides.add_slide(blank); title(s, "시스템: 2지 PneuNet + 바닥층 센서 + ITV 공압")
    image(s, CAD / "preview_finger.png", 0.5, 1.2, h=2.6, caption="손가락 CAD (105 × 30 mm, 공기 방 9개, DS30)")
    image(s, OUT / "model_render.png", 0.5, 4.2, w=5.3, caption="MuJoCo 2지 모델: 0 / 15 / 30 kPa (빨간 = 부푼 방, 시뮬레이션)")
    table(s, 6.0, 1.2, 6.8, [["신호", "측정", "역할"],
                              ["u 압력 지령", "–", "입력 (손가락당 1)"],
                              ["p 압력", "ITV 모니터", "출력 y₁, 상태"],
                              ["ε 변형률", "센서 MoE ε̂", "출력 y₂, 추종 대상"],
                              ["ε̇", "관측기·칼만 추정", "상태, 속도 제한"],
                              ["d, ḋ 근접", "MoE d̂ + 칼만", "상위: pre-shape·속도"],
                              ["F 접촉 힘", "MoE F̂", "상위: 어드미턴스"],
                              ["재질", "A: 정답 / B: 판별기", "도체·인체·유전체"]], [1.8, 2.3, 2.7], 12)
    text(s, 6.0, 4.6, 6.8, 2.2, ["비이상성: ITV 지연·데드밴드 0.3 kPa·1 kPa 계단·포화 30 kPa, 센서 TDM 잡음, MoE 추정 오차, "
                                 "Python 루프 10 ms, 방 부풂에 따른 공압 용량 변화, 하중·접촉 외란"], 12)

    # 4 플랜트 모델
    s = prs.slides.add_slide(blank); title(s, "플랜트 모델: 방이 부푸는 유한요소 손가락", True)
    image(s, OUT / "S0_calib.png", 0.5, 1.15, w=8.2, caption="S0: flex 손가락 보정 시도 (비단조 → PRBM 대체)")
    for i, (t, c) in enumerate([("ITV\n1차+지연+데드밴드\n+1 kPa 계단", "E8F0FB"), ("튜브·방\nC(p)ṗ_c = (p − p_c)/R_t", "E8F0FB"),
                                ("flex 손가락\n방 내벽에 p·A·n", "FDEBD0"), ("센서·MoE\nε̂, d̂, F̂", "E2F0D9")]):
        box(s, 0.5 + i * 2.15, 5.4, 1.9, 1.1, t, c, 11)
        if i:
            arrow(s, 0.5 + i * 2.15 - 0.25, 5.95, 0.5 + i * 2.15, 5.95)
    pl = get(P, "plant") or {}
    fx = pl.get("flex_S0", {})
    from finger_prbm import PrbmFinger
    fp = PrbmFinger()
    table(s, 9.0, 1.15, 3.9, [["항목", "값"], ["사용 모델", fmt(pl.get("model"))],
                              ["관절 강성 k [N·m/rad]", fmt(fp.k, 3)], ["압력 이득 α [N·m/kPa]", fmt(fp.alpha, 3)],
                              ["굽힘 감소 β", fmt(fp.beta, 3)], ["센서 중립축 거리 h [mm]", fmt(fp.h, 3)],
                              ["flex S0 young [kPa]", fmt(fx.get("young_pa") and fx["young_pa"] / 1e3, 3)],
                              ["flex 벽시계/시뮬 [배]", fmt(fx.get("wall_per_sim_s"), 3)]], [2.4, 1.5], 10)
    text(s, 9.0, 4.0, 3.9, 2.6, ["S0: flex(사면체 FEM, 방 내벽 압력)는 young 에 대해 굽힘이 비단조(좌굴) → 스펙 대체안 PRBM 채택",
                                 "보정: 30 kPa → 끝단 300° (사용자 예비 시험), ε(30 kPa) ≈ 12 %",
                                 "방 부풂 V(p): self-collision flex(체적 ×2) → 공압 용량 C = dV/dp + V/(κ p_abs), 화면의 빨간 방 크기"], 10, bullet=True)

    # 5 제어 블록도 (논문 그림 형식, 편집 가능한 도형)
    s = prs.slides.add_slide(blank); title(s, "제어 구조: 계층형 감독기 + 내부 루프 (과제 2–6절)")
    s_control_fig(s, P)

    # 6 과제 ↔ 강의 대응표
    s = prs.slides.add_slide(blank); title(s, "과제 절 ↔ 강의 대응")
    table(s, 0.5, 1.2, 12.3, [["과제 절", "할 일", "강의 (파일·쪽)", "스크립트"], *LECTURE_MAP], [1.8, 4.6, 4.1, 1.8], 12, 0.6)

    # 7–8 식별
    s_theory(prs, "sysid")
    s = prs.slides.add_slide(blank); title(s, "식별 결과", True)
    image(s, OUT / "sysid_S1_S3.png", 0.4, 1.15, w=12.5)
    Ge, Gp = get(P, "sysid.G_eps") or {}, get(P, "sysid.G_p") or {}
    table(s, 0.5, 5.2, 12.3, [["모델", "차수 (na, nb, nk)", "검증 fit [%]", "G(s) 분모 계수"],
                              ["u → ε", fmt(Ge and [Ge["na"], Ge["nb"], Ge["nk"]]),
                               fmt(Ge and [Ge["fit_val_pct"], Ge.get("fit_true_pct")], 3), gs_text(get(P, "model.phys"), "eps")],
                              ["u → p", fmt(Gp and [Gp["na"], Gp["nb"], Gp["nk"]]), fmt(Gp.get("fit_val_pct"), 3), gs_text(get(P, "model.phys"), "p")]],
          [1.6, 2.0, 2.6, 6.1], 12)
    text(s, 0.5, 6.35, 12.3, 0.8, "fit 두 값 = [측정 ε̂ 기준, 정답 ε 기준]. 측정 기준이 80 % 목표에 못 미친 것은 MoE 잡음(σ ≈ 0.4 %) 한계 — 가진 ±3 → ±5 kPa, 비트 0.05 → 0.25 s 로 키워 18.7 → 65.8 % 로 개선 (과정 그대로 보고).", 11, color=MUTED)

    # 9–10 상태공간
    s_theory(prs, "ss")
    s = prs.slides.add_slide(blank); title(s, "상태공간 해석 결과", True)
    image(s, OUT / "analysis_poles_obsv.png", 0.4, 1.15, w=8.0)
    M = get(P, "model") or {}
    ph = M.get("phys", {})
    table(s, 8.7, 1.15, 4.2, [["항목", "값"], ["상태 수 n", fmt(M.get("n"))], ["τ_v [s]", fmt(ph.get("tau_v"))], ["K_p", fmt(ph.get("K_p"))],
                              ["K_f [%/kPa]", fmt(ph.get("K_f"))], ["τ_f [s]", fmt(ph.get("tau_f"))], ["지연 θ_p / θ_ε [s]", fmt(ph and [ph.get("theta_p"), ph.get("theta_e")], 3)],
                              ["|eig(A_d)|", fmt(M.get("eig_d_abs"), 3)],
                              ["Lyapunov P > 0", fmt(M.get("lyap_pd"))], ["rank 𝒞", fmt(M.get("rank_ctrb"))],
                              ["rank 𝒪 (p / ε / 둘)", fmt(M.get("rank_obsv") and list(M["rank_obsv"].values()))]], [2.2, 2.0], 11)
    text(s, 0.5, 5.6, 12.3, 1.2, ["압력만 측정하면 손가락 상태가 보이지 않는다(랭크 1). 센서 ε를 쓰면 전 랭크(가관측). 손가락은 과감쇠라 2상태 x = [p, ε] 로 줄였다 (3차 피팅은 ζ 가 상한에 걸림).",
                                  "→ 굽힘 되먹임에는 손가락에 매립한 센서가 필요하다는 것을 제어 이론으로 보였다."], 14, True, ACCENT)

    # 11–13 결정론적
    s_theory(prs, "pp")
    s_theory(prs, "lqr")
    s = prs.slides.add_slide(blank); title(s, "결정론적 제어 비교 (S5)", True)
    image(s, OUT / "S5_timeseries.png", 0.4, 1.1, w=6.6)
    image(s, OUT / "S5_metrics.png", 7.1, 1.1, w=5.9)
    rows = metrics_rows(read_csv(OUT / "S5_metrics.csv"), ["rmse", "rmse_improve_pct", "overshoot_pct", "settle_s", "sum_du"],
                        ["RMSE [%]", "개선율 [%]", "오버슈트 [%]", "정착 [s]", "Σ|Δu|"])
    table(s, 7.1, 3.9, 5.9, rows, [1.9, 0.8, 0.8, 0.8, 0.8, 0.8], 9, 0.27)

    # 14–15 칼만·LQG
    s_theory(prs, "kf")
    s = prs.slides.add_slide(blank); title(s, "칼만·LQG 결과", True)
    image(s, OUT / "S5_timeseries.png", 0.4, 1.1, w=7.0, caption="아래 그래프: ε̇ 추정 (관측기 vs 칼만 vs 정답)")
    rows = metrics_rows(read_csv(OUT / "S5_metrics.csv"), ["est_rmse_epsdot", "rmse", "sum_du"], ["ε̇ 추정 RMSE", "추종 RMSE", "Σ|Δu|"])
    table(s, 7.6, 1.1, 5.3, rows, [2.3, 1.0, 1.0, 1.0], 10, 0.3)
    st = get(P, "stoch") or {}
    table(s, 7.6, 4.6, 5.3, [["공분산", "값"], ["V (측정) [p, ε]", fmt(st.get("V"))], ["W (공정)", fmt(st.get("W"))],
                             ["Kf (정상상태)", fmt(st.get("Kf"), 3)]], [2.0, 3.3], 10)

    # 16–17 DOB
    s_theory(prs, "dob")
    s = prs.slides.add_slide(blank); title(s, "DOB 강건성 비교 (S6)", True)
    image(s, OUT / "S6_dob.png", 0.4, 1.1, w=6.4)
    image(s, OUT / "S6_load_step.png", 6.9, 1.1, w=6.0)
    s6 = read_csv(OUT / "S6_metrics.csv")
    rows = [["섭동", "개루프 FF RMSE", "LQG RMSE", "LQG+DOB RMSE", "LQG 개선 (FF 대비)", "DOB 효과 (LQG 대비)"]]
    if s6:
        h = s6[0]; d6 = {r[0]: dict(zip(h[1:], map(float, r[1:]))) for r in s6[1:]}
        for pn in dict.fromkeys(k.split(" | ")[0] for k in d6):
            f, l, b_ = d6[f"{pn} | FF"], d6[f"{pn} | 없음"], d6[f"{pn} | DOB"]
            rows.append([pn, f"{f['rmse']:.3f}", f"{l['rmse']:.3f}", f"{b_['rmse']:.3f}",
                         f"{l['rmse_improve_pct']:+.0f} %", f"{b_['dob_vs_lqg_pct']:+.0f} %"])
    else:
        rows.append(["(실험 전)", None, None, None, None, None])
    table(s, 0.5, 4.55, 12.3, rows, [2.6, 1.9, 1.9, 1.9, 2.0, 2.0], 10, 0.3)

    # 18 상위 루프
    s = prs.slides.add_slide(blank); title(s, "상위 루프: 근접 · 속도 · 어드미턴스 · 재질")
    text(s, 0.5, 1.15, 6.3, 4.0, ["근접 스케줄: ε_ref = ε_open + (ε_pre − ε_open)·sat((d_far − d̂)/(d_far − d_near))",
                                  "접촉 예상 시간 t_c = d̂/(−ḋ̂) → ε̇_ref = (g(d̂) − ε)/max(t_c, t_min), |ε̇_ref| ≤ v_max",
                                  "어드미턴스: B_a·ε̇_ref = F_t − F̂ (데드존 δF)",
                                  "B_a = 4·τ_in·k_env → 힘 루프가 내부 루프보다 4배 느림 (캐스케이드 분리)",
                                  "게이트 접촉 3 샘플 연속일 때만 GRASP (잡음 방지)",
                                  "SAFETY: F̂ > F_max 또는 ε > ε_max → 즉시 풀기, 인체는 dF/dt 상한"], 13, bullet=True)
    ct = get(P, "contact") or {}
    from supervisor import MATERIAL
    rows = [["재질", "F_t (×F_block)", "F_max", "B_a 배수", "v_max 배수", "F_block [N]", "k_env [N/%]"]]
    for m, lab in (("conductor", "도체"), ("dielectric", "유전체"), ("human", "인체")):
        c = ct.get(m, {})
        rows.append([lab, *[f"(가정) {MATERIAL[m][k]}" for k in ("Ft", "Fmax", "Ba", "v")], fmt(c.get("F_block"), 3), fmt(c.get("k_env"), 3)])
    table(s, 7.0, 1.2, 5.9, rows, [0.9, 0.95, 0.8, 0.8, 0.85, 0.8, 0.8], 10, 0.4)
    text(s, 7.0, 3.0, 5.9, 2.0, ["속도를 넣는 이유: 닿는 순간 속도 = 충격력. 사람 손은 움직인다(ḋ). "
                                 "pre-grasp는 t_c 안에 모양을 맞춰야 물체를 밀지 않는다."], 12)

    # 19 파지 시연
    s = prs.slides.add_slide(blank); title(s, "파지 시연 (S7): 근접 → 접촉 → 어드미턴스 → 해제", True)
    cases = (("conductor", "도체"), ("dielectric_gate_only", "유전체 · 게이트만"), ("dielectric", "유전체 · 게이트 ∨ TENG"),
             ("human", "인체 (움직이는 손)"))
    for i, (m, lab) in enumerate(cases):
        movie(s, OUT / f"S7_{m}.mp4", OUT / f"S7_{m}_snap.png", 0.4 + i * 3.15, 1.15, 3.0, 2.25)
        text(s, 0.4 + i * 3.15, 3.42, 3.0, 0.3, lab, 12, True)
    r7 = get(P, "results_s7") or {}
    rows = [["경우", "목표 F_t [N]", "유지 F [N]", "파지 중 최대 F [N]", "접근 중 최대 F [N]", "F_max [N]", "F_max 초과"]]
    for m, lab in cases:
        v = r7.get(m, {})
        rows.append([lab, fmt(v.get("F_target"), 3), fmt(v.get("F_hold"), 3), fmt(v.get("F_peak"), 3),
                     fmt(v.get("F_peak_approach"), 3), fmt(v.get("F_max"), 3), fmt(v.get("exceeded"))])
    table(s, 0.5, 3.85, 12.3, rows, [2.7, 1.5, 1.5, 1.75, 1.75, 1.5, 1.6], 11, 0.36)
    text(s, 0.5, 5.8, 12.3, 1.4, ["유전체: v4 게이트는 도체 압자로만 학습 → 접촉을 놓쳐 계속 닫음(F_max 초과). TENG 래치를 더하면 접촉을 잡고 힘을 유지 → TENG 모달리티의 필요성",
                                  "인체: 파지 중 힘은 F_max 이하. 접근 중 최대 힘은 움직이는 손이 손가락에 부딪힌 충돌 (굽힘만으로 회피 불가 — 한계)"], 12, bullet=True)

    # 20 게인 표
    s = prs.slides.add_slide(blank); title(s, "게인 표 (params.json에서 자동 생성)", True)
    d = lambda k, nd=4: fmt(get(P, k), nd)
    table(s, 0.5, 1.15, 12.3, [["설계", "기호", "값", "근거"],
                               ["극배치", "K", d("det.pp.K"), "ζ = 0.8, ω_n = 1.5·|λ_dom|, 나머지 3배"],
                               ["극배치", "K_I", d("det.pp.KI"), "적분 확장 (Lec8_1 p58–65)"],
                               ["관측기", "L", d("det.obs.L", 3), "제어기 극 × 2 빠르게 (ε̂ 잡음)"],
                               ["LQR", "Q 대각 / R", fmt(get(P, "det.lqr.Q") and [*get(P, "det.lqr.Q"), get(P, "det.lqr.R")], 3), "Bryson: δp 15, δε 2 %, x_I 50, δu 15 kPa"],
                               ["LQR", "K", d("det.lqr.K"), "DARE"],
                               ["LQR", "K_I", d("det.lqr.KI"), "DARE (확대계)"],
                               ["LQR", "GM [dB] / PM [°]", fmt(get(P, "det.lqr.gm_db") and [get(P, "det.lqr.gm_db"), get(P, "det.lqr.pm_deg")], 3), "단위원 위 L(z)"],
                               ["칼만", "Kf", d("stoch.Kf", 3), "쌍대 DARE, V = S4"],
                               ["DOB", "τ_q [s] / r", fmt(get(P, "dob.tau_q") and [get(P, "dob.tau_q"), get(P, "dob.r")], 3), "강건 조건 |QΔ| < 1"],
                               ["상위", "v₀ [%/s]", "(가정) " + str(get(P, "det.v0")) if get(P, "det.v0") is not None else None, "가정값"]],
          [1.6, 2.2, 5.6, 2.9], 11, 0.42)

    # 21 실물 측정 계획
    s = prs.slides.add_slide(blank); title(s, "B단계: 실물 측정 계획 (물리량 → 바뀌는 값)")
    table(s, 0.5, 1.2, 12.3, [["ID", "실험", "측정 물리량", "바뀌는 값"], *REAL_PLAN], [0.8, 5.0, 3.6, 2.9], 12, 0.5)

    # 22 한계
    s = prs.slides.add_slide(blank); title(s, "한계와 다음 실험")
    text(s, 0.5, 1.2, 12.3, 5.8, LIMITS, 15, bullet=True)

    out_path = Path(out_path)
    prs.save(out_path)
    return out_path


if __name__ == "__main__":
    print(build())
