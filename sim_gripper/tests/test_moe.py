import numpy as np
import pandas as pd

from sim_gripper.perception.moe import MoE, mlp_forward
from sim_gripper.tests.conftest import BOARD_CSV


def r2(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)


def _board_replay():
    d = pd.read_csv(BOARD_CSV)
    d = d[d["mode"].isin([0, 1])].reset_index(drop=True)
    moe = MoE()
    dts = np.diff(d.t_s.values, prepend=d.t_s.values[0] - 0.035)
    outs = [moe.step(a, b, dt_s=float(max(dt, 1e-3)))
            for a, b, dt in zip(d.dL_pct.values, d.dR_pct.values, dts)]
    return d, outs


def test_mlp_forward_matches_sklearn(models):
    x = np.random.default_rng(0).normal(size=(200, 4))
    assert np.allclose(mlp_forward(models["expert_a"], x),
                       models["expert_a"].predict(x), atol=1e-9)
    xg = x[:, :2]
    assert np.allclose(mlp_forward(models["gate"], xg),
                       models["gate"].predict_proba(xg)[:, 1], atol=1e-9)


def test_gate_replay_matches_board():
    d, outs = _board_replay()
    sim = np.array([o.contact for o in outs])
    assert (sim == d["mode"].values).mean() >= 0.99


def test_expert_strain_tracks_board():
    d, outs = _board_replay()
    sim = np.array([o.strain_pct for o in outs])
    assert r2(d.strain_pct.values, sim) >= 0.95


def test_ema_reset_on_gate_change():
    moe = MoE()
    for _ in range(500):
        moe.step(0.0, 0.0)
    out = moe.step(-27.0, 15.0)  # 접촉 영역 입력
    assert out.contact == 1
    assert moe.ema == (-27.0, 15.0)
