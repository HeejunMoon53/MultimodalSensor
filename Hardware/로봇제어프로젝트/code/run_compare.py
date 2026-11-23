"""가상 실험 S4–S8 (스펙 6절): 잡음, 제어기 비교, 강건성(DOB), 파지 시연, 차단력·접촉 강성.

모든 결과는 시뮬레이션이다. 지표 CSV·그림·영상 → out/, 요약 → params.json["results"].
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import paths  # noqa: F401
from design_det import StateFeedback, load_model
from design_dob import Dob
from design_stoch import Kalman, Lqg
from metrics import effort, improvement_pct, rmse, step_metrics
from paths import OUT, load_params, save_params
from plant import Plant, Scenario
from supervisor import MATERIAL, Supervisor

plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "mathtext.fontset": "dejavusans"})
TS = 0.01
C_REF, C_Y, C_U, C_EST = "#222222", "#2CA02C", "#7a4ea3", "#d35400"


# ---------------- 제어기 ----------------
class OpenLoop:
    """기준선: S1 정적 맵 역함수 피드포워드 (되먹임 없음)."""

    def __init__(self, P):
        s1 = np.loadtxt(OUT / "sysid_S1.csv", delimiter=",", skiprows=1)
        k = s1[:, 0] % 2.0 > 1.5  # 각 단의 마지막 0.5 s
        u, e = s1[k, 1], s1[k, 6]
        order = np.argsort(e)
        self.e, self.uu = e[order], u[order]

    def reset(self):
        pass

    def u(self, y, r, x_true=None):
        return float(np.interp(r, self.e, self.uu))


class WithDob:
    def __init__(self, base, dob):
        self.base, self.dob = base, dob

    def reset(self):
        self.base.reset()

    def u(self, y, r, x_true=None):
        uc = self.base.u(y, r, x_true)
        return float(np.clip(self.dob.correct(uc, y[1]), 0.0, 30.0))

    @property
    def xh(self):
        return getattr(self.base, "xh", None)


def make_controllers(P, which=None):
    Ad, Bd, C, Ts, x0, u0, _ = load_model(P)
    det, st = P["det"], P["stoch"]
    L = np.array(det["obs"]["L"])
    n = Ad.shape[0]
    mk_kf = lambda ws=1.0: Kalman(Ad, Bd, C, np.eye(n), ws * np.diag(st["W"]), np.diag(st["V"]), np.zeros(n), np.eye(n))
    Ge = P["sysid"]["G_eps"]
    mk_dob = lambda tq: Dob(Ge["a"], Ge["b"], Ge["nk"], tq, Ts, r=P["dob"]["r"], y0=Ge["y0"], u0=Ge["u0"])
    ctl = {
        "개루프 FF(이상적 맵)": lambda: OpenLoop(P),
        "PP(전상태)": lambda: StateFeedback(Ad, Bd, C, det["pp"]["K"], det["pp"]["KI"], None, x0, u0),
        "PP+관측기": lambda: StateFeedback(Ad, Bd, C, det["pp"]["K"], det["pp"]["KI"], L, x0, u0),
        "LQR+관측기": lambda: StateFeedback(Ad, Bd, C, det["lqr"]["K"], det["lqr"]["KI"], L, x0, u0),
        "LQG": lambda: Lqg(det["lqr"]["K"], det["lqr"]["KI"], mk_kf(), x0, u0),
        "LQG(W×0.1)": lambda: Lqg(det["lqr"]["K"], det["lqr"]["KI"], mk_kf(0.1), x0, u0),
        "LQG(W×10)": lambda: Lqg(det["lqr"]["K"], det["lqr"]["KI"], mk_kf(10.0), x0, u0),
    }
    for tq in P["dob"]["tau_q_list"]:
        tag = "LQG+DOB" + ("*" if tq == P["dob"]["tau_q"] else "") + f"(τq={tq * 1e3:.0f}ms)"
        ctl[tag] = (lambda t=tq: WithDob(Lqg(det["lqr"]["K"], det["lqr"]["KI"], mk_kf(), x0, u0), mk_dob(t)))
    return {k: v for k, v in ctl.items() if which is None or k in which}


def est_state(c):
    if hasattr(c, "kf"):
        return c.kf.x_post
    if hasattr(c, "base") and hasattr(c.base, "kf"):
        return c.base.kf.x_post
    return getattr(c, "xh", None)


def eps_dot_of(x, phys):
    """상태 추정에서 ε̇: 3상태면 x[2], 2상태면 τ_f ε̇ = K_f p − ε."""
    return x[2] if len(x) == 3 else (phys["K_f"] * x[0] - x[1]) / phys["tau_f"]


def run_loop(plant, ctrl, ref, x0, n_pre=200, phys=None):
    """n_pre 샘플 동안 기준 = ref[0] 으로 먼저 정착시킨 뒤 기록."""
    phys = phys or load_params()["model"]["phys"]
    n = len(x0)
    ctrl.reset()
    rec = []
    full = np.r_[np.full(n_pre, x0[1]), ref]  # 동작점 ε₀ 에서 정착 후 기준 시작
    for k, r in enumerate(full):
        o = plant.step(np.array([u_last])) if k else plant.step(np.array([x0[0]]))
        tr = plant.truth()
        y = np.array([o.p_mon[0], o.eps_hat[0]])
        xt = np.array([tr.p[0], tr.eps[0], tr.eps_dot[0]])[:n]
        u_last = ctrl.u(y, r, xt)
        xh = est_state(ctrl)
        xh = (xh + x0) if xh is not None else np.full(n, np.nan)
        if k >= n_pre:
            rec.append([plant.t, r, o.eps_hat[0], tr.eps[0], tr.eps_dot[0], xh[1], eps_dot_of(xh, phys), u_last, tr.p[0], o.p_mon[0]])
    return np.array(rec)


COLS = "t,r,eps_hat,eps,eps_dot,eps_est,eps_dot_est,u,p,p_mon"


def summarize(rec, t_step=(0.0, 4.0)):
    t, r, y = rec[:, 0] - rec[0, 0], rec[:, 1], rec[:, 3]
    w = (t >= t_step[0]) & (t < t_step[1] - TS / 2)
    sm = step_metrics(t[w], y[w], r[w], band=0.1)
    ef = effort(rec[:, 7])
    est = rmse(rec[:, 6], rec[:, 4]) if np.isfinite(rec[:, 6]).all() else float("nan")
    return dict(**sm, rmse=rmse(y, r), rmse_meas=rmse(rec[:, 2], r), **ef, est_rmse_epsdot=est)


# ---------------- S4 ----------------
def s4_noise(P):
    pl = Plant(Scenario(fingers=1), seed=11)
    rows = [(o.p_mon[0], o.eps_hat[0]) for o in (pl.step(np.array([P["sysid"]["p0"]])) for _ in range(3300))]
    a = np.array(rows[300:])
    from scipy.signal import detrend
    var = [float(np.var(detrend(a[:, 0]))), float(np.var(detrend(a[:, 1])))]  # 지령 일정 → 선형 추세만 제거
    save_params("noise", dict(var=var, std=[float(np.sqrt(v)) for v in var], n=len(a)))
    print("S4 잡음 분산 [p, ε]:", var)


# ---------------- S5 ----------------
def reference(eps0, Ts=TS):
    n = lambda s: int(round(s / Ts))
    t = np.arange(n(6.0)) * Ts
    trap = np.r_[np.linspace(0, 4, n(1.5)), np.full(n(1.5), 4.0), np.linspace(4, 0, n(1.5)), np.zeros(n(1.0))]
    return eps0 + np.r_[np.full(n(4.0), 3.0), np.full(n(3.0), -3.0), trap, 2.0 * np.sin(2 * np.pi * 0.5 * t)]


def s5_compare(P):
    x0 = np.array(P["model"]["x0"])
    ref = reference(x0[1])
    res, recs = {}, {}
    for name, mk in make_controllers(P).items():
        rec = run_loop(Plant(Scenario(fingers=1), seed=5), mk(), ref, x0)
        recs[name], res[name] = rec, summarize(rec)
        np.savetxt(OUT / f"S5_{name.replace('/', '_').replace('*', '')}.csv", rec, delimiter=",", header=COLS, comments="")
        print("S5", name, {k: round(v, 3) for k, v in res[name].items()}, flush=True)
    base = res["개루프 FF(이상적 맵)"]
    for name, r in res.items():
        r["rmse_improve_pct"] = improvement_pct(base["rmse_meas"], r["rmse_meas"])
    _write_csv(OUT / "S5_metrics.csv", res)
    _plot_s5(recs, res)
    return res


def _write_csv(path, res):
    keys = list(next(iter(res.values())).keys())
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("controller," + ",".join(keys) + "\n")
        for k, r in res.items():
            f.write(k + "," + ",".join(f"{r[q]:.5g}" for q in keys) + "\n")


def _plot_s5(recs, res):
    names = list(recs)
    fig, ax = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    for i, n in enumerate(names):
        r = recs[n]; t = r[:, 0] - r[0, 0]
        if i == 0:
            ax[0].plot(t, r[:, 1], c=C_REF, lw=1.6, label="기준 r")
        ax[0].plot(t, r[:, 3], lw=0.9, label=n)
        ax[1].plot(t, r[:, 7], lw=0.8)
        if np.isfinite(r[:, 6]).all():
            ax[2].plot(t, r[:, 6], lw=0.8, label=n)
    r = recs[names[-1]]; ax[2].plot(r[:, 0] - r[0, 0], r[:, 4], c="k", lw=1.2, label="정답 ε̇")
    ax[0].set_ylabel("ε [%]"); ax[1].set_ylabel("u [kPa]"); ax[2].set_ylabel("ε̇ 추정 [%/s]"); ax[2].set_xlabel("t [s]")
    ax[0].legend(fontsize=7, ncol=4); ax[2].legend(fontsize=7, ncol=4)
    fig.suptitle("S5 기준 추종 비교 (시뮬레이션): 기준·출력 / 입력 / 추정 상태", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "S5_timeseries.png", dpi=150)
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for a, key, lab in zip(ax, ("rmse_meas", "overshoot_pct", "sum_du"), ("추종 RMSE (측정 ε̂) [%]", "오버슈트 [%]", "입력 변동 Σ|Δu| [kPa]")):
        v = [res[n][key] for n in names]
        a.barh(names, v, color=["#bbb"] + ["#2b6cb0"] * (len(names) - 1))
        a.set_title(lab, fontsize=9); a.invert_yaxis()
        for j, x in enumerate(v):
            a.text(x, j, f" {x:.3g}", va="center", fontsize=7)
    fig.suptitle("S5 지표 (시뮬레이션). RMSE 개선율은 개루프 대비", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "S5_metrics.png", dpi=150)


# ---------------- S6 ----------------
PERTS = {"공칭": {}, "강성 +30 %": dict(young_scale=1.3), "강성 −30 %": dict(young_scale=0.7),
         "ITV τ ×2": dict(tau_v_scale=2.0), "튜브 R ×2": dict(R_t_scale=2.0), "손끝 하중 계단": "load"}


def s6_robust(P):
    x0 = np.array(P["model"]["x0"])
    ref = np.full(int(10 / TS), x0[1] + 3.0)
    tq = P["dob"]["tau_q"]
    pick = [k for k in make_controllers(P) if k in ("개루프 FF(이상적 맵)", "LQG") or k.startswith("LQG+DOB*")]
    res, recs = {}, {}
    for pname, kw in PERTS.items():
        for cname in pick:
            scn = Scenario(fingers=1, **(kw if isinstance(kw, dict) else {}))
            pl = Plant(scn, seed=7)
            if kw == "load":
                orig = pl.step

                def stepped(u, pl=pl, orig=orig):
                    pl.scn.tip_load_N = 0.5 if pl.t > 6.0 else 0.0
                    return orig(u)
                pl.step = stepped
            rec = run_loop(pl, make_controllers(P, [cname])[cname](), ref, x0)
            e = rec[:, 3] - rec[:, 1]
            key = f"{pname} | {'DOB' if 'DOB' in cname else ('FF' if '개루프' in cname else '없음')}"
            res[key] = dict(rmse=rmse(rec[:, 3], rec[:, 1]), ess=float(np.mean(e[-100:])),
                            max_err_after_1s=float(np.max(np.abs(e[100:]))), **effort(rec[:, 7]))
            recs[key] = rec
            print("S6", key, {k: round(v, 4) for k, v in res[key].items()}, flush=True)
    for pname in PERTS:
        f, a, b = res[f"{pname} | FF"], res[f"{pname} | 없음"], res[f"{pname} | DOB"]
        f["rmse_improve_pct"] = 0.0
        a["rmse_improve_pct"] = improvement_pct(f["rmse"], a["rmse"])   # 개루프 대비
        b["rmse_improve_pct"] = improvement_pct(f["rmse"], b["rmse"])
        b["dob_vs_lqg_pct"] = improvement_pct(a["rmse"], b["rmse"]); a["dob_vs_lqg_pct"] = f["dob_vs_lqg_pct"] = 0.0
    _write_csv(OUT / "S6_metrics.csv", res)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    xs = np.arange(len(PERTS))
    ax.bar(xs - 0.27, [res[f"{p} | FF"]["rmse"] for p in PERTS], 0.27, color="#ccc", label="개루프 FF")
    ax.bar(xs, [res[f"{p} | 없음"]["rmse"] for p in PERTS], 0.27, color="#888", label="LQG")
    ax.bar(xs + 0.27, [res[f"{p} | DOB"]["rmse"] for p in PERTS], 0.27, color="#2b6cb0", label=f"LQG + DOB (τq={tq*1e3:.0f} ms)")
    for i, p in enumerate(PERTS):
        ax.text(i + 0.27, res[f"{p} | DOB"]["rmse"], f"{res[f'{p} | DOB']['dob_vs_lqg_pct']:+.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(xs, list(PERTS), fontsize=8); ax.set_ylabel("추종 RMSE [%]"); ax.legend(fontsize=8)
    ax.set_title("S6 섭동별 효과 (시뮬레이션). 숫자 = LQG 대비 DOB 개선율", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "S6_dob.png", dpi=150)
    r0, r1 = recs["손끝 하중 계단 | 없음"], recs["손끝 하중 계단 | DOB"]
    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    for r, lab, c in ((r0, "LQG", "#999"), (r1, "LQG+DOB", "#2b6cb0")):
        ax[0].plot(r[:, 0] - r[0, 0], r[:, 3], c=c, label=lab); ax[1].plot(r[:, 0] - r[0, 0], r[:, 7], c=c)
    ax[0].plot(r0[:, 0] - r0[0, 0], r0[:, 1], c=C_REF, ls="--", label="기준")
    ax[0].axvline(4.0, c="r", lw=0.6); ax[0].set_ylabel("ε [%]"); ax[0].legend(fontsize=8)
    ax[1].set_ylabel("u [kPa]"); ax[1].set_xlabel("t [s]")
    fig.suptitle("S6 손끝 하중 계단 외란 응답 (시뮬레이션)", fontsize=10); fig.tight_layout()
    fig.savefig(OUT / "S6_load_step.png", dpi=150)
    return res


# ---------------- S8 ----------------
GEOMS = [("r8 z-60", 8, -60), ("r15 z-50", 15, -50), ("r15 z-70", 15, -70), ("r15 z-90", 15, -90),
         ("r25 z-70", 25, -70), ("r25 z-95", 25, -95)]   # 물체 반지름 [mm] · 높이 [mm] (접촉 위치)


def efm_series(P, p, u):
    """측정 p·u 로 돌린 ε_f 개루프 모델 (식별 A_d, B_d 2행) — k_eq 와 독립인 회귀 변수."""
    Ad, Bd, _, _, x0, u0, _ = load_model(P)
    e, out = 0.0, []
    for pk, uk in zip(p, u):
        out.append(e + x0[1])
        e = Ad[1, 0] * (pk - x0[0]) + Ad[1, 1] * e + Bd[1, 0] * (uk - u0)
    return np.array(out)


def _ramp_contact(P, scn, nonideal, seconds=6.0):
    pl = Plant(scn, seed=3, nonideal=nonideal)
    pl.fcal = 1.0
    rows = []
    for k in range(int(seconds / TS)):
        u = min(30.0, 30.0 * k * TS / 4.0)
        o = pl.step(np.array([u])); tr = pl.truth()
        rows.append((u, tr.eps[0], tr.F_N[0], o.val_hat[0] if o.contact[0] else np.nan, o.p_mon[0], o.eps_hat[0]))
    a = np.array(rows)
    ef = efm_series(P, a[:, 4], a[:, 0])
    c = a[:, 2] > 0.05
    keq, c0 = np.polyfit(ef[c], a[c, 2], 1)
    kenv = float(np.polyfit(a[c, 1], a[c, 2], 1)[0])
    return a, ef, dict(F_block=float(a[-50:, 2].mean()), k_eq=float(keq), eps_c=float(-c0 / keq), k_env=kenv,
                       g=float(keq / kenv), eps_contact=float(a[c, 1][0]))


def s8_contact(P):
    """접촉 강성: k_eq = dF/dε_f (모델), k_env = dF/dε (센서), 재질 3종 (MoE) + 위치·크기 6종 (정답).
    힘 장착 보정 F̂ = c·F 와 접촉 중 F̂ 잡음 V_F (도체)."""
    out, fh = {}, []
    for mat in MATERIAL:
        a, ef, out[mat] = _ramp_contact(P, Scenario(fingers=1, material=mat, obj_start_mm=(0.0, 0.0, -70.0)), True)
        if mat == "conductor":
            m = (a[:, 2] > 0.05) & np.isfinite(a[:, 3])
            fh = (a[m, 2], a[m, 3])
        print("S8", mat, {k: round(v, 3) for k, v in out[mat].items()}, flush=True)
    cfit = float(np.sum(fh[0] * fh[1]) / np.sum(fh[0] ** 2)) if len(fh) and len(fh[0]) else 1.0
    from scipy.signal import detrend
    hold = np.array([fh[0], fh[1]]).T[-150:]                  # 램프 끝 1.5 s (선형 추세 제거 후 잔차)
    out["V_F"] = float(np.var(detrend(hold[:, 1] / cfit - hold[:, 0])))
    geo = []
    for name, r, z in GEOMS:
        _, _, g = _ramp_contact(P, Scenario(fingers=1, obj_k_N_mm=None, obj_radius_mm=r, obj_start_mm=(0.0, 0.0, z)), False)
        geo.append(dict(name=name, r=r, z=z, **g))
        print("S8 geom", name, {k: round(v, 3) for k, v in g.items()}, flush=True)
    out["geometry"] = geo
    save_params("contact", out)
    save_params("force_cal", {"c": cfit, "note": "도체 S8 원점 통과 직선 F̂ = c·F"})
    fig, ax = plt.subplots(figsize=(9.5, 3.4))
    xs = np.arange(len(geo))
    ax.bar(xs - 0.2, [g["k_eq"] for g in geo], 0.4, color="#7a4ea3", label="k_eq = dF/dε_f  [N/%]")
    ax.bar(xs + 0.2, [g["k_env"] / 3 for g in geo], 0.4, color="#2CA02C", label="k_env/3 = (dF/dε)/3  [N/%]")
    for m, c_ in zip(MATERIAL, ("#555", "#1F77B4", "#d35400")):
        ax.axhline(out[m]["k_eq"], c=c_, lw=0.8, ls=":", label=f"k_eq {m} (r15 z-70, k_obj 변경)")
    ax.set_xticks(xs, [g["name"] for g in geo], fontsize=8); ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.set_title("S8 접촉 강성 (시뮬레이션): 위치·크기에 따라 k_eq 약 2배, 재질(무르기)은 거의 무관", fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / "S8_keq.png", dpi=150)
    print("S8 힘 보정 c =", round(cfit, 3), "V_F =", out["V_F"])
    return out


# ---------------- 하이브리드 제어기 (스펙 12절) ----------------
class Hybrid:
    """자유 모드 = LQG(ε), 접촉 모드 = ContactLqg(F). 상위 sup.mode 로 전환, 양방향 무충격."""

    def __init__(self, P, use_rls=True, use_dob=False, schedule=True):
        from design_contact import ContactLqg, make_schedule
        Ad, Bd, C, Ts, x0, u0, phys = load_model(P)
        ct, cd = P["contact"], P["contact_design"]
        self.x0 = x0
        self.free = make_controllers(P, ["LQG"])["LQG"]()
        sched = make_schedule(Ad, Bd, cd["grid"] if schedule else [cd["k_nom"]] * 2)
        Ge = P["sysid"]["G_eps"]
        dobf = (lambda y0, u0_: Dob(Ge["a"], Ge["b"], Ge["nk"], P["dob"]["tau_q"], Ts, r=P["dob"]["r"], y0=y0, u0=u0_)) if use_dob else None
        self.con = ContactLqg(Ad, Bd, x0, u0, phys, sched, cd["k_nom"], P["noise"]["var"][0], ct["V_F"],
                              np.array(P["stoch"]["W"]), use_rls=use_rls, dob_factory=dobf)
        self.in_con, self.u_prev = False, 0.0

    def reset(self):
        self.free.reset(); self.in_con = False

    def u(self, p, eps_hat, F_hat, sup):
        if sup.mode == "force":
            if not self.in_con:
                self.con.enter(self.free.kf.x_post + self.x0, self.u_prev); self.in_con = True
            u = self.con.u(p, F_hat, sup.F_ref)
        else:
            if self.in_con:
                self.free.bumpless(np.array([p, eps_hat]), self.u_prev); self.in_con = False  # 자유 모드 상태 = 측정 (접촉 중 ε_f ≠ ε)
            u = self.free.u(np.array([p, eps_hat]), sup.eps_ref)
        self.u_prev = u
        return u


class AdmittanceCtrl:
    """비교용 기존 방식: 상위 어드미턴스가 ε_ref 를 내고 LQG(ε) 가 추종."""

    def __init__(self, P):
        self.free = make_controllers(P, ["LQG"])["LQG"]()
        self.con = None

    def reset(self):
        self.free.reset()

    def u(self, p, eps_hat, F_hat, sup):
        return self.free.u(np.array([p, eps_hat]), sup.eps_ref)


CTRL9 = {"A 어드미턴스→ε (기존)": dict(kind="adm"),
         "B F-LQG 공칭": dict(kind="hyb", use_rls=False, schedule=False),
         "C F-LQG + RLS 스케줄": dict(kind="hyb", use_rls=True),
         "D C + DOB": dict(kind="hyb", use_rls=True, use_dob=True)}


def make_grasp_ctrl(P, spec):
    spec = dict(spec)
    return AdmittanceCtrl(P) if spec.pop("kind") == "adm" else Hybrid(P, **spec)


def make_sup(P, mat, kind, Ts=TS):
    det, ct = P["det"], P["contact"]
    tau_in = max(-TS / np.log(abs(complex(*p))) for p in det["lqr"]["poles"])
    FB = ct["conductor"]["F_block"]
    return Supervisor(F_block=FB, Ba0=4.0 * tau_in * ct["conductor"]["k_env"], v0=det["v0"], eps_open=0.0, eps_pre=0.3,
                      eps_max=12.0, grasp_mode="admittance" if kind == "adm" else "force", Ts=Ts)


# ---------------- S9 ----------------
SCN9 = [("도체 r15 z-70 (공칭)", "conductor", 15, -70), ("도체 r25 z-95 (k_eq 낮음)", "conductor", 25, -95),
        ("유전체 r8 z-60", "dielectric", 8, -60), ("인체 r15 z-70 (무름)", "human", 15, -70)]


def s9_force(P, seconds=10.0, t_step=6.0):
    """고정 물체 힘 유지: 닫기 → 접촉 → F_t 유지 → t_step 에 목표 ×1.3 계단. 정답 F 로 평가."""
    res, recs = {}, {}
    for sname, mat, r, z in SCN9:
        for cname, spec in CTRL9.items():
            pl = Plant(Scenario(fingers=1, material=mat, obj_radius_mm=r, obj_start_mm=(0.0, 0.0, z)), seed=9)
            sup, ctl = make_sup(P, mat, spec["kind"]), make_grasp_ctrl(P, spec)
            u, rows, t_g = 0.0, [], None
            for k in range(int(seconds / TS)):
                o = pl.step(np.array([u])); tr = pl.truth()
                if pl.t > t_step and sup.FB == P["contact"]["conductor"]["F_block"]:
                    sup.FB *= 1.3                                   # 목표 힘 계단 (+30 %)
                c = o.contact[0]
                sup.step(dict(d_hat=0.0 if c else o.val_hat[0], F_hat=o.val_hat[0] if c else 0.0, contact=c,
                              eps_hat=o.eps_hat[0]), mat, "grasp")
                if t_g is None and sup.state == "GRASP":
                    t_g = pl.t
                u = ctl.u(o.p_mon[0], o.eps_hat[0], o.val_hat[0] if c else 0.0, sup)
                Ft = MATERIAL[mat]["Ft"] * sup.FB
                kh = ctl.con.k_eq if getattr(ctl, "con", None) is not None and getattr(ctl, "in_con", False) else np.nan
                rows.append([pl.t, Ft, tr.F_N[0], o.val_hat[0] if c else 0.0, u, tr.eps[0], kh, int(sup.state == "GRASP")])
            a = np.array(rows)
            t = a[:, 0]
            w1 = (t > (t_g or 0) + 1.5) & (t < t_step); w2 = t > t_step + 1.5
            e = a[:, 2] - a[:, 1]
            m = dict(t_grasp=float(t_g or np.nan),
                     rmse_hold=float(np.sqrt(np.mean(e[w1 | w2] ** 2))),
                     rmse_hold_hat=float(np.sqrt(np.mean((a[:, 3] - a[:, 1])[w1 | w2] ** 2))),   # 제어기 기준 (F̂ 추종)
                     ess1_pct=float(100 * np.mean(e[(t > t_step - 1.0) & (t < t_step)]) / a[t < t_step, 1][-1]),
                     ess2_pct=float(100 * np.mean(e[t > seconds - 1.0]) / a[-1, 1]),
                     overshoot_pct=float(100 * max(0.0, (a[t > t_step, 2].max() - a[-1, 1]) / a[-1, 1])),
                     F_peak=float(a[t > (t_g or 0), 2].max()), **effort(a[t > (t_g or 0), 4]),
                     k_hat_end=float(np.nanmean(a[-100:, 6])) if np.isfinite(a[-100:, 6]).any() else float("nan"))
            key = f"{sname} | {cname}"
            res[key], recs[key] = m, a
            print("S9", key, {k: round(v, 3) for k, v in m.items()}, flush=True)
    _write_csv(OUT / "S9_metrics.csv", res)
    _plot_s9(res, recs, t_step)
    return res


def _plot_s9(res, recs, t_step):
    cols = {"A": "#999", "B": "#7a4ea3", "C": "#2b6cb0", "D": "#c0392b"}
    fig, ax = plt.subplots(len(SCN9), 1, figsize=(10, 2.1 * len(SCN9)), sharex=True)
    for i, (sname, *_ ) in enumerate(SCN9):
        for cname in CTRL9:
            a = recs[f"{sname} | {cname}"]
            ax[i].plot(a[:, 0], a[:, 2], c=cols[cname[0]], lw=0.9, label=cname)
        ax[i].plot(a[:, 0], a[:, 1], c=C_REF, ls="--", lw=1.0, label="목표 F_t")
        ax[i].set_ylabel("F [N]"); ax[i].set_title(sname, fontsize=8, loc="left")
    ax[0].legend(fontsize=7, ncol=5); ax[-1].set_xlabel("t [s]")
    fig.suptitle("S9 접촉 후 힘 유지 (정답 F, 시뮬레이션): 기존 어드미턴스 vs 힘 직접 추종", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "S9_force.png", dpi=150)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.4))
    xs = np.arange(len(SCN9))
    for j, cname in enumerate(CTRL9):
        ax[0].bar(xs + (j - 1.5) * 0.2, [res[f"{s[0]} | {cname}"]["rmse_hold"] for s in SCN9], 0.2, color=cols[cname[0]], label=cname)
        ax[1].bar(xs + (j - 1.5) * 0.2, [abs(res[f"{s[0]} | {cname}"]["ess2_pct"]) for s in SCN9], 0.2, color=cols[cname[0]])
    for a_, lab in zip(ax, ("유지 RMSE [N]", "|정상 오차| [%] (계단 후)")):
        a_.set_xticks(xs, [s[0].split(" (")[0] for s in SCN9], fontsize=7); a_.set_title(lab, fontsize=9)
    ax[0].legend(fontsize=7)
    fig.suptitle("S9 지표 (시뮬레이션)", fontsize=10); fig.tight_layout(); fig.savefig(OUT / "S9_metrics.png", dpi=150)


# ---------------- S7 ----------------
def approach_path(material, z_stop=-70.0, v=40.0, z0=-230.0):
    def f(t):
        z = min(z_stop, z0 + v * t)
        x = 4.0 * np.sin(2 * np.pi * 0.6 * t) if material == "human" else 0.0  # 사람 손은 흔들린다
        return (x, 0.0, z)
    return f


def s7_grasp(P, seconds=9.0, fps=25, cases=(("conductor", True), ("dielectric", False), ("dielectric", True), ("human", True)),
             ctrl_name="C F-LQG + RLS 스케줄"):  # D(+DOB)는 2지 파지에서 입력 진동 → 해결 전까지 C
    """cases: (재질, TENG 융합 사용). 유전체는 게이트만 vs 게이트 ∨ TENG 를 비교한다. 제어기 = 스펙 12절 하이브리드."""
    import imageio.v2 as imageio
    summary = {}
    for mat, use_teng in cases:
        tag = mat + ("" if use_teng else "_gate_only")
        spec = CTRL9[ctrl_name]
        pl = Plant(Scenario(material=mat, obj_path=approach_path(mat)), seed=21, teng=use_teng)
        ctr = [make_grasp_ctrl(P, spec) for _ in range(2)]
        sup = [make_sup(P, mat, spec["kind"]) for _ in range(2)]  # ε_max 12 % ≈ 30 kPa, pre-shape 0.3 % (물체가 손끝을 지나가야 함)
        FB = sup[0].FB
        writer = imageio.get_writer(OUT / f"S7_{tag}.mp4", fps=fps, macro_block_size=1)
        rows, snaps, u = [], [], np.zeros(2)
        for k in range(int(seconds / TS)):
            o = pl.step(u); tr = pl.truth()
            cmd = "release" if pl.t > seconds - 1.5 else ("grasp" if pl.t > 4.5 else "approach")  # 팔 도착 후 파지 명령
            for i in range(2):
                Fh = o.val_hat[i] if o.contact[i] else 0.0
                obs = dict(d_hat=o.val_hat[i] if not o.contact[i] else 0.0, F_hat=Fh, contact=o.contact[i], eps_hat=o.eps_hat[i])
                sup[i].step(obs, mat, cmd)
                if sup[i].state == "OPEN":
                    u[i] = 0.0; ctr[i].reset()  # 열림: 완전 배기 (잡음으로 손가락이 굽지 않게)
                else:
                    u[i] = ctr[i].u(o.p_mon[i], o.eps_hat[i], Fh, sup[i])
            rows.append([pl.t, tr.d_mm[0], o.val_hat[0], tr.F_N[0], sup[0].eps_ref, tr.eps[0], u[0],
                         ["OPEN", "APPROACH", "CONTACT", "GRASP", "SAFETY", "RELEASE"].index(sup[0].state), tr.F_N[1]])
            if k % int(1 / (fps * TS)) == 0:
                img = pl.frames()
                writer.append_data(img)
                if k in (0, int(3.0 / TS), int(5.0 / TS), int(7.0 / TS)):
                    snaps.append(img)
        writer.close()
        a = np.array(rows)
        np.savetxt(OUT / f"S7_{tag}.csv", a, delimiter=",", header="t,d,val_hat,F0,eps_ref,eps,u,state,F1", comments="")
        if snaps:
            imageio.imwrite(OUT / f"S7_{tag}_snap.png", np.concatenate(snaps, axis=1))
        Fmax = MATERIAL[mat]["Fmax"] * FB
        g = a[:, 0] > 4.5                       # 파지 명령 이후 (접근 중 충돌과 구분)
        summary[tag] = dict(teng=use_teng, F_block=FB, ctrl=ctrl_name, F_peak=float(a[g][:, [3, 8]].max()), F_peak_approach=float(a[~g][:, [3, 8]].max()),
                            F_max=Fmax, F_target=MATERIAL[mat]["Ft"] * FB, exceeded=bool(a[g][:, [3, 8]].max() > Fmax),
                            F_hold=float(a[(a[:, 0] > 5.5) & (a[:, 0] < seconds - 1.6), 3].mean()))
        _plot_s7(a, tag, summary[tag])
        print("S7", tag, summary[tag], flush=True)
    save_params("results_s7", summary)
    return summary


def _plot_s7(a, mat, s):
    t = a[:, 0]
    fig, ax = plt.subplots(4, 1, figsize=(9, 7), sharex=True)
    ax[0].plot(t, a[:, 1], c="k", label="d 정답"); ax[0].set_ylabel("d [mm]"); ax[0].set_ylim(0, 40)
    ax[1].plot(t, a[:, 3], c="#c0392b", label="F 정답")
    ax[1].axhline(s["F_target"], ls="--", c="gray", lw=0.8); ax[1].axhline(s["F_max"], ls=":", c="r", lw=0.8)
    ax[1].set_ylabel("F [N]")
    ax[2].plot(t, a[:, 4], c=C_REF, label="ε_ref"); ax[2].plot(t, a[:, 5], c=C_Y, label="ε"); ax[2].legend(fontsize=8)
    ax[2].set_ylabel("ε [%]")
    ax[3].step(t, a[:, 7], c="#555"); ax[3].set_yticks(range(6), ["OPEN", "APPR", "CONT", "GRASP", "SAFE", "REL"], fontsize=7)
    ax[3].set_xlabel("t [s]")
    fig.suptitle(f"S7 파지 — {mat} (시뮬레이션): 근접 → 접촉 → 힘 추종 → 해제", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / f"S7_{mat}.png", dpi=150)  # mat = 태그 (재질[_gate_only])


def render_model():
    """0 kPa / 15 kPa / 30 kPa 정상 상태 렌더 (2지, 물체 없음)."""
    import imageio.v2 as imageio
    pl = Plant(Scenario(), seed=0, nonideal=False)
    imgs = []
    for p in (0.0, 15.0, 30.0):
        for _ in range(int(2.0 / TS)):
            pl.step(np.array([p, p]))
        imgs.append(pl.frames())
    imageio.imwrite(OUT / "model_render.png", np.concatenate(imgs, axis=1))


def main(which=("R", "S4", "S8", "S5", "S6", "S9", "S7")):
    OUT.mkdir(exist_ok=True)
    if "R" in which:
        render_model()
    if "S4" in which:
        s4_noise(load_params())
    if "S8" in which:
        s8_contact(load_params())
    if "S5" in which:
        save_params("results_s5", s5_compare(load_params()))
    if "S6" in which:
        save_params("results_s6", s6_robust(load_params()))
    if "S9" in which:
        save_params("results_s9", s9_force(load_params()))
    if "S7" in which:
        s7_grasp(load_params(), ctrl_name=load_params().get("s7_ctrl", "C F-LQG + RLS 스케줄"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(tuple(sys.argv[1:]) or ("R", "S4", "S8", "S5", "S6", "S9", "S7"))
