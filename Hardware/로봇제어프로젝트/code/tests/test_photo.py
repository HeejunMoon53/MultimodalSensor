import numpy as np

from plant import Plant, Scenario


def _run(photo, mat, steps=120):
    pl = Plant(Scenario(material=mat, obj_start_mm=(0, 0, -70), photo=photo), seed=3)
    rec = []
    for _ in range(steps):
        o = pl.step(np.array([20.0, 20.0]))
        tr = pl.truth()
        rec.append([*tr.p, *tr.eps, *tr.F_N, *o.val_hat])
    return pl, np.array(rec)


def test_photo_props_do_not_change_physics():
    for mat, scene in (("conductor", "hammer"), ("human", "wrist")):
        _, a = _run(None, mat)
        pl, b = _run(scene, mat)
        assert np.array_equal(a, b), mat
        assert pl.m.ngeom > Plant(Scenario(material=mat)).m.ngeom   # 소품이 실제로 들어갔다


def test_photo_camera_renders():
    pl = Plant(Scenario(material="human", obj_start_mm=(0, 0, -120), photo="wrist"), seed=0)
    img = pl.frames(cam="photo", w=320, h=240)
    assert img.shape == (240, 320, 3) and img.std() > 10
