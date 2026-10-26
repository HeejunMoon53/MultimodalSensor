import numpy as np

from sim_gripper.actuators import make_actuator
from sim_gripper.actuators.pneumatic import PneumaticActuator
from sim_gripper.actuators.tendon import TendonActuator

DT = 0.001
Q0 = np.zeros(4)


def test_tendon_slack_zero():
    a = TendonActuator()
    for _ in range(100):
        tau = a.step(0.0, Q0, DT)
    assert np.all(tau == 0)


def test_tendon_time_constant():
    a = TendonActuator()
    for _ in range(int(a.tau_m / DT)):
        a.step(0.05, Q0, DT)
    assert abs(a.theta_m / (0.05 * a.theta_max) - 0.632) < 0.05


def test_pneumatic_time_constant():
    a = PneumaticActuator()
    for _ in range(int(a.tau_p / DT)):
        a.step(0.05, Q0, DT)
    assert abs(a.P / (0.05 * a.P_max) - 0.632) < 0.05


def test_pneumatic_rate_limit():
    a = PneumaticActuator()
    prev = 0.0
    for _ in range(50):
        a.step(1.0, Q0, DT)
        assert (a.P - prev) / DT <= a.Pdot_max * (1 + 1e-9)
        prev = a.P


def test_pneumatic_efficiency_drops_with_q():
    a = PneumaticActuator()
    for _ in range(300):
        a.step(0.5, Q0, DT)
    assert np.all(a.torque(np.full(4, 1.0)) < a.torque(Q0))


def test_make_actuator_kinds():
    assert isinstance(make_actuator("tendon"), TendonActuator)
    assert isinstance(make_actuator("pneumatic"), PneumaticActuator)


def test_pneumatic_deadzone():
    a = PneumaticActuator(P0=62e3)
    a.P = 50e3
    assert np.all(a.torque(Q0) == 0)
    a.P = 100e3
    assert np.allclose(a.torque(Q0), a.alpha * 38e3)


def test_make_pneumatic60a_preset():
    a = make_actuator("pneumatic60a")
    assert a.P_max == 200e3 and a.P0 == 62e3 and a.beta == 0.0
