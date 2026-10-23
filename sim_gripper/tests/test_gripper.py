import mujoco
import numpy as np
import pytest

from sim_gripper.model.gripper import FingerParams, GripperSim, ObjectSpec, build_mjcf

METAL = ObjectSpec("metal", "cylinder", (0.025, 0.04), 0.1, "conductor")
EGG = ObjectSpec("egg", "sphere", (0.025,), 0.06, "dielectric", fragile_F_N=3.5)


def _run(sim, tau_val, seconds):
    tau = np.full((3, 4), tau_val)
    for _ in range(int(seconds / sim.model.opt.timestep)):
        sim.step(tau, 0.0)


def test_model_loads():
    m = mujoco.MjModel.from_xml_string(build_mjcf(FingerParams(), METAL))
    assert int(np.sum(m.jnt_type == mujoco.mjtJoint.mjJNT_HINGE)) == 12


def test_joint_stiffness():
    assert abs(FingerParams().joint_stiffness() - 0.47) < 0.05


def test_distance_decreases():
    sim = GripperSim(FingerParams(), METAL)
    d0 = sim.pad_distance_mm().copy()
    _run(sim, 0.03, 0.3)
    assert np.all(sim.pad_distance_mm() < d0)


def test_contact_force_positive():
    sim = GripperSim(FingerParams(), METAL)
    _run(sim, 0.2, 1.0)
    assert np.all(sim.pad_force_N() > 0)
    assert np.all(sim.pad_distance_mm() == 0)


def test_egg_breaks():
    sim = GripperSim(FingerParams(), EGG)
    _run(sim, 0.6, 1.0)
    assert sim.object_broken
