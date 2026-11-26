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
