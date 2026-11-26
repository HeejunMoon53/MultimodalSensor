import numpy as np
from scipy import signal

from design_stoch import Kalman, Lqg
from design_tf import design
from paths import load_params


def test_closed_loop_tf_matches_lqg_time_simulation():
    P = load_params()
    res, fr = design(P)
    M, D, S = P["model"], P["det"]["lqr"], P["stoch"]
    Ad, Bd, C = np.array(M["Ad"]), np.array(M["Bd"]), np.array(M["C"])
    x0, u0 = np.array(M["x0"]), M["u0"]
    kf = Kalman(Ad, Bd, C, np.eye(2), np.diag(S["W"]), np.diag(S["V"]), np.zeros(2), np.zeros((2, 2)))
    kf.M = np.array(S["M"])
    lqg = Lqg(np.array(D["K"]), D["KI"], kf, x0, u0)
    lqg._init = (np.zeros(2), np.array(S["M"]))   # 정상상태 칼만 = TF 와 같은 조건
    lqg.reset()
    lqg.kf.update = lambda y: _fixed(lqg.kf, y, np.array(S["Kf"]))
    lqg.kf.predict = lambda u: setattr(lqg.kf, "x_prior", Ad @ lqg.kf.x_post + Bd[:, 0] * u) or lqg.kf.x_prior
    n, dr = 300, 0.5                                  # 작은 스텝: 포화 없음
    x, eps = np.zeros(2), []
    for _ in range(n):
        y = C @ x
        eps.append(y[1])
        u = lqg.u(y + x0, x0[1] + dr) - u0
        x = Ad @ x + Bd[:, 0] * u
    _, yt = signal.dstep(fr["sys"]["T"], n=n)
    assert np.allclose(np.array(eps), dr * yt[0][:, 0], atol=1e-6)


def _fixed(kf, y, Kf):
    kf.x_post = kf.x_prior + Kf @ (np.asarray(y, float) - kf.C @ kf.x_prior)
    return kf.x_post


def test_integral_action_and_margins():
    res, _ = design(load_params())
    assert abs(res["T_dc"] - 1.0) < 1e-3           # 적분기 → ε/r 정상상태 이득 1
    assert "(z − 1)" in res["Ce"] and "(z − 1)" in res["F"]
    assert max(res["cl_poles"]) < 1.0
    assert res["gm_db"] > 6 and 30 < res["pm_deg"] <= 180


def test_contact_tf_matches_contact_lqg_time_simulation():
    from design_contact import ContactLqg, make_schedule
    from design_tf import design_contact
    P = load_params()
    res, frs = design_contact(P)
    kn = res["k_nom"]
    M, cd = P["model"], P["contact_design"]
    Ad, Bd = np.array(M["Ad"]), np.array(M["Bd"])
    x0, u0, k = np.array(M["x0"]), M["u0"], cd["k_nom"]
    con = ContactLqg(Ad, Bd, x0, u0, M["phys"], make_schedule(Ad, Bd, [k, k]), k, P["noise"]["var"][0],
                     P["contact"]["V_F"], np.array(P["stoch"]["W"]), use_rls=False)
    eps_c = x0[1] - 1.0                                # 접촉점: 동작점보다 1 % 아래
    con.enter(x0, u0)
    con.c = -k * eps_c
    con._bump, con.xI = False, 0.0                    # TF 와 같은 영 초기조건 (무충격 초기화 끔)
    Kf = np.array(res["by_k"][kn]["Kf"])
    con.kf.update = lambda y: _fixed(con.kf, y, Kf)
    con.kf.predict = lambda u: setattr(con.kf, "x_prior", Ad @ con.kf.x_post + Bd[:, 0] * u) or con.kf.x_prior
    F0 = k * (x0[1] - eps_c)
    n, dF = 300, 0.3
    x, Fs = np.zeros(2), []
    for _ in range(n):
        F = k * (x0[1] + x[1] - eps_c)
        Fs.append(F - F0)
        u = con.u(x0[0] + x[0], F, F0 + dF) - u0
        x = Ad @ x + Bd[:, 0] * u
    _, yt = signal.dstep(frs[kn]["sys"]["T"], n=n)
    assert np.allclose(np.array(Fs), dF * yt[0][:, 0], atol=1e-6)


def test_contact_tf_integral_and_margins_over_k_grid():
    from design_tf import design_contact
    res, _ = design_contact(load_params())
    assert len(res["by_k"]) == 3
    for r in res["by_k"].values():
        assert abs(r["T_dc"] - 1.0) < 1e-3 and "(z − 1)" in r["Cm"]
        assert max(r["cl_poles"]) < 1.0 and r["gm_db"] > 6 and r["pm_deg"] > 30
