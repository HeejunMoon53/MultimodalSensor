# -*- coding: utf-8 -*-
"""Paper/make_figures.py - 논문용 그림 일괄 생성 (실측 데이터 기반).
색상 컨벤션(CLAUDE.md): L=#FF8C00(주황), R=#2CA02C(초록), TENG=#1F77B4(파랑)
축/범례는 영문 - 국문/영문 두 버전 원고에서 동일 그림을 공유한다.
"""
import glob, json, os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

sys.stdout.reconfigure(encoding="utf-8")
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.linewidth": 0.8, "axes.grid": True, "grid.alpha": 0.25,
    "savefig.dpi": 300, "savefig.bbox": "tight", "figure.facecolor": "white",
})
C_L, C_R, C_V = "#FF8C00", "#2CA02C", "#1F77B4"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NN = os.path.join(ROOT, "nn_decoupling")
OUT = os.path.join(ROOT, "Paper", "figures")
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p)
    plt.close(fig)
    print("  saved", name)


# Fig 1 - TDM cycle timing diagram + signal-path schematic
def fig1():
    fig, (ax0, ax) = plt.subplots(2, 1, figsize=(7.2, 4.4),
                                  gridspec_kw={"height_ratios": [1.0, 1.15]})
    ax0.set_xlim(0, 10.2)
    ax0.set_ylim(0, 3.2)
    ax0.axis("off")

    def box(x, y, w, h, t, fc="#f4f4f4"):
        ax0.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                     fc=fc, ec="#333", lw=0.9))
        ax0.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=7.4)

    def arrow(x1, y1, x2, y2):
        ax0.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                      mutation_scale=8, lw=0.9, color="#333"))

    box(0.05, 1.05, 1.5, 0.75, "EGaIn spiral\ncoil (2-wire)", "#fff2e0")
    box(1.95, 1.05, 1.1, 0.75, "ADG734\nMUX", "#eef4ff")
    box(3.55, 1.98, 2.0, 0.62, "LDC1614  (I$^2$C DMA)", "#ffd9a8")
    box(3.55, 1.12, 2.0, 0.62, "OPAMP + ADC  (TENG)", "#cfe0f5")
    box(3.55, 0.26, 2.0, 0.62, "OPAMP + ADC  ($R_{DC}$)", "#cfe9d4")
    box(5.95, 1.05, 1.75, 0.75, "STM32G473CBT6\nTIM7 1 ms ISR", "#f0f0f0")
    box(8.10, 1.05, 2.0, 0.75, "on-board MoE\ninference + UART", "#fdeaea")
    arrow(1.55, 1.42, 1.95, 1.42)
    arrow(3.05, 1.62, 3.55, 2.20)
    arrow(3.05, 1.42, 3.55, 1.42)
    arrow(3.05, 1.22, 3.55, 0.62)
    arrow(5.55, 2.20, 5.95, 1.66)
    arrow(5.55, 1.42, 5.95, 1.42)
    arrow(5.55, 0.62, 5.95, 1.18)
    arrow(7.70, 1.42, 8.10, 1.42)
    ax0.text(0.05, 2.95, "(a)  Single-electrode signal path", fontsize=9, fontweight="bold")

    ax.set_xlim(-330, 1060)
    ax.set_ylim(-0.35, 3.35)
    for name, y in [("MUX / analog", 2.55), ("ADC (DMA)", 1.70),
                    ("I$^2$C (DMA)", 0.85), ("CPU", 0.00)]:
        ax.text(-40, y + 0.17, name, ha="right", va="center", fontsize=7.4)

    def blk(x, w, y, t, c, h=0.34, fs=7.0):
        ax.add_patch(Rectangle((x, y), w, h, fc=c, ec="#333", lw=0.7))
        if t:
            ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)

    blk(0, 6, 2.55, "", "#999")
    blk(6, 144, 2.55, "LDC mode", "#ffd9a8")
    blk(150, 150, 2.55, "TENG mode", "#cfe0f5")
    blk(300, 150, 2.55, "R mode", "#cfe9d4")
    blk(450, 550, 2.55, "idle (coil floating)", "#f0f0f0")
    blk(150, 150, 1.70, "TENG sample", "#cfe0f5", fs=6.6)
    blk(300, 150, 1.70, "$R_{DC}$ sample", "#cfe9d4", fs=6.6)
    blk(6, 194, 0.85, "LDC1614 read (28-bit)", "#ffd9a8", fs=6.6)
    blk(452, 260, 0.00, "MoE inference 260 us", "#f7c9c9", fs=6.6)
    ax.annotate("", xy=(0, 3.12), xytext=(1000, 3.12),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color="#333"))
    ax.text(500, 3.18, "TDM period = 1000 us (TIM7)", ha="center", fontsize=7.4)
    ax.annotate("MUX settling 6 us", xy=(6, 2.53), xytext=(120, 2.15),
                fontsize=6.4, color="#444",
                arrowprops=dict(arrowstyle="-", lw=0.6, color="#777"))
    ax.set_xlabel("time within one TDM cycle (us)")
    ax.set_xticks([0, 200, 400, 600, 800, 1000])
    ax.set_yticks([])
    ax.grid(axis="x", alpha=0.2)
    ax.text(-330, 3.42, "(b)  Time-division measurement schedule",
            fontsize=9, fontweight="bold")
    for sp in ("left", "right", "top"):
        ax.spines[sp].set_visible(False)
    save(fig, "fig1_tdm.png")


METAL_OFF, HAND_OFF, L0MM = 52.0, 30.0, 120.0


def _load(d, off):
    rows = []
    for f in sorted(glob.glob(os.path.join(d, "*.csv"))):
        x = pd.read_csv(f)
        if len(x) < 5:
            continue
        x["strain_pct"] = (x["xa_mm"].abs() * 2) / L0MM * 100
        x["prox_mm"] = (off + x["z_mm"]).round(2)
        rows.append(x)
    return pd.concat(rows, ignore_index=True)


def _base(df):
    r = df[(df.strain_pct <= 0.5) & (df.prox_mm >= df.prox_mm.max() - 3)]
    if len(r) == 0:
        r = df
    return float(r.ldc_raw.median()), float(r.r_raw.median())


def _delta(df, L0, R0):
    df = df.copy()
    df["dL_pct"] = ((L0 / df.ldc_raw.clip(lower=1)) ** 2 - 1) * 100
    df["dR_pct"] = (df.r_raw - R0) / R0 * 100
    return df


def _grid(df, sb, pb):
    S, P = np.meshgrid((sb[:-1] + sb[1:]) / 2, (pb[:-1] + pb[1:]) / 2)
    ZL = np.full(S.shape, np.nan)
    ZR = np.full(S.shape, np.nan)
    si = np.digitize(df.strain_pct, sb) - 1
    pi = np.digitize(df.prox_mm, pb) - 1
    for a in range(S.shape[0]):
        for b in range(S.shape[1]):
            m = (pi == a) & (si == b)
            if m.sum() >= 1:
                ZL[a, b] = df.dL_pct[m].mean()
                ZR[a, b] = df.dR_pct[m].mean()
    # 격자 결측(bin에 샘플이 없는 칸)은 strain 축 -> proximity 축 순으로 선형 보간
    def fill(Z):
        D = pd.DataFrame(Z)
        D = D.interpolate(axis=1, limit_direction="both")
        D = D.interpolate(axis=0, limit_direction="both")
        return D.values
    return S, P, fill(ZL), fill(ZR)


def fig2():
    base = os.path.join(NN, "data", "metal")
    mp1 = _load(os.path.join(base, "metal", "p1_strain_discrete"), METAL_OFF)
    mp2 = _load(os.path.join(base, "metal", "p2_proximity_discrete"), METAL_OFF)
    hp1 = _load(os.path.join(base, "hand", "p1_strain_discrete"), HAND_OFF)
    hp2 = _load(os.path.join(base, "hand", "p2_proximity_discrete"), HAND_OFF)
    L0m, R0m = _base(mp1)
    L0h, R0h = _base(hp1)
    M = pd.concat([_delta(mp1, L0m, R0m), _delta(mp2, L0m, R0m)], ignore_index=True)
    H = pd.concat([_delta(hp1, L0h, R0h), _delta(hp2, L0h, R0h)], ignore_index=True)
    sb = np.arange(-0.85, 32.0, 1.7)
    Sm, Pm, ZmL, ZmR = _grid(M, sb, np.arange(0, 54, 1.5))
    Sh, Ph, ZhL, ZhR = _grid(H, sb, np.arange(0, 31.5, 1.0))
    fig, axs = plt.subplots(2, 2, figsize=(7.0, 4.6))
    panels = [
        (Sm, Pm, ZmL, "(a) Metal target - $\\Delta L/L_0$ (%)", "PuOr_r", True),
        (Sm, Pm, ZmR, "(b) Metal target - $\\Delta R/R_0$ (%)", "Greens", False),
        (Sh, Ph, ZhL, "(c) Hand target - $\\Delta L/L_0$ (%)", "PuOr_r", True),
        (Sh, Ph, ZhR, "(d) Hand target - $\\Delta R/R_0$ (%)", "Greens", False),
    ]
    for ax, (S, P, Z, ttl, cm, div) in zip(axs.ravel(), panels):
        Zm = np.ma.masked_invalid(Z)
        if div:
            v = float(np.nanmax(np.abs(Z)))
            pc = ax.pcolormesh(S, P, Zm, cmap=cm, shading="auto", vmin=-v, vmax=v)
        else:
            pc = ax.pcolormesh(S, P, Zm, cmap=cm, shading="auto")
        cs = ax.contour(S, P, Zm, colors="k", linewidths=0.4, alpha=0.5)
        ax.clabel(cs, fontsize=5.5, fmt="%.0f")
        fig.colorbar(pc, ax=ax, pad=0.02)
        ax.set_title(ttl, fontsize=8.2)
        ax.set_xlabel("strain (%)")
        ax.set_ylabel("proximity d (mm)")
    fig.tight_layout()
    save(fig, "fig2_surfaces.png")
    st = dict(metal_dL=[float(M.dL_pct.min()), float(M.dL_pct.max())],
              metal_dR=[float(M.dR_pct.min()), float(M.dR_pct.max())],
              hand_dL=[float(H.dL_pct.min()), float(H.dL_pct.max())],
              hand_dR=[float(H.dR_pct.min()), float(H.dR_pct.max())],
              n_metal=int(len(M)), n_hand=int(len(H)))
    json.dump(st, open(os.path.join(OUT, "fig2_stats.json"), "w"), indent=1)
    print("  ", st)


def fig3():
    d = pd.read_csv(os.path.join(NN, "pressure_0805test", "test0805_dataset",
                                 "mms_20260806_200653.csv"))
    d["strain_pct"] = (d.ya_mm + d.yb_mm) / L0MM * 100
    d["F"] = -d.Fz_N
    d["F"] = d.F - d.loc[d.z_mm >= 0, "F"].mean()
    d["contact"] = (d.z_mm < 0).astype(int)
    d["cyc"] = (d.strain_pct.round(3) != d.strain_pct.round(3).shift(1)).cumsum()
    sizes = d.groupby("cyc").size()
    good = sizes[sizes >= 500].index
    lo = d[(d.cyc.isin(good)) & (d.strain_pct < 1)]
    hi = d[(d.cyc.isin(good)) & (d.strain_pct > 29)]
    fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.35))
    for ax, sub, ttl in [(axs[0], lo, "(a) strain = 0 %"), (axs[1], hi, "(b) strain = 30 %")]:
        s = sub[sub.contact == 1]
        ax.plot(s.F, s.dL_pct, ".", ms=1.1, color=C_L, alpha=.55)
        a2 = ax.twinx()
        a2.plot(s.F, s.dR_pct, ".", ms=1.1, color=C_R, alpha=.55)
        a2.grid(False)
        ax.set_title(ttl, fontsize=8.2)
        ax.set_xlabel("contact force $F_z$ (N)")
        ax.set_ylabel("$\\Delta L/L_0$ (%)", color=C_L)
        a2.set_ylabel("$\\Delta R/R_0$ (%)", color=C_R)
        ax.tick_params(axis="y", colors=C_L)
        a2.tick_params(axis="y", colors=C_R)
    seg = None
    for c in good:
        s = d[(d.cyc == c) & (d.contact == 1)]
        if len(s) > 400:
            seg = s
            break
    if seg is not None:
        z = seg.z_mm.values
        t = seg.t_s.values - seg.t_s.values[0]
        deep = np.abs(z - z.min()) < 0.05
        i0 = int(np.argmax(deep))
        j = i0
        while j + 1 < len(deep) and deep[j + 1]:
            j += 1
        tt = t[i0:j + 1] - t[i0]
        yy = seg.dR_pct.values[i0:j + 1]
        # dwell 끝의 릴리즈 전이(마지막 3%)는 완화 피팅에서 제외
        k = max(20, int(len(tt) * 0.97))
        tt, yy = tt[:k], yy[:k]
        axs[2].plot(tt, yy, color=C_R, lw=1.0, label="measured $\\Delta R$")
        if len(tt) > 20:
            # y = A + B*exp(-t/tau) 를 tau 그리드 위에서 최소제곱으로 피팅
            best = None
            for tau in np.linspace(0.15, 6.0, 400):
                X = np.column_stack([np.ones_like(tt), np.exp(-tt / tau)])
                c, *_ = np.linalg.lstsq(X, yy, rcond=None)
                e = float(np.sum((X @ c - yy) ** 2))
                if best is None or e < best[0]:
                    best = (e, tau, c)
            _, tau, c = best
            axs[2].plot(tt, c[0] + c[1] * np.exp(-tt / tau), "k--", lw=1.1,
                        label="SLS fit, tau = %.2f s" % tau)
            print("   dwell relaxation fit: tau = %.3f s" % tau)
        axs[2].set_xlabel("dwell time at fixed depth (s)")
        axs[2].set_ylabel("$\\Delta R/R_0$ (%)")
        axs[2].set_title("(c) viscoelastic relaxation", fontsize=8.2)
        axs[2].legend(fontsize=6.2, frameon=False)
    fig.tight_layout()
    save(fig, "fig3_pressure.png")
    out = {}
    for lab, sub in [("eps0", lo), ("eps30", hi)]:
        s = sub[sub.contact == 1]
        if len(s) > 50:
            out[lab] = dict(F_max=float(s.F.max()),
                            dR_span=float(s.dR_pct.max() - s.dR_pct.min()),
                            dL_min=float(s.dL_pct.min()),
                            dL_at_Fmax=float(s.dL_pct.values[int(np.argmax(s.F.values))]))
    json.dump(out, open(os.path.join(OUT, "fig3_stats.json"), "w"), indent=1)
    print("  ", out)


def fig4():
    r = json.load(open(os.path.join(NN, "checkpoints", "arch_search_results.json")))
    p = np.array([x["params"] for x in r])
    m = np.array([x["mae_d"] for x in r])
    n = [x["name"] for x in r]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.scatter(p, m, s=22, color=C_V, zorder=3, ec="k", lw=.4)
    ax.scatter([50306], [1.783], s=50, marker="D", color="#888", ec="k", lw=.4,
               zorder=3, label="sklearn MLP (50,306 par.)")
    for x, y, t in zip(p, m, n):
        if t in ("nano", "tiny-deep", "small", "medium-deep", "large", "base"):
            ax.annotate(t, (x, y), textcoords="offset points", xytext=(3, 3), fontsize=6)
    md = [x for x in r if x["name"] == "medium-deep"][0]
    ax.scatter([md["params"]], [md["mae_d"]], s=70, facecolor="none", ec="#d62728",
               lw=1.3, zorder=4, label="Pareto knee (medium-deep)")
    ax.set_xscale("log")
    ax.set_xlabel("parameters (log scale)")
    ax.set_ylabel("proximity MAE d (mm)")
    ax.legend(fontsize=6, frameon=False, loc="upper right")
    fig.tight_layout()
    save(fig, "fig4_pareto.png")


def fig5():
    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    ax.axis("off")
    ax.set_xlim(0, 10.4)
    ax.set_ylim(0, 3.2)

    def box(x, y, w, h, t, fc, fs=7.2):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                    fc=fc, ec="#333", lw=0.9))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)

    def ar(x1, y1, x2, y2, c="#333", ls="-"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=8, lw=0.9, color=c,
                                     linestyle=ls, shrinkA=0, shrinkB=0))

    box(0.05, 1.15, 1.30, 0.80,
        "$\\Delta L/L_0$\n$\\Delta R/R_0$\n(1 kHz)", "#f6f6f6")
    box(1.75, 0.15, 1.45, 0.65, "causal EMA\n$\\tau$ = 1.01 s", "#eef4ff")
    box(3.55, 2.30, 1.60, 0.62, "Gate  2-8-4-1\n(65 par.)", "#fdeaea")
    box(3.55, 0.55, 1.60, 0.62,
        "feature vector\n[$\\Delta L$, $\\Delta R$, EMA]", "#fafafa", fs=6.6)
    box(5.85, 1.75, 2.15, 0.62,
        "Expert A - non-contact\n4-24-16-8-2 (674 par.)", "#eaf1fb", fs=6.8)
    box(5.85, 0.70, 2.15, 0.62,
        "Expert B - contact\n4-24-16-8-2 (674 par.)", "#fdeeea", fs=6.8)
    box(8.55, 1.10, 1.80, 0.95,
        "strain (%)\nd (mm) or F (N)\nUART / control", "#f0f0f0")

    ar(1.35, 1.42, 1.75, 0.62)              # input -> EMA
    ar(1.35, 1.68, 3.55, 2.56)              # input -> gate
    ar(1.35, 1.30, 3.55, 0.92)              # input -> feature vector
    ar(3.20, 0.48, 3.55, 0.72)              # EMA -> feature vector
    ar(5.15, 1.00, 5.85, 1.90)              # features -> Expert A
    ar(5.15, 0.80, 5.85, 1.05)              # features -> Expert B
    ar(5.30, 2.28, 5.90, 2.40, c="#c0392b", ls=(0, (3, 2)))
    ar(5.30, 2.28, 5.90, 1.36, c="#c0392b", ls=(0, (3, 2)))
    ax.text(5.62, 2.62, "route", fontsize=6.3, color="#c0392b", ha="center")
    ar(4.20, 2.28, 2.75, 0.84, c="#c0392b")
    ax.text(3.05, 1.62, "EMA reset on\nmode change", fontsize=6.3,
            color="#c0392b", ha="center")
    ar(8.00, 2.06, 8.55, 1.85)
    ar(8.00, 1.01, 8.55, 1.35)
    ax.text(0.05, 3.02,
            "Mixture-of-Experts decoupler: 1,413 parameters, float32, executed on the MCU",
            fontsize=8.4, fontweight="bold")
    save(fig, "fig5_moe.png")


def r2(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    s = ((y - y.mean()) ** 2).sum()
    return float(1 - ((y - p) ** 2).sum() / s) if s > 0 else float("nan")


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(p, float)) ** 2)))


def load_rt(f):
    d = pd.read_csv(os.path.join(NN, "test0816_RealtimeDecoupling", f))
    d = d[d["mode"].isin([0, 1])]
    d = d[(d.strain_pct.between(-5, 35)) & (d.dL_pct.abs() < 50) & (d.dR_pct.abs() < 50)
          & (d.gate_proba.between(0, 1))]
    d = d[np.where(d["mode"] == 1, d.value.between(-20, 20), d.value.between(-20, 30))]
    d = d.copy()
    d["contact"] = (d.Z_mm <= -0.2).astype(int)
    off = d.loc[d.contact == 0, "Fz_act_N"].mean()
    d["F_true"] = -(d.Fz_act_N - off)
    return d.reset_index(drop=True)


def fig6():
    d = load_rt("moe_monitor_20260819_153948.csv")
    d = d.assign(t=d.t_s - d.t_s.min())
    fig, axs = plt.subplots(4, 1, figsize=(7.0, 5.0), sharex=True)
    axs[0].plot(d.t, d.dL_pct, lw=.5, color=C_L)
    a2 = axs[0].twinx()
    a2.plot(d.t, d.dR_pct, lw=.5, color=C_R)
    a2.grid(False)
    axs[0].set_ylabel("$\\Delta L/L_0$ (%)", color=C_L)
    a2.set_ylabel("$\\Delta R/R_0$ (%)", color=C_R)
    axs[0].set_title("(a) raw TDM signals (acquired on-board at 1 kHz, logged at 100 Hz)",
                     fontsize=8.2)
    axs[1].plot(d.t, d.strain_act_pct, lw=1.0, color="#555", label="ground truth")
    axs[1].plot(d.t, d.strain_pct, lw=.5, color=C_L, alpha=.85, label="on-board estimate")
    axs[1].set_ylabel("strain (%)")
    axs[1].set_ylim(-3, 34)
    axs[1].legend(fontsize=6.2, ncol=2, loc="lower right", framealpha=0.9)
    axs[1].set_title("(b) strain", fontsize=8.2)
    a = d[d["mode"] == 0]
    axs[2].plot(d.t, d.Z_mm, lw=1.0, color="#555")
    axs[2].plot(a.t, a.value, ".", ms=.6, color=C_V, alpha=.6)
    axs[2].set_ylabel("distance d (mm)")
    axs[2].set_title("(c) proximity (Expert A)", fontsize=8.2)
    b = d[d["mode"] == 1]
    axs[3].plot(d.t, d.F_true, lw=.8, color="#555")
    axs[3].plot(b.t, b.value, ".", ms=.8, color="#d62728", alpha=.7)
    axs[3].set_ylabel("force F (N)")
    axs[3].set_xlabel("time (s)")
    axs[3].set_title("(d) contact force (Expert B)", fontsize=8.2)
    # Part 경계 표시: Part1 근접 스윕 / Part2 인장 스윕 / Part3 동시 자극
    for ax in axs:
        ax.margins(x=0.005)
        for xb in (398.5, 733.0):
            ax.axvline(xb, color="#777", ls=":", lw=0.9)
    for xt, lab in [(200, "Part 1: proximity sweeps"),
                    (565, "Part 2: strain sweeps"),
                    (772, "Part 3: both")]:
        axs[0].text(xt, axs[0].get_ylim()[1] * 0.98, lab, fontsize=6.6,
                    ha="center", va="top", color="#444")
    fig.tight_layout()
    save(fig, "fig6_realtime.png")


def fig7():
    fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.4))
    d = load_rt("moe_monitor_20260819_153948.csv")
    t = d.t_s - d.t_s.min()
    p1 = d[(t >= 0) & (t <= 397)]
    a = p1[p1["mode"] == 0]
    b = d[d["mode"] == 1]
    axs[0].plot(p1.strain_act_pct, p1.strain_pct, ".", ms=.8, color=C_L, alpha=.5)
    axs[0].plot([0, 32], [0, 32], "k--", lw=.8)
    axs[0].set_xlabel("true strain (%)")
    axs[0].set_ylabel("estimated strain (%)")
    axs[0].set_title("(a) strain, Part 1", fontsize=8.2)
    axs[1].plot(a.Z_mm, a.value, ".", ms=.8, color=C_V, alpha=.5)
    axs[1].plot([0, 26], [0, 26], "k--", lw=.8)
    axs[1].set_xlabel("true d (mm)")
    axs[1].set_ylabel("estimated d (mm)")
    axs[1].set_title("(b) proximity, Part 1", fontsize=8.2)
    axs[2].plot(b.F_true, b.value, ".", ms=.8, color="#d62728", alpha=.5)
    lim = [float(min(b.F_true.min(), 0)), float(b.F_true.max())]
    axs[2].plot(lim, lim, "k--", lw=.8)
    axs[2].set_xlabel("true F (N)")
    axs[2].set_ylabel("estimated F (N)")
    axs[2].set_title("(c) contact force", fontsize=8.2)
    fig.tight_layout()
    save(fig, "fig7_parity.png")
    res = {}
    for f in ["moe_monitor_20260819_151903.csv", "moe_monitor_20260819_153948.csv"]:
        dd = load_rt(f)
        tt = dd.t_s - dd.t_s.min()
        P1 = dd[(tt >= 0) & (tt <= 397)]
        A = P1[P1["mode"] == 0]
        B = dd[dd["mode"] == 1]
        res[f] = dict(n=int(len(dd)),
                      gate_acc=float((dd["mode"] == dd.contact).mean()),
                      strain_r2=r2(P1.strain_act_pct, P1.strain_pct),
                      strain_rmse=rmse(P1.strain_act_pct, P1.strain_pct),
                      dist_r2=r2(A.Z_mm, A.value), dist_rmse=rmse(A.Z_mm, A.value),
                      force_r2=r2(B.F_true, B.value), force_rmse=rmse(B.F_true, B.value),
                      lat_med=float(dd.latency_us.median()),
                      lat_p95=float(dd.latency_us.quantile(.95)))
    json.dump(res, open(os.path.join(OUT, "realtime_stats.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig7):
        print("[fig]", f.__name__)
        f()
    print("done ->", OUT)
