# -*- coding: utf-8 -*-
"""Paper/fig_sensor.py — 그림 0: 센서 기하 · 제작 공정 · 자극별 응답 시그니처.

내용 근거: 26.03.27 세미나 자료(p5–p8, p13) 및 26.08.20 그룹미팅 자료(p19, p22).
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

sys.stdout.reconfigure(encoding="utf-8")
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.linewidth": 0.8, "savefig.dpi": 300,
    "savefig.bbox": "tight", "figure.facecolor": "white",
})
C_L = "#FF8C00"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

UP, DOWN, DASH, ARROW = "↑", "↓", "—", "→"


def fig0():
    fig = plt.figure(figsize=(7.2, 4.7))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.02],
                          width_ratios=[1.05, 0.95], hspace=0.28, wspace=0.20)

    # ── (a) 코일 기하 + 표적 ────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0, 0])
    ax.set_xlim(-1.3, 11.2)
    ax.set_ylim(0.05, 6.5)
    ax.axis("off")
    ax.add_patch(Rectangle((0.8, 5.05), 8.0, 0.55, fc="#8f8f8f", ec="#333", lw=0.8))
    ax.text(4.8, 5.32, "target  ($L_t$, $R_t$)", ha="center", va="center",
            fontsize=7.0, color="white")

    x0, x1, y0, y1, pitch = 1.1, 8.5, 0.75, 3.55, 0.30
    px, py = [x0], [y0]
    for k in range(5):
        o = k * pitch
        px += [x1 - o, x1 - o, x0 + o, x0 + o]
        py += [y0 + o, y1 - o, y1 - o, y0 + o + pitch]
    ax.plot(px, py, color=C_L, lw=1.3, solid_joinstyle="miter")
    ax.plot([x0, x0, x0 - 1.05], [y0, y0 - 0.32, y0 - 0.32], color=C_L, lw=1.3)
    ax.plot([px[-1], x0 - 0.55, x0 - 0.55, x0 - 1.05],
            [py[-1], py[-1], y0 - 0.55, y0 - 0.55], color=C_L, lw=1.3)
    ax.text(-1.25, y0 - 0.05, "two-wire\nlead", fontsize=6.4, color="#555",
            ha="left", va="bottom")

    ax.annotate("", xy=(0.55, y0), xytext=(0.55, y1),
                arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(0.18, (y0 + y1) / 2, "a", fontsize=9, fontweight="bold",
            ha="center", va="center")
    ax.annotate("", xy=(x0, 4.15), xytext=(x1, 4.15),
                arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text((x0 + x1) / 2, 4.32, "b", fontsize=9, fontweight="bold", ha="center")
    ax.annotate("", xy=(9.35, y1), xytext=(9.35, 5.03),
                arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(9.65, (y1 + 5.03) / 2, "d", fontsize=9, fontweight="bold", va="center")
    ax.add_patch(plt.Circle((10.5, 2.2), 0.30, fc="#fff2e0", ec=C_L, lw=1.0))
    ax.annotate("2r", xy=(10.5, 2.2), xytext=(10.5, 1.20), fontsize=7.2,
                ha="center", arrowprops=dict(arrowstyle="-", lw=0.6))
    ax.text(-1.3, 6.22, "(a)  Planar rectangular spiral geometry",
            fontsize=8.6, fontweight="bold")

    # ── (b) 제작 공정 ───────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0, 1])
    ax.set_xlim(0, 10.8)
    ax.set_ylim(0.05, 6.5)
    ax.axis("off")
    steps = [("Step 1", "EGaIn DIW", "#fff2e0"),
             ("Step 2", "Bridging", "#eef4ff"),
             ("Step 3", "Covering", "#eaf7ec"),
             ("Step 4", "Wire insert / cut", "#f4f4f4")]
    for i, (s_, lab, c) in enumerate(steps):
        y = 5.05 - i * 1.30
        ax.add_patch(FancyBboxPatch((0.2, y), 6.3, 0.85, boxstyle="round,pad=0.05",
                                    fc=c, ec="#333", lw=0.8))
        ax.text(1.30, y + 0.43, s_, fontsize=7.2, fontweight="bold",
                va="center", ha="center")
        ax.text(4.35, y + 0.43, lab, fontsize=7.2, va="center", ha="center")
        if i < 3:
            ax.add_patch(FancyArrowPatch((3.35, y - 0.03), (3.35, y - 0.42),
                                         arrowstyle="-|>", mutation_scale=7,
                                         lw=0.8, color="#333"))
    ax.text(0, 6.22, "(b)  Fabrication process", fontsize=8.6, fontweight="bold")
    ax.text(6.85, 3.3,
            "bridging routes the\ninner terminal out\nover the windings\n"
            + ARROW + " two-wire\n    single electrode",
            fontsize=6.4, color="#c0392b", va="center")

    # ── (c) 자극별 응답 시그니처 ────────────────────────────────────────────
    ax = fig.add_subplot(gs[1, :])
    ax.axis("off")
    ax.text(0, 1.06, "(c)  Response signature of each stimulus",
            fontsize=8.6, fontweight="bold", transform=ax.transAxes)
    col = ["Stimulus", "$L$", "$R_s$ (AC)", "$R_{DC}$", "$V_{TENG}$",
           "Dominant mechanism"]
    data = [
        ["Stretching", UP, UP, UP, DASH,
         "length " + UP + ", section " + DOWN + " " + ARROW + " $R$ " + UP
         + " ; geometry " + ARROW + " $L$ " + UP],
        ["Conductor approach", DOWN, UP, DASH, DASH,
         "eddy-current loss " + ARROW + " reflected impedance"],
        ["Dielectric approach", UP, DASH, DASH, DASH,
         "permittivity / field redistribution (amplification)"],
        ["Contact (charged)", DASH, DASH, DASH, UP,
         "triboelectric charge transfer"],
        ["Compression", DOWN + "*", UP, UP, DASH,
         "local section " + DOWN + " ; $Q$ " + DOWN + " " + ARROW
         + " apparent $L$ " + UP],
    ]
    tb = ax.table(cellText=data, colLabels=col, loc="upper center",
                  cellLoc="center", bbox=[0, 0.02, 1, 0.95])
    tb.auto_set_font_size(False)
    tb.set_fontsize(6.6)
    widths = [0.235, 0.055, 0.085, 0.070, 0.080, 0.475]
    for (r, c), cell in tb.get_celld().items():
        cell.set_linewidth(0.5)
        cell.set_edgecolor("#999")
        cell.set_width(widths[c])
        if r == 0:
            cell.set_facecolor("#efefef")
            cell.set_text_props(fontweight="bold")
        if c in (0, 5):
            cell.set_text_props(ha="left")
            cell._text.set_x(0.025)

    path = os.path.join(OUT, "fig0_sensor.png")
    fig.savefig(path)
    plt.close(fig)
    print("  saved fig0_sensor.png")


if __name__ == "__main__":
    fig0()
