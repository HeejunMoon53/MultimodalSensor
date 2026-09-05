"""
candidate1_baseline_gate.py
후보 1: 게이트(접촉 분류기) + 모드별 전문가(expert) MLP, 이력 피처 없음.

  (dL,dR) -> Gate -> contact 0/1
  contact=0 -> Expert A(proximity): (dL,dR) -> (strain, proximity_mm)
  contact=1 -> Expert B(pressure) : (dL,dR) -> (strain, force_N)

기존 model.py 스타일(hidden 소형 MLP, tanh)을 그대로 따름. 이력 피처가 없는
버전이라 히스테리시스 영향을 그대로 받는 기준선(baseline) 역할.
"""

import numpy as np
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import common

HIDDEN_EXPERT = (24, 16, 8)   # model.py SinglePINNMLP와 동일 스펙
HIDDEN_GATE = (8, 4)


def build_gate():
    return make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=HIDDEN_GATE, activation="tanh", solver="adam",
                      max_iter=3000, random_state=0, early_stopping=True, n_iter_no_change=30),
    )


def build_expert():
    return make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN_EXPERT, activation="tanh", solver="adam",
                      max_iter=4000, random_state=0, early_stopping=True, n_iter_no_change=40),
    )


def run(feature_cols, candidate_name="candidate1_baseline_gate", ema_halflife=None):
    df = common.load_raw()
    df = common.add_labels(df)
    if ema_halflife is not None:
        df, ema_cols = common.add_ema_features(df, halflife_s=ema_halflife)
        feature_cols = feature_cols + ema_cols

    train_df, test_df = common.split_by_cycle(df)

    # ── 게이트 ──────────────────────────────────────────────────────────────
    gate = build_gate()
    gate.fit(train_df[feature_cols].values, train_df["contact"].values)
    gate_pred_test = gate.predict(test_df[feature_cols].values)
    gate_metrics = common.classification_metrics(test_df["contact"].values, gate_pred_test)
    print(f"[Gate] acc={gate_metrics['acc']:.4f}  f1={gate_metrics['f1']:.4f}")

    # ── Expert A: proximity (strain, dist) ────────────────────────────────
    tr_a = train_df[train_df.phase == "proximity"]
    te_a = test_df[test_df.phase == "proximity"]
    expert_a = build_expert()
    expert_a.fit(tr_a[feature_cols].values, tr_a[["strain_pct", "z_mm"]].values)
    pred_a_oracle = expert_a.predict(te_a[feature_cols].values)
    m_a_strain = common.regression_metrics(te_a["strain_pct"].values, pred_a_oracle[:, 0])
    m_a_dist = common.regression_metrics(te_a["z_mm"].values, pred_a_oracle[:, 1])
    print(f"[Expert A: proximity] strain R2={m_a_strain['r2']:.4f} RMSE={m_a_strain['rmse']:.3f}%p | "
          f"dist R2={m_a_dist['r2']:.4f} RMSE={m_a_dist['rmse']:.3f}mm")

    # ── Expert B: pressure (strain, force) ──────────────────────────────────
    tr_b = train_df[train_df.phase == "pressure"]
    te_b = test_df[test_df.phase == "pressure"]
    expert_b = build_expert()
    expert_b.fit(tr_b[feature_cols].values, tr_b[["strain_pct", "Force_N"]].values)
    pred_b_oracle = expert_b.predict(te_b[feature_cols].values)
    m_b_strain = common.regression_metrics(te_b["strain_pct"].values, pred_b_oracle[:, 0])
    m_b_force = common.regression_metrics(te_b["Force_N"].values, pred_b_oracle[:, 1])
    print(f"[Expert B: pressure]  strain R2={m_b_strain['r2']:.4f} RMSE={m_b_strain['rmse']:.3f}%p | "
          f"force R2={m_b_force['r2']:.4f} RMSE={m_b_force['rmse']:.3f}N")

    # ── End-to-end: 학습된 게이트로 라우팅했을 때 최종 파이프라인 성능 ─────────
    X_test = test_df[feature_cols].values
    gate_pred_full = gate.predict(X_test)
    strain_pred = np.where(gate_pred_full == 0,
                            expert_a.predict(X_test)[:, 0],
                            expert_b.predict(X_test)[:, 0])
    m_e2e_strain = common.regression_metrics(test_df["strain_pct"].values, strain_pred)
    print(f"[End-to-end] strain (전체 test, 게이트 라우팅 포함) R2={m_e2e_strain['r2']:.4f} "
          f"RMSE={m_e2e_strain['rmse']:.3f}%p")

    result = dict(
        feature_cols=feature_cols,
        gate=gate_metrics,
        expert_a_oracle=dict(strain=m_a_strain, distance=m_a_dist),
        expert_b_oracle=dict(strain=m_b_strain, force=m_b_force),
        end_to_end_strain=m_e2e_strain,
    )
    common.save_result(candidate_name, result)
    return result


if __name__ == "__main__":
    run(common.FEATURE_COLS_BASE.copy())
