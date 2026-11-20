import mujoco

from finger_flex import FlexFinger, build_single
from tests.helpers import settle


def test_rest_at_zero_pressure():
    f = FlexFinger(); m, d = build_single(f)
    settle(f, m, d, 0.0, 0.25)
    assert abs(f.tip_angle(d)) < 2.0


def test_bends_and_inflates_monotonic():
    f = FlexFinger(); m, d = build_single(f)
    ang, vol = [], []
    for p in (0, 10, 20):
        settle(f, m, d, p, 1.0)
        ang.append(f.tip_angle(d)); vol.append(f.chamber_volume(d))
    assert ang[0] < ang[1] < ang[2] and vol[0] < vol[1] < vol[2]
