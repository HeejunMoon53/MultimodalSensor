"""상·하위 계층 실험 (스펙 13절). 모든 결과는 시뮬레이션.

S10 하위 반사 안전: 인체를 쥔 뒤 손이 갑자기 손가락 B 쪽으로 10 mm 움직인다 (0.1 s).
     상위만 100 Hz(지연 0) · 상위만 20 Hz + 20 ms · 상위 20 Hz + 하위 반사 1 kHz 를 비교한다.
S11 시나리오 2 상호작용: 쥔 손이 천천히 밀고 당긴다 (±6 mm, 0.25 Hz).
     안전 + 힘 유지(C, F_ref = F_t) vs 어드미턴스 따라가기(B_a ε̇_ref = F_t − F̂). 둘 다 하위 반사 켬.

실행 (code 폴더에서): C:/ml_env/Scripts/python.exe run_hri.py [S10] [S11]
"""
import sys

import numpy as np

import paths  # noqa: F401
from layers import Reflex, UpperLink
from paths import OUT, load_params, save_params
from plant import Plant, Scenario
from run_compare import CTRL9, TS, approach_path, make_grasp_ctrl, make_sup, plt
from supervisor import MATERIAL

STATES = ["OPEN", "APPROACH", "CONTACT", "GRASP", "SAFETY", "RELEASE"]
UP_PC = dict(n_up=5, n_lat=2)      # 상위 PC: 20 Hz, 통신 지연 20 ms (가정값)
UP_FAST = dict(n_up=1, n_lat=0)    # 기존 시뮬 가정: 감독기도 100 Hz, 지연 0
C_CTRL = "C F-LQG + RLS 스케줄"


def hand_path(t_grasp=4.5, jerk=None, push=None):
    """인체 손: 접근(흔들림 ±4 mm) 후 jerk=(t, dx, t_rise) 계단 이동 또는 push=(t0, A, f) 밀고 당기기 [mm]."""
    base = approach_path("human")

    def f(t):
        x, y, z = base(t)
        if jerk is not None:
            x += jerk[1] * np.clip((t - jerk[0]) / jerk[2], 0.0, 1.0)
        if push is not None and t > push[0]:
            x += push[1] * np.sin(2 * np.pi * push[2] * (t - push[0]))
        return (x, y, z)
    return f


def run_case(P, path, seconds, up=UP_PC, reflex=True, ctrl=C_CTRL, mat="human", t_grasp=4.5, seed=21, safety="eps", up_drop=None, fault=None,
             t_release=None, scn_kw=None, hook=None):
    """2지, 상위 UpperLink(주기·지연) + 하위(내부 루프 10 ms, 반사 1 kHz). 기록 열은 COLS.
    safety: 상위 SAFETY 동작. "eps" = ε_ref 를 열림 쪽으로 (기존), "vent" = 상위가 배기 명령 (u = 0).
    up_drop: 이 시각 [s] 이후 상위 통신 두절 (상태·기준 동결).
    fault: (t, 손가락, u) 이 시각부터 내부 루프 지령이 u 로 폭주 (고장 주입). 배기(반사·상위 SAFETY)가 우선한다.
    t_release: 이 시각 [s] 이후 상위 명령 = release. scn_kw: Scenario 추가 인자 (photo 등).
    hook(pl, o, u, sup, trip): 매 스텝 끝에 호출 (영상·기록용, run_video.py)."""
    spec = CTRL9[ctrl]
    pl = Plant(Scenario(material=mat, obj_path=path, **(scn_kw or {})), seed=seed)
    ctr = [make_grasp_ctrl(P, spec) for _ in range(2)]
    sup = [make_sup(P, mat, spec["kind"], Ts=up["n_up"] * TS) for _ in range(2)]
    link = [UpperLink(s, **up) for s in sup]
    FB = sup[0].FB
    Fmax, Ft = MATERIAL[mat]["Fmax"] * FB, MATERIAL[mat]["Ft"] * FB
    if reflex:
        pl.reflex = [Reflex(Fmax, Ft) for _ in range(2)]
    u, rows = np.zeros(2), []
    for k in range(int(seconds / TS)):
        o = pl.step(u); tr = pl.truth()
        cmd = "release" if t_release is not None and pl.t > t_release else ("grasp" if pl.t > t_grasp else "approach")
        trip = [bool(reflex and pl.reflex[i].tripped) for i in range(2)]
        for i in range(2):
            Fh = o.val_hat[i] if o.contact[i] else 0.0
            if up_drop is None or pl.t < up_drop:
                link[i].step(dict(d_hat=o.val_hat[i] if not o.contact[i] else 0.0, F_hat=Fh, contact=o.contact[i],
                                  eps_hat=o.eps_hat[i], reflex=int(trip[i])), mat, cmd)
            if sup[i].state == "OPEN" or trip[i] or (safety == "vent" and sup[i].state == "SAFETY"):  # 배기 중: 내부 루프도 0 에서 다시 시작 (적분 와인드업 방지)
                u[i] = 0.0; ctr[i].reset()
                if hasattr(ctr[i], "u_prev"):
                    ctr[i].u_prev = 0.0
            else:
                u[i] = ctr[i].u(o.p_mon[i], o.eps_hat[i], Fh, sup[i])
                if fault is not None and pl.t >= fault[0] and i == fault[1]:
                    u[i] = fault[2]
        rows.append([pl.t, *tr.F_N, *(o.val_hat * o.contact), *u, *tr.p, *[STATES.index(s.state) for s in sup], *trip,
                     *tr.d_mm])
        if hook is not None:
            hook(pl, o, u, sup, trip)
    return np.array(rows), dict(Fmax=Fmax, Ft=Ft, n_trips=[r.n_trips for r in pl.reflex] if reflex else [0, 0])


COLS = "t,F0,F1,Fh0,Fh1,u0,u1,p0,p1,st0,st1,trip0,trip1,d0,d1"


def _s10_metrics(a, info, t0, seconds):
    t, F = a[:, 0], a[:, 1:3]
    w = t >= t0
    over = np.maximum(F[w] - info["Fmax"], 0.0)
    return dict(F_peak=float(F[w].max()), F_max=info["Fmax"], t_over_s=float((over.max(axis=1) > 0).sum() * TS),
                impulse_over_Ns=float(over.sum() * TS), F_end=float(F[t > seconds - 0.5].max(axis=1).mean()),
                n_trips=int(sum(info["n_trips"])), F_hold_before=float(F[(t > 5.5) & (t < t0)].mean()))


S10_CASES = {"상위 20 Hz + 20 ms · SAFETY = ε 열기": dict(n_lat=2, reflex=False, safety="eps"),
             "상위 배기 · 지연 20 ms": dict(n_lat=2, reflex=False), "상위 배기 · 지연 100 ms": dict(n_lat=10, reflex=False),
             "상위 배기 · 지연 200 ms": dict(n_lat=20, reflex=False), "상위 배기 · 통신 두절": dict(n_lat=2, reflex=False, drop=True),
             "하위 반사 1 kHz": dict(n_lat=2, reflex=True), "하위 반사 1 kHz · 통신 두절": dict(n_lat=2, reflex=True, drop=True)}


def s10_reflex(P, seconds=8.0, t_f=6.5):
    """(1) 고장 주입: 파지 유지 중 t_f 에 손가락 B 내부 루프 지령이 30 kPa 로 폭주. 재질 = 인체·도체.
    상위 주기 20 Hz, 지연·두절을 바꿔 가며 하위 반사(1 kHz)와 비교. 상위 SAFETY 는 배기(ε 열기는 기존 참고).
    (2) 손 급이동 (인체, 0.1 s 에 10 mm): 상위 SAFETY 가 ε 열기 vs 배기."""
    res, recs = {}, {}
    for mat in ("human", "conductor"):
        for name, c in S10_CASES.items():
            a, info = run_case(P, approach_path(mat), seconds, mat=mat, up=dict(n_up=5, n_lat=c["n_lat"]), reflex=c["reflex"],
                               safety=c.get("safety", "vent"), up_drop=t_f - 0.2 if c.get("drop") else None, fault=(t_f, 1, 30.0))
            key = f"{mat} | {name}"
            res[key], recs[key] = _s10_metrics(a, info, t_f, seconds), a
            np.savetxt(OUT / f"S10_{mat}_{list(S10_CASES).index(name)}.csv", a, delimiter=",", header=COLS, comments="")
            print("S10", key, {k: round(v, 3) for k, v in res[key].items()}, flush=True)
    t_j = 6.5
    for name, sf in (("손 급이동 · SAFETY = ε 열기", "eps"), ("손 급이동 · SAFETY = 배기", "vent")):
        a, info = run_case(P, hand_path(jerk=(t_j, 10.0, 0.1)), 8.5, up=UP_PC, reflex=False, safety=sf)
        key = f"human | {name}"
        res[key], recs[key] = _s10_metrics(a, info, t_j, 8.5), a
        print("S10", key, {k: round(v, 3) for k, v in res[key].items()}, flush=True)
    _plot_s10(recs, res, t_f)
    save_params("results_s10", res)
    return res


def _plot_s10(recs, res, t_f):
    names = list(S10_CASES)
    show = {names[0]: "#999", names[1]: "#2b6cb0", names[3]: "#7fa7d9", names[4]: "#7a4ea3", names[5]: "#2CA02C"}
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.0), gridspec_kw=dict(width_ratios=[1.3, 1.2, 1.0]))
    for nm, c in show.items():
        a = recs[f"human | {nm}"]
        ax[0].plot(a[:, 0], a[:, 2], c=c, lw=1.1, label=nm)
    ax[0].axhline(res[f"human | {names[0]}"]["F_max"], ls=":", c="r", lw=0.9, label="F_max (인체)")
    ax[0].axvline(t_f, c="#888", lw=0.7)
    ax[0].set_xlim(t_f - 0.3, t_f + 1.3); ax[0].set_xlabel("t [s]"); ax[0].set_ylabel("손가락 B 정답 F [N]")
    ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
    ax[0].set_title("(a) 인체 파지 중 지령 폭주 (손가락 B → 30 kPa)", fontsize=9, loc="left")
    y = np.arange(len(names))
    for k, (mat, c) in enumerate((("human", "#c0392b"), ("conductor", "#555"))):
        v = [res[f"{mat} | {n}"]["impulse_over_Ns"] for n in names]
        ax[1].barh(y + (k - 0.5) * 0.38, v, 0.38, color=c, label={"human": "인체", "conductor": "도체"}[mat])
        for j, x in enumerate(v):
            ax[1].text(x, y[j] + (k - 0.5) * 0.38, f" {x:.2f}", va="center", fontsize=6.5)
    ax[1].set_yticks(y, names, fontsize=7); ax[1].invert_yaxis(); ax[1].legend(fontsize=7, loc="lower right")
    ax[1].set_xlabel("F_max 초과 충격량 ∫ max(F - F_max, 0) dt [N·s]"); ax[1].set_title("(b) 지연 · 두절 비교 (1.5 s 창)", fontsize=9, loc="left")
    for nm, c in (("손 급이동 · SAFETY = ε 열기", "#999"), ("손 급이동 · SAFETY = 배기", "#2b6cb0")):
        a = recs[f"human | {nm}"]
        ax[2].plot(a[:, 0], a[:, 2], c=c, lw=1.1, label=nm.split(" · ")[1])
    ax[2].axhline(res[f"human | {names[0]}"]["F_max"], ls=":", c="r", lw=0.9)
    ax[2].set_xlim(6.2, 8.5); ax[2].set_ylim(0, 8); ax[2].set_xlabel("t [s]"); ax[2].legend(fontsize=7); ax[2].grid(alpha=0.3)
    ax[2].set_title("(c) 손 급이동 10 mm / 0.1 s (첫 피크 = 수동 충돌)", fontsize=9, loc="left")
    fig.suptitle("S10 하위 반사 안전 (시뮬레이션): 상위 20 Hz + 지연 vs 하위 1 kHz 반사", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "S10.png", dpi=150)


def s11_interact(P, seconds=12.0, t0=5.5):
    cases = {"안전 + 힘 유지 (C, F_ref = F_t)": dict(ctrl=C_CTRL),
             "어드미턴스 따라가기 (가상 댐퍼 B_a)": dict(ctrl="A 어드미턴스→ε (기존)")}
    path = hand_path(push=(t0, 6.0, 0.25))
    res, recs = {}, {}
    for name, cfg in cases.items():
        a, info = run_case(P, path, seconds, up=UP_PC, reflex=True, **cfg)
        t, F = a[:, 0], a[:, 1:3]
        w = t > t0
        m = dict(contact_both_pct=float(100 * np.mean((F[w] > 0.05).all(axis=1))),
                 rmse_F_N=float(np.sqrt(np.mean((F[w] - info["Ft"]) ** 2))), F_target=info["Ft"],
                 F_peak=float(F[w].max()), F_max=info["Fmax"],
                 t_over_s=float(((F[w] > info["Fmax"]).any(axis=1)).sum() * TS),
                 n_trips=int(sum(info["n_trips"])),
                 safety_pct=float(100 * np.mean((a[w][:, 9:11] == STATES.index("SAFETY")).any(axis=1))))
        res[name], recs[name] = m, a
        np.savetxt(OUT / f"S11_{list(cases).index(name)}.csv", a, delimiter=",", header=COLS, comments="")
        print("S11", name, {k: round(v, 3) for k, v in m.items()}, flush=True)
    _plot(recs, res, "S11", 4.0, seconds, "S11 시나리오 2 상호작용 (시뮬레이션): 쥔 손이 ±6 mm 밀고 당김", mark=t0)
    save_params("results_s11", res)
    return res


def _plot(recs, res, tag, t_a, t_b, title, mark=None):
    n = len(recs)
    fig, ax = plt.subplots(n, 1, figsize=(10, 2.3 * n + 0.6), sharex=True)
    for k, (name, a) in enumerate(recs.items()):
        t, m = a[:, 0], res[name]
        for i, c in ((0, "#7a4ea3"), (1, "#c0392b")):
            ax[k].plot(t, a[:, 1 + i], c=c, lw=1.0, label=f"F 정답 손가락 {'AB'[i]}")
            tr = a[:, 11 + i] > 0
            if tr.any():
                ax[k].fill_between(t, 0, 1, where=tr, transform=ax[k].get_xaxis_transform(), color=c, alpha=0.12, lw=0)
        ax[k].axhline(m["F_max"], ls=":", c="r", lw=0.9, label="F_max")
        if "F_target" in m:
            ax[k].axhline(m["F_target"], ls="--", c="#222", lw=0.8, label="F_t")
        if mark is not None:
            ax[k].axvline(mark, c="#888", lw=0.7)
        ax[k].set_ylabel("F [N]"); ax[k].set_title(name, fontsize=9, loc="left"); ax[k].grid(alpha=0.3)
    ax[0].legend(fontsize=7, ncol=4, loc="upper left")
    ax[-1].set_xlim(t_a, t_b); ax[-1].set_xlabel("t [s]   (옅은 띠 = 하위 반사 배기 중)")
    fig.suptitle(title, fontsize=10); fig.tight_layout(); fig.savefig(OUT / f"{tag}.png", dpi=150)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    which = tuple(sys.argv[1:]) or ("S10", "S11")
    if "S10" in which:
        s10_reflex(load_params())
    if "S11" in which:
        s11_interact(load_params())
