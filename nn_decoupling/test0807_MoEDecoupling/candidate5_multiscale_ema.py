"""
candidate5_multiscale_ema.py
후보 5: 단일 τ EMA 대신 여러 시간상수(0.1/0.3/1.0/3.0s)의 EMA를 병렬로 넣어
MLP가 선형결합하게 함 — 작은 선형 RNN의 state가 표현할 수 있는 것과 근사한 형태.

주의: 이 환경에서 torch가 DLL 로드 실패라 실제 GRU/LSTM 학습은 불가능해서
"다중 시간상수 뱅크"로 근사 대체. candidate2(단일 τ)와 직접 비교해서
더 풍부한 이력 표현이 실제로 도움이 되는지만 확인하는 목적.
"""

import candidate1_baseline_gate as c1
import common

HALFLIVES = [0.1, 0.3, 1.0, 3.0]


def main():
    df = common.load_raw()
    df = common.add_labels(df)

    feature_cols = common.FEATURE_COLS_BASE.copy()
    for hl in HALFLIVES:
        df, ema_cols = common.add_ema_features(df, halflife_s=hl, suffix=f"_{hl}")
        feature_cols += ema_cols
    print(f"[config] {len(HALFLIVES)}개 시간상수 사용: {HALFLIVES} -> 피처 {len(feature_cols)}개")

    # candidate1.run은 자체적으로 load_raw/add_labels/add_ema_features를 다시 하므로
    # 여기서는 별도 실행 로직으로 분리 (df를 이미 만들어놨으니 재사용)
    train_df, test_df = common.split_by_cycle(df)

    import numpy as np

    gate = c1.build_gate()
    gate.fit(train_df[feature_cols].values, train_df["contact"].values)
    gate_pred_test = gate.predict(test_df[feature_cols].values)
    gate_metrics = common.classification_metrics(test_df["contact"].values, gate_pred_test)
    print(f"[Gate] acc={gate_metrics['acc']:.4f}  f1={gate_metrics['f1']:.4f}")

    tr_a = train_df[train_df.phase == "proximity"]
    te_a = test_df[test_df.phase == "proximity"]
    expert_a = c1.build_expert()
    expert_a.fit(tr_a[feature_cols].values, tr_a[["strain_pct", "z_mm"]].values)
    pred_a = expert_a.predict(te_a[feature_cols].values)
    m_a_strain = common.regression_metrics(te_a["strain_pct"].values, pred_a[:, 0])
    m_a_dist = common.regression_metrics(te_a["z_mm"].values, pred_a[:, 1])
    print(f"[Expert A: proximity] strain R2={m_a_strain['r2']:.4f} | dist R2={m_a_dist['r2']:.4f}")

    tr_b = train_df[train_df.phase == "pressure"]
    te_b = test_df[test_df.phase == "pressure"]
    expert_b = c1.build_expert()
    expert_b.fit(tr_b[feature_cols].values, tr_b[["strain_pct", "Force_N"]].values)
    pred_b = expert_b.predict(te_b[feature_cols].values)
    m_b_strain = common.regression_metrics(te_b["strain_pct"].values, pred_b[:, 0])
    m_b_force = common.regression_metrics(te_b["Force_N"].values, pred_b[:, 1])
    print(f"[Expert B: pressure]  strain R2={m_b_strain['r2']:.4f} RMSE={m_b_strain['rmse']:.3f}%p | "
          f"force R2={m_b_force['r2']:.4f} RMSE={m_b_force['rmse']:.3f}N")

    X_test = test_df[feature_cols].values
    gate_pred_full = gate.predict(X_test)
    strain_pred = np.where(gate_pred_full == 0,
                            expert_a.predict(X_test)[:, 0],
                            expert_b.predict(X_test)[:, 0])
    m_e2e = common.regression_metrics(test_df["strain_pct"].values, strain_pred)
    print(f"[End-to-end] strain R2={m_e2e['r2']:.4f} RMSE={m_e2e['rmse']:.3f}%p")

    result = dict(
        feature_cols=feature_cols,
        halflives=HALFLIVES,
        gate=gate_metrics,
        expert_a_oracle=dict(strain=m_a_strain, distance=m_a_dist),
        expert_b_oracle=dict(strain=m_b_strain, force=m_b_force),
        end_to_end_strain=m_e2e,
    )
    common.save_result("candidate5_multiscale_ema", result)


if __name__ == "__main__":
    main()
