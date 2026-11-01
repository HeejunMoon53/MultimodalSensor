"""보이는 형상(visual layer)은 물리에 영향이 없어야 한다: 질량·관성·궤적이 visual=False와 비트 단위로 같음."""
import mujoco
import numpy as np
import pytest

from sim_gripper.model.gripper import BellowsParams, FingerParams, GripperSim, ObjectSpec, build_mjcf

EGG = ObjectSpec("egg", "sphere", (0.022,), 0.06, "dielectric", fragile_F_N=3.5)
METAL = ObjectSpec("metal", "cylinder", (0.025, 0.04), 0.2, "conductor")
FPS = [FingerParams(), BellowsParams()]


def _traj(fp, obj, visual, steps=1500):
    sim = GripperSim(fp, obj, visual=visual)
    tau = np.full((3, fp.n_joints), 0.15)
    for _ in range(steps):
        sim.step(tau, sim.lift0)
    return sim


@pytest.mark.parametrize("fp", FPS, ids=["flat", "bellows"])
@pytest.mark.parametrize("obj", [EGG, METAL], ids=["egg", "metal"])
def test_visual_layer_does_not_change_dynamics(fp, obj):
    a, b = _traj(fp, obj, False), _traj(fp, obj, True)
    assert np.array_equal(a.model.body_mass, b.model.body_mass)
    assert np.array_equal(a.model.body_inertia, b.model.body_inertia)
    assert a.lift0 == b.lift0
    assert np.array_equal(a.data.qpos, b.data.qpos)
    assert np.array_equal(a.pad_force_N(), b.pad_force_N())


@pytest.mark.parametrize("fp", FPS, ids=["flat", "bellows"])
def test_collision_hidden_visual_shown(fp):
    m = mujoco.MjModel.from_xml_string(build_mjcf(fp, EGG, visual=True))
    vis = [g for g in range(m.ngeom) if m.geom_group[g] == 1]
    assert vis and all(m.geom_contype[g] == 0 and m.geom_conaffinity[g] == 0 for g in vis)
    finger_bodies = {b for b in range(m.nbody) if m.body(b).name.startswith("f")}
    for g in range(m.ngeom):
        if m.geom_bodyid[g] in finger_bodies and m.geom_group[g] != 1:
            assert m.geom_group[g] == (0 if m.geom(g).name.startswith("pad_") else 3)
    assert m.geom_group[m.geom("obj").id] == 3          # 계란 충돌 구는 숨기고 타원체를 보여줌


def test_bellows_uses_cad_meshes():
    m = mujoco.MjModel.from_xml_string(build_mjcf(BellowsParams(), EGG, visual=True))
    assert m.nmesh >= 9                                  # 벨로즈 8 + 루트 (+ 베이스)


def test_flat_finger_shows_tendon():
    m = mujoco.MjModel.from_xml_string(build_mjcf(FingerParams(), EGG, visual=True))
    assert m.ntendon == 3
