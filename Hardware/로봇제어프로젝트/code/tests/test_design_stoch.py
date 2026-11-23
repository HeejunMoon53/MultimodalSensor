import numpy as np
import pytest

from analysis import c2d, physical_ss
from design_det import observer_gain
from design_stoch import Kalman, RangeKF, steady_kalman

A, B, C = physical_ss(0.05, 2.0, 15.0, 0.4)
Ad, Bd = c2d(A, B, 0.01)
Bw = np.eye(3)
W = np.diag([0.05, 0.01, 1.0])
V = np.diag([0.05 ** 2, 0.3 ** 2])


def test_steady_kalman_satisfies_dual_dare():
    Kf, M = steady_kalman(Ad, C, Bw, W, V)
    S = C @ M @ C.T + V
    rhs = Ad @ (M - M @ C.T @ np.linalg.solve(S, C @ M)) @ Ad.T + Bw @ W @ Bw.T
    assert np.allclose(M, rhs, atol=1e-8)


def test_kalman_reduces_estimation_error():
    rng = np.random.default_rng(0)
    L = observer_gain(Ad, C, np.exp(-4 * np.array([20.0, 25.0, 30.0]) * 0.01))
    kf = Kalman(Ad, Bd, C, Bw, W, V, np.zeros(3), np.eye(3))
    x, xo = np.zeros(3), np.zeros(3)
    eo, ek = [], []
    for k in range(3000):
        u = 3.0 * np.sin(0.02 * k)
        y = C @ x + rng.multivariate_normal(np.zeros(2), V)
        xk = kf.update(y)
        ek.append(xk[2] - x[2]); eo.append(xo[2] - x[2])
        xo = Ad @ xo + Bd[:, 0] * u + L @ (y - C @ xo)
        kf.predict(u)
        x = Ad @ x + Bd[:, 0] * u + rng.multivariate_normal(np.zeros(3), W)
    assert np.sqrt(np.mean(np.square(ek[500:]))) < np.sqrt(np.mean(np.square(eo[500:])))


def test_range_kf_tracks_constant_velocity():
    kf = RangeKF(0.01, 50.0, 0.5)
    rng = np.random.default_rng(0)
    for k in range(300):
        d, v = kf.step(80 - 20 * k * 0.01 + 0.5 * rng.normal())
    assert v == pytest.approx(-20, abs=2)


def test_lqg_bumpless_return_matches_previous_input():
    import numpy as np
    from design_det import load_model
    from design_stoch import Kalman, Lqg
    from paths import load_params
    P = load_params()
    Ad, Bd, C, Ts, x0, u0, _ = load_model(P)
    kf = Kalman(Ad, Bd, C, np.eye(2), np.diag(P["stoch"]["W"]), np.diag(P["stoch"]["V"]), np.zeros(2), np.eye(2))
    c = Lqg(P["det"]["lqr"]["K"], P["det"]["lqr"]["KI"], kf, x0, u0)
    c.bumpless(x0 + np.array([5.0, 2.0]), 21.3)
    assert abs(c.u(x0 + np.array([5.0, 2.0]), x0[1] + 1.0) - 21.3) < 0.5
