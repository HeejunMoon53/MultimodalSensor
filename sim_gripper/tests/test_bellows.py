import mujoco
import numpy as np
import pytest

from sim_gripper.model.calibrate_bellows import FIG9_SLOPE_DEG_PER_KPA, P0_KPA, blocked_force_N, free_bending_deg
from sim_gripper.model.gripper import BellowsParams, GripperSim, ObjectSpec, build_mjcf

METAL = ObjectSpec("metal", "cylinder", (0.025, 0.04), 0.2, "conductor")


def test_bellows_model_loads():
    m = mujoco.MjModel.from_xml_string(build_mjcf(BellowsParams(), METAL))
    assert int(np.sum(m.jnt_type == mujoco.mjtJoint.mjJNT_HINGE)) == 24


def test_bellows_open_no_contact():
    sim = GripperSim(BellowsParams(), METAL)
    for _ in range(800):
        sim.step(np.zeros((3, 8)), 0.0)
    assert np.all(sim.pad_distance_mm() > 1.0) and np.all(sim.pad_force_N() == 0)
    assert abs(np.degrees(sim.joint_angles()[0].sum()) - 41.0) < 3.0      # precurve 유지


@pytest.mark.parametrize("p_kpa", [100, 150, 200])
def test_free_bending_matches_fig9(p_kpa):
    target = FIG9_SLOPE_DEG_PER_KPA * (p_kpa - P0_KPA)
    assert abs(free_bending_deg(p_kpa * 1e3) - target) < 6.0


def test_blocked_force_200kpa():
    assert abs(blocked_force_N(200e3) - 6.28) < 1.0
