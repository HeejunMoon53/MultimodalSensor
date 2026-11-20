import numpy as np
import pytest

from sysid import arx_ls, c2d_tf, d2c_zoh, prbs, simulate_arx


def test_arx_recovers_known_model():
    a_true, b_true = np.array([-1.5, 0.7]), np.array([0.1, 0.05])
    u = prbs(4000, 7, 1.0, 0)
    y = simulate_arx(a_true, b_true, 1, u, np.zeros(2))
    a, b = arx_ls(y + 1e-4 * np.random.default_rng(0).normal(size=y.size), u, 2, 2, 1)
    assert np.allclose(a, a_true, atol=1e-2) and np.allclose(b, b_true, atol=1e-2)


def test_arx_rejects_unexciting_input():
    with pytest.raises(ValueError):
        arx_ls(np.ones(500), np.ones(500), 2, 2, 1)


def test_d2c_roundtrip():
    nums, dens = [2.0], [1.0, 3.0, 2.0]
    numz, denz = c2d_tf(nums, dens, 0.01)
    n2, d2 = d2c_zoh(numz, denz, 0.01)
    assert np.allclose(np.sort(np.roots(d2)), np.sort(np.roots(dens)), atol=1e-6)
    assert np.polyval(n2, 0) / np.polyval(d2, 0) == pytest.approx(1.0, rel=1e-6)
