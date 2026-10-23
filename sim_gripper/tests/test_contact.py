import numpy as np
import pytest

from sim_gripper.perception.contact import DielectricEstimator, TengContact
from sim_gripper.perception.moe import MoE
from sim_gripper.sensor.forward import SensorForward, TengModel


@pytest.fixture(scope="module")
def fwd():
    return SensorForward()


def test_moe_contact_hint_forces_expert_b(models):
    m = MoE(models=models)
    for _ in range(100):
        m.step(10.0, 9.5)
    o = m.step(10.0, 9.5, contact_hint=1)
    assert o.contact == 1 and o.gate_proba < 0.5 and m.ema == (10.0, 9.5)


def test_teng_latch_on_press_off_release():
    teng, c = TengModel(), TengContact()
    states = []
    for F in np.r_[np.zeros(100), np.linspace(0, 3, 300), np.full(500, 3.0), np.linspace(3, 0, 100), np.zeros(200)]:
        states.append(c.update(teng.step(F, 0.001)))
    s = np.array(states)
    assert s[:100].sum() == 0 and s[150:900].all() and s[-100:].sum() == 0


def test_teng_holds_through_slow_force_drift():
    teng, c = TengModel(), TengContact()
    for F in np.linspace(0, 3, 300):
        c.update(teng.step(F, 0.001))
    for F in np.linspace(3, 2, 2000):        # 0.5 N/s 완만한 감소 → 래치 유지
        out = c.update(teng.step(F, 0.001))
    assert out == 1


@pytest.mark.parametrize("eps,F", [(10, 1.0), (12, 2.0), (15, 3.0)])
def test_dielectric_estimator_inverts_forward(fwd, eps, F):
    dL, dR = fwd.signals(eps, 0.0, F, "dielectric")
    e_hat, F_hat = DielectricEstimator(fwd).estimate(dL, dR)
    assert abs(e_hat - eps) < 1.0 and abs(F_hat - F) < 0.5
