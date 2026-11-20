import numpy as np

from analysis import c2d, ctrb, ctrb_canonical, dlyap, is_pd, obsv, physical_ss, rank, similarity


def test_pressure_only_is_unobservable():
    A, B, C = physical_ss(0.05, 2.0, 15.0, 0.4)
    assert rank(obsv(A, C[:1])) == 1 and rank(obsv(A, C[1:2])) == 3 and rank(ctrb(A, B)) == 3


def test_dlyap_pd_iff_stable():
    A, B, _ = physical_ss(0.05, 2.0, 15.0, 0.4)
    Ad, _ = c2d(A, B, 0.01)
    assert is_pd(dlyap(Ad.T, np.eye(3))) and np.all(abs(np.linalg.eigvals(Ad)) < 1)
    assert not is_pd(dlyap(1.02 * Ad.T / max(abs(np.linalg.eigvals(Ad))), np.eye(3)))


def test_similarity_preserves_eigs():
    A1, *_ = ctrb_canonical([2.0], [1, 3, 2])
    A2 = np.array([[-1, 0], [0, -2.0]])
    Q = similarity(A1, A2)
    assert np.allclose(np.linalg.inv(Q) @ A1 @ Q, A2, atol=1e-8)
