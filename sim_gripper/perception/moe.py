"""v4 Gate-MoE 디커플러 — 펌웨어 moe_inference.c 동작을 numpy로 그대로 옮긴 것.

순서: 게이트(원본 ΔL, ΔR) → 판단이 바뀐 그 사이클에 EMA 리셋, 아니면 블렌드 → 전문가.
"""
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PKL = ROOT / "nn_decoupling/test0909_realtime/new/stm32_deploy_moe_v4/models.pkl"

EMA_ALPHA = 0.00098716675          # dt=1ms, tau=1.0125s (moe_params.h)
GATE_THRESHOLD = 0.5
STRAIN_LIM = (-2.0, 32.0)
DIST_LIM = (-1.7, 26.09)
FORCE_LIM = (-2.347, 15.69)


def mlp_forward(mlp, x):
    h = np.atleast_2d(np.asarray(x, float))
    for W, b in zip(mlp.coefs_[:-1], mlp.intercepts_[:-1]):
        h = np.tanh(h @ W + b)
    out = h @ mlp.coefs_[-1] + mlp.intercepts_[-1]
    if mlp.out_activation_ == "logistic":
        return 1.0 / (1.0 + np.exp(-out[:, 0]))
    return out


@dataclass
class MoeOut:
    strain_pct: float
    value: float          # contact 0: dist_mm, 1: force_N
    contact: int
    gate_proba: float


def _scale(sc, x):
    return (np.asarray(x, float) - sc.mean_) / sc.scale_


class MoE:
    def __init__(self, pkl_path=DEFAULT_PKL, models=None):
        if models is None:
            with open(pkl_path, "rb") as f:
                models = pickle.load(f)
        self.models = models
        self.reset()

    def reset(self):
        self.ema = (0.0, 0.0)
        self._prev = -1

    def step(self, dL, dR, dt_s=0.001):
        m = self.models
        p = float(mlp_forward(m["gate"], _scale(m["sc_gate"], [dL, dR]))[0])
        contact = int(p >= GATE_THRESHOLD)

        if self._prev < 0 or contact != self._prev:
            self.ema = (float(dL), float(dR))
        else:
            a = 1.0 - (1.0 - EMA_ALPHA) ** (dt_s / 0.001)
            eL, eR = self.ema
            self.ema = (eL + a * (dL - eL), eR + a * (dR - eR))
        self._prev = contact

        x = [dL, dR, self.ema[0], self.ema[1]]
        if contact:
            y = mlp_forward(m["expert_b"], _scale(m["sc_b"], x))[0]
            lim = FORCE_LIM
        else:
            y = mlp_forward(m["expert_a"], _scale(m["sc_a"], x))[0]
            lim = DIST_LIM
        return MoeOut(float(np.clip(y[0], *STRAIN_LIM)), float(np.clip(y[1], *lim)),
                      contact, p)
