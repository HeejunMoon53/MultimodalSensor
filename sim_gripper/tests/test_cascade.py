from dataclasses import replace

import numpy as np

from sim_gripper.control.cascade import CascadeController, CascadeParams
from sim_gripper.control.controller import MATERIAL_TABLE
from sim_gripper.perception.moe import MoeOut

DT = 0.001
P = CascadeParams()


def _m(value, contact, eps=15.0):
    return MoeOut(strain_pct=eps, value=value, contact=contact, gate_proba=float(contact))


def _outs(ds, contact=0, eps=15.0, mat="conductor"):
    return [(_m(d, contact, eps), mat) for d in ds]


def test_ff_increases_with_bending():
    c = CascadeController(P)
    u = [c.u_ff(b) for b in (0.0, 3.0, 6.0, 9.0)]
    assert u[0] == 0.0 and np.all(np.diff(u) > 0)


def test_open_resets_reference():
    c = CascadeController(P)
    c.b_ref[:] = 5.0
    c.u[:] = 0.5
    for _ in range(2000):
        u = c.step(_outs((20, 20, 20)), "OPEN", DT)
    assert np.all(c.b_ref == 0.0) and np.allclose(u, P.base.u_open)


def test_approach_rate_scheduled_by_proximity():
    for d, v in ((30.0, P.v_far_b), (3.0, P.v_near_b)):
        c = CascadeController(P)
        c.step(_outs((d, d, d)), "APPROACH", DT)
        assert np.allclose(c.b_ref, v * DT)


def test_sync_slows_nearest_finger():
    c = CascadeController(P)
    c.step(_outs((30.0, 15.0, 30.0)), "APPROACH", DT)
    assert c.b_ref[1] < c.b_ref[0] and abs(c.b_ref[0] - c.b_ref[2]) < 1e-12
    s = (15.0 + P.sync_soft_mm) / (30.0 + P.sync_soft_mm)
    assert abs(c.b_ref[1] / c.b_ref[0] - c._v(15.0) / P.v_far_b * s) < 1e-9


def test_sync_ignores_noise_near_contact():
    """접촉 직전 d̂ ~ 노이즈 크기 (0.0 vs 0.2 mm) — 비율이 0으로 떨어지지 않아야 함."""
    c = CascadeController(P)
    c.step(_outs((0.0, 0.2, 0.2)), "APPROACH", DT)
    assert c.b_ref[0] / c.b_ref[1] > 0.9


def test_force_loop_raises_reference_below_target():
    c = CascadeController(P)
    F_t = MATERIAL_TABLE["conductor"][0]
    c.step(_outs((F_t - 1,) * 3, contact=1), "GRASP", DT)
    b0 = c.b_ref.copy()
    c.step(_outs((F_t - 1,) * 3, contact=1), "GRASP", DT)
    assert np.allclose(c.b_ref - b0, DT / P.B_b)


def test_free_reference_clamped_near_measurement():
    c = CascadeController(P)
    for _ in range(5000):
        c.step(_outs((30.0,) * 3), "APPROACH", DT)          # 손가락이 막혀 b̂ = 0 그대로
    assert np.all(c.b_ref <= P.e_max + 1e-9)


def test_contact_inner_loop_has_no_integrator():
    """접촉 중 적분은 힘 루프(admittance) 하나만 — 내부 PI 적분이 겹치면 이중 적분 → 힘 오버슈트."""
    c = CascadeController(P)
    c.step(_outs((1.0,) * 3, contact=1), "GRASP", DT)
    I0 = c.I.copy()
    for _ in range(500):
        c.step(_outs((1.0,) * 3, contact=1), "GRASP", DT)
    assert np.allclose(c.I, I0)
    assert np.all(c.b_ref > P.e_max)                        # 접촉 중엔 넓은 클램프 → 힘을 낼 수 있음


def test_soft_object_lowers_force_target():
    p = replace(P, k_soft=2.0)
    stiff, soft = CascadeController(p), CascadeController(p)
    for k in range(400):
        F = 0.5 + 0.005 * k
        stiff.step(_outs((F,) * 3, contact=1, eps=15.0 - 0.0005 * k), "GRASP", DT)   # b 0.2 %, F +2 N
        soft.step(_outs((F,) * 3, contact=1, eps=15.0 - 0.01 * k), "GRASP", DT)      # b 4 %, F +2 N
    assert soft.F_t[0] < stiff.F_t[0] == MATERIAL_TABLE["conductor"][0]


def test_slip_raises_force_target():
    c = CascadeController(P)
    F_t = MATERIAL_TABLE["conductor"][0]
    for _ in range(300):
        c.step(_outs((F_t,) * 3, contact=1, eps=10.0), "HOLD", DT)
    for k in range(200):                                     # 20 N/s 하강 후 2 N 유지, ε̂ 그대로
        c.step(_outs((max(F_t - 0.02 * k, 2.0),) * 3, contact=1, eps=10.0), "HOLD", DT)
    assert c.F_t[0] > F_t


def test_noisy_hold_does_not_trigger_slip():
    c, rng = CascadeController(P), np.random.default_rng(0)
    F_t = MATERIAL_TABLE["conductor"][0]
    for _ in range(3000):
        c.step(_outs((F_t + 0.116 * rng.normal(),) * 3, contact=1, eps=10.0), "HOLD", DT)
    assert np.all(c.F_t == F_t)


def test_safety_backs_off():
    c = CascadeController(P)
    c.u[:] = 0.5
    c.b_ref[:] = 6.0
    c.step(_outs((9.0,) * 3, contact=1, eps=9.0), "GRASP", DT)
    u = c.step(_outs((9.0,) * 3, contact=1, eps=9.0), "GRASP", DT)
    assert all(c.safety_trip) and np.all(np.array(u) < 0.5) and np.all(c.b_ref <= 6.0 - P.back_off + 1e-9)


def test_command_rate_bounded():
    c, rng = CascadeController(P), np.random.default_rng(0)
    prev = c.u.copy()
    for k in range(1000):
        u = np.array(c.step(_outs((rng.uniform(0, 10),) * 3, contact=k % 2, eps=rng.uniform(5, 15)),
                            "GRASP", DT))
        assert np.all(np.abs(u - prev) <= 2 * P.base.u_rate_max * DT + 1e-12)
        prev = u
