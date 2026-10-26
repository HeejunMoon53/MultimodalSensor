"""논문 실험 그림 F4–F9 (영문 라벨, PNG 300 dpi + SVG). 메인 플랫폼: 판형 텐던 손가락 + 그리퍼 보정 MoE.

python -m sim_gripper.paper.figures  →  sim_gripper/out/paper_figs/   (시뮬 로그 캐시: out/paper_runs/)
"""
import json
import pickle
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from sim_gripper.control.controller import MATERIAL_TABLE, CtrlParams
from sim_gripper.experiments.calibrated import make_gripper_moe
from sim_gripper.experiments.run_all import OUT
from sim_gripper.paper.diagrams import COLOR_L, COLOR_R, COLOR_TENG, INK, MUTED, _save, plt
from sim_gripper.perception.analytic import D_GRID, EPS_GRID, error_map, fit_empirical
from sim_gripper.perception.moe import DEFAULT_PKL
from sim_gripper.sensor.forward import SensorForward
from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS, Scenario

FIG_DIR = OUT / "paper_figs"
RUN_DIR = OUT / "paper_runs"
C_TRUE, C_EST = "#333333", "#7B4FBF"
PHASE_BG = {"APPROACH": "#F3F3F3", "GRASP": "#E7E7E7", "HOLD": "#DCDCDC", "RELEASE": "#F3F3F3"}
OBJ_LIMIT = {"E2_egg": 3.5, "E2_hand": 3.0, "E1_metal": 8.0}
NAMES = {"E1_metal": "Metal cylinder", "E2_hand": "Human finger (soft)", "E2_egg": "Egg"}


def _cached(key, fn):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    path = RUN_DIR / f"{key}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    df = fn()
    df.to_pickle(path)
    return df


def _run(scen, finger="flat", latency=0, ablate=(), ctrl=None, models=None, t_end=None):
    sc = SCENARIOS[scen] if t_end is None else replace(SCENARIOS[scen], t_end=t_end)
    key = f"{scen}_{finger}_L{latency}_{'-'.join(ablate) or 'full'}_{'' if ctrl is None else f'B{ctrl.B_a}'}_{t_end}"
    return _cached(key, lambda: run(sc, finger=finger, latency_ms=latency, ablate=ablate, ctrl=ctrl,
                                    moe_models=models)[0])


def _phases(ax, df, labels=False):
    ph = df.phase.values
    edges = np.flatnonzero(ph[1:] != ph[:-1]) + 1
    for a, b in zip(np.r_[0, edges], np.r_[edges, len(ph)]):
        if ph[a] in PHASE_BG:
            ax.axvspan(df.t.iloc[a], df.t.iloc[b - 1], color=PHASE_BG[ph[a]], lw=0, zorder=0)
            if labels:
                ax.text((df.t.iloc[a] + df.t.iloc[b - 1]) / 2, 1.02, ph[a].title(), transform=ax.get_xaxis_transform(),
                        ha="center", va="bottom", fontsize=6.3, color=MUTED)


def _style(ax, axis="both"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(False)
    ax.grid(True, axis=axis, color="#EBEBEB", lw=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=6.5)


def fig4_grasp_timeline(models, out_dir=FIG_DIR):
    df = _run("E1_metal", models=models)
    i, t = 0, df.t
    c = df.contact_0.astype(bool)
    fig, axs = plt.subplots(6, 1, figsize=(7.2, 7.0), sharex=True, gridspec_kw={"hspace": 0.12})
    ax = axs[0]
    ax.plot(t, df.d_true_0.clip(upper=25), color=C_TRUE, lw=1.3, label="true")
    ax.plot(t, df.value_0.where(~c), color=C_EST, lw=0.8, alpha=0.85, label="estimated (no contact)")
    ax.set_ylabel("Proximity\nd [mm]", fontsize=7)
    ax = axs[1]
    ax.plot(t, df.V_0, color=COLOR_TENG, lw=0.9, label="V_TENG")
    ax2 = ax.twinx()
    ax2.fill_between(t, 0, c.astype(int), step="post", color=COLOR_TENG, alpha=0.12, lw=0)
    ax2.set_ylim(0, 1.05), ax2.set_yticks([0, 1]), ax2.set_yticklabels(["no", "yes"], fontsize=6)
    ax2.set_ylabel("contact", fontsize=6.5, color=COLOR_TENG)
    ax.set_ylabel("Contact\nV_TENG [a.u.]", fontsize=7)
    ax = axs[2]
    F_t, F_max = MATERIAL_TABLE[df.material_0.iloc[-1]]
    ax.plot(t, df.F_true_0, color=C_TRUE, lw=1.3, label="true")
    ax.plot(t, df.value_0.where(c), color=C_EST, lw=0.7, alpha=0.8, label="estimated")
    ax.axhline(F_t, color=INK, ls="--", lw=0.7)
    ax.axhline(F_max, color="#B00020", ls=":", lw=0.8)
    ax.text(t.iloc[-1], F_t, " F_t", fontsize=6, va="center")
    ax.text(t.iloc[-1], F_max, " F_max", fontsize=6, va="center", color="#B00020")
    ax.set_ylabel("Force\nF [N]", fontsize=7)
    ax = axs[3]
    ax.plot(t, df.eps_true_0, color=C_TRUE, lw=1.3, label="true")
    ax.plot(t, df.eps_hat_0, color=C_EST, lw=0.7, alpha=0.8, label="estimated")
    ax.set_ylabel("Strain\nε [%]", fontsize=7)
    ax = axs[4]
    ax.plot(t, df.dL_0, color=COLOR_L, lw=0.8, label="ΔL/L₀")
    ax.plot(t, df.dR_0, color=COLOR_R, lw=0.8, label="ΔR/R₀")
    ax.set_ylabel("Raw TDM\nsignals [%]", fontsize=7)
    ax = axs[5]
    ax.plot(t, df.u_0, color="#2E7D5B", lw=1.2, label="actuator command u")
    mat = df.material_0
    k = np.flatnonzero(mat.values != "unknown")
    if len(k):
        ax.axvline(t.iloc[k[0]], color="#17BECF", lw=0.9, ls="--")
        ax.text(t.iloc[k[0]], 0.95, f" material = {mat.iloc[k[0]]} (from ΔL residual)", fontsize=6,
                color="#0E7C86", va="top", transform=ax.get_xaxis_transform())
    ax.set_ylabel("Command u\n& material", fontsize=7)
    ax.set_xlabel("time [s]", fontsize=7)
    for k, ax in enumerate(axs):
        _phases(ax, df, labels=(k == 0))
        _style(ax)
        ax.legend(loc="best", fontsize=5.8, frameon=True, framealpha=0.85, edgecolor="none", ncol=2)
        ax.text(-0.085, 1.0, "abcdef"[k], transform=ax.transAxes, fontsize=8, weight="bold", va="top")
    axs[0].set_xlim(0.3, 9.6)
    return _save(fig, out_dir, "fig4_grasp_timeline")


def fig5_material_adaptive(models, out_dir=FIG_DIR):
    fwd = SensorForward()
    scen = ["E1_metal", "E2_hand", "E2_egg"]
    cols = {"E1_metal": "#4A6FA5", "E2_hand": "#C2703D", "E2_egg": "#7A9A3A"}
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw={"wspace": 0.28})
    for s in scen:
        df = _run(s, models=models)
        t_c = df.t[(df.F_true_0 > 0.05)].iloc[0]
        pre = df[(df.t > t_c - 1.2) & (df.t < t_c)]
        r = pre.dL_0 - np.array([fwd.dL_eps(fwd.eps_from_dR(v)) for v in pre.dR_0])
        axs[0].plot(pre.t - t_c, r.rolling(20, min_periods=1).mean(), color=cols[s], lw=1.1,
                    label=f"{NAMES[s]} → {df.material_0.iloc[-1]}")
        g = df[df.phase.isin(["GRASP", "HOLD"])]
        axs[1].plot(g.t - t_c, g.F_true_0, color=cols[s], lw=1.2, label=NAMES[s])
        F_t = MATERIAL_TABLE[df.material_0.iloc[-1]][0]
        axs[1].axhline(F_t, color=cols[s], ls="--", lw=0.7)
    axs[0].axhspan(-0.5, 0.5, color="#EEEEEE", lw=0)
    axs[0].text(-1.05, 1.2, "undecided band ±θ", fontsize=5.8, color=MUTED, va="bottom")
    axs[0].set_xlabel("time to first contact [s]", fontsize=7)
    axs[0].set_ylabel("ΔL residual  ΔL − ΔL_ε(ε_R)  [%]", fontsize=7)
    axs[0].set_title("a  pre-contact material recognition", fontsize=7.5, loc="left")
    axs[1].axhline(OBJ_LIMIT["E2_egg"], color="#B00020", ls=":", lw=0.8)
    axs[1].text(0.05, OBJ_LIMIT["E2_egg"] + 0.1, "egg breaks (3.5 N)", fontsize=5.8, color="#B00020")
    axs[1].set_xlabel("time after first contact [s]", fontsize=7)
    axs[1].set_ylabel("grasp force (true) [N]", fontsize=7)
    axs[1].set_title("b  material-adaptive force target (dashed: F_t)", fontsize=7.5, loc="left")
    for ax in axs:
        _style(ax)
        ax.legend(fontsize=5.8, frameon=False)
    return _save(fig, out_dir, "fig5_material_adaptive")


LAT = (0, 5, 10, 20, 50, 100)
GAINS = (0.5, 1.0, 2.0, 4.0, 8.0)


def latency_sweep(models):
    rows = []
    for B in GAINS:
        for L in LAT:
            df = _run("E2_egg", latency=L, ctrl=CtrlParams(B_a=B), models=models, t_end=4.5)
            g = df[df.phase != "OPEN"]
            rows.append(dict(finger="flat", B_a=B, latency=L, peak=g[[f"F_true_{i}" for i in range(3)]].max().max(),
                             broken=bool(df.broken.iloc[-1])))
    for L in LAT:
        df = _run("E2_egg", finger="bellows60a", latency=L, ctrl=CtrlParams(B_a=1.0, u_max=1.0), models=models,
                  t_end=4.5)
        g = df[df.phase != "OPEN"]
        rows.append(dict(finger="bellows60a", B_a=1.0, latency=L,
                         peak=g[[f"F_true_{i}" for i in range(3)]].max().max(), broken=bool(df.broken.iloc[-1])))
    return pd.DataFrame(rows)


def fig6_latency(models, out_dir=FIG_DIR):
    res = latency_sweep(models)
    flat = res[res.finger == "flat"]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.35})
    ax = axs[0]
    M = flat.pivot(index="B_a", columns="latency", values="peak").loc[list(GAINS), list(LAT)]
    Br = flat.pivot(index="B_a", columns="latency", values="broken").loc[list(GAINS), list(LAT)]
    im = ax.imshow(M.values, cmap="Purples", vmin=0, vmax=6, aspect="auto")
    ax.grid(False)
    for a in range(len(GAINS)):
        for b in range(len(LAT)):
            v, br = M.values[a, b], Br.values[a, b]
            ax.text(b, a, f"{v:.1f}" + ("\n✕" if br else ""), ha="center", va="center", fontsize=6,
                    color="white" if v > 3.5 else INK, weight="bold" if br else "normal")
    ax.set_xticks(range(len(LAT)), [f"{L}" for L in LAT])
    ax.set_yticks(range(len(GAINS)), [f"{B:g}" for B in GAINS])
    ax.set_xlabel("sensor → controller latency [ms]", fontsize=7)
    ax.set_ylabel("admittance damping B_a  (small = fast)", fontsize=7)
    ax.set_title("a  peak egg force [N] (tendon); ✕ = egg broken", fontsize=7.2, loc="left", pad=8)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.ax.tick_params(labelsize=6)
    ax.axvspan(-0.5, 0.5, fill=False, ec="#2E7D5B", lw=1.5)
    ax = axs[1]
    for fing, col, lab in (("flat", C_EST, "tendon (τ_m = 20 ms), B_a = 1"),
                           ("bellows60a", "#C2703D", "pneumatic 60A (τ_p = 150 ms), B_a = 1")):
        r = res[(res.finger == fing) & (res.B_a == 1.0)]
        xi = [LAT.index(L) for L in r.latency]
        ax.plot(xi, r.peak, marker="o", ms=3.5, color=col, lw=1.2, label=lab)
        for _, row in r[r.broken].iterrows():
            ax.plot(LAT.index(row.latency), row.peak, marker="x", ms=7, color="#B00020", mew=1.6)
    ax.axhline(3.5, color="#B00020", ls=":", lw=0.8)
    ax.text(0, 3.55, "egg breaks", fontsize=5.8, color="#B00020", va="bottom")
    ax.axvspan(-0.3, 0.3, color="#2E7D5B", alpha=0.15, lw=0)
    ax.axvspan(1.7, 4.3, color="#999999", alpha=0.12, lw=0)
    ax.text(3.0, 2.2, "typical PC / USB\nloop (illustrative)", ha="center", fontsize=5.6, color=MUTED)
    ax.set_xticks(range(len(LAT)), [str(L) for L in LAT])
    ax.set_xlabel("latency [ms]", fontsize=7)
    ax.set_ylabel("peak egg force [N]", fontsize=7)
    ax.set_title("b  actuator speed sets latency sensitivity", fontsize=7.2, loc="left")
    _style(ax, "y")
    ax.legend(fontsize=5.6, frameon=False, loc="center left")
    paths = _save(fig, out_dir, "fig6_latency")
    res.to_csv(out_dir / "fig6_latency_data.csv", index=False)
    return paths


def fig7_analytic_vs_moe(out_dir=FIG_DIR, n_noise=20):
    fwd = SensorForward()
    v4 = pickle.loads(DEFAULT_PKL.read_bytes())
    m = error_map(fit_empirical(fwd), fwd, models=v4, n_noise=n_noise)
    fig, axs = plt.subplots(1, 4, figsize=(7.2, 2.3), gridspec_kw={"width_ratios": [1, 1, 1, 1.15], "wspace": 0.45})
    ext = [D_GRID[0], D_GRID[-1], EPS_GRID[0], EPS_GRID[-1]]
    kw = dict(origin="lower", aspect="auto", extent=ext)
    im0 = axs[0].imshow(m["fail_rate"], cmap="Reds", vmin=0, vmax=1, **kw)
    axs[0].set_title("a  analytic: divergence rate", fontsize=6.8, loc="left")
    dd = np.ma.masked_invalid(m["d_err"])
    cmap = plt.get_cmap("Purples").copy()
    cmap.set_bad("#B00020", 0.35)
    im1 = axs[1].imshow(dd, cmap=cmap, vmin=0, vmax=5, **kw)
    axs[1].set_title("b  analytic: |d̂ − d| [mm]", fontsize=6.8, loc="left")
    axs[2].imshow(m["moe_d_err"], cmap="Purples", vmin=0, vmax=5, **kw)
    axs[2].set_title("c  MoE: |d̂ − d| [mm]", fontsize=6.8, loc="left")
    for ax, im in ((axs[0], im0), (axs[2], im1)):
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
        cb.ax.tick_params(labelsize=5.5)
    for ax in axs[:3]:
        ax.grid(False)
        ax.set_xlabel("distance d [mm]", fontsize=6.5)
        ax.tick_params(labelsize=6)
    axs[0].set_ylabel("strain ε [%]", fontsize=6.5)
    ax = axs[3]
    fail = m["fail_rate"].mean(0)
    ax.plot(D_GRID, fail * 100, color="#B00020", lw=1.2, marker="o", ms=2.5, label="analytic divergence [%]")
    ax.plot(D_GRID, np.nanmean(m["d_err"], 0), color="#C2703D", lw=1.0, label="analytic error [mm]")
    ax.plot(D_GRID, m["moe_d_err"].mean(0), color=C_EST, lw=1.2, label="MoE error [mm]")
    ax.set_xlabel("distance d [mm]", fontsize=6.5)
    ax.set_title("d  mean over ε", fontsize=6.8, loc="left")
    ax.set_ylim(0, 105)
    ax.set_yscale("symlog", linthresh=5)
    _style(ax)
    ax.legend(fontsize=5.4, frameon=False)
    paths = _save(fig, out_dir, "fig7_analytic_vs_moe")
    np.savez(out_dir / "fig7_maps.npz", eps=EPS_GRID, d=D_GRID, **{k: v for k, v in m.items()})
    return paths


ABL = [("full", ()), ("− proximity", ("proximity",)), ("− material", ("material",)), ("− TENG", ("teng",)),
       ("− safety", ("safety",))]
ABL_TICK = ["full", "−prox.", "−material", "−TENG", "−safety"]


def ablation(models):
    rows = []
    for name, ab in ABL:
        for s in ("E2_egg", "E2_hand", "E1_metal"):
            df = _run(s, ablate=ab, models=models)
            g = df[df.phase != "RELEASE"]
            appr = df[df.phase.isin(["APPROACH", "GRASP"])]
            peak = g[[f"F_true_{i}" for i in range(3)]].max().max()
            fdot = max(appr[f"F_true_{i}"].diff().max() * 1000 for i in range(3))
            hold = df[df.phase == "HOLD"]
            lifted = len(hold) and hold.obj_z.iloc[-1] - df.obj_z.iloc[0] >= 0.02
            ok = bool(lifted and not df.broken.iloc[-1] and not df.failed.iloc[-1] and peak <= OBJ_LIMIT[s])
            rows.append(dict(condition=name, scenario=s, peak=peak, impact=fdot, success=ok,
                             broken=bool(df.broken.iloc[-1]), grasped=bool(len(hold) > 0)))
    return pd.DataFrame(rows)


def fig8_ablation(models, out_dir=FIG_DIR):
    res = ablation(models)
    conds = [c for c, _ in ABL]
    scen = ["E2_egg", "E2_hand", "E1_metal"]
    cols = {"E1_metal": "#4A6FA5", "E2_hand": "#C2703D", "E2_egg": "#7A9A3A"}
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw={"wspace": 0.3})
    x = np.arange(len(conds))
    wd = 0.26
    for k, s in enumerate(scen):
        r = res[res.scenario == s].set_index("condition").loc[conds]
        bars = axs[0].bar(x + (k - 1) * wd, r.peak, wd, color=cols[s], label=NAMES[s])
        for xi, (_, row) in zip(x + (k - 1) * wd, r.iterrows()):
            mark = "✓" if row.success else ("B" if row.broken else "✕")
            axs[0].text(xi, row.peak + 0.12, mark, ha="center", fontsize=6.0, weight="bold",
                        color="#2E7D5B" if row.success else "#B00020", va="bottom")
        axs[1].bar(x + (k - 1) * wd, r.impact, wd, color=cols[s])
    for s, lim in OBJ_LIMIT.items():
        if s != "E1_metal":
            axs[0].axhline(lim, color=cols[s], ls=":", lw=0.8)
    axs[0].set_xticks(x, ABL_TICK, fontsize=6.3)
    axs[0].set_ylabel("peak grasp force [N]", fontsize=7)
    axs[0].set_title("a  peak force;  ✓ success, ✕ failed, B broken", fontsize=7.2, loc="left")
    axs[0].set_ylim(0, 8)
    axs[0].legend(fontsize=5.8, frameon=False, loc="upper left")
    axs[1].set_xticks(x, ABL_TICK, fontsize=6.3)
    axs[1].set_ylabel("max dF/dt at contact [N/s]", fontsize=7)
    axs[1].set_yscale("log")
    axs[1].set_title("b  contact impact", fontsize=7.2, loc="left")
    for ax in axs:
        _style(ax, "y")
    paths = _save(fig, out_dir, "fig8_ablation")
    res.to_csv(out_dir / "fig8_ablation_data.csv", index=False)
    return paths


def fig9_adaptation(out_dir=FIG_DIR):
    ds = json.loads((OUT / "domain_shift.json").read_text(encoding="utf-8"))
    meths = {"recal": ("#8C564B", "re-scale + linear"), "finetune": (C_EST, "fine-tune"),
             "mixed": ("#D62728", "fine-tune + flat data"), "scratch": ("#17BECF", "from scratch")}
    n_list = [int(n) for n in ds["methods"]["mixed"]]
    panels = [("sim", "strain_r2", "a  gripper strain R²"), ("sim", "force_r2", "b  gripper force R²"),
              ("flat", "strain_r2", "c  flat-test strain R² (forgetting)")]
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4), sharex=True, gridspec_kw={"wspace": 0.35})
    for ax, (dom, key, title) in zip(axs, panels):
        for meth, (col, lab) in meths.items():
            ax.plot(n_list, [ds["methods"][meth][str(n)][dom][key] for n in n_list], marker="o", ms=3, lw=1.2,
                    color=col, label=lab)
        ref = ds["v4_flat"][key] if dom == "flat" else ds["v4_shift"][key]
        ax.axhline(ref, color=INK, ls="--", lw=0.8, label="deployed v4")
        ax.set_xscale("log")
        ax.set_ylim(max(min(ax.get_ylim()[0], 0), -1), 1.02)
        ax.set_title(title, fontsize=7, loc="left")
        ax.set_xlabel("gripper calibration samples N", fontsize=6.5)
        _style(ax)
    axs[0].legend(fontsize=5.4, frameon=False, loc="lower right")
    return _save(fig, out_dir, "fig9_adaptation")


def make_all(out_dir=FIG_DIR):
    from sim_gripper.paper.diagrams import fig1_architecture, fig2_timing_budget, fig3_state_machine
    models = make_gripper_moe()
    out = []
    for fn in (fig1_architecture, fig2_timing_budget, fig3_state_machine, fig7_analytic_vs_moe, fig9_adaptation):
        out += fn(out_dir)
        print(out[-1], flush=True)
    for fn in (fig4_grasp_timeline, fig5_material_adaptive, fig6_latency, fig8_ablation):
        out += fn(models, out_dir)
        print(out[-1], flush=True)
    return out


if __name__ == "__main__":
    make_all()
