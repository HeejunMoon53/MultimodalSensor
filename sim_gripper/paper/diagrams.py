"""논문 다이어그램 F1–F3 (영문 라벨, PNG 300 dpi + SVG).

F1 전체 알고리즘 블록도 · F2 1 ms TDM 타이밍·모델 예산 · F3 상태 머신과 모달리티 역할.
실측 근거: 보드 로그 latency_us 중앙값 261 µs (STM32G473 @170 MHz), X-CUBE-AI 리포트 (gate/expert).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

COLOR_L, COLOR_R, COLOR_TENG = "#FF8C00", "#2CA02C", "#1F77B4"
INK, MUTED, LINE = "#222222", "#666666", "#9A9A9A"
FILL = {"sense": "#EEF3F8", "ai": "#F1ECF8", "info": "#F4F4F4", "ctrl": "#EEF6EE", "act": "#FBF1E6"}
MOD = {"Strain": "#8C564B", "Proximity": "#7B4FBF", "Force": "#D62728", "Contact": COLOR_TENG,
       "Material": "#17BECF"}

# X-CUBE-AI 리포트 (nn_decoupling/test0909_realtime/new/stm32_deploy_moe_v4/*_generate_report.txt)
BUDGET = {"gate": dict(params=68, macc=202, flash=272, ram=48),
          "expert_a": dict(params=674, macc=1154, flash=2696, ram=160),
          "expert_b": dict(params=674, macc=1154, flash=2696, ram=160)}
INFER_US = 261.3          # 보드 로그 moe_monitor_20260910_010437_test.csv latency_us 중앙값

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.unicode_minus": False,
                     "svg.fonttype": "none"})


def _save(fig, out_dir, name):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{name}.png", out_dir / f"{name}.svg"]
    fig.savefig(paths[0], dpi=300, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    plt.close(fig)
    return paths


def _box(ax, x, y, w, h, title, lines=(), fill="#FFFFFF", title_color=INK, fs=5.6, title_fs=6.4, gap=0.052,
         first=0.085):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                                fc=fill, ec=LINE, lw=0.8))
    ax.text(x + w / 2, y + h - 0.025, title, ha="center", va="top", fontsize=title_fs, weight="bold",
            color=title_color)
    for k, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - first - k * gap, ln, ha="center", va="top", fontsize=fs, color=INK)


def _arrow(ax, p0, p1, color=INK, text=None, style="-|>", lw=1.0, rad=0.0, tpos=0.5, toff=(0, 0.018), fs=6.5):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=8, color=color, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        x = p0[0] + (p1[0] - p0[0]) * tpos + toff[0]
        y = p0[1] + (p1[1] - p0[1]) * tpos + toff[1]
        ax.text(x, y, text, ha="center", va="bottom", fontsize=fs, color=color)


def _chip(ax, x, y, label, w=0.072, fs=5.6):
    ax.add_patch(FancyBboxPatch((x, y), w, 0.034, boxstyle="round,pad=0.002,rounding_size=0.01",
                                fc=MOD[label], ec="none"))
    ax.text(x + w / 2, y + 0.017, label, ha="center", va="center", fontsize=fs, color="white", weight="bold")


def fig1_architecture(out_dir):
    """F1: 단일 전극 센서 → TDM → Gate-MoE → 다중 모달리티 → 온보드 제어 → 액추에이터 (1 kHz 폐루프)."""
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
    top, bot = 0.86, 0.36
    h = top - bot
    ax.add_patch(FancyBboxPatch((0.142, 0.17), 0.702, 0.80, boxstyle="round,pad=0.004,rounding_size=0.015",
                                fc="none", ec="#4A4A4A", lw=1.0, ls=(0, (4, 3))))
    ax.text(0.152, 0.955, "On-board STM32G473 (170 MHz) · 1 kHz · no PC in the loop", fontsize=6.8,
            color="#4A4A4A", va="top", style="italic")
    _box(ax, 0.0, bot + 0.06, 0.125, h - 0.12, "Soft gripper",
         ["3 fingers", "TPU 60A bellows", "", "EGaIn spiral coil", "single electrode", "(2 wires)"], FILL["act"])
    # TDM
    _box(ax, 0.155, bot, 0.15, h, "TDM sensing", [], FILL["sense"])
    for k, (lab, col, sub) in enumerate([("L  (LDC1614)", COLOR_L, "I²C-DMA, 28-bit f"),
                                         ("V_TENG  (ADC)", COLOR_TENG, "100 µs window"),
                                         ("R_DC  (ADC)", COLOR_R, "100 µs, divider")]):
        y = top - 0.165 - k * 0.105
        ax.add_patch(FancyBboxPatch((0.165, y), 0.13, 0.085, boxstyle="round,pad=0.002,rounding_size=0.008",
                                    fc="white", ec=col, lw=1.1))
        ax.text(0.23, y + 0.058, lab, ha="center", fontsize=5.7, color=col, weight="bold")
        ax.text(0.23, y + 0.02, sub, ha="center", fontsize=5.0, color=MUTED)
    ax.text(0.23, bot + 0.03, "→ ΔL, ΔR, V", ha="center", fontsize=5.0, color=MUTED)
    # Decoupling
    _box(ax, 0.325, bot, 0.215, h, "Gate-MoE decoupling", [], FILL["ai"])
    ax.text(0.4325, top - 0.085, "Gate MLP: p(contact | ΔL, ΔR)", ha="center", fontsize=5.4)
    ax.text(0.4325, top - 0.125, "∨ TENG contact latch", ha="center", fontsize=5.4, color=COLOR_TENG)
    for k, (t, sub) in enumerate([("Expert A (no contact)", "ΔL, ΔR, EMA → ε̂, d̂"),
                                  ("Expert B (contact)", "ΔL, ΔR, EMA → ε̂, F̂")]):
        y = top - 0.26 - k * 0.105
        ax.add_patch(FancyBboxPatch((0.338, y), 0.189, 0.085, boxstyle="round,pad=0.002,rounding_size=0.008",
                                    fc="white", ec="#7B4FBF", lw=0.9))
        ax.text(0.4325, y + 0.058, t, ha="center", fontsize=5.5, weight="bold")
        ax.text(0.4325, y + 0.02, sub, ha="center", fontsize=5.3)
    ax.text(0.4325, bot + 0.03, "1,416 params · 5.5 KB · 261 µs", ha="center", fontsize=5.0, color=MUTED)
    # Information
    _box(ax, 0.56, bot, 0.11, h, "Modalities", [], FILL["info"])
    for k, lab in enumerate(["Strain", "Proximity", "Force", "Contact", "Material"]):
        _chip(ax, 0.569, top - 0.12 - k * 0.062, lab, w=0.092, fs=5.4)
    ax.text(0.615, bot + 0.03, "5 outputs / finger", ha="center", fontsize=4.8, color=MUTED)
    # Controller
    _box(ax, 0.69, bot, 0.14, h, "Controller", [], FILL["ctrl"])
    for k, (t, b) in enumerate([("State select (FSM)", True), ("Pre-shape:", True), ("proximity-scheduled", False),
                                ("Admittance:", True), ("material-adaptive F_t", False), ("Safety layer", True)]):
        ax.text(0.76, top - 0.085 - k * 0.06, t, ha="center", fontsize=5.4, weight="bold" if b else "normal")
    # Actuator
    _box(ax, 0.865, bot + 0.06, 0.135, h - 0.12, "Actuator",
         ["u ∈ [0, 1]", "pneumatic", "0–200 kPa", "(or tendon)", "τ = α(P − P₀)"], FILL["act"])
    y = top - 0.20
    _arrow(ax, (0.125, y), (0.155, y))
    _arrow(ax, (0.305, y), (0.325, y))
    _arrow(ax, (0.54, y), (0.56, y))
    _arrow(ax, (0.67, y), (0.69, y))
    _arrow(ax, (0.83, y), (0.865, y))
    ax.add_patch(FancyArrowPatch((0.93, bot + 0.06), (0.06, bot + 0.06), arrowstyle="-|>", mutation_scale=8,
                                 color=MUTED, lw=1.0, connectionstyle="arc3,rad=-0.22"))
    ax.text(0.5, 0.20, "physical interaction: bending · approach · contact · pressing", ha="center",
            fontsize=5.7, color=MUTED, style="italic")
    ax.text(0.0, 0.06, "Sensing, inference and control share the 1 kHz TDM period; inference measured on board "
            "(median 261 µs, max 265 µs).", fontsize=5.3, color=MUTED)
    return _save(fig, out_dir, "fig1_architecture")


def fig2_timing_budget(out_dir):
    """F2: 1 ms 주기 안의 측정·추론·제어 타이밍 + 모델 예산 표."""
    fig = plt.figure(figsize=(7.2, 2.9))
    ax = fig.add_axes([0.07, 0.30, 0.60, 0.62])
    lanes = [("LDC1614 read (I²C-DMA)", 0, 200, COLOR_L),
             ("TENG window (ADC-DMA)", 0, 100, COLOR_TENG),
             ("R_DC window (ADC-DMA)", 100, 200, COLOR_R),
             ("MoE inference (gate + EMA + expert)", 200, 200 + INFER_US, "#7B4FBF"),
             ("Material + controller + command*", 200 + INFER_US, 200 + INFER_US + 20, "#2E7D5B"),
             ("Idle / UART streaming (optional)", 200 + INFER_US + 20, 1000, "#D9D9D9")]
    for k, (lab, a, b, c) in enumerate(lanes):
        yk = len(lanes) - 1 - k
        ax.barh(yk, b - a, left=a, height=0.62, color=c, edgecolor="white", lw=1.5)
        ax.text(-12, yk, lab, ha="right", va="center", fontsize=6.8)
        if b - a > 60:
            ax.text((a + b) / 2, yk, f"{b - a:.0f} µs", ha="center", va="center", fontsize=6.4,
                    color="white" if c not in ("#D9D9D9",) else INK, weight="bold")
    ax.axvline(1000, color=INK, lw=0.8, ls="--")
    ax.text(1000, len(lanes) - 0.35, " next TIM7 tick", fontsize=6.2, va="bottom")
    ax.set_xlim(0, 1050), ax.set_ylim(-0.6, len(lanes) - 0.3)
    ax.set_yticks([])
    ax.set_xlabel("time within one TDM cycle [µs]")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    fig.text(0.07, 0.0, "*controller not yet on the board: estimated (<20 µs, a few hundred FLOPs). "
             "Measurement slots run in parallel (DMA).", fontsize=5.6, color=MUTED)
    # 예산 표
    tb = fig.add_axes([0.70, 0.18, 0.29, 0.74])
    tb.axis("off")
    rows = [["", "params", "MACC", "Flash", "RAM"]]
    for k, v in BUDGET.items():
        rows.append([k.replace("_", " "), f"{v['params']}", f"{v['macc']:,}", f"{v['flash']:,} B", f"{v['ram']} B"])
    tot = {f: sum(v[f] for v in BUDGET.values()) for f in ("params", "flash")}
    rows.append(["total", f"{tot['params']:,}", "1,356†", f"{tot['flash']:,} B", "160 B"])
    t = tb.table(cellText=rows, loc="upper center", cellLoc="center", colWidths=[0.24, 0.17, 0.19, 0.24, 0.16])
    t.auto_set_font_size(False)
    t.set_fontsize(5.6)
    t.scale(1.0, 1.4)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#CFCFCF")
        if r == 0 or r == len(rows) - 1:
            cell.set_text_props(weight="bold")
    tb.text(0.5, 0.22, "X-CUBE-AI (float32), STM32G473CBT6\n†1 inference = gate + one expert\n"
            f"measured latency: {INFER_US:.0f} µs (median), 265 µs (max)\n"
            "≈ 26 % of the 1 ms TDM period", ha="center", va="top", fontsize=5.8, color=INK,
            transform=tb.transAxes)
    return _save(fig, out_dir, "fig2_timing_budget")


def fig3_state_machine(out_dir):
    """F3: 상태 머신 — 각 상태의 제어 법칙과 그것을 구동하는 모달리티."""
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
    states = [
        ("OPEN", ["u → u_open", "(fingers relaxed)"], []),
        ("APPROACH", ["closing speed set by d̂:", "fast far, slow near", "material from ΔL", "residual (latched)"],
         ["Proximity", "Material", "Strain"]),
        ("GRASP", ["admittance", "B_a·u̇ = F_t − F̂", "F_t by material:", "metal 4 N, other 1.5 N"],
         ["Force", "Contact", "Material"]),
        ("HOLD / LIFT", ["admittance holds F_t", "lift 4 cm", "slip → F̂ drops", "→ u rises"], ["Force", "Contact"]),
        ("RELEASE", ["u → u_open", "TENG (−) pulse", "confirms release"], ["Contact"]),
    ]
    w, gap, y0, h = 0.17, 0.0325, 0.30, 0.40
    xs = [0.005 + k * (w + gap) for k in range(len(states))]
    for (name, lines, mods), x in zip(states, xs):
        _box(ax, x, y0, w, h, name, lines, FILL["ctrl"] if mods else FILL["info"], fs=5.3, title_fs=6.4,
             gap=0.05, first=0.09)
        for k, mlab in enumerate(mods):
            _chip(ax, x + 0.006 + k * 0.0535, y0 + 0.015, mlab, w=0.051, fs=4.5)
    labels = ["approach cmd", "all fingers in contact\n(gate ∨ TENG)", "lift cmd", "release cmd"]
    for k, lab in enumerate(labels):
        p0, p1 = (xs[k] + w * 0.7, y0 + h), (xs[k + 1] + w * 0.3, y0 + h)
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=8, color=INK, lw=0.9,
                                     connectionstyle="arc3,rad=-0.45"))
        ax.text((p0[0] + p1[0]) / 2, y0 + h + 0.115, lab, ha="center", va="bottom", fontsize=5.4, color=MUTED)
    ax.add_patch(FancyArrowPatch((xs[1] + w / 2, y0), (xs[4] + w / 2, y0), arrowstyle="-|>", mutation_scale=8,
                                 color="#B00020", lw=0.9, connectionstyle="arc3,rad=0.18"))
    ax.text(0.5, 0.135, "no contact within 3 s → RELEASE (grasp failed)", ha="center", fontsize=5.6, color="#B00020")
    ax.add_patch(FancyBboxPatch((0.005, 0.01), 0.99, 0.11, boxstyle="round,pad=0.004,rounding_size=0.012",
                                fc="#FDECEC", ec="#B00020", lw=0.8))
    ax.text(0.5, 0.085, "Safety layer — every state, highest priority:  F_lp > F_max(material)  ∨  dF_lp/dt > 50 N/s  ∨  "
            "ε̂ ∉ [0, 30] %  →  open at 2·u̇_max", ha="center", fontsize=5.6, color="#7A0016")
    ax.text(0.5, 0.035, "F_lp = low-pass F̂ (τ = 50 ms).  Per-finger loop at 1 kHz; |Δu| ≤ u̇_max·T_s on every path, so "
            "gate flicker cannot kick the actuator.", ha="center", fontsize=5.2, color="#7A0016")
    return _save(fig, out_dir, "fig3_state_machine")
