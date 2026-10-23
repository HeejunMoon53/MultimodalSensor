"""실험 러너: E1~E4 × {텐던, 공압} + E6 (이상 센서 vs 파이프라인).

python -m sim_gripper.experiments.run_all  →  sim_gripper/out/
"""
import json
import pickle
from pathlib import Path

import numpy as np

from sim_gripper.control.controller import MATERIAL_TABLE
from sim_gripper.perception.moe import DEFAULT_PKL
from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS
from sim_gripper.viz.plots import plot_actuator_compare, plot_ideal_vs_pipeline, plot_timeline
from sim_gripper.viz.render import save_mp4

OUT = Path(__file__).resolve().parents[1] / "out"
LIFT_OK_M = 0.02
GRID = ["E1_metal", "E2_hand", "E2_egg", "E3_sponge", "E3_small", "E3_large", "E4_disturb"]


def _r2(y, yhat):
    ss = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - yhat) ** 2) / ss) if ss > 0 else float("nan")


def compute_metrics(df):
    hold = df[df.phase == "HOLD"]
    grip = df[df.phase.isin(["GRASP", "HOLD"])]
    F_t = [MATERIAL_TABLE.get(df[f"material_{i}"].iloc[-1], MATERIAL_TABLE["dielectric"])[0] for i in range(3)]
    err = np.concatenate([hold[f"F_true_{i}"].values - F_t[i] for i in range(3)]) if len(hold) else np.array([])
    max_force = float(max(df[f"F_true_{i}"].max() for i in range(3)))
    over = [(grip[f"F_true_{i}"].max() - F_t[i]) / F_t[i] * 100 for i in range(3)] if len(grip) else [np.nan]
    settle = []
    for i in range(3):
        if not len(grip):
            break
        bad = np.abs(grip[f"F_true_{i}"].values - F_t[i]) > 0.1 * F_t[i]
        last_bad = np.flatnonzero(bad)
        if len(last_bad) == 0:
            settle.append(0.0)
        elif last_bad[-1] < len(bad) - 1:
            settle.append(float(grip.t.iloc[last_bad[-1] + 1] - grip.t.iloc[0]))
    lift = float(hold.obj_z.iloc[-1] - df.obj_z.iloc[0]) if len(hold) else 0.0
    touch = np.concatenate([(df[f"F_true_{i}"] > 0.05).values for i in range(3)])
    gate = np.concatenate([df[f"contact_{i}"].astype(bool).values for i in range(3)])
    eps = np.concatenate([df[f"eps_true_{i}"].values for i in range(3)])
    eps_hat = np.concatenate([df[f"eps_hat_{i}"].values for i in range(3)])
    mat = [df[f"material_{i}"].iloc[-1] == df.mat_true.iloc[0] for i in range(3)]
    return {
        "force_rmse": float(np.sqrt(np.mean(err ** 2))) if len(err) else float("nan"),
        "max_force": max_force,
        "overshoot_pct": float(np.nanmax(over)),
        "settle_s": float(np.mean(settle)) if len(settle) == 3 else float("nan"),
        "lift_m": lift,
        "success": bool(lift >= LIFT_OK_M and not df.failed.iloc[-1] and not df.broken.iloc[-1]),
        "broken": bool(df.broken.iloc[-1]),
        "gate_acc": float(np.mean(touch == gate)),
        "strain_r2": _r2(eps, eps_hat),
        "material_acc": float(np.mean(mat)),
    }


def run_all(out_dir=OUT):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_PKL, "rb") as f:
        models = pickle.load(f)
    metrics, e1 = {}, {}
    for name in GRID:
        for act in ("tendon", "pneumatic"):
            video = name == "E1_metal" and act == "tendon"
            df, frames = run(SCENARIOS[name], actuator=act, moe_models=models, record_video=video)
            metrics[f"{name}_{act}"] = compute_metrics(df)
            plot_timeline(df, 0, out_dir / f"timeline_{name}_{act}.png")
            df.to_pickle(out_dir / f"log_{name}_{act}.pkl")
            if name == "E1_metal":
                e1[act] = df
            if video:
                save_mp4(frames, out_dir / "E1_metal_tendon.mp4")
            print(name, act, metrics[f"{name}_{act}"], flush=True)
    plot_actuator_compare(e1, out_dir / "compare_actuators.png")
    pairs = {}
    for name in ("E1_metal", "E2_hand"):
        ideal, _ = run(SCENARIOS[name], sensor_mode="ideal", moe_models=models)
        metrics[f"{name}_ideal"] = compute_metrics(ideal)
        pipe = e1["tendon"] if name == "E1_metal" else None
        if pipe is None:
            pipe, _ = run(SCENARIOS[name], moe_models=models)
        pairs[name] = {"ideal": ideal, "pipeline": pipe}
    plot_ideal_vs_pipeline(pairs, out_dir / "ideal_vs_pipeline.png")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    run_all()
