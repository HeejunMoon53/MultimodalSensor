import numpy as np

from sim_gripper.control.controller import MATERIAL_TABLE, CtrlParams, FingerController, GraspSupervisor
from sim_gripper.perception.moe import MoeOut

DT = 0.001
P = CtrlParams()


def _m(value, contact, eps=15.0):
    return MoeOut(strain_pct=eps, value=value, contact=contact, gate_proba=float(contact))


def test_open_goes_to_u_open():
    c = FingerController(P)
    c.u = 0.5
    for _ in range(2000):
        u = c.step(_m(20.0, 0), "conductor", "OPEN", DT)
    assert u == P.u_open


def test_preshape_monotonic_bounded():
    c = FingerController(P)
    us = []
    for d in np.linspace(20, 3, 3000):
        us.append(c.step(_m(d, 0), "conductor", "APPROACH", DT))
    us = np.array(us)
    assert np.all(np.diff(us) >= -1e-12) and us.max() <= P.u_pre + 1e-12 and us[-1] > 0.9 * P.u_pre


def test_admittance_increment():
    c = FingerController(P)
    c.u = 0.4
    F_t = MATERIAL_TABLE["conductor"][0]
    c.step(_m(F_t - 1, 1), "conductor", "GRASP", DT)
    u1 = c.u
    c.step(_m(F_t - 1, 1), "conductor", "GRASP", DT)
    assert abs((c.u - u1) - DT / P.B_a) < 1e-12


def test_safety_on_force():
    c = FingerController(P)
    c.u = 0.5
    c.step(_m(9.0, 1), "conductor", "GRASP", DT)
    u1 = c.step(_m(9.0, 1), "conductor", "GRASP", DT)
    assert c.safety_trip and u1 < 0.5
    for _ in range(5):
        c.step(_m(1.0, 1), "conductor", "GRASP", DT)
    assert not c.safety_trip


def test_safety_on_eps_out_of_range():
    c = FingerController(P)
    c.u = 0.5
    c.step(_m(2.0, 1, eps=31.5), "conductor", "GRASP", DT)
    assert c.safety_trip and c.u < 0.5


def test_gate_flicker_bounded():
    c = FingerController(P)
    c.u = 0.3
    prev = c.u
    for k in range(1000):
        u = c.step(_m(5.0 if k % 2 else 10.0, k % 2), "conductor", "APPROACH", DT)
        assert abs(u - prev) <= 2 * P.u_rate_max * DT + 1e-12
        prev = u


def test_unknown_uses_dielectric():
    a, b = FingerController(P), FingerController(P)
    a.u = b.u = 0.4
    for _ in range(10):
        a.step(_m(1.0, 1), "unknown", "GRASP", DT)
        b.step(_m(1.0, 1), "dielectric", "GRASP", DT)
    assert a.u == b.u


def test_grasp_timeout_releases():
    s = GraspSupervisor(P)
    s.update(0.0, [0, 0, 0], "approach")
    assert s.phase == "APPROACH"
    s.update(2.0, [1, 1, 0], None)
    assert s.phase == "APPROACH"
    s.update(3.1, [1, 1, 0], None)
    assert s.phase == "RELEASE" and s.failed


def test_supervisor_full_sequence():
    s = GraspSupervisor(P)
    s.update(0.0, [0, 0, 0], "approach")
    s.update(0.5, [1, 1, 1], None)
    assert s.phase == "GRASP"
    s.update(1.0, [1, 1, 1], "lift")
    assert s.phase == "HOLD"
    s.update(2.0, [1, 1, 1], "release")
    assert s.phase == "RELEASE" and not s.failed
