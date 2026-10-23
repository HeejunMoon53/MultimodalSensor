"""0909 실측 데이터 → 센서 순방향 모델 룩업 테이블(tables.npz).

ΔL_ε, ΔR_ε : 214746, proximity≈24 mm 슬라이스, bin 평균 → 2차 다항 피팅
ΔL_prox    : 근접 곡면(214746+222022, mode 0) − 곡면(ε, 24)
ΔL_F, ΔR_F : 압력 곡면(220210, mode 1) − 곡면(ε, F=0)
격자화는 plot_new_training_data.grid() (bin 평균 + NaN-가중 가우시안) 그대로.
실행: python -m sim_gripper.sensor.build_tables
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NEW_DIR = ROOT / "nn_decoupling/test0909_realtime/new"
DEFAULT_TABLES = Path(__file__).with_name("tables.npz")

EPS = np.arange(0.0, 30.0 + 1e-9, 0.5)
D = np.arange(0.0, 24.0 + 1e-9, 0.5)
F = np.arange(0.0, 12.0 + 1e-9, 0.25)


def _edges(c):
    h = (c[1] - c[0]) / 2
    return np.concatenate([c - h, [c[-1] + h]])


def _poly(x, y, deg=2):
    xb = _edges(EPS)
    idx = np.digitize(x, xb) - 1
    ok = (idx >= 0) & (idx < len(EPS))
    s = pd.Series(np.asarray(y)[ok]).groupby(idx[ok]).mean()
    return np.polyval(np.polyfit(EPS[s.index], s.values, deg), EPS)


def build_tables(out_path=DEFAULT_TABLES):
    sys.path.insert(0, str(NEW_DIR))
    import plot_new_training_data as m

    d1 = m.load("moe_monitor_20260909_214746.csv", trim=(0, 359.9))
    d2 = m.load("moe_monitor_20260909_222022.csv", trim=(0, 402.0))
    d3 = m.load("moe_monitor_20260909_220210.csv", trim=(15.35, 666.5))

    far = d1[(d1.prox_mm - 24).abs() < 0.5]
    dL_eps = _poly(far.strain_act_pct.values, far.dL_pct_smooth.values)
    dR_eps = _poly(far.strain_act_pct.values, far.dR_pct_smooth.values)

    prox = pd.concat([d1[d1["mode"] == 0], d2[d2["mode"] == 0]], ignore_index=True)
    _, _, SL, _ = m.grid(prox, "prox_mm", _edges(D), _edges(EPS))      # (eps, d)
    dL_prox = SL - SL[:, [-1]]

    press = d3[d3["mode"] == 1]
    _, _, FL, FR = m.grid(press, "F_true", _edges(F), _edges(EPS))     # (eps, F)
    dL_F = FL - FL[:, [0]]
    dR_F = FR - FR[:, [0]]

    np.savez(out_path, eps=EPS, d=D, F=F, dL_eps=dL_eps, dR_eps=dR_eps,
             dL_prox=dL_prox, dL_F=dL_F, dR_F=dR_F)
    print("saved", out_path)


if __name__ == "__main__":
    build_tables()
