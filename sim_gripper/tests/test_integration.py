import pytest

from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def e1(models):
    return run(SCENARIOS["E1_metal"], moe_models=models)[0]


def test_e1_lifts_object(e1):
    z0 = e1.obj_z.iloc[0]
    assert e1.loc[e1.t >= 7.0, "obj_z"].iloc[0] - z0 >= 0.02
    assert not e1.failed.iloc[-1]


def test_e2_egg_not_broken(models):
    df, _ = run(SCENARIOS["E2_egg"], moe_models=models)
    assert not df.broken.iloc[-1]


def test_e2_hand_low_force(models):
    df, _ = run(SCENARIOS["E2_hand"], moe_models=models)
    hold = df[df.phase == "HOLD"]
    assert len(hold) > 0
    assert all(hold[f"F_true_{i}"].mean() < 3.0 for i in range(3))
