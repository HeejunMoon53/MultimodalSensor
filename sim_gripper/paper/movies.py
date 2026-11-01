"""논문 보충 영상 (Supplementary Movies) + 본문용 스냅샷 줄 — 모두 시뮬레이션.

python -m sim_gripper.paper.movies  →  sim_gripper/out/movies/
  S1  계란 파지 1회: 3D + 동기 신호 패널 (ΔL·ΔR, V_TENG, 근접 d̂, 힘 F̂)
  S2  ablation 2×2 동시 재생 (full / −근접 / −재질 / −TENG), 같은 계란
  S3  금속 + 외란 (S1 레이아웃)
  각 영상: .mp4 (1280×720, 30 fps) + .gif 미리보기, S1·S3은 스냅샷 줄 PNG/SVG.
합성 함수(compose_*, snapshot_strip)는 (로그 DataFrame, 프레임, 프레임 시각)만 받음
→ 실물 실험 때 펌웨어 로그 + 카메라 영상으로 그대로 교체.
"""
import imageio.v2 as imageio
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from sim_gripper.control.controller import MATERIAL_TABLE  # noqa: E402
from sim_gripper.experiments.run_all import OUT  # noqa: E402
from sim_gripper.sim.loop import CONTACT_F  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False})   # d̂·F̂ 결합 기호
MOVIE_DIR = OUT / "movies"
COLOR_L, COLOR_R, COLOR_TENG = "#FF8C00", "#2CA02C", "#1F77B4"
C_TRUE, C_EST, INK, MUTED = "#333333", "#7B4FBF", "#222222", "#777777"
C_COND = ["#333333", "#9467BD", "#D62728", "#8C564B", "#17BECF"]   # 조건별 (L·R·TENG 색과 겹치지 않게)
PHASE_BG = {"APPROACH": "#F3F3F3", "GRASP": "#E7E7E7", "HOLD": "#DCDCDC", "RELEASE": "#F3F3F3"}
FPS = 30
LIFT_OK = 0.02


def approach_time(df):
    """접근 명령 → 세 손가락 모두 실제 접촉(F > CONTACT_F)까지 [s]. 접촉 못 하면 nan."""
    app = df.t[df.phase == "APPROACH"]
    if not len(app):
        return float("nan")
    t0, late = app.iloc[0], df[df.t >= app.iloc[0]]
    first = [late.t[late[f"F_true_{i}"] > CONTACT_F] for i in range(3)]
    return float(max(f.iloc[0] for f in first) - t0) if all(len(f) for f in first) else float("nan")


def snapshot_times(df):
    """단계별 대표 시각 5개: 접근 중간, 파지 시작, 힘 수렴, 들어 올림, 놓기."""
    def span(p):
        t = df.t[df.phase == p]
        return (t.iloc[0], t.iloc[-1]) if len(t) else (np.nan, np.nan)
    a, g, h, r = span("APPROACH"), span("GRASP"), span("HOLD"), span("RELEASE")
    want = [((a[0] + a[1]) / 2, "Approach"), (g[0] + 0.1, "Contact"), (g[1] - 0.1, "Grasp"),
            (h[1] - 0.1, "Lift & hold"), (min(r[0] + 0.8, r[1]), "Release")]
    return [(float(df.t.iloc[np.abs(df.t.values - t).argmin()]), lab) for t, lab in want if t == t]


def _shade(ax, t, ph):
    edges = np.flatnonzero(ph[1:] != ph[:-1]) + 1
    for a, b in zip(np.r_[0, edges], np.r_[edges, len(ph)]):
        if ph[a] in PHASE_BG:
            ax.axvspan(t[a], t[b - 1], color=PHASE_BG[ph[a]], lw=0, zorder=0)


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.grid(True, axis="y", color="#EBEBEB", lw=0.5)
    ax.set_axisbelow(True)


def _sim_badge(ax):
    ax.text(0.015, 0.975, "SIMULATION", transform=ax.transAxes, fontsize=9, weight="bold", color="white",
            va="top", bbox=dict(boxstyle="round,pad=0.3", fc="#555555", ec="none", alpha=0.85))


def _write(fig_frames, path):
    """mp4 + 반 해상도 10 fps gif 미리보기."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with imageio.get_writer(str(path), fps=FPS, codec="libx264", quality=8, macro_block_size=8) as w:
        for f in fig_frames:
            w.append_data(f)
    imageio.mimsave(str(path.with_suffix(".gif")), [f[::2, ::2] for f in fig_frames[::3]], duration=0.1, loop=0)
    return path


def _grab(fig):
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()


def _idx(t_arr, t):
    return int(np.searchsorted(t_arr, t, side="right"))


def compose_s1(df, frames, times, path, title, finger=0, step=5):
    """3D 프레임 + 신호 패널 4단 (진행에 따라 그려짐). step: 신호 다운샘플 [ms]."""
    i = finger
    d = df.iloc[::step]
    t, ph = d.t.values, d.phase.values
    c = d[f"contact_{i}"].values.astype(bool)
    series = [  # (axis, y, color, lw, label)
        (0, d[f"dL_{i}"].values, COLOR_L, 1.0, "ΔL/L₀"), (0, d[f"dR_{i}"].values, COLOR_R, 1.0, "ΔR/R₀"),
        (1, d[f"V_{i}"].values, COLOR_TENG, 1.0, "V_TENG"),
        (2, d[f"d_true_{i}"].clip(upper=25).values, C_TRUE, 1.6, "true"),
        (2, np.where(~c, d[f"value_{i}"].values, np.nan), C_EST, 0.8, "estimated (no contact)"),
        (3, d[f"F_true_{i}"].values, C_TRUE, 1.6, "true"),
        (3, np.where(c, d[f"value_{i}"].values, np.nan), C_EST, 0.6, "estimated (contact)"),
        (4, d[f"eps_true_{i}"].values, C_TRUE, 1.6, "true"),
        (4, d[f"eps_hat_{i}"].values, C_EST, 0.6, "estimated")]
    nrow = 5
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    gs = fig.add_gridspec(nrow, 2, width_ratios=[1.2, 1], left=0.01, right=0.97, top=0.93, bottom=0.08,
                          wspace=0.12, hspace=0.2)
    ax_img = fig.add_subplot(gs[:, 0])
    ax_img.set_axis_off()
    im = ax_img.imshow(frames[0])
    _sim_badge(ax_img)
    status = ax_img.text(0.015, 0.02, "", transform=ax_img.transAxes, fontsize=11, family="monospace",
                         color="white", va="bottom", bbox=dict(boxstyle="round,pad=0.4", fc="black", ec="none", alpha=0.6))
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, weight="bold")
    axs = [fig.add_subplot(gs[k, 1]) for k in range(nrow)]
    for k in range(1, nrow):
        axs[k].sharex(axs[0])
    ylab = ["raw TDM [%]", "V_TENG [a.u.]", "proximity [mm]", "force [N]", "strain [%]"]
    lines = []
    for k, y, col, lw, lab in series:
        lines.append((axs[k].plot(t, y, color=col, lw=lw, label=lab)[0], y))
    mat = df[f"material_{i}"].values
    F_t = MATERIAL_TABLE.get(mat[-1] if mat[-1] in MATERIAL_TABLE else "dielectric")[0]
    axs[3].axhline(F_t, color=INK, ls="--", lw=0.7)
    axs[3].text(t[-1], F_t, " F_t", fontsize=8, va="center")
    cursors = []
    for k, ax in enumerate(axs):
        _shade(ax, t, ph)
        _style(ax)
        ax.set_ylabel(ylab[k], fontsize=8.5)
        ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
        cursors.append(ax.axvline(t[0], color="#B00020", lw=1.0))
        if k < nrow - 1:
            ax.tick_params(labelbottom=False)
    fig.align_ylabels(axs)
    axs[0].set_xlim(t[0], t[-1])
    axs[-1].set_xlabel("time [s]", fontsize=9)
    out = []
    for f, tf in zip(frames, times):
        n = _idx(t, tf)
        for ln, y in lines:
            ln.set_data(t[:n], y[:n])
        for cl in cursors:
            cl.set_xdata([tf, tf])
        im.set_data(f)
        r = df.iloc[min(_idx(df.t.values, tf), len(df)) - 1]
        est = (f"force est. {r[f'value_{i}']:4.1f} N" if r[f"contact_{i}"]
               else f"proximity est. {r[f'value_{i}']:4.1f} mm")
        status.set_text(f"t = {tf:4.1f} s   {r.phase:<8s}  finger {i + 1}\n"
                        f"material: {r[f'material_{i}']:<10s}\n{est}")
        out.append(_grab(fig))
    plt.close(fig)
    return _write(out, path)


def _outcome(df, tf, lim=None):
    r = df.iloc[min(_idx(df.t.values, tf), len(df)) - 1]
    peak = df[df.t <= tf][[f"F_true_{i}" for i in range(3)]].max().max()
    if r.broken:
        return f"BROKEN  peak {peak:.1f} N", "#B00020"
    if r.failed:
        return "FAILED (no grasp)", "#B00020"
    if r.phase == "HOLD" and r.obj_z - df.obj_z.iloc[0] >= LIFT_OK:
        return f"lifted  peak {peak:.1f} N", "#2E7D5B"
    return f"{r.phase.lower():<9s} peak {peak:.1f} N", "white"


def compose_grid(runs, times, path, title="Modality ablation (same egg)", limit=None, step=5):
    """runs: [(라벨, df, frames)] — 같은 시각 프레임을 격자로 + 아래에 조건별 최대 접촉력."""
    n = len(runs)
    ncol = min(n, 4)
    nrow = int(np.ceil(n / ncol))
    fig = plt.figure(figsize=(12.8, 3.2 + 2.4 * nrow), dpi=100)
    gs = fig.add_gridspec(nrow + 1, ncol, height_ratios=[1] * nrow + [0.8], left=0.06, right=0.99, top=0.9,
                          bottom=0.1, wspace=0.03, hspace=0.12)
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, weight="bold")
    fig.text(0.99, 0.975, "SIMULATION", ha="right", va="top", fontsize=9, weight="bold", color="white",
             bbox=dict(boxstyle="round,pad=0.3", fc="#555555", ec="none"))
    ims, texts = [], []
    for k, (lab, df, fr) in enumerate(runs):
        ax = fig.add_subplot(gs[k // ncol, k % ncol])
        ax.set_axis_off()
        ims.append(ax.imshow(fr[0]))
        ax.text(0.5, 0.97, lab, transform=ax.transAxes, ha="center", va="top", fontsize=12, weight="bold",
                color="white", bbox=dict(boxstyle="round,pad=0.25", fc=C_COND[k % len(C_COND)], ec="none"))
        texts.append(ax.text(0.02, 0.03, "", transform=ax.transAxes, fontsize=9, family="monospace", va="bottom",
                             bbox=dict(boxstyle="round,pad=0.3", fc="black", ec="none", alpha=0.6)))
    axF = fig.add_subplot(gs[nrow, :])
    curves = []
    for k, (lab, df, _) in enumerate(runs):
        d = df.iloc[::step]
        y = d[[f"F_true_{i}" for i in range(3)]].max(axis=1).values
        curves.append((axF.plot(d.t.values, y, color=C_COND[k % len(C_COND)], lw=1.3, label=lab)[0],
                       d.t.values, y))
    if limit:
        axF.axhline(limit, color="#B00020", ls=":", lw=0.9)
        axF.text(0.2, limit, "break limit", fontsize=8, color="#B00020", va="bottom")
    axF.set_xlim(0, runs[0][1].t.iloc[-1])
    axF.set_ylabel("max contact\nforce [N]", fontsize=9)
    axF.set_xlabel("time [s]", fontsize=9)
    axF.legend(loc="upper left", fontsize=8, frameon=False, ncol=n)
    _style(axF)
    cursor = axF.axvline(0, color="#B00020", lw=1.0)
    out = []
    for j, tf in enumerate(times):
        for k, (_, df, fr) in enumerate(runs):
            ims[k].set_data(fr[min(j, len(fr) - 1)])
            s, col = _outcome(df, tf)
            texts[k].set_text(s)
            texts[k].set_color(col)
        for ln, t, y in curves:
            n_ = _idx(t, tf)
            ln.set_data(t[:n_], y[:n_])
        cursor.set_xdata([tf, tf])
        out.append(_grab(fig))
    plt.close(fig)
    return _write(out, path)


def snapshot_strip(df, frames, times, path, title=None):
    """본문 그림용: 단계별 5컷 + 시각 (PNG 300 dpi + SVG)."""
    snaps = snapshot_times(df)
    fig, axs = plt.subplots(1, len(snaps), figsize=(7.2, 1.75), gridspec_kw={"wspace": 0.04})
    for ax, (ts, lab) in zip(np.atleast_1d(axs), snaps):
        j = int(np.abs(np.asarray(times) - ts).argmin())
        ax.imshow(frames[j])
        ax.set_axis_off()
        ax.set_title(f"{lab}\nt = {ts:.1f} s", fontsize=7)
    if title:
        fig.suptitle(title, fontsize=7.5, x=0.01, ha="left", y=0.98)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return path.with_suffix(".png")


CAM = ((0.0, 0.0, 0.06), 0.27, 135.0, -18.0)   # lookat, distance, azimuth, elevation (리프트 40 mm 포함)


def record(scenario, models, size=(720, 540), cam=CAM, **run_kw):
    """폐루프 실행 + 오프스크린 렌더 (FPS, 고정 카메라) → df, frames, frame times."""
    import mujoco

    from sim_gripper.sim.loop import run
    W, H = size
    st = {"r": None, "next": 0.0}
    frames, times = [], []
    cam_ = mujoco.MjvCamera()
    cam_.lookat[:], (cam_.distance, cam_.azimuth, cam_.elevation) = cam[0], cam[1:]

    def on_step(sim, row):
        if row["t"] + 1e-9 < st["next"]:
            return
        if st["r"] is None:
            sim.model.vis.global_.offwidth = max(sim.model.vis.global_.offwidth, W)
            sim.model.vis.global_.offheight = max(sim.model.vis.global_.offheight, H)
            st["r"] = mujoco.Renderer(sim.model, H, W)
        st["r"].update_scene(sim.data, camera=cam_)
        frames.append(st["r"].render().copy())
        times.append(row["t"])
        st["next"] += 1.0 / FPS

    df, _ = run(scenario, moe_models=models, on_step=on_step, **run_kw)
    if st["r"] is not None:
        st["r"].close()
    return df, frames, times


ABL_MOVIE = [("full", ()), ("− proximity", ("proximity",)), ("− material", ("material",)), ("− TENG", ("teng",))]


def make_all(out_dir=MOVIE_DIR):
    from sim_gripper.experiments.calibrated import make_gripper_moe
    from sim_gripper.sim.scenarios import SCENARIOS
    models = make_gripper_moe()
    out = []
    df, fr, tm = record(SCENARIOS["E2_egg"], models)
    out.append(compose_s1(df, fr, tm, out_dir / "S1_egg_grasp.mp4",
                          "Movie S1  Grasping an egg with the single-electrode sensor (simulation)"))
    out.append(snapshot_strip(df, fr, tm, out_dir / "S1_egg_strip", "Egg grasp (simulation)"))
    print(out[-2], out[-1], flush=True)
    runs = [(lab, *record(SCENARIOS["E2_egg"], models, ablate=ab)[:2]) for lab, ab in ABL_MOVIE]
    out.append(compose_grid(runs, tm, out_dir / "S2_ablation_egg.mp4",
                            "Movie S2  Removing one modality at a time — same egg (simulation)",
                            limit=SCENARIOS["E2_egg"].obj.fragile_F_N))
    print(out[-1], flush=True)
    df, fr, tm = record(SCENARIOS["E4_disturb"], models)
    out.append(compose_s1(df, fr, tm, out_dir / "S3_metal_disturbance.mp4",
                          "Movie S3  Metal cylinder with an external pull during hold (simulation)"))
    out.append(snapshot_strip(df, fr, tm, out_dir / "S3_metal_strip", "Metal + disturbance (simulation)"))
    print(out[-2], out[-1], flush=True)
    return out


if __name__ == "__main__":
    make_all()
