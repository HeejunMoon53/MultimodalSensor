import numpy as np

from sim_gripper.control.controller import CtrlParams, FingerController
from sim_gripper.perception.moe import MoeOut
from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS, Scenario


def _short(name="E1_metal", t=1.5):
    return Scenario("short", SCENARIOS[name].obj, t_end=t)


def _grasp_lag(df):
    """세 손가락 모두 실제 접촉한 시각 → 상태 머신이 GRASP로 전환한 시각."""
    touch = (df[[f"F_true_{i}" for i in range(3)]] > 0.05).all(axis=1)
    return df.t[df.phase == "GRASP"].iloc[0] - df.t[touch].iloc[0]


def test_latency_delays_controller_input(models):
    d0, _ = run(_short(t=2.5), moe_models=models)
    d50, _ = run(_short(t=2.5), moe_models=models, latency_ms=50)
    assert 0.03 < _grasp_lag(d50) - _grasp_lag(d0) < 0.08


def test_ablate_material_uses_conductor(models):
    df, _ = run(_short("E2_egg", 2.0), moe_models=models, ablate=("material",))
    assert set(df.material_0.unique()) == {"conductor"}


def test_ablate_proximity_hides_distance(models):
    df, _ = run(_short(t=0.8), moe_models=models, ablate=("proximity",))
    nc = df[df.contact_0 == 0]
    assert np.all(nc.value_0 == 30.0)


def test_cascade_mode_grasps_and_logs(models):
    """제어 배선 검증 (이상 센서). v4 파이프라인 성능은 experiments.cascade_compare에서 비교."""
    sc = Scenario("short", SCENARIOS["E1_metal"].obj, t_end=4.0, events=[(0.5, "approach")])
    df, _ = run(sc, moe_models=models, ctrl_mode="cascade", sensor_mode="ideal")
    assert (df.phase == "GRASP").any()
    assert {"obj_x", "obj_y", "b_ref_0", "F_t_0"} <= set(df.columns)
    grip = df[df.phase == "GRASP"].iloc[-500:]
    assert abs(grip.F_true_0.mean() - 4.0) < 1.0


def test_safety_flag_disables_trip():
    c = FingerController(CtrlParams(safety=False))
    c.u = 0.5
    for _ in range(10):
        c.step(MoeOut(15.0, 20.0, 1, 1.0), "conductor", "GRASP", 0.001)
    assert not c.safety_trip
