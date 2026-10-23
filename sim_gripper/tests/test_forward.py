import numpy as np
import pytest

from sim_gripper.sensor.forward import SensorForward, TengModel


@pytest.fixture(scope="module")
def fwd():
    return SensorForward()


def test_strain_only(fwd):
    dL, dR = fwd.signals(30, 24, 0, "conductor")
    assert abs(dL - 20.0) < 1.5 and abs(dR - 20.9) < 1.5


def test_conductor_near(fwd):
    dL, dR = fwd.signals(0, 1, 0, "conductor")
    assert abs(dL + 22) < 2.5 and abs(dR) < 0.5


def test_dielectric_near(fwd):
    dL, _ = fwd.signals(0, 1, 0, "dielectric")
    assert 1.5 < dL < 3.0


def test_pressure(fwd):
    _, dR = fwd.signals(0, 0, 10, "conductor")
    assert abs(dR - 20) < 4


def test_strain_clip(fwd):
    assert fwd.strain_from_curvature(1.0) == 0.0
    assert fwd.strain_from_curvature(-1.0) == 30.0


def test_teng_sign():
    m, dt = TengModel(), 0.001
    v_up = [m.step(3.0 if k >= 10 else 0.0, dt) for k in range(600)]
    v_dn = [m.step(0.0, dt) for _ in range(600)]
    peak_up, peak_dn = max(v_up), min(v_dn)
    assert peak_up > 0 and peak_dn < 0
    assert abs(v_up[-1]) < 0.05 * peak_up and abs(v_dn[-1]) < 0.05 * abs(peak_dn)
