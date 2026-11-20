import numpy as np
import pytest

from analysis import c2d, physical_ss
from design_det import acker, dlqr, observer_gain

A, B, C = physical_ss(0.05, 2.0, 15.0, 0.4)
Ad, Bd = c2d(A, B, 0.01)


def test_acker_places_poles():
    z = np.array([0.9, 0.85, 0.8])
    K = acker(Ad, Bd, z)
    assert np.allclose(np.sort(np.linalg.eigvals(Ad - Bd @ K).real), np.sort(z), atol=1e-6)


def test_dlqr_satisfies_dare():
    K, P = dlqr(Ad, Bd, np.eye(3), np.eye(1))
    rhs = Ad.T @ P @ Ad - Ad.T @ P @ Bd @ np.linalg.inv(np.eye(1) + Bd.T @ P @ Bd) @ Bd.T @ P @ Ad + np.eye(3)
    assert np.allclose(P, rhs, atol=1e-8)


def test_separation_principle():
    K = acker(Ad, Bd, [0.9, 0.85, 0.8])
    L = observer_gain(Ad, C, [0.5, 0.45, 0.4])
    big = np.block([[Ad, -Bd @ K], [L @ C, Ad - L @ C - Bd @ K]])
    want = np.r_[np.linalg.eigvals(Ad - Bd @ K), np.linalg.eigvals(Ad - L @ C)]
    assert np.allclose(np.sort_complex(np.linalg.eigvals(big)), np.sort_complex(want), atol=1e-6)


def test_place_rejects_unstable_target():
    with pytest.raises(ValueError):
        acker(Ad, Bd, [1.05, 0.9, 0.8])
