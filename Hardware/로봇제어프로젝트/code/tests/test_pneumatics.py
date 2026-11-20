import numpy as np
import pytest

from pneumatics import Itv, Line


def run_to_steady(itv, u, t=2.0, dt=1e-3):
    p = 0.0
    for _ in range(int(t / dt)):
        p = itv.step(u, dt)
    return p


def test_quantized_and_deadband():
    itv = Itv(seed=0, mon_sigma=0.0)
    assert run_to_steady(itv, 0.2) == 0.0
    assert run_to_steady(itv, 12.4) == pytest.approx(12.0, abs=1e-6)


def test_ideal_is_first_order():
    itv = Itv(ideal=True)
    y = [itv.step(10.0, 1e-3) for _ in range(50)]
    assert y[-1] == pytest.approx(10 * (1 - np.exp(-0.05 / 0.05)), rel=0.02)


def test_itv_bad_input():
    itv = Itv()
    for u in (-5.0, float("nan"), 99.0):
        p = itv.step(u, 1e-3)
        assert np.isfinite(p) and 0 <= p <= 30


def test_line_settles_to_supply():
    ln = Line()
    pc = [ln.step(20.0, 5e4, 2e3, 1e-3) for _ in range(5000)]
    assert pc[-1] == pytest.approx(20.0, abs=0.1)
