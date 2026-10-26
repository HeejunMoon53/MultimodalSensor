import numpy as np
import pandas as pd

from sim_gripper.experiments.run_all import compute_metrics
from sim_gripper.model import gripper
from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS, Scenario


def _synthetic():
    n = 100
    df = pd.DataFrame({"t": np.arange(n) * 0.001,
                       "phase": ["APPROACH"] * 20 + ["GRASP"] * 30 + ["HOLD"] * 50,
                       "obj_z": np.r_[np.full(50, 0.04), np.linspace(0.04, 0.07, 50)],
                       "broken": False, "failed": False, "mat_true": "conductor"})
    for i in range(3):
        df[f"F_true_{i}"] = np.r_[np.zeros(20), np.full(30, 3.0), np.full(50, 5.0)]   # HOLD 오차 1 N
        df[f"value_{i}"] = df[f"F_true_{i}"]
        df[f"contact_{i}"] = (df[f"F_true_{i}"] > 0.05).astype(int)
        df[f"eps_true_{i}"] = np.linspace(15, 10, n)
        df[f"eps_hat_{i}"] = np.linspace(15, 10, n)
        df[f"material_{i}"] = "conductor"
    return df


def test_metrics_on_synthetic_df():
    m = compute_metrics(_synthetic())
    assert abs(m["force_rmse"] - 1.0) < 1e-9
    assert m["success"] and m["gate_acc"] == 1.0 and m["material_acc"] == 1.0
    assert abs(m["strain_r2"] - 1.0) < 1e-9 and abs(m["max_force"] - 5.0) < 1e-9


def test_run_without_video_when_render_fails(models, monkeypatch):
    monkeypatch.setattr(gripper.GripperSim, "render_frame", lambda self, *a, **k: None)
    sc = Scenario("short", SCENARIOS["E1_metal"].obj, t_end=0.1)
    df, frames = run(sc, moe_models=models, record_video=True)
    assert len(df) == 100 and frames == []


def test_run_calls_on_step_every_tick(models):
    calls = []
    sc = Scenario("short", SCENARIOS["E1_metal"].obj, t_end=0.05)
    run(sc, moe_models=models, on_step=lambda sim, row: calls.append(row["t"]))
    assert len(calls) == 50 and calls[0] == 0.0


def test_metrics_has_strain_rmse():
    assert abs(compute_metrics(_synthetic())["strain_rmse"]) < 1e-12


def test_metrics_has_force_estimation_rmse():
    assert abs(compute_metrics(_synthetic())["force_est_rmse"]) < 1e-12


def test_max_force_ignores_release_impacts():
    df = _synthetic()
    df.loc[df.index[-1], "phase"] = "RELEASE"
    df.loc[df.index[-1], "F_true_0"] = 50.0
    assert compute_metrics(df)["max_force"] == 5.0
