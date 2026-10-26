import math

import pytest

from sim_gripper.cad.export import export_all
from sim_gripper.cad.finger import FingerCAD, make_finger


@pytest.fixture(scope="module")
def finger():
    return make_finger(FingerCAD())


def test_finger_is_single_valid_solid(finger):
    assert finger.is_valid and len(finger.solids()) == 1


def test_finger_depth_and_chord(finger):
    p, bb = FingerCAD(), finger.bounding_box()
    assert abs(bb.size.Y - p.depth) < 0.5
    assert abs(bb.max.Z - p.root_len) < 0.5
    assert -112 < bb.min.Z < -95                     # ρ·sin41° ≈ 96 mm + 벨로즈 두께
    th = math.radians(p.precurve_deg)
    assert abs(p.rho() * th - p.arc_len) < 1e-9


def test_finger_is_hollow(finger):
    solid = make_finger(FingerCAD(), hollow=False)
    assert finger.volume < 0.8 * solid.volume


def test_export_writes_stl(tmp_path):
    files = export_all(tmp_path)
    for key in ("finger_stl", "finger_step", "base_stl", "settings"):
        assert files[key].exists() and files[key].stat().st_size > 0
