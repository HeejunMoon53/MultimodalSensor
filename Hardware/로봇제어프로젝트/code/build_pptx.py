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


def table(slide, x, y, w, rows, widths=None, size=11, row_h=0.32, font=FONT):
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
                r.font.size, r.font.name, r.font.bold = Pt(size), font, (i == 0)
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
    panel(s, 0.35, 1.2, 3.1, 5.05, "(a) 상위 · PC 20 Hz  [4.2 · 11.8절]", "FFF5EA", "B5762A")
    panel(s, 3.6, 1.2, 6.4, 5.05, "(b) 하위 · STM32 + TDM: 내부 루프 100 Hz (자유 ε / 접촉 F) + 반사 1 kHz  [4–6절]", "EEF3FA", "3C6AA8")
    panel(s, 10.15, 1.2, 2.85, 5.05, "(c) 플랜트  (시뮬레이션)", "F3F3F3", "6B6B6B")

    # (a) 상위 감독기: 상태 머신 하나가 상태별로 기준 하나를 고른다 (전이 조건은 다음 장)
    blk(s, 0.55, 1.6, 2.67, 3.15, [""], 8)
    sig(s, 0.6, 1.63, "상태 머신 → 기준 하나 선택", 9, 2.6, PP_ALIGN.CENTER, INK, False, FONT)
    for k, (st, law) in enumerate((("OPEN", "u = 0 (배기)"), ("APPROACH", "$ε_{ref} = g(d̂),  속도 ≤ (g − ε)/t_c"),
                                   ("GRASP", "$F_{ref}: F̂ → F_t  (경사)"), ("SAFETY", "u = 0 (배기)"), ("RELEASE", "$ε_{ref} → 0"))):
        yy = 2.0 + k * 0.5
        blk(s, 0.62, yy, 0.86, 0.3, [st], 7, STATE_FILL.get(st, "FFFFFF"), shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        m = law.startswith("$")
        sig(s, 1.52, yy + 0.04, law.lstrip("$"), 7.5, 1.68, italic=m, font=MATH if m else FONT)
    sig(s, 0.6, 4.48, "전이 조건 · 파라미터: 다음 장", 7, 2.6, PP_ALIGN.CENTER, MUTED, False, FONT)
    blk(s, 0.55, 5.05, 2.67, 0.8, ["재질 m (시뮬: 정답 라벨)", "→ F_t, F_{max}, v_{max} (가정값)"], 9, YELLOW)
    wire(s, [(1.7, 5.05), (1.7, 4.75)])

    # (b) 내부 루프
    lq, st, dob = get(P, "det.lqr") or {}, get(P, "stoch") or {}, get(P, "dob") or {}
    wire(s, [(3.22, Y), (4.06, Y)]); sig(s, 3.27, Y - 0.3, "ε_{ref} | F_{ref}", 9, 0.6)
    sig(s, 3.24, Y + 0.12, "UART τ_c", 7, 0.7, color=MUTED, italic=False)
    # 하위 반사 안전: 측정 버스 F̂ (1 kHz) → u 차단 (점선)
    blk(s, 9.05, 5.2, 0.9, 0.5, ["반사 1 kHz", "$F̂ > F_{max} → u = 0"], 7, "FBE3E3")
    dot(s, 9.5, 5.95); wire(s, [(9.5, 5.95), (9.5, 5.7)])
    wire(s, [(9.85, 5.2), (9.85, Y + 0.03)], dash=True)
    dot(s, 3.85, Y)
    sumj(s, 4.2, Y, {"l": "+", "b": "−"})
    wire(s, [(3.85, Y), (3.85, 2.97), (5.0, 2.97)])
    blk(s, 5.0, 2.75, 1.1, 0.45, ["$N_u + K N_x"], 11)
    sig(s, 5.0, 2.5, "기준 피드포워드", 8, 1.1, PP_ALIGN.CENTER, MUTED, False, FONT)
    wire(s, [(6.1, 2.97), (6.45, 2.97), (6.45, Y - 0.14)])
    wire(s, [(4.34, Y), (4.5, Y)]); sig(s, 4.36, Y - 0.27, "e", 10, 0.2)
    blk(s, 4.5, Y - 0.25, 0.6, 0.5, ["$1/(z−1)"], 10)
    wire(s, [(5.1, Y), (5.4, Y)]); sig(s, 5.12, Y - 0.27, "x_I", 10, 0.3)
    blk(s, 5.4, Y - 0.22, 0.55, 0.44, ["$K_I(k̂)"], 10)
    sig(s, 5.0, Y + 0.25, f"자유: {fmt(lq.get('KI'), 3)}", 7, 1.0, PP_ALIGN.CENTER, MUTED, False)
    wire(s, [(5.95, Y), (6.31, Y)])
    sumj(s, 6.45, Y, {"t": "+", "l": "−", "b": "−"})
    wire(s, [(6.59, Y), (8.81, Y)]); sig(s, 7.5, Y - 0.27, "u_c", 11, 0.4)
    sumj(s, 8.95, Y, {"l": "+", "b": "−"})
    wire(s, [(9.09, Y), (10.35, Y)]); sig(s, 9.85, Y - 0.27, "u", 11, 0.3)
    dot(s, 9.7, Y); wire(s, [(9.7, Y), (9.7, 4.67), (9.45, 4.67)])
    blk(s, 8.3, 4.4, 1.15, 0.7, ["DOB", "$Q(z)[P_n⁻¹y − u]", f"$τ_q = {fmt(dob.get('tau_q'), 2)} s"], 8)
    wire(s, [(8.95, 4.4), (8.95, Y + 0.14)]); sig(s, 8.68, 4.08, "d̂", 11, 0.3)
    blk(s, 5.4, 4.45, 0.55, 0.44, ["$K(k̂)"], 10)
    for yy in (Y - 0.27, 4.4):  # 게인 스케줄 표기: 블록을 비스듬히 지나는 화살표 (적응 제어 관례)
        wire(s, [(5.28, yy + 0.55), (6.07, yy - 0.02)], dash=True)
    blk(s, 6.75, 1.85, 2.75, 0.62, ["RLS 최소제곱 (P2 Lec3)", "$F̂ = k̂_{eq} ε_{f,m} + ĉ  →  K(k̂), K_I(k̂)"], 8, "FFFFFF")
    sig(s, 6.75, 2.5, "접촉 모드에서만, k̂ ∈ 격자 · ε̂_c ∈ 진입값 ± 4 % 투영", 7, 2.75, PP_ALIGN.CENTER, MUTED, False, FONT)
    sig(s, 4.25, 4.56, f"자유: {fmt(lq.get('K'), 3)}", 7, 1.1, PP_ALIGN.RIGHT, MUTED, False)
    wire(s, [(5.95, 4.67), (6.45, 4.67), (6.45, Y + 0.14)])
    blk(s, 6.6, 5.1, 1.4, 0.55, ["칼만 필터  x̂ = [p, ε_f]", "$y: [p, ε̂] | [p, ε̃_f]"], 8)
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
    wire(s, [(11.7, 5.55), (11.7, 5.95), (4.2, 5.95), (4.2, Y + 0.14)]); sig(s, 4.25, 5.35, "ε̂ | F̂", 10, 0.6)
    wire(s, [(10.8, Y + 0.3), (10.8, 5.95)], head=False); dot(s, 10.8, 5.95); sig(s, 10.85, 5.0, "p", 11, 0.2)
    for x, y2 in ((7.3, 5.65), (8.875, 5.1)):
        dot(s, x, 5.95); wire(s, [(x, 5.95), (x, y2)])
    sig(s, 8.95, 5.98, "y = [p, ε̂ | F̂]", 10, 1.2)
    # 감독기 버스 d̂, F̂, 접촉
    wire(s, [(12.85, 5.2), (13.15, 5.2), (13.15, 6.6), (0.2, 6.6), (0.2, 1.86), (0.55, 1.86)])
    for yy in (3.2, 3.85, 4.5):
        dot(s, 0.2, yy); wire(s, [(0.2, yy), (0.55, yy)])
    sig(s, 4.0, 6.33, "d̂, ḋ̂, F̂, 접촉 c = gate ∨ TENG", 10, 4.0)
    cap = s.shapes.add_textbox(Inches(0.35), Inches(6.72), Inches(12.65), Inches(0.7)).text_frame
    cap.word_wrap = True
    _rich(cap.paragraphs[0], "그림 6. 계층형 제어 구조. (a) 상태 머신이 근접 스케줄·속도 제한(ε_{ref}) 또는 힘 기준(F_{ref}, GRASP)을 고른다 "
          "(GRASP→SAFETY: F̂ > F_{max}). (b) 자유: u = −K(x̂ − N_x r) + N_u r − K_I x_I − d̂, r = ε_{ref}, x_I += ε_{ref} − ε̂. "
          "접촉: r = (F_{ref} − ĉ)/k̂_{eq}, x_I += F_{ref} − F̂, 게인 K(k̂), K_I(k̂) (점선 = 스케줄). 전환 때 무충격. "
          "하위 반사는 TDM 샘플마다 F̂ 를 보고 배기한다 (상위 지연·통신 두절과 무관, S10). "
          "(c) 손가락마다 ITV 하나, 같은 설계. 노란 칸 = 가정값, 수치는 params.json에서 자동 기입.", 10, MUTED, MATH, False)


def mat(s, x, y, name, M, nd=3, cw=0.62, size=10):
    """수업식 행렬 표기: 'name =' + 대괄호 + 우측 정렬 원소. M 없으면 노란 '?'. 반환: 오른쪽 끝 x."""
    sig(s, x, y, name + " =", size, 0.7)
    x0 = x + 0.12 + 0.11 * len(name.replace("_", ""))
    if M is None:
        blk(s, x0, y - 0.02, 0.4, 0.26, ["?"], size, YELLOW)
        return x0 + 0.45
    M = [list(r) if isinstance(r, (list, tuple)) else [r] for r in M]
    rows, cols, rh = len(M), len(M[0]), 0.23
    top = y + 0.12 - rows * rh / 2
    for side, xb in (("l", x0), ("r", x0 + 0.06 + cols * cw)):
        b = s.shapes.add_shape(MSO_SHAPE.LEFT_BRACKET if side == "l" else MSO_SHAPE.RIGHT_BRACKET,
                               Inches(xb), Inches(top), Inches(0.06), Inches(rows * rh))
        b.line.color.rgb, b.line.width = LINE, Pt(1); b.fill.background()
    for i, r in enumerate(M):
        for j, v in enumerate(r):
            sig(s, x0 + 0.04 + j * cw, top + i * rh, v if isinstance(v, str) else f"{float(v):.{nd}g}", size, cw - 0.04,
                PP_ALIGN.RIGHT, italic=False)
    return x0 + 0.14 + cols * cw


def _diag(v):
    return "diag(" + (", ".join(f"{x:.3g}" for x in v) if v else "?") + ")"


def s_ss_fig(s, P, mode):
    """수업(Lec8–9, P2_Lec1) 형식 이산 상태공간 블록도: 플랜트 z⁻¹ 루프 / 적분 서보 + LQR / 현재 추정 칼만.
    mode = 'free' (ε 추종) | 'contact' (F 추종, RLS 게인 스케줄, 1 kHz 반사 스위치). 모든 신호는 동작점 편차."""
    c = mode == "contact"
    Y1, Yi, Yo, Ya, Yk = 2.3, 3.95, 5.0, 5.75, 6.3
    panel(s, 0.3, 1.2, 3.95, 2.35, "제어기: 적분 서보 + LQR" + (" (게인 스케줄)" if c else ""), "EEF3FA", "3C6AA8")
    panel(s, 4.4, 1.2, 4.7, 2.35, "플랜트 (식별 모델, 손가락 1개)", "F3F3F3", "6B6B6B")
    panel(s, 0.3, 3.7, 8.8, 2.9, "칼만 필터", "FFF5EA", "B5762A")
    r_ = "F_{ref}" if c else "ε_{ref}"
    # 제어기
    sig(s, 0.32, Y1 + 0.04, r_, 10, 0.5)
    wire(s, [(0.35, Y1), (0.71, Y1)]); dot(s, 0.55, Y1)
    sumj(s, 0.85, Y1, {"l": "+", "b": "−"})
    wire(s, [(0.99, Y1), (1.1, Y1)])
    blk(s, 1.1, Y1 - 0.22, 0.6, 0.44, ["$1/(z−1)"], 10)
    wire(s, [(1.7, Y1), (2.0, Y1)]); sig(s, 1.73, Y1 - 0.27, "x_I", 10, 0.3)
    blk(s, 2.0, Y1 - 0.22, 0.55, 0.44, ["$K_I(k̂)" if c else "$K_I"], 10)
    wire(s, [(2.55, Y1), (2.86, Y1)])
    sumj(s, 3.0, Y1, {"t": "+", "l": "−", "b": "−"})
    wire(s, [(0.55, Y1), (0.55, 1.62), (1.25, 1.62)])
    blk(s, 1.25, 1.45, 1.35, 0.34, ["$N_u + K N_x"], 10)
    if c:
        sig(s, 1.25, 1.83, "r = (F_{ref} − ĉ)/k̂", 8, 1.4, PP_ALIGN.CENTER, MUTED)
    wire(s, [(2.6, 1.62), (3.0, 1.62), (3.0, Y1 - 0.14)])
    if c:
        wire(s, [(3.14, Y1), (3.3, Y1)])
        blk(s, 3.3, Y1 - 0.25, 0.65, 0.5, ["반사 S", "1 kHz"], 8, "FBE3E3")
        sig(s, 3.12, Y1 - 0.52, "F̂ > F_{max} 3샘플 → u = 0", 7, 1.3, color=MUTED, italic=False)
        wire(s, [(3.95, Y1), (4.75, Y1)])
    else:
        wire(s, [(3.14, Y1), (4.75, Y1)])
    sig(s, 4.15 if c else 3.3, Y1 - 0.27, "u", 11, 0.2); dot(s, 4.1, Y1)
    # 플랜트: x(k+1) = A_d x + B_d u + w,  y = C x + v
    blk(s, 4.75, Y1 - 0.2, 0.5, 0.4, ["$B_d"], 11)
    wire(s, [(5.25, Y1), (5.51, Y1)])
    sumj(s, 5.65, Y1, {"l": "+", "t": "+", "b": "+"})
    wire(s, [(5.65, 1.55), (5.65, Y1 - 0.14)]); sig(s, 5.72, 1.5, "w(k)", 10, 0.5)
    wire(s, [(5.79, Y1), (6.1, Y1)]); sig(s, 5.75, Y1 - 0.45, "x(k+1)", 9, 0.6)
    blk(s, 6.1, Y1 - 0.22, 0.5, 0.44, ["$z⁻¹"], 11)
    wire(s, [(6.6, Y1), (7.3, Y1)]); sig(s, 6.65, Y1 - 0.27, "x(k)", 10, 0.5); dot(s, 6.95, Y1)
    blk(s, 7.3, Y1 - 0.2, 0.5, 0.4, ["$C_c" if c else "$C"], 11)
    wire(s, [(7.8, Y1), (8.11, Y1)])
    sumj(s, 8.25, Y1, {"l": "+", "t": "+"})
    wire(s, [(8.25, 1.55), (8.25, Y1 - 0.14)]); sig(s, 8.32, 1.5, "v(k)", 10, 0.5)
    wire(s, [(8.39, Y1), (8.9, Y1), (8.9, 3.75)] if c else [(8.39, Y1), (8.9, Y1), (8.9, Yi), (7.74, Yi)])
    sig(s, 8.3, Y1 + 0.1, "y = [p, F, ε]" if c else "y = [p, ε]", 9, 0.8)
    blk(s, 6.0, 2.88, 0.5, 0.36, ["$A_d"], 11)
    wire(s, [(6.95, Y1), (6.95, 3.06), (6.5, 3.06)]); wire(s, [(6.0, 3.06), (5.65, 3.06), (5.65, Y1 + 0.14)])
    # 적분 오차용 측정 버스
    dot(s, 8.9, 3.62); wire(s, [(8.9, 3.62), (0.85, 3.62), (0.85, Y1 + 0.14)])
    sig(s, 1.0, 3.33, "F̂ (MoE, TDM 1 kHz)" if c else "ε̂ = C_ε y (MoE)", 9, 2.2)
    # 칼만: 예측 x̂⁻(k+1) = A_d x̂(k) + B_d u,  보정 x̂(k) = x̂⁻ + K_f (y − C x̂⁻)
    if c:
        blk(s, 8.05, 3.75, 1.0, 0.4, ["$ε̃_f = (F̂ − ĉ)/k̂"], 8)
        wire(s, [(8.05, Yi), (7.74, Yi)])
    wire(s, [(4.1, Y1), (4.1, Yo), (4.2, Yo)])
    blk(s, 4.2, Yo - 0.2, 0.5, 0.4, ["$B_d"], 11)
    wire(s, [(4.7, Yo), (4.96, Yo)])
    sumj(s, 5.1, Yo, {"l": "+", "b": "+"})
    wire(s, [(5.24, Yo), (5.5, Yo)])
    blk(s, 5.5, Yo - 0.22, 0.5, 0.44, ["$z⁻¹"], 11)
    wire(s, [(6.0, Yo), (7.46, Yo)]); sig(s, 6.5, Yo + 0.06, "x̂⁻(k)", 10, 0.6); dot(s, 6.4, Yo)
    wire(s, [(6.4, Yo), (6.4, Yi), (6.6, Yi)])
    blk(s, 6.6, Yi - 0.18, 0.5, 0.36, ["$C"], 11)
    wire(s, [(7.1, Yi), (7.46, Yi)])
    sumj(s, 7.6, Yi, {"l": "−", "r": "+"})
    wire(s, [(7.6, Yi + 0.14), (7.6, 4.28)])
    blk(s, 7.3, 4.28, 0.6, 0.34, ["$K_f"], 11)
    wire(s, [(7.6, 4.62), (7.6, Yo - 0.14)])
    sumj(s, 7.6, Yo, {"l": "+", "t": "+"})
    wire(s, [(7.74, Yo), (8.3, Yo), (8.3, Yk)], head=False); dot(s, 8.3, Ya)
    sig(s, 7.8, Yo + 0.06, "x̂(k)", 10, 0.5)
    blk(s, 6.6, Ya - 0.18, 0.55, 0.36, ["$A_d"], 11)
    wire(s, [(8.3, Ya), (7.15, Ya)]); wire(s, [(6.6, Ya), (5.1, Ya), (5.1, Yo + 0.14)])
    blk(s, 4.6, Yk - 0.18, 0.6, 0.36, ["$K(k̂)" if c else "$K"], 11)
    wire(s, [(8.3, Yk), (5.2, Yk)]); wire(s, [(4.6, Yk), (3.0, Yk), (3.0, Y1 + 0.14)])
    if c:  # RLS → 게인 스케줄 (점선)
        blk(s, 0.5, 4.15, 2.2, 0.85, ["RLS (λ = 0.999)", "$θ̂ = [k̂_{eq}, ĉ],  φ = [ε_{f,m}, 1]", "$F̂ = φᵀθ̂  → K(k̂), K_I(k̂), ε̃_f"], 8)
        wire(s, [(2.27, 4.15), (2.27, Y1 + 0.22)], dash=True)
        wire(s, [(2.7, 4.6), (3.3, 4.6), (3.3, 6.0), (4.9, 6.0), (4.9, Yk - 0.18)], dash=True)
        sig(s, 0.5, 5.1, "ε_{f,m}: 측정 p 로 돌린 개루프 모델", 7, 2.4, color=MUTED, italic=False, font=FONT)
    # 오른쪽: 수치 (params.json)
    M, lq, st = get(P, "model") or {}, get(P, "det.lqr") or {}, get(P, "stoch") or {}
    X, y = 9.3, 1.3
    sig(s, X, y, "수치 (params.json, T_s = 10 ms)", 10, 3.8, color=MUTED, italic=False, font=FONT); y += 0.5
    xe = mat(s, X, y, "A_d", M.get("Ad")); mat(s, xe + 0.1, y, "B_d", M.get("Bd"))
    y += 0.6
    if not c:
        sig(s, X, y, "x = [p, ε_f],  u = ITV 지령,  C = I_2", 10, 3.8); y += 0.4
        sig(s, X, y, f"Q = {_diag(lq.get('Q'))},  R = {fmt(lq.get('R'), 3)}", 9, 3.8); y += 0.45
        K = lq.get("K")
        xe = mat(s, X, y, "K", [K[0][:2]] if K else None)
        mat(s, xe + 0.05, y, "K_I", None if lq.get("KI") is None else [[lq["KI"]]]); y += 0.45
        sig(s, X, y, f"V = {_diag(st.get('V'))}", 9, 3.8); y += 0.3
        sig(s, X, y, f"W = {_diag(st.get('W'))},  B_w = I", 9, 3.8); y += 0.55
        mat(s, X, y, "K_f", st.get("Kf"), cw=0.7); y += 0.6
        pl = lq.get("poles")
        sig(s, X, y, "폐루프 극 |z| = " + (", ".join(f"{abs(complex(*q)):.3f}" for q in pl) if pl else "?"), 9, 3.8); y += 0.32
        sig(s, X, y, f"GM {fmt(lq.get('gm_db'), 3)} dB · PM {fmt(lq.get('pm_deg'), 3)}°", 9, 3.8)
    else:
        cn = get(P, "contact.conductor") or {}
        k, g = cn.get("k_eq"), cn.get("g")
        sig(s, X, y, "x = [p, ε_f]  (자유 모드와 같음)", 10, 3.8); y += 0.6
        mat(s, X, y, "C_c", None if k is None else [[1, 0], [0, k], [0, g]])
        sig(s, X + 2.0, y - 0.1, "행 = p, F, ε", 8, 1.7, color=MUTED, italic=False, font=FONT)
        sig(s, X + 2.0, y + 0.15, "도체 S8 값 (k_{eq}, g)", 8, 1.7, color=MUTED, italic=False, font=FONT); y += 0.55
        sig(s, X, y, "x_I(k+1) = x_I(k) + F_{ref} − F̂", 9, 3.8); y += 0.3
        sig(s, X, y, "Q = diag(1/15², 1/2², 1/(0.4·25)²),  R = 1/15²", 9, 3.8); y += 0.35
        gains = get(P, "contact_design.gains") or {}
        keys = sorted(gains, key=float)[::2]
        rows = [["k̂ (격자)", "K", "적분 게인"]] + ([[k_, fmt(gains[k_]["K"], 3), fmt(gains[k_]["KI"], 3)] for k_ in keys] or [["?", "?", "?"]])
        table(s, X, y, 3.8, rows, [0.7, 2.1, 1.0], 9, 0.27, font=MATH); y += 0.27 * len(rows) + 0.2
        sig(s, X, y, "V = diag(V_p, V_F / k̂²)  (k̂ 따라 매 스텝)", 9, 3.8); y += 0.3
        sig(s, X, y, "P_0 = diag(0.005, 5),  k̂ ∈ 격자,  ε̂_c ∈ 진입값 ± 4 %", 9, 3.8)
    cap = s.shapes.add_textbox(Inches(0.3), Inches(6.68), Inches(12.8), Inches(0.7)).text_frame
    cap.word_wrap = True
    eq = ("x(k+1) = A_d x + B_d u + w,  y = C x + v,  u = −K(x̂ − N_x r) + N_u r − K_I x_I,  x_I += ε_{ref} − ε̂. "
          "칼만: x̂⁻(k+1) = A_d x̂ + B_d u,  x̂ = x̂⁻ + K_f(y − C x̂⁻). 분리 원리로 K 와 K_f 를 따로 설계 (LQG).") if not c else \
         ("상태 · A_d · B_d 는 자유 모드와 같고 출력만 C_c (F = k_{eq}(ε_f − ε_c)). 적분은 힘 오차, 게인은 RLS 의 k̂ 로 격자 DARE 를 보간. "
          "칼만은 F̂ 를 ε̃_f 로 바꿔 C = I 로 쓴다. 반사 S 는 하위(STM32) 1 kHz 에서 u 를 끊는다 (상위 감독기를 기다리지 않음).")
    _rich(cap.paragraphs[0], "모든 신호는 동작점 편차 (δx, δu). " + eq, 10, MUTED, MATH, False)


def _tf_diagram(s, r_lbl, m, gm_blk, cm_blk, noise):
    """고전 2자유도 블록도: r → F → Σ → G_p → p → G_m → m, p 는 C_p (위), m 은 C_m (아래) 로 되먹임."""
    Y = 2.05
    sig(s, 0.3, Y + 0.04, r_lbl, 10, 0.8)
    wire(s, [(0.4, Y), (0.75, Y)])
    blk(s, 0.75, Y - 0.22, 0.75, 0.44, ["$F(z)"], 11, "EEF3FA")
    wire(s, [(1.5, Y), (1.96, Y)])
    sumj(s, 2.1, Y, {"l": "+", "t": "−", "b": "−"})
    wire(s, [(2.24, Y), (2.75, Y)]); sig(s, 2.45, Y - 0.32, "u", 11, 0.3)
    blk(s, 2.75, Y - 0.22, 0.95, 0.44, ["$G_p(z)"], 11, "F3F3F3")
    wire(s, [(3.7, Y), (4.6, Y)]); sig(s, 3.75, Y - 0.3, "p", 11, 0.3); dot(s, 4.1, Y)
    blk(s, 4.6, Y - 0.22, 1.2 if len(gm_blk) > 12 else 0.95, 0.44, ["$" + gm_blk], 11, "F3F3F3")
    x2 = 5.8 if len(gm_blk) > 12 else 5.55
    wire(s, [(x2, Y), (6.7, Y)]); sig(s, 6.45, Y - 0.3, m, 11, 0.3); dot(s, 6.2, Y)
    wire(s, [(4.1, Y), (4.1, 1.4), (3.65, 1.4)])
    blk(s, 2.75, 1.2, 0.9, 0.4, ["$C_p(z)"], 11, "EEF3FA")
    wire(s, [(2.75, 1.4), (2.1, 1.4), (2.1, Y - 0.14)])
    wire(s, [(6.2, Y), (6.2, 2.75), (3.7, 2.75)])
    blk(s, 2.75, 2.55, 0.95, 0.4, ["$" + cm_blk], 11, "EEF3FA")
    wire(s, [(2.75, 2.75), (2.1, 2.75), (2.1, Y + 0.14)])
    sig(s, 4.2, 2.8, noise, 8, 2.0, color=MUTED, italic=False, font=FONT)
    sig(s, 0.3, 3.05, "선형 구간만 (포화 · anti-windup 제외). F, C_p, " + cm_blk.replace("(z)", "") +
        " 는 한 보상기: 같은 상태 (칼만 추정 + 적분) 를 공유.", 8, 6.9, color=MUTED, italic=False, font=FONT)


def _bode(s, name):
    if (OUT / name).exists():
        image(s, OUT / name, 7.55, 1.15, w=5.5)
    else:
        blk(s, 7.55, 1.15, 5.5, 4.8, ["?  (design_tf.py 실행 필요)"], 12, "FFF2A8")


def _caption(s, t):
    cap = s.shapes.add_textbox(Inches(0.3), Inches(6.68), Inches(12.8), Inches(0.7)).text_frame
    cap.word_wrap = True
    _rich(cap.paragraphs[0], t, 10, MUTED, MATH, False)


def s_tf_fig(s, P):
    """전달함수 관점 (자유 모드): u = F r − C_p p − C_ε ε, 플랜트 G_p · G_εp (design_tf.py, params tf)."""
    t = get(P, "tf") or {}
    _tf_diagram(s, "r = ε_{ref}", "ε", "G_{εp}(z)", "C_ε(z)", "+ 측정 잡음 v (MoE 추정 ε)")
    q = lambda k: t.get(k, "?")
    rows = [["블록", "전달함수 (T_s = 10 ms)", "뜻"],
            ["G_p = p/u", q("Gp"), "ITV 1차, 연속 " + q("Gp_s")],
            ["G_εp = ε/p", q("Gep"), "손가락 굽힘, 연속 " + q("Ge_s")],
            ["C_p", q("Cp"), "압력 되먹임 (적분 없음)"],
            ["C_ε", q("Ce"), "z = 1 극 = 적분기"],
            ["F", q("F"), "기준 경로 N_u + K N_x + 적분"],
            ["T = ε/r", q("T"), "극 = LQR 극"]]
    table(s, 0.3, 3.45, 7.0, rows, [1.05, 4.05, 1.9], 8, 0.36, font=MATH)
    gm, pm, dl = t.get("gm_db"), t.get("pm_deg"), t.get("delay_pm_loss_deg")
    _bode(s, "tf_bode.png")
    lines = [f"루프 L = C_p G_p + C_ε G_ε (u 에서 끊음): GM {fmt(gm, 3)} dB, PM {fmt(pm, 3)}°, ω_c {fmt(t.get('wc_rad_s'), 3)} rad/s",
             f"모델에 없는 지연 θ_p + θ_ε 가 ω_c 에서 위상 약 {fmt(dl, 2)}° 를 더 깎는다 (추정, 시뮬레이션 모델)."]
    sig(s, 7.55, 6.05, lines[0], 9, 5.6, italic=False); sig(s, 7.55, 6.35, lines[1], 9, 5.6, italic=False, color=MUTED)
    _caption(s, "LQG 는 상태공간에서 설계하지만, 정상상태 칼만 이득을 쓰면 선형 시불변 보상기라 전달함수와 똑같다 "
             "(시간 응답 일치를 시험 코드로 확인). 폐루프 T 의 극은 LQR 극 0.962 · 0.864 · 0.722 이고, 칼만 극 0.718 · 0.312 는 "
             "r → ε 에서 상쇄된다 (분리 원리). 접촉 모드는 다음 장.")


def s_tf_contact_fig(s, P):
    """전달함수 관점 (접촉 모드, k̂ 고정 = RLS 수렴 뒤): u = F r − C_p p − C_F F̂, 플랜트 G_F = k_eq G_εp G_p."""
    t = get(P, "tf_contact") or {}
    kn = t.get("k_nom")
    by = t.get("by_k") or {}
    n = by.get(kn, {})
    _tf_diagram(s, "r = F_{ref}", "F", "k_{eq} G_{εp}(z)", "C_F(z)", "+ 측정 잡음 (MoE 추정 F)")
    blk(s, 4.75, 1.08, 1.75, 0.5, ["RLS → k_{eq} 추정", "→ C_p, C_F, F 를 고름"], 8, "FFF5EA")
    wire(s, [(4.75, 1.33), (4.3, 1.33)], dash=True)
    q = lambda k: n.get(k, "?")
    rows = [["블록", f"전달함수 (공칭 k_eq = {kn or '?'})", "뜻"],
            ["G_F = F/u", q("Gm"), "자유 모드 G_ε × k_eq"],
            ["C_p", q("Cp"), "압력 되먹임"],
            ["C_F", q("Cm"), "z = 1 극 = 힘 적분기"],
            ["F", q("F"), "기준 경로 (F_ref/k_eq)"],
            ["T = F/F_ref", q("T"), "극 = 접촉 LQR 극"]]
    table(s, 0.3, 3.4, 7.0, rows, [1.05, 4.05, 1.9], 8, 0.3, font=MATH)
    y = 3.4 + 0.3 * len(rows) + 0.1
    sm = [["k_eq (격자)", "GM [dB]", "PM [°]", "ω_c [rad/s]", "폐루프 극 |z|"]] +          ([[k, fmt(r.get("gm_db"), 3), fmt(r.get("pm_deg"), 3), fmt(r.get("wc_rad_s"), 3),
            ", ".join(f"{v:.3f}" for v in r.get("cl_poles", []))] for k, r in by.items()] or [["?"] * 5])
    table(s, 0.3, y, 7.0, sm, [1.2, 1.0, 1.0, 1.3, 2.5], 8, 0.25, font=MATH)
    _bode(s, "tf_bode_contact.png")
    sig(s, 7.55, 6.05, "k_eq 마다 다른 보상기 (게인 스케줄 = k_eq 별 LTI 보상기 묶음).", 9, 5.6, italic=False)
    sig(s, 7.55, 6.35, "k_eq 가 클수록 ω_c ↑, PM ↓ (공칭 모델 기준, 시뮬레이션).", 9, 5.6, italic=False, color=MUTED)
    _caption(s, "접촉 중 RLS 가 수렴해 k_eq 추정값이 멈추면 접촉 제어기도 선형 시불변: 칼만 측정 = F/k_{eq}, 기준 F_{ref}/k_{eq}, "
             "적분 x_I += F_{ref} − F. 시간 응답이 ContactLqg 와 일치함을 시험 코드로 확인. RLS 적응 중 · 반사 S 동작 중에는 시변 · 비선형이라 TF 로 표현되지 않는다.")


def s_layers_fig(s):
    """상·하위 계층 개요: 상위 PC (시나리오·재질·상태 머신·기준) | UART | 하위 STM32 + TDM (1 kHz 측정·반사, 100 Hz 내부 루프) | 플랜트."""
    panel(s, 0.35, 1.15, 9.6, 1.75, "(a) 상위 제어기 · PC (20 Hz, 가정)", "FFF5EA", "B5762A")
    panel(s, 0.35, 3.45, 9.6, 2.6, "(b) 하위 제어기 · STM32G473 + TDM 보드 (PC 없이 단독 동작)", "EEF3FA", "3C6AA8")
    panel(s, 10.15, 1.15, 2.85, 4.9, "(c) 플랜트", "F3F3F3", "6B6B6B")
    for x, w, ln, fill in ((0.55, 2.1, ["시나리오 관리", "S1 도체 파지", "S2 인체 상호작용"], "FFFFFF"),
                           (2.95, 2.0, ["재질 식별 m", "도체 / 인체 / 유전체", "$→ F_t, F_{max}, v_{max}"], YELLOW),
                           (5.25, 2.2, ["상태 머신", "OPEN → APPROACH → GRASP", "SAFETY · RELEASE"], "FFFFFF"),
                           (7.75, 2.0, ["기준 생성", "$ε_{ref} | F_{ref}", "안전 동작 = 배기"], "FFFFFF")):
        blk(s, x, 1.6, w, 0.95, ln, 9, fill)
    for x1, x2 in ((2.65, 2.95), (4.95, 5.25), (7.45, 7.75)):
        wire(s, [(x1, 2.075), (x2, 2.075)])
    sig(s, 0.55, 3.0, "UART 링크 · 지연 τ_c (가정 20 ms, S10에서 20–200 ms · 두절 시험)", 9, 6.0, color=MUTED, italic=False, font=FONT)
    # 하위 1 kHz 줄
    blk(s, 0.55, 3.9, 1.9, 0.7, ["TDM 측정 1 kHz", "$L · R_{DC} · V_{TENG}", "(실측 주기 1 ms)"], 8, "EAF3E4")
    blk(s, 2.75, 3.9, 1.9, 0.7, ["MoE v4 디커플링", "$ε̂, d̂, F̂, c", "(실측 추론 260 µs)"], 8)
    blk(s, 4.95, 3.9, 2.2, 0.7, ["반사 안전 1 kHz", "$F̂ > F_{max}  3 ms 연속", "→ 배기 (u = 0) 래치"], 8, "FBE3E3")
    wire(s, [(2.45, 4.25), (2.75, 4.25)]); wire(s, [(4.65, 4.25), (4.95, 4.25)])
    # 하위 100 Hz 줄
    blk(s, 2.75, 4.95, 1.9, 0.7, ["칼만 필터", "$x̂ = [p, ε_f]"], 8)
    blk(s, 4.95, 4.95, 2.2, 0.7, ["내부 루프 100 Hz", "LQG(ε) | F-LQG + RLS"], 8)
    wire(s, [(3.7, 4.6), (3.7, 4.95)]); wire(s, [(4.65, 5.3), (4.95, 5.3)])
    blk(s, 7.55, 4.4, 0.9, 0.7, ["배기", "우선"], 8, "FFFFFF", shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    wire(s, [(7.15, 4.25), (8.0, 4.25), (8.0, 4.4)], dash=True); wire(s, [(7.15, 5.3), (8.0, 5.3), (8.0, 5.1)])
    sig(s, 7.2, 3.95, "1 kHz", 8, 0.5, color=MUTED, italic=False, font=FONT)
    sig(s, 7.2, 5.36, "100 Hz", 8, 0.6, color=MUTED, italic=False, font=FONT)
    # 상·하위 링크
    wire(s, [(6.6, 3.9), (6.6, 2.55)], dash=True)
    sig(s, 6.68, 3.0, "↑ d̂, F̂, c, 반사 플래그", 9, 2.0, italic=False)
    wire(s, [(8.75, 2.55), (8.75, 5.85), (6.05, 5.85), (6.05, 5.65)], dash=True)
    sig(s, 8.82, 3.0, "↓ ε_{ref} | F_{ref}, F_t, F_{max}", 9, 1.3)
    # 플랜트
    blk(s, 10.4, 4.45, 2.3, 0.6, ["ITV × 2", "지연 10 ms · τ 50 ms"], 8)
    blk(s, 10.4, 3.15, 2.3, 0.9, ["PneuNet 2지 (DS30)", "30 kPa ≈ 300°"], 8)
    blk(s, 10.4, 1.65, 2.3, 0.9, ["센서 (DS30 + EGaIn)", "단일 전극 2선"], 8, "EAF3E4")
    wire(s, [(8.45, 4.75), (10.4, 4.75)]); sig(s, 9.2, 4.48, "u_1, u_2", 10, 0.8)
    wire(s, [(11.55, 4.45), (11.55, 4.05)]); wire(s, [(11.55, 3.15), (11.55, 2.55)])
    sig(s, 11.6, 2.65, "ε, d, F", 9, 0.8)
    wire(s, [(12.7, 2.1), (13.15, 2.1), (13.15, 6.25), (1.5, 6.25), (1.5, 4.6)])
    sig(s, 1.58, 5.0, "센서 코일 L · R · V", 8, 1.2, italic=False, font=FONT)
    cap = s.shapes.add_textbox(Inches(0.35), Inches(6.4), Inches(12.65), Inches(0.9)).text_frame
    cap.word_wrap = True
    _rich(cap.paragraphs[0], "그림 5. 상·하위 계층. 하위(STM32 + TDM)는 센서 주기 1 ms에서 반사 안전을 돌려, 상위 지연·통신 두절과 무관하게 배기한다 (S10). "
          "상위는 시나리오 · 재질 · 상태 머신 · 기준을 맡는다. 실측 = TDM 주기 · MoE 추론 시간. 상위 주기 · 지연은 가정값, "
          "하위 내부 루프는 펌웨어 이식 전 (시뮬레이션). 노란 칸 = 시뮬에선 정답 라벨 (B단계 R1).", 10, MUTED, MATH, False)


def s_flow(s, y, stages):
    """시나리오 단계 띠: stages = [(이름, 신호, 상위, 하위)], 쉐브론 + 아래 3줄."""
    w = 12.3 / len(stages)
    for k, (nm, sg, up, lo) in enumerate(stages):
        x = 0.5 + k * w
        b = box(s, x, y, w + 0.05, 0.5, nm, "DCE6F2" if k % 2 == 0 else "C9D8EC", 12, True,
                MSO_SHAPE.CHEVRON if k else MSO_SHAPE.PENTAGON)
        b.line.fill.background()
        text(s, x + 0.1, y + 0.55, w - 0.15, 1.3, [f"신호: {sg}", f"상위: {up}", f"하위: {lo}"], 9, font=MATH)


STATE_FILL = {"OPEN": "FFFFFF", "APPROACH": "DCE6F2", "GRASP": "D9EAD3", "SAFETY": "FBE3E3"}


def _finger(s, xt, yt, ang, L=0.78, w=0.15):
    """손가락: 위 끝 (xt, yt) 고정, ang° 시계 방향 회전 (+ = 아래 끝이 왼쪽). 반환: 손끝 좌표."""
    import math
    a = math.radians(ang)
    cx, cy = xt - L / 2 * math.sin(a), yt + L / 2 * math.cos(a)
    f = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx - w / 2), Inches(cy - L / 2), Inches(w), Inches(L))
    f.rotation = ang
    f.fill.solid(); f.fill.fore_color.rgb = RGBColor.from_string("9DC3E6")
    f.line.color.rgb, f.line.width = RGBColor.from_string("2F5597"), Pt(1)
    return xt - L * math.sin(a), yt + L * math.cos(a)


def _obj(s, cx, cy, kind):
    if kind == "도체":
        o = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - 0.27), Inches(cy - 0.27), Inches(0.54), Inches(0.54))
        o.fill.solid(); o.fill.fore_color.rgb = RGBColor.from_string("BFBFBF")
        o.line.color.rgb, o.line.width = RGBColor.from_string("595959"), Pt(1)
        tf = o.text_frame; tf.word_wrap = False; tf.margin_left = tf.margin_right = 0
        _run(tf.paragraphs[0], "금속", 8); tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    else:
        o = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx - 0.3), Inches(cy - 0.24), Inches(0.6), Inches(0.62))
        o.fill.solid(); o.fill.fore_color.rgb = RGBColor.from_string("F4C7A1")
        o.line.color.rgb, o.line.width = RGBColor.from_string("A0522D"), Pt(1)
        tf = o.text_frame; _run(tf.paragraphs[0], "손", 9); tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    return o


def _mark(s, shape, x, y, w, h, fill, text_="", size=7, rot=0):
    m = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    m.rotation = rot
    m.fill.solid(); m.fill.fore_color.rgb = RGBColor.from_string(fill); m.line.fill.background()
    if text_:
        tf = m.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        _run(tf.paragraphs[0], text_, size, True); tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    return m


def s_photo(s, P):
    """run_photo.py 렌더 사진 2행 × 4단계 (같은 폐루프, 소품만 다름) + 칸마다 실제 상태·시각·힘."""
    heads = ("탐지 · 식별", "접근", "접촉", "파지 · 유지 | 상호작용")
    rows = (("conductor", "도체: 금속 자루", "시나리오 1"), ("human", "인체: 손목", "시나리오 2"))
    res = get(P, "results_photo") or {}
    X0, W, PW, PH = 1.2, 3.0, 2.9, 2.175
    for k, nm in enumerate(heads):
        b = box(s, X0 + k * W, 1.05, W + 0.05, 0.36, nm, "DCE6F2" if k % 2 == 0 else "C9D8EC", 11, True,
                MSO_SHAPE.CHEVRON if k else MSO_SHAPE.PENTAGON)
        b.line.fill.background()
    for r, (mat, lab, sc) in enumerate(rows):
        y0 = 1.5 + r * 2.68
        lb = box(s, 0.2, y0 + 0.6, 0.95, 1.0, f"{sc}\n{lab.split(':')[0]}", "FFF5EA" if r == 0 else "FCE4D6", 10, True)
        lb.text_frame.word_wrap = False; lb.text_frame.margin_left = lb.text_frame.margin_right = 0
        sig(s, 0.2, y0 + 1.65, lab.split(": ")[1], 9, 0.95, PP_ALIGN.CENTER, MUTED, False, FONT)
        shots = (res.get(mat) or [{}] * 4) + [{}] * 4
        for k in range(4):
            x = X0 + k * W + 0.05
            image(s, OUT / f"photo_{mat}_{k}.png", x, y0, w=PW, h=PH)
            i = shots[k]
            st = i.get("state", "?")
            chip = box(s, x + 0.05, y0 + 0.05, 1.35 if "/" in st else 1.0, 0.25, st, STATE_FILL.get(st.split("/")[-1], "FFFFFF"), 8, True)
            chip.line.color.rgb = RGBColor.from_string("7F7F7F")
            ln = (f"t = {fmt(i.get('t'), 3)} s · d = {fmt(i.get('d_mm'), 3)} mm · F = {fmt(i.get('F_N'), 2)} N · u = {fmt(i.get('u_kPa'), 3)} kPa"
                  if i else "?")
            sig(s, x, y0 + PH + 0.03, ln, 8, PW, italic=False)
    text(s, 0.3, 6.88, 12.8, 0.55, ["시뮬레이션 렌더 (MuJoCo, 같은 C F-LQG + RLS 폐루프 · TDM · MoE · TENG). 사람·망치는 보이기만 하는 소품이고 물리는 r 15 mm 원기둥 "
                                    "(도체 = 강체, 인체 = 무른 패드). 아래 줄 = 그 순간의 상태 · 시각 · 거리 · 정답 힘 · 지령. "
                                    "인체는 힘 추정 편향으로 GRASP ↔ SAFETY 를 반복하므로 마지막 칸은 반사·SAFETY 가 동작한 순간 (S11과 같은 한계)."], 9, color=MUTED)


def s_story(s):
    """시나리오 그림 (개념도): 행 = 도체 / 인체, 열 = 단계. 칸마다 손가락·물체 스케치 + 상태 칩 + 하위 제어기 + 신호."""
    phases = ["탐지", "식별", "접근", "접촉", "파지 · 유지 | 상호작용"]
    # (왼손가락 각도, 물체 y, 상태, 하위 제어기, 신호/규칙)
    rows = {
        "도체": [(22, 1.45, "OPEN", "자유 LQG: ε 유지 (열림)", "d̂ < 24 mm → 탐지"),
                 (22, 1.45, "APPROACH", "자유 LQG", "ΔL 잔차 (−) → 도체\nF_t = 0.5·, F_{max} = 0.8·F_{block}"),
                 (6, 1.33, "APPROACH", "자유 LQG: ε_{ref} = g(d̂)", "근접 스케줄 · 속도 제한"),
                 (-11, 1.22, "GRASP", "자유 LQG → F-LQG (무충격)", "게이트 ∨ TENG 3샘플"),
                 (-13, 1.22, "GRASP", "F-LQG + RLS, 반사 대기", "F_{ref} 경사 → F_t 유지")],
        "인체": [(22, 1.45, "OPEN", "자유 LQG: ε 유지 (열림)", "d̂, ḋ̂ (움직이는 물체)"),
                 (22, 1.45, "APPROACH", "자유 LQG, 반사 문턱 ↓", "인체 → F_t = 0.15·, F_{max} = 0.3·\n속도 × 0.4 (B단계 실측 필요)"),
                 (8, 1.33, "APPROACH", "자유 LQG: 느린 pre-shape", "접촉 시각 t_c 맞춤"),
                 (-11, 1.22, "GRASP", "F-LQG (dF/dt 상한)", "게이트 ∨ TENG"),
                 (-9, 1.22, "SAFETY", "반사 1 kHz: F̂ > F_{max} → 배기", "(a) 약한 힘 유지 (b) 어드미턴스 따라가기")],
    }
    X0, W, H = 1.15, 2.4, 2.75
    for k, nm in enumerate(phases):
        b = box(s, X0 + k * W, 1.1, W + 0.05, 0.36, nm, "DCE6F2" if k % 2 == 0 else "C9D8EC", 11, True,
                MSO_SHAPE.CHEVRON if k else MSO_SHAPE.PENTAGON)
        b.line.fill.background()
    for r, (kind, cells) in enumerate(rows.items()):
        y0 = 1.55 + r * H
        lab = box(s, 0.25, y0 + 0.4, 0.85, 1.3, f"시나리오 {r + 1}\n{kind}", "FFF5EA" if r == 0 else "FCE4D6", 10, True)
        lab.text_frame.word_wrap = False
        lab.text_frame.margin_left = lab.text_frame.margin_right = 0
        for k, (ang, oy, st, lo, sg) in enumerate(cells):
            x = X0 + k * W
            fr = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 0.05), Inches(y0), Inches(W - 0.1), Inches(1.95))
            fr.fill.solid(); fr.fill.fore_color.rgb = RGBColor.from_string("FAFAFA")
            fr.line.color.rgb, fr.line.width = RGBColor.from_string("BFBFBF"), Pt(0.75)
            cx = x + W / 2 - 0.25
            palm = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(cx - 0.45), Inches(y0 + 0.12), Inches(0.9), Inches(0.16))
            palm.fill.solid(); palm.fill.fore_color.rgb = RGBColor.from_string("595959"); palm.line.fill.background()
            tl = _finger(s, cx - 0.33, y0 + 0.24, ang)
            tr = _finger(s, cx + 0.33, y0 + 0.24, -ang)
            oy_ = y0 + oy if k < 4 or kind == "도체" else y0 + oy + 0.0
            _obj(s, cx, oy_, kind)
            if k == 0:  # 근접장: 점선 원
                for rr in (0.38, 0.5):
                    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - rr), Inches(oy_ - rr), Inches(2 * rr), Inches(2 * rr))
                    c.fill.background(); c.line.color.rgb = RGBColor.from_string("FF8C00"); c.line.width = Pt(1)
                    c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                sig(s, cx + 0.5, y0 + 0.75, "d̂ (L)", 9, 0.6, color=RGBColor.from_string("C55A11"))
            if k == 1:
                _mark(s, MSO_SHAPE.ROUNDED_RECTANGLE, cx + 0.38, oy_ - 0.5, 0.55, 0.3, "FFF2CC" if kind == "인체" else "E2EFDA",
                      "도체" if kind == "도체" else "인체", 8)
            if k == 2:
                wire(s, [(cx + 0.62, y0 + 0.55), (cx + 0.62, y0 + 0.95)]); sig(s, cx + 0.66, y0 + 0.62, "ε_{ref}↑", 9, 0.6)
            if k == 3:
                for px in (tl[0], tr[0]):
                    _mark(s, MSO_SHAPE.STAR_8_POINT, px - 0.12, tl[1] - 0.12, 0.24, 0.24, "1F77B4")
                sig(s, cx + 0.55, y0 + 0.95, "TENG", 9, 0.6, color=RGBColor.from_string("1F77B4"), italic=False)
            if k == 4:
                _mark(s, MSO_SHAPE.RIGHT_ARROW, tl[0] - 0.42, tl[1] - 0.09, 0.32, 0.18, "2CA02C")
                _mark(s, MSO_SHAPE.LEFT_ARROW, tr[0] + 0.1, tr[1] - 0.09, 0.32, 0.18, "2CA02C")
                if kind == "인체":
                    _mark(s, MSO_SHAPE.UP_DOWN_ARROW, cx + 0.55, y0 + 1.05, 0.16, 0.6, "A0522D")
                    _mark(s, MSO_SHAPE.LIGHTNING_BOLT, cx + 0.72, y0 + 0.3, 0.32, 0.45, "C00000")
                    sig(s, cx + 0.72, y0 + 0.78, "반사", 8, 0.4, color=RGBColor.from_string("C00000"), italic=False, font=FONT)
                else:
                    sig(s, cx + 0.62, y0 + 0.85, "F̂ → F_t", 9, 0.7, color=RGBColor.from_string("2CA02C"))
            # 아래: 상태 칩 + 하위 + 신호
            chip = box(s, x + W - 1.1, y0 + 1.62, 0.98, 0.27, st, STATE_FILL[st], 8, True)
            chip.line.color.rgb = RGBColor.from_string("7F7F7F")
            for j, ln in enumerate([f"하위: {lo}", *sg.split("\n")]):
                sig(s, x + 0.12, y0 + 2.0 + j * 0.22, ln, 8, W - 0.2, italic=False)
    cap = s.shapes.add_textbox(Inches(0.3), Inches(7.05), Inches(12.8), Inches(0.35)).text_frame
    cap.word_wrap = True
    _rich(cap.paragraphs[0], "개념도 (시뮬레이션 상황 묘사). 상위(PC 20 Hz)는 상태 칩과 기준(ε_{ref}, F_{ref}, F_{max})을 바꾸고, "
          "하위(STM32 + TDM)는 매 칸의 루프와 1 kHz 반사를 돌린다. 주황 점선 = 인덕턴스 L 근접장, 파랑 별 = TENG 접촉, 초록 화살표 = 파지력. "
          "식별은 시뮬에서 정답 라벨 (ΔL 잔차 판별기는 도체 · 유전체만 가름).", 9, MUTED, MATH, False)


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
    text(s, 0.8, 3.2, 11.7, 0.8, "단일 전극 멀티모달 센서(인장·근접·힘) 기반 식별 · LQR · LQG · DOB · 상·하위 계층 (반사 안전)", 18, color=MUTED)
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

    # 5 변수 정의 (스펙 12절)
    s = prs.slides.add_slide(blank); title(s, "상태 · 입력 · 출력 정의 (손가락 i = 1, 2, 모드별)")
    table(s, 0.5, 1.15, 8.3, [["구분", "자유 모드 (접촉 전)", "접촉 모드 (접촉 후)"],
                              ["입력 u_i", "ITV_i 압력 지령 0–30 kPa", "같음 (ITV 2개, 손가락별 루프)"],
                              ["상태 x_i", "[p, ε_f]  (A, B = 식별값)", "같음: [p, ε_f]"],
                              ["출력 y", "[p, ε],  ε = ε_f", "[p, F, ε]:  F = k_eq(ε_f − ε_c),  ε = ε_c + g(ε_f − ε_c)"],
                              ["추종 · 적분", "ε_ref,  Σ(ε_ref − ε̂)", "F_ref,  Σ(F_ref − F̂)  (전환 때 무충격)"],
                              ["칼만 측정", "[p, ε̂]", "[p, ε̃_f],  ε̃_f = (F̂ − ĉ)/k̂_eq"],
                              ["게인", "K, K_I (자유 LQR)", "K(k̂_eq), K_I(k̂_eq): 격자 5점 DARE + 보간"],
                              ["상위 변수", "[d, ḋ] (근접 칼만), 재질 m", "k̂_eq, ĉ (RLS),  k̂_env = ΔF̂/Δε̂ (식별 보조)"]],
          [1.4, 2.9, 4.0], 11, 0.5, font="Cambria Math")  # 맑은 고딕은 결합 문자(ε̂) 깨짐
    text(s, 9.0, 1.15, 3.9, 5.6, ["ε_f = '물체가 없으면 갔을 굽힘'. 접촉해도 A, B가 그대로라 모델 하나로 두 모드를 다룬다.",
                                  "접촉하면 측정 ε는 일부만 움직인다 (S8: g = 0.28–0.48). 힘 F가 실제 출력이 된다.",
                                  "k_eq는 물체 무르기보다 '어디를, 얼마나 큰 것을' 쥐었는지에 달렸다 (S8) → RLS로 추정.",
                                  "외란: 하중·모델 오차·두 손가락이 물체로 묶이는 결합 → 입력 외란으로 보고 DOB가 맡는다."], 12, bullet=True)

    # 6 제어 블록도 (논문 그림 형식, 편집 가능한 도형)
    s = prs.slides.add_slide(blank); title(s, "제어 구조: 상위 제어기(PC) / 하위 제어기(STM32 + TDM)")
    s_layers_fig(s)
    s = prs.slides.add_slide(blank); title(s, "제어 구조 상세: 상위 감독기 + 하위 내부 루프 (과제 2–6절)")
    s_control_fig(s, P)
    s = prs.slides.add_slide(blank); title(s, "상태공간 블록도 ① 자유 모드: LQG + 적분 서보 (Lec8–9, P2_Lec1)")
    s_ss_fig(s, P, "free")
    s = prs.slides.add_slide(blank); title(s, "상태공간 블록도 ② 접촉 모드: F-LQG + RLS 게인 스케줄 + 반사")
    s_ss_fig(s, P, "contact")
    s = prs.slides.add_slide(blank); title(s, "전달함수 블록도: G(z) 와 LQG 등가 보상기 (자유 모드)", True)
    s_tf_fig(s, P)
    s = prs.slides.add_slide(blank); title(s, "전달함수 블록도: 접촉 모드 (k_eq 별 LQG 등가 보상기)", True)
    s_tf_contact_fig(s, P)

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

    # 접촉 모드 (스펙 12절): 이론 · S8 접촉 강성·가관측성 · S9 힘 유지
    s_theory(prs, "contact")
    s = prs.slides.add_slide(blank); title(s, "접촉 강성(S8)과 접촉 모드 가관측성", True)
    image(s, OUT / "S8_keq.png", 0.4, 1.1, w=7.0)
    image(s, OUT / "contact_obsv.png", 7.5, 1.1, w=5.4)
    ct = get(P, "contact") or {}
    rows = [["조건", "k_eq [N/%]", "k_env [N/%]", "g", "ε_c [%]", "F_block [N]"]]
    for g in ct.get("geometry", []):
        rows.append([g["name"], fmt(g["k_eq"], 3), fmt(g["k_env"], 3), fmt(g["g"], 2), fmt(g["eps_c"], 2), fmt(g["F_block"], 3)])
    for m, lab in (("conductor", "도체 (강체)"), ("dielectric", "유전체 (2 N/mm)"), ("human", "인체 (0.7 N/mm)")):
        if m in ct:
            rows.append([lab + " r15 z−70", fmt(ct[m]["k_eq"], 3), fmt(ct[m]["k_env"], 3), fmt(ct[m].get("g"), 2), fmt(ct[m].get("eps_c"), 2), fmt(ct[m]["F_block"], 3)])
    table(s, 0.5, 4.45, 7.4, rows, [2.2, 1.0, 1.0, 0.8, 1.0, 1.4], 9, 0.24)
    cd = get(P, "contact_design") or {}
    text(s, 8.1, 4.5, 4.8, 2.6, ["소프트 손가락이 직렬 강성을 지배 → 물체 무르기는 k_eq에 거의 영향 없음, 접촉 위치·크기는 약 2배.",
                                 f"게인 격자 k_eq = {fmt(cd.get('grid'), 3)}, 공칭 {fmt(cd.get('k_nom'), 3)}",
                                 "g → 0 (막힌 손가락)이면 ε̂만으로는 상태가 안 보인다 → 접촉 모드는 F̂를 측정으로 쓴다.",
                                 f"F̂ 잡음 V_F = {fmt(ct.get('V_F'), 3)} N² (S8)"], 11, bullet=True)
    s = prs.slides.add_slide(blank); title(s, "접촉 후 힘 유지 비교 (S9): 기존 어드미턴스 vs 힘 직접 추종", True)
    image(s, OUT / "S9_force.png", 0.4, 1.1, w=6.4)
    image(s, OUT / "S9_metrics.png", 6.9, 1.1, w=6.0)
    s9 = read_csv(OUT / "S9_metrics.csv")
    rows = [["유지 RMSE (정답 F) [N]", "A 기존", "B F-LQG", "C +RLS", "D +DOB", "B vs A", "최선 vs A"]]
    if s9:
        h = s9[0]
        d9 = {r_[0]: dict(zip(h[1:], map(float, r_[1:]))) for r_ in s9[1:]}
        for sc in dict.fromkeys(k.split(" | ")[0] for k in d9):
            v = [d9[k]["rmse_hold"] for k in d9 if k.startswith(sc + " | ")]
            rows.append([sc, *[f"{x:.3g}" for x in v], f"{100 * (v[1] - v[0]) / v[0]:+.0f} %", f"{100 * (min(v[1:]) - v[0]) / v[0]:+.0f} %"])
    else:
        rows.append(["(실험 전)", *[None] * 6])
    table(s, 6.9, 3.85, 6.0, rows, [2.1, 0.6, 0.65, 0.6, 0.6, 0.7, 0.75], 9, 0.3)
    text(s, 6.9, 5.5, 6.0, 1.6, ["힘 직접 추종(B)이 어드미턴스(A)보다 유지 오차를 크게 줄인다 (도체·유전체).",
                                 "RLS 스케줄(C)은 k_eq가 공칭과 다를 때만 이득 (r25). 공칭 물체에선 F̂ 편향이 k̂을 끌어 오버슈트 증가.",
                                 "인체: 목표 힘보다 F̂ 오차가 커서 모든 제어기가 실패 (센서 한계). 전체 지표: out/S9_metrics.csv"], 10, bullet=True)

    # 상위 제어기: 상태 머신 · 동작 예시 · 파라미터 (slides_upper)
    import slides_upper as su
    s = prs.slides.add_slide(blank); title(s, "상위 제어기: 상태 머신 (전이 조건 · 상태별 기준)")
    su.s_upper_fsm(s, P)
    s = prs.slides.add_slide(blank); title(s, "상위 제어기 동작 예시: 입력 → 상태 → 기준 하나", True)
    su.s_upper_timeline(s, P)
    s = prs.slides.add_slide(blank); title(s, "상위 파라미터: 값 · 뜻 · 정한 근거")
    su.s_upper_params(s, P)

    # 19 파지 시연
    s = prs.slides.add_slide(blank); title(s, "파지 시연 (S7): 근접 → 접촉 → 힘 추종 → 해제", True)
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
    text(s, 0.5, 5.8, 12.3, 1.4, ["제어기 = 하이브리드 C (자유 LQG → 접촉 F-LQG + RLS 스케줄). D(+DOB)는 2지 힘 유지에서 입력이 0–30 kPa로 진동해 제외 (해결 예정). 도체·유전체(TENG)는 목표 힘 근처로 유지 (이전 어드미턴스: 도체 1.2 N, 유전체 1.36 N).",
                                  "유전체 게이트만: 접촉을 놓쳐 힘 모드로 못 들어감 → 파지 실패. TENG 융합이 필요.",
                                  "인체: F_max 이하(최대 1.5 N)지만 유지 힘이 목표의 절반 이하. F̂ 오차(접촉 중 약 +1.5 N)가 목표 0.93 N보다 커서 SAFETY가 반복 (센서 한계). 도체 유지 힘이 목표보다 큰 것도 F̂ 편향 (−0.5 N 내외)"], 11, bullet=True)

    # 시나리오 1: 도체
    s = prs.slides.add_slide(blank); title(s, "시나리오 그림: 도체 파지 vs 인체 상호작용 (단계별 상태 · 제어기)")
    s_story(s)
    s = prs.slides.add_slide(blank); title(s, "사진 비교: 망치를 든 손 — 자루(도체) vs 손목(인체)", True)
    s_photo(s, P)
    s = prs.slides.add_slide(blank); title(s, "시나리오 1 (도체): 탐지 → 접근 → 접촉 → 파지 · 유지", True)
    s_flow(s, 1.15, [("탐지", "근접 d̂ < 24 mm", "OPEN → APPROACH", "TDM·MoE 1 kHz"),
                     ("식별", "ΔL 잔차 부호 (−: 도체)", "재질 → F_t 0.5·, F_max 0.8·F_block", "—"),
                     ("접근", "d̂, ḋ̂ (칼만)", "근접 스케줄 · 속도 제한 → ε_ref", "자유 LQG (ε)"),
                     ("접촉", "게이트 ∨ TENG 3 샘플", "APPROACH → GRASP", "무충격 전환 → F-LQG"),
                     ("파지 · 유지", "F̂", "F_ref 경사 → F_t", "F-LQG + RLS, 반사 F_max")])
    movie(s, OUT / "S7_conductor.mp4", OUT / "S7_conductor_snap.png", 0.5, 3.05, 4.6, 3.45)
    image(s, OUT / "S7_conductor.png", 5.3, 3.0, h=3.6)
    v = r7.get("conductor", {})
    table(s, 9.9, 3.05, 3.0, [["도체 (S7)", "값"], ["목표 F_t [N]", fmt(v.get("F_target"), 3)], ["유지 F [N]", fmt(v.get("F_hold"), 3)],
                              ["파지 중 최대 [N]", fmt(v.get("F_peak"), 3)], ["F_max [N]", fmt(v.get("F_max"), 3)],
                              ["F_max 초과", fmt(v.get("exceeded"))]], [1.8, 1.2], 10, 0.32)
    text(s, 9.9, 5.15, 3.0, 1.9, ["유지 힘이 목표보다 큰 것은 F̂ 편향 (MoE).",
                                  "식별: 이 시뮬은 정답 라벨. 판별기(ΔL 잔차)는 도체·유전체만 가름."], 10, bullet=True)

    # 시나리오 2: 인체
    s = prs.slides.add_slide(blank); title(s, "시나리오 2 (인체): 탐지 → 접근 → 접촉 → 상호작용 (S11)", True)
    s_flow(s, 1.15, [("탐지", "근접 d̂, 움직임 ḋ̂", "OPEN → APPROACH", "TDM·MoE 1 kHz"),
                     ("식별", "인체 (B단계 실측 필요)", "F_t 0.15·, F_max 0.3·F_block, v × 0.4", "반사 문턱 = 인체 F_max"),
                     ("접근", "d̂, ḋ̂", "느린 pre-shape, t_c 맞춤", "자유 LQG (ε)"),
                     ("접촉", "게이트 ∨ TENG", "GRASP (dF/dt 상한)", "무충격 전환"),
                     ("상호작용", "F̂, 손 움직임", "(a) 안전 + 약한 힘 유지 (b) 어드미턴스 따라가기", "반사 1 kHz 항상")])
    image(s, OUT / "S11.png", 0.4, 3.0, w=7.2)
    r11 = list((get(P, "results_s11") or {}).values())
    r11 = (r11 + [{}, {}])[:2]
    rows = [["S11 (손 ±6 mm, 0.25 Hz)", "(a) 힘 유지 C", "(b) 어드미턴스"]]
    for k, lab, nd in (("contact_both_pct", "두 손가락 접촉 유지 [%]", 3), ("rmse_F_N", "F_t 대비 RMSE [N]", 3),
                       ("F_peak", "최대 F [N]", 3), ("t_over_s", "F_max 초과 시간 [s]", 2), ("n_trips", "반사 배기 횟수", 3)):
        rows.append([lab, *[fmt(v_.get(k), nd) for v_ in r11]])
    table(s, 7.8, 3.05, 5.1, rows, [2.5, 1.3, 1.3], 10, 0.32)
    text(s, 7.8, 5.1, 5.1, 2.0, ["(b) 어드미턴스는 손이 밀면 물러나서 최대 힘이 F_max 근처에 머문다. (a)는 손이 밀 때 F_max를 넘는 순간이 있다.",
                                 "두 방식 모두 목표 힘 유지에는 실패: F̂ 편향(+1.5 N) > 목표 0.93 N → 반사·SAFETY 반복 (센서 한계, B단계 R1·R6).",
                                 "인체 접근 영상: 파지 시연(S7) 슬라이드."], 10, bullet=True)

    # S10 하위 반사
    s = prs.slides.add_slide(blank); title(s, "하위 제어기의 이점 (S10): 1 kHz 반사 vs 상위 지연 · 두절", True)
    image(s, OUT / "S10.png", 0.3, 1.1, w=12.7)
    r10 = get(P, "results_s10") or {}
    rows = [["지령 폭주 (손가락 B → 30 kPa)", "인체 최대 F [N]", "인체 초과 충격량 [N·s]", "도체 최대 F [N]", "도체 초과 충격량 [N·s]"]]
    for nm in ("상위 배기 · 지연 20 ms", "상위 배기 · 지연 200 ms", "상위 배기 · 통신 두절", "하위 반사 1 kHz", "하위 반사 1 kHz · 통신 두절"):
        h_, c_ = r10.get(f"human | {nm}", {}), r10.get(f"conductor | {nm}", {})
        rows.append([nm, fmt(h_.get("F_peak"), 3), fmt(h_.get("impulse_over_Ns"), 2), fmt(c_.get("F_peak"), 3), fmt(c_.get("impulse_over_Ns"), 2)])
    table(s, 0.5, 4.6, 7.6, rows, [2.8, 1.1, 1.3, 1.1, 1.3], 9, 0.29)
    text(s, 8.3, 4.6, 4.6, 2.6, ["구동기가 만드는 과부하(지령 폭주)에선 감지 지연만큼 힘이 계속 오른다 → 하위 반사가 최대 힘·충격량을 가장 줄이고, 통신이 끊겨도 동작.",
                                 "상위 지연 20 ms는 ITV 지연(10 ms)·시정수(50 ms)와 비슷해 차이가 작다. 지연 100 ms 이상·두절에서 차이가 커진다.",
                                 "손 급이동의 첫 피크는 수동 충돌(제어로 못 줄임). 그 뒤 힘은 안전 동작이 ε 열기면 남고(약 3.7 N) 배기면 빠진다(0.6 N).",
                                 "결론: 안전 동작은 배기, 실행은 하위(TDM 주기)에서. 반사 문턱 F_max는 상위가 재질로 정해 내려보낸다."], 10, bullet=True)

    s = prs.slides.add_slide(blank); title(s, "대시보드 영상: 망치 받기 · 팔 오잡기", True)
    su.s_videos(s, P)

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
                               ["접촉 LQR", "k_eq 격자 / K_I(격자)", fmt(get(P, "contact_design.grid") and
                                                                        [get(P, "contact_design.grid"), [v["KI"] for v in get(P, "contact_design.gains").values()]], 3),
                                "C_F = [0, k_eq], Bryson δF 0.4 N (가정)"],
                               ["RLS", "λ / k̂ 투영 / ε̂_c 범위", "(가정) 0.999 / 격자 / 진입값 ± 4 %", "F̂ 잡음 σ≈0.25 N 에 맞춘 느린 적응"],
                               ["상위", "v₀ [%/s]", "(가정) " + str(get(P, "det.v0")) if get(P, "det.v0") is not None else None, "가정값"]],
          [1.6, 2.2, 5.6, 2.9], 10, 0.37)

    # 21 실물 측정 계획
    s = prs.slides.add_slide(blank); title(s, "B단계: 실물 측정 계획 (물리량 → 바뀌는 값)")
    table(s, 0.5, 1.2, 12.3, [["ID", "실험", "측정 물리량", "바뀌는 값"], *REAL_PLAN], [0.8, 5.0, 3.6, 2.9], 12, 0.5)

    # 22 한계
    s = prs.slides.add_slide(blank); title(s, "한계와 다음 실험")
    text(s, 0.5, 1.2, 12.3, 5.8, LIMITS, 13, bullet=True)

    out_path = Path(out_path)
    prs.save(out_path)
    return out_path


if __name__ == "__main__":
    print(build())
