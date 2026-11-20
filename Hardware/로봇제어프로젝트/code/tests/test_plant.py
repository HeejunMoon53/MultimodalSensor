import numpy as np
import pytest

from plant import Plant, PlantDiverged, Scenario


def test_deterministic_same_seed():
    a, b = Plant(Scenario(fingers=1), seed=3), Plant(Scenario(fingers=1), seed=3)
    for _ in range(30):
        oa, ob = a.step(np.array([10.0])), b.step(np.array([10.0]))
    assert np.allclose(oa.eps_hat, ob.eps_hat) and np.allclose(oa.p_mon, ob.p_mon)


def test_ideal_returns_truth():
    pl = Plant(Scenario(fingers=1), nonideal=False)
    for _ in range(50):
        o = pl.step(np.array([15.0]))
    assert np.allclose(o.eps_hat, pl.truth().eps)


def test_contact_force_when_closing_on_object():
    pl = Plant(Scenario(obj_start_mm=(0, 0, -70)), nonideal=False)
    for _ in range(300):
        pl.step(np.array([30.0, 30.0]))
    assert pl.truth().F_N.max() > 0.05


def test_divergence_raises():
    pl = Plant(Scenario(fingers=1))
    pl.step(np.array([10.0]))
    pl.d.qvel[:] = np.nan  # 수치 발산 주입
    with pytest.raises(PlantDiverged):
        pl.step(np.array([10.0]))
