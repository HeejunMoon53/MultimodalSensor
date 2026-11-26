"""대시보드 영상 (시뮬레이션): 왼쪽 MuJoCo 3D, 오른쪽 센서 원신호 · 추정값 · 기준 · 입력 · 상위 상태를 실시간 그래프로.

폐루프는 run_hri.run_case 와 같다: 상위 PC 20 Hz + 지연 20 ms (UpperLink), 하위 내부 루프 100 Hz (C F-LQG + RLS),
하위 반사 1 kHz, TDM → v4 MoE → 게이트 ∨ TENG. 재질은 정답 라벨 (판별기 미구현, M1).

A 망치 받기 (도체): 사람이 망치를 내밂 → 근접 탐지 → pre-shape → 파지 명령 → 힘 추종 → 사람이 손을 뗌 → 유지.
  하중 이전은 근사다: 물체(mocap)가 0.3 s 동안 3 mm 처지고, 손 소품만 물러난다. 무게·마찰·미끄럼은 없다 (자유 물체 모델 = 다음 단계).
B 팔 오잡기 (인체): 망치를 쥔 손목을 잡음 → 팔이 손가락 B 쪽으로 10 mm / 0.1 s 급이동 → 하위 반사 배기 + 상위 SAFETY
  → release 명령 (시나리오 스크립트) → 열림.

실행 (code 폴더에서): C:/ml_env/Scripts/python.exe run_video.py [A] [B]
→ out/V_{A,B}.mp4 · V_{A,B}_poster.png · V_{A,B}.csv, out/upper_timeline.png, params["results_video"]
"""
import sys

import numpy as np

import paths  # noqa: F401
from paths import OUT, load_params, save_params
from run_compare import approach_path
from run_hri import STATES, UP_PC, hand_path, run_case
from supervisor import MATERIAL

COLOR_L, COLOR_R, COLOR_TENG = "#FF8C00", "#2CA02C", "#1F77B4"
FING = ("#7a4ea3", "#c0392b")          # 손가락 A, B (run_hri 그림과 같음)
STATE_RGB = {"OPEN": "#ffffff", "APPROACH": "#bcd3ee", "CONTACT": "#bcd3ee", "GRASP": "#b6dcab", "SAFETY": "#f2a9a9", "RELEASE": "#dddddd"}

SCEN = {
    "A": dict(title="A. 망치 받기 (사람 → 그리퍼, 자루 = 도체)", mat="conductor", photo="hammer", seconds=9.0,
              t_grasp=4.5, t_hand=6.5, t_release=None),
    "B": dict(title="B. 팔 오잡기 (인체) → 반사 · SAFETY → 놓기", mat="human", photo="wrist", seconds=9.5,
              t_grasp=4.5, jerk=(6.5, 10.0, 0.1), t_release=7.8),
}
HAND_AWAY = np.array([0.0, 0.07, -0.12])   # 손을 뗄 때 손 소품 이동 [m] (보이기만)


def handover_path(t_hand=6.5, sag=3.0, t_sag=0.3):
    """사람이 t_hand 에 손을 떼면 망치(mocap)가 t_sag 동안 sag [mm] 처진다 (하중 이전 근사)."""
    base = approach_path("conductor")

    def f(t):
        x, y, z = base(t)
        return (x, y, z - sag * float(np.clip((t - t_hand) / t_sag, 0.0, 1.0))) if t > t_hand else (x, y, z)
    return f


def phase_label(state, trip, released_by_hand, jerk):
    if trip or state == "SAFETY":
        return "반사 배기 · SAFETY (힘 > F_max)"
    if jerk:
        return "팔 급이동 (10 mm / 0.1 s)"
    return {"OPEN": "대기", "APPROACH": "탐지 · 접근 (근접 pre-shape)", "CONTACT": "접촉",
            "GRASP": "손을 뗌 → 하중 이전 (근사), 힘 유지" if released_by_hand else "접촉 → 힘 추종 (F_ref 경사)",
            "RELEASE": "놓기 (release)"}[state]


class Dashboard:
    """그래프 6단 (손가락 A 기준, 힘·입력은 A·B). 매 프레임 지금까지의 기록만 그린다."""

    def __init__(self, title, seconds, Ft, Fmax, w, h):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 8})
        self.plt, self.T = plt, seconds
        self.fig, ax = plt.subplots(6, 1, figsize=(w / 100, h / 100), dpi=100, sharex=True,
                                    gridspec_kw=dict(height_ratios=[0.45, 1, 1, 1.15, 1, 1]))
        self.ax = ax
        self.title = title
        self.cmap = ListedColormap([STATE_RGB[s] for s in STATES])
        self.band = ax[0].imshow(np.full((2, 2), np.nan), aspect="auto", cmap=self.cmap, vmin=-0.5, vmax=len(STATES) - 0.5,
                                 extent=(0, seconds, 1.5, -0.5), interpolation="nearest")
        ax[0].set_yticks([0, 1], ["상위 A", "상위 B"]); ax[0].set_ylim(1.5, -0.5)
        self.st_txt = ax[0].text(0.995, 0.5, "", transform=ax[0].transAxes, ha="right", va="center", fontsize=8, weight="bold")
        L = lambda i, c, lab, **kw: ax[i].plot([], [], c=c, lw=1.0, label=lab, **kw)[0]
        self.L = dict(
            dL=L(1, COLOR_L, "ΔL/L$_0$ [%]"), dR=L(1, COLOR_R, "ΔR/R$_0$ [%]"),
            d=L(2, "#888", "d 정답"), d_hat=L(2, COLOR_L, r"$\hat{d}$ (MoE, L)"),
            F0=L(3, FING[0], "F 정답 A", alpha=0.45), F1=L(3, FING[1], "F 정답 B", alpha=0.45),
            Fh0=L(3, FING[0], r"$\hat{F}$ A"), Fh1=L(3, FING[1], r"$\hat{F}$ B"), Fr=L(3, "#222", "F_ref A", ls="--"),
            eps=L(4, "#1d6b1d", "ε 정답", alpha=0.5), eps_hat=L(4, COLOR_R, r"$\hat{\varepsilon}$ (MoE, R)"), eps_ref=L(4, "#222", "ε_ref A", ls="--"),
            u0=L(5, FING[0], "u A"), u1=L(5, FING[1], "u B"), p0=L(5, "#555", "p A (방)", ls=":"))
        self.axT = ax[1].twinx(); self.L["teng"] = self.axT.plot([], [], c=COLOR_TENG, lw=0.8, label="V_TENG")[0]
        self.axC = ax[2].twinx(); self.L["c"] = self.axC.step([], [], c=COLOR_TENG, lw=1.0, where="post", label="접촉 c = 게이트 ∨ TENG")[0]
        self.axC.set_ylim(-0.1, 1.6); self.axC.set_yticks([0, 1]); self.axT.set_ylabel("V", fontsize=7)
        ax[3].axhline(Fmax, c="r", ls=":", lw=0.9, label="F_max (재질)"); ax[3].axhline(Ft, c="#222", ls="-.", lw=0.6, label="F_t")
        for i, (yl, lim) in enumerate((("TDM 원신호", None), ("근접 [mm]", (0, 40)), ("힘 [N]", (-0.2, max(4.0, 1.6 * Fmax))),
                                       ("굽힘 ε [%]", (-1, 14)), ("[kPa]", (-1, 32))), start=1):
            ax[i].set_ylabel(yl, fontsize=8); ax[i].grid(alpha=0.25)
            if lim:
                ax[i].set_ylim(*lim)
            ax[i].legend(fontsize=6.5, loc="upper left", ncol=3, framealpha=0.7)
        self.axT.legend(fontsize=6.5, loc="upper right", framealpha=0.7); self.axC.legend(fontsize=6.5, loc="upper right", framealpha=0.7)
        ax[-1].set_xlim(0, seconds); ax[-1].set_xlabel("t [s]   (옅은 빨강 = 하위 반사 배기 중)")
        self.cur = [a.axvline(0, c="#444", lw=0.6) for a in ax]
        self.fig.tight_layout(rect=(0, 0, 1, 0.96))
        self.trip_spans = []

    def draw(self, lg, label):
        t = np.asarray(lg["t"])
        g = lambda k, j=None: np.asarray(lg[k]) if j is None else np.asarray(lg[k])[:, j]
        for k, v in (("dL", g("LR", 0)), ("dR", g("LR", 1)), ("teng", g("teng")), ("d", g("d")), ("d_hat", g("d_hat")),
                     ("c", g("c")), ("F0", g("F", 0)), ("F1", g("F", 1)), ("Fh0", g("F_hat", 0)), ("Fh1", g("F_hat", 1)),
                     ("Fr", g("F_ref")), ("eps", g("eps")), ("eps_hat", g("eps_hat")), ("eps_ref", g("eps_ref")),
                     ("u0", g("u", 0)), ("u1", g("u", 1)), ("p0", g("p"))):
            self.L[k].set_data(t, v)
        lr = np.r_[g("LR").ravel(), 0.0]
        self.ax[1].set_ylim(min(lr.min(), -0.5) * 1.15, max(lr.max(), 0.5) * 1.15)
        tv = np.r_[np.abs(g("teng")), 0.1]
        self.axT.set_ylim(-1.15 * tv.max(), 1.15 * tv.max())
        st = np.asarray(lg["state"], float).T
        self.band.set_data(np.c_[st, np.full((2, 1), np.nan)]); self.band.set_extent((0, t[-1] + 1e-3, 1.5, -0.5))
        trip = np.asarray(lg["trip"]).any(axis=1)
        if trip[-1] and (not self.trip_spans or self.trip_spans[-1][1] is not None):
            self.trip_spans.append([t[-1], None])
        if self.trip_spans and self.trip_spans[-1][1] is None:
            if not trip[-1]:
                self.trip_spans[-1][1] = t[-1]
        for p in getattr(self, "_spans", []):
            p.remove()
        self._spans = [a.axvspan(s0, s1 if s1 is not None else t[-1], color="#e74c3c", alpha=0.12, lw=0)
                       for s0, s1 in self.trip_spans for a in self.ax[1:]]
        for c in self.cur:
            c.set_xdata([t[-1], t[-1]])
        sA, sB = (STATES[int(x)] for x in st[:, -1])
        self.st_txt.set_text(f"A {sA} · B {sB}")
        self.fig.suptitle(f"{self.title}    t = {t[-1]:4.2f} s    ▶ {label}", fontsize=9, x=0.01, ha="left")
        self.fig.canvas.draw()
        return np.asarray(self.fig.canvas.buffer_rgba())[..., :3].copy()


def _overlay(img, lines):
    """3D 화면 왼쪽 위에 글자 (PIL, 맑은 고딕)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.fromarray(img); dr = ImageDraw.Draw(im, "RGBA")
    try:
        fo = ImageFont.truetype("malgun.ttf", max(12, img.shape[0] // 34))
    except OSError:
        fo = ImageFont.load_default()
    y = 8
    for ln in lines:
        x0, y0, x1, y1 = dr.textbbox((10, y), ln, font=fo)
        dr.rectangle((x0 - 4, y0 - 2, x1 + 4, y1 + 2), fill=(255, 255, 255, 190))
        dr.text((10, y), ln, fill=(30, 30, 30), font=fo); y = y1 + 6
    return np.asarray(im)


def run(key, seconds=None, out_dir=OUT, fps=25, w=800, h=600, P=None):
    """→ (기록 dict, 마지막 합성 프레임). out_dir/V_{key}.mp4 · .csv · _poster.png 저장."""
    import imageio.v2 as imageio
    import mujoco
    c = SCEN[key]
    P = load_params() if P is None else P
    T = seconds or c["seconds"]
    if key == "A":
        path = handover_path(c["t_hand"])
    else:
        path = hand_path(jerk=c["jerk"])
    FB = P["contact"]["conductor"]["F_block"]
    Ft, Fmax = MATERIAL[c["mat"]]["Ft"] * FB, MATERIAL[c["mat"]]["Fmax"] * FB
    dash = Dashboard(c["title"], c["seconds"], Ft, Fmax, w, h)
    lg = {k: [] for k in ("t", "state", "mode", "trip", "d", "d_hat", "c", "gate", "teng", "LR", "F", "F_hat", "F_ref",
                          "eps", "eps_hat", "eps_ref", "u", "p")}
    every = max(1, int(round(1.0 / (fps * 0.01))))
    out_dir.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(out_dir / f"V_{key}.mp4", fps=fps, macro_block_size=1)
    st = dict(k=0, frame=None, hand=None, poster=None)

    def hook(pl, o, u, sup, trip):
        tr = pl.truth()
        s0 = sup[0]
        lg["t"].append(pl.t); lg["state"].append([STATES.index(s.state) for s in sup]); lg["mode"].append(s0.mode)
        lg["trip"].append(list(trip)); lg["d"].append(min(tr.d_mm[0], 60.0))
        lg["d_hat"].append(o.val_hat[0] if not o.contact[0] else np.nan); lg["c"].append(int(o.contact[0]))
        lg["gate"].append(int(o.gate[0])); lg["teng"].append(float(o.teng[0])); lg["LR"].append(list(o.LR[0]))
        lg["F"].append(list(tr.F_N)); lg["F_hat"].append([o.val_hat[i] if o.contact[i] else 0.0 for i in range(2)])
        lg["F_ref"].append(s0.F_ref if s0.mode == "force" else np.nan)
        lg["eps"].append(tr.eps[0]); lg["eps_hat"].append(o.eps_hat[0]); lg["eps_ref"].append(s0.eps_ref if s0.mode == "eps" else np.nan)
        lg["u"].append(list(u)); lg["p"].append(tr.p[0])
        if key == "A":   # 손 소품: 손을 떼면 물러남 (geom_pos 만, 물리 불변)
            if st["hand"] is None:
                ids = [i for i in range(pl.m.ngeom) if (mujoco.mj_id2name(pl.m, mujoco.mjtObj.mjOBJ_GEOM, i) or "").startswith("hand")]
                st["hand"] = (ids, pl.m.geom_pos[ids].copy())
            ids, p0 = st["hand"]
            s = float(np.clip((pl.t - c["t_hand"]) / 0.6, 0.0, 1.0))
            pl.m.geom_pos[ids] = p0 + s * HAND_AWAY
        st["k"] += 1
        if st["k"] % every:
            return
        sname = sup[0].state if not (trip[1] or sup[1].state == "SAFETY") else sup[1].state
        jerk = key == "B" and c["jerk"][0] <= pl.t < c["jerk"][0] + 0.15
        label = phase_label(sname, any(trip), key == "A" and pl.t >= c["t_hand"], jerk)
        if c["t_release"] is not None and pl.t > c["t_release"] and sup[0].state in ("RELEASE", "OPEN"):
            label = "release 명령 → 놓기" if sup[0].state == "RELEASE" else "열림 (놓음)"
        img3 = pl.frames(cam="photo", w=w, h=h)
        img3 = _overlay(img3, [c["title"].split(" (")[0], f"t = {pl.t:4.2f} s   {label}", "시뮬레이션 · 소품은 보이기만 함"])
        frame = np.concatenate([img3, dash.draw(lg, label)], axis=1)
        writer.append_data(frame)
        st["frame"] = frame
        if st["poster"] is None and pl.t >= (c["t_hand"] + 0.8 if key == "A" else c["jerk"][0] + 0.3):
            st["poster"] = frame

    a, info = run_case(P, path, T, up=UP_PC, reflex=True, mat=c["mat"], t_grasp=c["t_grasp"], safety="vent",
                       t_release=c["t_release"], scn_kw=dict(photo=c["photo"]), hook=hook)
    writer.close()
    import imageio.v2 as iio
    iio.imwrite(out_dir / f"V_{key}_poster.png", st["poster"] if st["poster"] is not None else st["frame"])
    cols = ["t", "stA", "stB", "tripA", "tripB", "d", "d_hat", "c", "gate", "teng", "dL", "dR", "FA", "FB", "FhA", "FhB",
            "F_ref", "eps", "eps_hat", "eps_ref", "uA", "uB", "p"]
    arr = np.column_stack([lg["t"], lg["state"], lg["trip"], lg["d"], lg["d_hat"], lg["c"], lg["gate"], lg["teng"], lg["LR"],
                           lg["F"], lg["F_hat"], lg["F_ref"], lg["eps"], lg["eps_hat"], lg["eps_ref"], lg["u"], lg["p"]])
    np.savetxt(out_dir / f"V_{key}.csv", arr, delimiter=",", header=",".join(cols), comments="")
    dash.plt.close(dash.fig)
    lg["info"] = info
    return lg, st["frame"]


def metrics(key, lg):
    c, info = SCEN[key], lg["info"]
    t, F = np.asarray(lg["t"]), np.asarray(lg["F"])
    st = np.asarray(lg["state"]); trip = np.asarray(lg["trip"]).any(axis=1)
    i_app = int(np.argmax(st[:, 0] > 0)); i_g = int(np.argmax(st[:, 0] == STATES.index("GRASP")))
    m = dict(F_max=info["Fmax"], F_t=info["Ft"], t_detect=float(t[i_app]), t_grasp_state=float(t[i_g]),
             F_peak=float(F.max()), n_trips=int(sum(info["n_trips"])))
    if key == "A":
        w0, w1 = (t > c["t_grasp"] + 1.0) & (t < c["t_hand"]), t > c["t_hand"] + 0.8
        m.update(F_hold_before=float(F[w0].mean()), F_hold_after=float(F[w1].mean()), F_peak_grasp=float(F[t > c["t_grasp"]].max()),
                 both_contact_after_pct=float(100 * np.mean((F[w1] > 0.05).all(axis=1))))
    else:
        tj = c["jerk"][0]
        tt = t[(t >= tj) & trip]
        m.update(t_trip_after_jerk_s=float(tt[0] - tj) if len(tt) else None, F_peak_jerk=float(F[t >= tj].max()),
                 t_over_s=float(((F[t >= tj] > info["Fmax"]).any(axis=1)).sum() * 0.01),
                 final_state=STATES[int(st[-1, 0])], safety_seen=bool((st[t >= tj] == STATES.index("SAFETY")).any()))
    return m


def plot_timeline(logs, path=OUT / "upper_timeline.png"):
    """상위 제어기 동작 예시: 입력(d 추정, c) → 상태 → 기준 하나 (ε_ref 또는 F_ref)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 9})
    fig, ax = plt.subplots(4, len(logs), figsize=(6.4 * len(logs), 6.6), sharex="col", squeeze=False,
                           gridspec_kw=dict(height_ratios=[1, 0.6, 0.5, 1.2]))
    for j, (key, lg) in enumerate(logs.items()):
        c = SCEN[key]
        t = np.asarray(lg["t"]); st = np.asarray(lg["state"])[:, 0]
        a = ax[:, j]
        a[0].plot(t, lg["d"], c="#999", lw=1, label="d 정답"); a[0].plot(t, lg["d_hat"], c=COLOR_L, lw=1, label=r"$\hat{d}$ (센서)")
        a[0].axhline(24, c="k", ls="--", lw=0.7); a[0].axhline(5, c="k", ls=":", lw=0.7)
        a[0].text(t[-1], 24, " d_far 24", va="center", fontsize=7); a[0].text(t[-1], 5, " d_near 5", va="center", fontsize=7)
        a[0].set_ylim(0, 45); a[0].set_ylabel("입력 ① 근접 [mm]"); a[0].legend(fontsize=7, loc="upper right")
        a[0].set_title(c["title"], fontsize=10, loc="left")
        a[1].step(t, lg["c"], c=COLOR_TENG, where="post", lw=1, label="접촉 c (게이트 ∨ TENG)")
        trip = np.asarray(lg["trip"]).any(axis=1)
        a[1].fill_between(t, 0, 1.3, where=trip, step="post", color="#e74c3c", alpha=0.2, lw=0, label="하위 반사 배기")
        a[1].set_ylim(-0.1, 1.4); a[1].set_yticks([0, 1]); a[1].set_ylabel("입력 ② 접촉"); a[1].legend(fontsize=7, loc="upper left")
        for k, s in enumerate(STATES):
            on = st == k
            if on.any():
                a[2].fill_between(t, 0, 1, where=on, step="post", color=STATE_RGB[s], lw=0)
                i0 = np.flatnonzero(on)
                for seg in np.split(i0, np.flatnonzero(np.diff(i0) > 1) + 1):
                    if t[seg[-1]] - t[seg[0]] > 0.45:
                        a[2].text((t[seg[0]] + t[seg[-1]]) / 2, 0.5, s, ha="center", va="center", fontsize=7.5, weight="bold")
        a[2].set_yticks([]); a[2].set_ylabel("상태 (상위)")
        a[3].plot(t, lg["eps_ref"], c="#222", lw=1.3, label="ε_ref [%] (자유 모드 기준)")
        a[3].plot(t, lg["eps_hat"], c=COLOR_R, lw=0.7, alpha=0.6, label=r"$\hat{\varepsilon}$ [%]")
        a3 = a[3].twinx()
        a3.plot(t, lg["F_ref"], c="#c0392b", lw=1.6, label="F_ref [N] (접촉 모드 기준)")
        a3.plot(t, np.asarray(lg["F"])[:, 0], c="#c0392b", lw=0.7, alpha=0.4, label="F 정답 A [N]")
        a3.axhline(lg["info"]["Fmax"], c="r", ls=":", lw=0.8); a3.set_ylim(0, 1.5 * max(lg["info"]["Fmax"], 1)); a3.set_ylabel("F [N]")
        a[3].set_ylim(-0.5, 13); a[3].set_ylabel("출력: 기준 하나"); a[3].set_xlabel("t [s]")
        a[3].legend(fontsize=7, loc="upper left"); a3.legend(fontsize=7, loc="center left")
        for x in a:
            x.axvline(c["t_grasp"], c="#555", lw=0.6, ls="--"); x.grid(alpha=0.2)
        a[0].text(c["t_grasp"], 44, " 파지 명령", fontsize=7, va="top")
    fig.suptitle("상위 제어기 동작 (시뮬레이션): 근접·접촉 입력 → 상태 전이 → 상태별 기준 하나를 하위로", fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def main(which):
    sys.stdout.reconfigure(encoding="utf-8")
    P = load_params()
    logs, res = {}, {}
    for key in which:
        lg, _ = run(key, P=P)
        logs[key], res[key] = lg, metrics(key, lg)
        print(key, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[key].items()}, flush=True)
    if logs:
        plot_timeline(logs)
        old = load_params().get("results_video", {})
        save_params("results_video", {**old, **res})


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("A", "B"))
