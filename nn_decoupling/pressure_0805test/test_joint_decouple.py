"""
test_joint_decouple.py
(dL, dR [+ EMA]) -> (strain, force/distance) 동시 디커플링이 실제로 되는지 테스트.
압력(pressure) 모드뿐 아니라 근접(proximity) 모드도 같은 방식으로 검증한다.

앞서 계산한 민감도 분석(정적 선형 근사, 압력 모드 기준):
  strain 방향 : (dL,dR) per 1%   = (0.635, 0.664)   -> 거의 45도 (L,R 거의 동일 비율)
  force  방향 : (dL,dR) per 1N   = (2.070, 11.575)   -> R가 훨씬 가파름 (R-편향)
  두 방향 사이 각도 ~33.6도, 자코비안 조건수 ~23  -> 완전히 겹치진 않지만(분리 가능) 꽤 ill-conditioned.

여기서는 실제 비선형 MLP가 held-out cycle에서 strain, force(압력 모드)/distance(근접 모드)를
얼마나 잘 동시에 복원하는지로 "학습 기반 디커플링" 자체의 실현 가능성을 직접 검증한다.

사이클 분할은 test0807_MoEDecoupling/common.py의 cycle_id(=strain 값이 바뀔 때마다 새 사이클)를
그대로 재사용한다 — 예전에 이 스크립트가 쓰던 자체 segment_id(=z_mm 부호가 바뀔 때만 새 구간)는
"근접 구간 하나가 다음 strain 스텝으로 넘어가는 전환 램프, 그리고 기록 맨 끝의 스테이지 원점복귀(homing)
구간"까지 하나의 구간으로 묶어버려서, 근접모드 held-out 평가에 실제 프로토콜에 없는 잡음 구간이
섞이는 버그가 있었다. cycle_id + min_len=500 필터를 쓰면 이런 짧은 전환 구간이 자동으로 걸러진다.
"""

import os
import sys

import matplotlib.pyplot as plt
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test0807_MoEDecoupling"))
import common

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

EMA_HALFLIFE_S = 0.702  # fit_relaxation_tau.py 결과(tau=1.0125s, mms_20260806 only) 기반
HIDDEN = (24, 16, 8)

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_F = "#1F77B4"


def load_data():
    df = common.load_raw()
    df = common.add_labels(df)
    df, ema_cols = common.add_ema_features(df, halflife_s=EMA_HALFLIFE_S)
    return df, ema_cols


def fit_predict(train_df, test_df, feats, targets):
    Xtr, Xte = train_df[feats].values, test_df[feats].values
    ytr, yte = train_df[targets].values, test_df[targets].values
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN, activation="tanh", solver="adam",
                      max_iter=4000, random_state=0, early_stopping=True, n_iter_no_change=40),
    )
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    return yte, pred


def main():
    df, ema_cols = load_data()
    feats = common.FEATURE_COLS_BASE + ema_cols  # [dL_pct, dR_pct, dL_ema, dR_ema]

    train_df, test_df = common.split_by_cycle(df)  # cycle_id 기준, min_len=500
    print(f"cycles: train={train_df.cycle_id.nunique()}  test={sorted(test_df.cycle_id.unique())}")

    # ── 압력(pressure) 모드: (strain, force) ──────────────────────────────────
    tr_p = train_df[train_df.phase == "pressure"]
    te_p = test_df[test_df.phase == "pressure"]
    print(f"[pressure] test strain values: {sorted(te_p.strain_pct.round(2).unique())}")
    yte_p, pred_p = fit_predict(tr_p, te_p, feats, ["strain_pct", "Force_N"])
    r2_strain_p = r2_score(yte_p[:, 0], pred_p[:, 0])
    r2_force = r2_score(yte_p[:, 1], pred_p[:, 1])
    mae_strain_p = mean_absolute_error(yte_p[:, 0], pred_p[:, 0])
    mae_force = mean_absolute_error(yte_p[:, 1], pred_p[:, 1])
    print(f"[pressure] strain R2={r2_strain_p:.4f} MAE={mae_strain_p:.3f}%p | "
          f"force R2={r2_force:.4f} MAE={mae_force:.3f}N")

    # ── 근접(proximity) 모드: (strain, z_mm) ──────────────────────────────────
    tr_x = train_df[train_df.phase == "proximity"]
    te_x = test_df[test_df.phase == "proximity"]
    print(f"[proximity] test strain values: {sorted(te_x.strain_pct.round(2).unique())}")
    yte_x, pred_x = fit_predict(tr_x, te_x, feats, ["strain_pct", "z_mm"])
    r2_strain_x = r2_score(yte_x[:, 0], pred_x[:, 0])
    r2_dist = r2_score(yte_x[:, 1], pred_x[:, 1])
    mae_strain_x = mean_absolute_error(yte_x[:, 0], pred_x[:, 0])
    mae_dist = mean_absolute_error(yte_x[:, 1], pred_x[:, 1])
    print(f"[proximity] strain R2={r2_strain_x:.4f} MAE={mae_strain_x:.3f}%p | "
          f"distance R2={r2_dist:.4f} MAE={mae_dist:.3f}mm")

    # ── 시각화: 2x2 (위: proximity, 아래: pressure) ───────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(13, 12))

    ax = axes[0, 0]
    ax.scatter(yte_x[:, 0], pred_x[:, 0], s=4, alpha=0.3, color=COLOR_L)
    lims = [yte_x[:, 0].min(), yte_x[:, 0].max()]
    ax.plot(lims, lims, 'k--', linewidth=1)
    ax.set_xlabel("Actual strain [%]"); ax.set_ylabel("Predicted strain [%]")
    ax.set_title(f"Proximity — strain decoupling: R2={r2_strain_x:.3f}")
    ax.grid(alpha=0.25)

    ax = axes[0, 1]
    ax.scatter(yte_x[:, 1], pred_x[:, 1], s=4, alpha=0.3, color=COLOR_F)
    lims = [yte_x[:, 1].min(), yte_x[:, 1].max()]
    ax.plot(lims, lims, 'k--', linewidth=1)
    ax.set_xlabel("Actual distance z [mm]"); ax.set_ylabel("Predicted distance z [mm]")
    ax.set_title(f"Proximity — distance decoupling: R2={r2_dist:.3f}")
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    ax.scatter(yte_p[:, 0], pred_p[:, 0], s=4, alpha=0.3, color=COLOR_L)
    lims = [yte_p[:, 0].min(), yte_p[:, 0].max()]
    ax.plot(lims, lims, 'k--', linewidth=1)
    ax.set_xlabel("Actual strain [%]"); ax.set_ylabel("Predicted strain [%]")
    ax.set_title(f"Pressure — strain decoupling: R2={r2_strain_p:.3f}")
    ax.grid(alpha=0.25)

    ax = axes[1, 1]
    ax.scatter(yte_p[:, 1], pred_p[:, 1], s=4, alpha=0.3, color=COLOR_R)
    lims = [yte_p[:, 1].min(), yte_p[:, 1].max()]
    ax.plot(lims, lims, 'k--', linewidth=1)
    ax.set_xlabel("Actual force [N]"); ax.set_ylabel("Predicted force [N]")
    ax.set_title(f"Pressure — force decoupling: R2={r2_force:.3f}")
    ax.grid(alpha=0.25)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "test_joint_decouple.png")
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")


if __name__ == "__main__":
    main()
