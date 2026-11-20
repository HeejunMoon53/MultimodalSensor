import mujoco

from finger_prbm import PrbmFinger


def build(f):
    xml = (f'<mujoco><compiler angle="radian"/><option timestep="0.002" gravity="0 0 0"/>'
           f'<worldbody>{f.mjcf("finger")}</worldbody></mujoco>')
    m = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(m)
    f.attach(m, d)
    return m, d


def settle(f, m, d, p, sec):
    for _ in range(int(sec / m.opt.timestep)):
        f.apply_pressure(d, p); mujoco.mj_step(m, d)


def test_rest_at_zero_pressure():
    f = PrbmFinger(); m, d = build(f)
    settle(f, m, d, 0.0, 0.5)
    assert abs(f.tip_angle(d)) < 2.0


def test_bends_and_inflates_monotonic():
    f = PrbmFinger(); m, d = build(f)
    ang, vol = [], []
    for p in (0, 10, 20, 30):
        settle(f, m, d, p, 2.0)
        ang.append(f.tip_angle(d)); vol.append(f.chamber_volume(d))
    assert ang[0] < ang[1] < ang[2] < ang[3] and vol[0] < vol[1] < vol[2]
    assert abs(ang[3] - 300.0) < 15.0


def test_sensor_strain_at_30kpa():
    f = PrbmFinger(); m, d = build(f)
    settle(f, m, d, 30.0, 2.0)
    assert abs(f.sensor_strain(d) - 12.0) < 1.0
