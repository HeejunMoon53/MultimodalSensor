"""시뮬레이션 실시간 보기: MuJoCo 3D 창 + 그래프 창 (힘·변형률·압력/입력·근접/접촉·오차). 모든 값은 시뮬레이션.

실행 (저장소 루트에서):
  C:/ml_env/Scripts/python.exe Hardware/로봇제어프로젝트/code/live_view.py --case grasp --mat conductor --ctrl D
  --case grasp : 물체가 아래에서 다가옴 → 근접 pre-shape → 파지 명령(4.5 s) → 힘 유지 → 해제 (S7 과 같음)
  --case hold  : 고정 물체를 쥐고 6 s 에 목표 힘 +30 % 계단 (S9 와 같음)
  --ctrl A|B|C|D : A 어드미턴스(기존) · B F-LQG · C +RLS 스케줄 · D +DOB
  --no3d : 그래프만 · --headless : 창 없이 끝까지 돌리고 PNG·CSV 만 저장
그래프는 손가락 0 기준. 끝나면 out/live_<case>_<mat>_<ctrl>.csv/png 저장.
"""
import argparse
import sys
import time

import numpy as np

import paths  # noqa: F401
from paths import OUT, load_params

CTRL_KEY = {"A": "A 어드미턴스→ε (기존)", "B": "B F-LQG 공칭", "C": "C F-LQG + RLS 스케줄", "D": "D C + DOB"}
STATES = ["OPEN", "APPROACH", "CONTACT", "GRASP", "SAFETY", "RELEASE"]
COLS = "t,F,F_hat,F_ref,F_t,F_max,eps,eps_hat,eps_ref,p,p_mon,u,d,d_hat,contact,gate,teng_V,k_hat,state,mode_force"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=("grasp", "hold"), default="grasp")
    ap.add_argument("--mat", choices=("conductor", "dielectric", "human"), default="conductor")
    ap.add_argument("--ctrl", choices=tuple(CTRL_KEY), default="D")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--no3d", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--window", type=float, default=10.0, help="그래프 표시 구간 [s]")
    a = ap.parse_args(argv)

    import matplotlib
    if a.headless:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
    import run_compare as rc
    from plant import Plant, Scenario
    from supervisor import MATERIAL

    P = load_params()
    TS = rc.TS
    secs = a.seconds or (9.0 if a.case == "grasp" else 10.0)
    if a.case == "grasp":
        scn = Scenario(material=a.mat, obj_path=rc.approach_path(a.mat))
    else:
        scn = Scenario(material=a.mat, obj_start_mm=(0.0, 0.0, -70.0))
    pl = Plant(scn, seed=21)
    spec = rc.CTRL9[CTRL_KEY[a.ctrl]]
    ctr = [rc.make_grasp_ctrl(P, spec) for _ in range(2)]
    sup = [rc.make_sup(P, a.mat, spec["kind"]) for _ in range(2)]
    FB0 = sup[0].FB

    viewer = None
    if not (a.no3d or a.headless):
        import mujoco.viewer
        viewer = mujoco.viewer.launch_passive(pl.m, pl.d)

    # 그래프 창
    fig, ax = plt.subplots(5, 1, figsize=(10, 9.5), sharex=True)
    def ln(i, c, lab, **kw):
        return ax[i].plot([], [], c=c, lw=1.0, label=lab, **kw)[0]
    L = dict(F=ln(0, "#c0392b", "F 정답"), F_hat=ln(0, "#1F77B4", "F 센서 (MoE)"), F_ref=ln(0, "#222", "F_ref", ls="--"),
             F_max=ln(0, "r", "F_max", ls=":"),
             eps=ln(1, "#2CA02C", "ε 정답"), eps_hat=ln(1, "#8fd18f", "ε 센서 (MoE)"), eps_ref=ln(1, "#222", "ε_ref", ls="--"),
             p=ln(2, "#7a4ea3", "p 방 압력"), u=ln(2, "#d35400", "u 지령"),
             d=ln(3, "#444", "d 정답 [mm]"), d_hat=ln(3, "#FF8C00", "d 센서 [mm]"),
             err=ln(4, "#c0392b", "F - F_ref (정답) [N]"), err_hat=ln(4, "#1F77B4", "F센서 - F_ref [N]"))
    ax_c = ax[3].twinx(); L["contact"] = ax_c.step([], [], c="#1F77B4", lw=0.8, label="접촉 c")[0]
    ax_c.set_ylim(-0.1, 1.5); ax_c.set_yticks([0, 1])
    ax_k = ax[4].twinx(); L["k"] = ax_k.plot([], [], c="#555", lw=1.0, label="k_eq 추정 (RLS) [N/%]")[0]; ax_k.set_ylim(0.1, 0.8)
    for i, yl in enumerate(("F [N]", "ε [%]", "[kPa]", "근접 d [mm]", "오차 [N]")):
        ax[i].set_ylabel(yl, fontsize=8); ax[i].legend(fontsize=7, loc="upper left", ncol=4); ax[i].grid(alpha=0.3)
    ax_k.legend(fontsize=7, loc="upper right"); ax_c.legend(fontsize=7, loc="upper right")
    ax[0].set_ylim(-0.2, 7); ax[1].set_ylim(-2, 14); ax[2].set_ylim(-1, 32); ax[3].set_ylim(0, 40); ax[4].set_ylim(-3, 3)
    ax[4].set_xlabel("t [s]")
    info = fig.text(0.01, 0.995, "", va="top", fontsize=9, family="Malgun Gothic")
    fig.suptitle(f"실시간 시뮬레이션 — {a.case} · {a.mat} · {CTRL_KEY[a.ctrl]}", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    if not a.headless:
        plt.ion(); plt.show(block=False)

    rows, u = [], np.zeros(2)
    wall0 = time.perf_counter()
    for k in range(int(secs / TS)):
        if viewer is not None and not viewer.is_running():
            break
        o = pl.step(u); tr = pl.truth()
        if a.case == "grasp":
            cmd = "release" if pl.t > secs - 1.5 else ("grasp" if pl.t > 4.5 else "approach")
        else:
            cmd = "grasp"
            if pl.t > 6.0 and sup[0].FB == FB0:
                for s_ in sup:
                    s_.FB *= 1.3  # 목표 힘 +30 % 계단 (S9)
        for i in range(2):
            Fh = o.val_hat[i] if o.contact[i] else 0.0
            sup[i].step(dict(d_hat=o.val_hat[i] if not o.contact[i] else 0.0, F_hat=Fh, contact=o.contact[i],
                             eps_hat=o.eps_hat[i]), a.mat, cmd)
            if sup[i].state == "OPEN":
                u[i] = 0.0; ctr[i].reset()
            else:
                u[i] = ctr[i].u(o.p_mon[i], o.eps_hat[i], Fh, sup[i])
        s0, c0 = sup[0], ctr[0]
        Ft, Fmax = MATERIAL[a.mat]["Ft"] * s0.FB, MATERIAL[a.mat]["Fmax"] * s0.FB
        Fref = s0.F_ref if s0.mode == "force" else (Ft if s0.state == "GRASP" else np.nan)
        kh = c0.con.k_eq if getattr(c0, "con", None) is not None and getattr(c0, "in_con", False) else np.nan
        rows.append([pl.t, tr.F_N[0], o.val_hat[0] if o.contact[0] else np.nan, Fref, Ft, Fmax, tr.eps[0], o.eps_hat[0],
                     s0.eps_ref if s0.mode == "eps" else np.nan, tr.p[0], o.p_mon[0], u[0], tr.d_mm[0], o.val_hat[0] if not o.contact[0] else np.nan,
                     o.contact[0], o.gate[0], o.teng[0], kh, STATES.index(s0.state), int(s0.mode == "force")])
        if viewer is not None:
            viewer.sync()
        if not a.headless and k % 5 == 0:  # 50 ms 마다 그래프 갱신
            _update(L, ax, np.array(rows), a.window)
            info.set_text(f"t = {pl.t:5.2f} s  (벽시계 {time.perf_counter() - wall0:5.1f} s)   상태 {s0.state} / {s0.mode}   "
                          f"F = {tr.F_N[0]:.2f} N   F̂ = {rows[-1][2] if o.contact[0] else 0:.2f} N   ε = {tr.eps[0]:.2f} %   "
                          f"ε̂ = {o.eps_hat[0]:.2f} %   u = {u[0]:.1f} kPa")
            fig.canvas.draw_idle(); fig.canvas.flush_events()

    R = np.array(rows)
    _update(L, ax, R, R[-1, 0] + 0.1)
    tag = f"live_{a.case}_{a.mat}_{a.ctrl}"
    np.savetxt(OUT / f"{tag}.csv", R, delimiter=",", header=COLS, comments="")
    fig.savefig(OUT / f"{tag}.png", dpi=130)
    g = R[:, 18] == STATES.index("GRASP")
    if g.any():
        e = R[g, 1] - R[g, 3]
        print(f"GRASP 구간 {g.sum() * TS:.2f} s: F 오차 RMSE {np.sqrt(np.nanmean(e ** 2)):.3f} N, 최대 F {R[:, 1].max():.2f} N "
              f"(F_max {R[-1, 5]:.2f}), F̂ − F 평균 {np.nanmean(R[g, 2] - R[g, 1]):+.2f} N")
    print("저장:", OUT / f"{tag}.csv", OUT / f"{tag}.png")
    if viewer is not None:
        viewer.close()
    if not a.headless:
        plt.ioff(); plt.show()


def _update(L, ax, R, window):
    t = R[:, 0]
    for k, j in (("F", 1), ("F_hat", 2), ("F_ref", 3), ("F_max", 5), ("eps", 6), ("eps_hat", 7), ("eps_ref", 8),
                 ("p", 9), ("u", 11), ("d", 12), ("d_hat", 13), ("contact", 14), ("k", 17)):
        L[k].set_data(t, R[:, j])
    L["err"].set_data(t, R[:, 1] - R[:, 3]); L["err_hat"].set_data(t, R[:, 2] - R[:, 3])
    ax[0].set_xlim(max(0.0, t[-1] - window), max(window, t[-1]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
