import pytest

from sim_gripper.experiments.calibrated import make_gripper_moe
from sim_gripper.experiments.run_all import compute_metrics
from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def cal(models):
    return make_gripper_moe(n=8000, seed=0, base=models, cache=None)


def test_calibrated_keeps_architecture(models, cal):
    for k in ("gate", "expert_a", "expert_b"):
        assert [w.shape for w in cal[k].coefs_] == [w.shape for w in models[k].coefs_]
    assert sum(w.size for k in ("gate", "expert_a", "expert_b") for w in cal[k].coefs_ + cal[k].intercepts_) == 1413


def test_calibrated_improves_bellows_force(models, cal):
    sc = SCENARIOS["E1_metal"]
    v4 = compute_metrics(run(sc, finger="bellows60a", moe_models=models, seed=7)[0])
    gm = compute_metrics(run(sc, finger="bellows60a", moe_models=cal, seed=7)[0])
    assert gm["strain_rmse"] < v4["strain_rmse"]
    assert gm["force_rmse"] <= v4["force_rmse"] + 0.1
