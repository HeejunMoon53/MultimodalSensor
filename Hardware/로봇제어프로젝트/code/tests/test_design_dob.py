import numpy as np

from design_dob import Dob, q_filter

A_ = np.array([-1.6, 0.64])      # 이중극 z = 0.8
B_ = np.array([0.02, 0.01])
NK = 1


def run(dob, dist=0.0, n=600, kp=2.0, r=1.0):
    y, u_hist = np.zeros(n), np.zeros(n)
    for k in range(2, n):
        y[k] = -A_[0] * y[k - 1] - A_[1] * y[k - 2] + B_[0] * u_hist[k - 1] + B_[1] * u_hist[k - 2]
        uc = kp * (r - y[k])
        u = dob.correct(uc, y[k]) if dob else uc
        u_hist[k] = u + dist
    return y


def test_dob_transparent_on_nominal():
    y0 = run(None)
    y1 = run(Dob(A_, B_, NK, tau_q=0.05, Ts=0.01))
    assert np.max(np.abs(y1 - y0)) < 1e-6


def test_dob_rejects_constant_input_disturbance():
    base = run(None, dist=0.0)[-1]
    e_no = abs(run(None, dist=-2.0)[-1] - base)
    e_dob = abs(run(Dob(A_, B_, NK, tau_q=0.05, Ts=0.01), dist=-2.0)[-1] - base)
    assert e_dob < 0.1 * e_no


def test_q_filter_proper():
    num, den = q_filter(0.05, 2)
    assert len(den) - len(num) == 2
