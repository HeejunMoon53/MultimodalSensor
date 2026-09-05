"""
candidate3_unified_mlp.py
후보 3: 명시적 게이트 없이 하나의 MLP가 (strain, position) 전체를 담당.

position(z_mm)은 근접(양수, mm)과 압력(음수, mm)을 하나의 연속 변수로 통일한 값
(이전 시각화의 "Proximity+Pressure" 축과 동일한 아이디어). 게이트/분기 없이 이
연속 함수 하나로 두 물리 체계의 급격한 전환을 표현할 수 있는지 검증.

입력: (dL, dR, dL_ema, dR_ema) — candidate2와 동일 이력 피처 사용
출력: (strain_pct, z_mm)
"""

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import common

HIDDEN = (32, 24, 16, 8)   # 게이트 없이 두 체계를 다 학습해야 하니 candidate1/2보다 약간 키움
TAU_OVERALL_S = 1.0125  # fit_relaxation_tau.py 결과 (mms_20260806 only)
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931


def main():
    df = common.load_raw()
    df = common.add_labels(df)
    df, ema_cols = common.add_ema_features(df, halflife_s=EMA_HALFLIFE_S)
    feature_cols = common.FEATURE_COLS_BASE + ema_cols

    train_df, test_df = common.split_by_cycle(df)

    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN, activation="tanh", solver="adam",
                      max_iter=5000, random_state=0, early_stopping=True, n_iter_no_change=50),
    )
    model.fit(train_df[feature_cols].values, train_df[["strain_pct", "z_mm"]].values)

    pred = model.predict(test_df[feature_cols].values)
    m_strain_all = common.regression_metrics(test_df["strain_pct"].values, pred[:, 0])
    m_pos_all = common.regression_metrics(test_df["z_mm"].values, pred[:, 1])
    print(f"[전체] strain R2={m_strain_all['r2']:.4f} RMSE={m_strain_all['rmse']:.3f}%p | "
          f"z_mm(통합 position) R2={m_pos_all['r2']:.4f} RMSE={m_pos_all['rmse']:.3f}mm")

    # 근접(z>=0)/압력(z<0) 서브셋으로 나눠서 - 게이트 없이도 두 영역을 잘 잡는지 확인
    prox_mask = test_df["z_mm"].values >= 0
    press_mask = ~prox_mask

    m_strain_prox = common.regression_metrics(test_df["strain_pct"].values[prox_mask], pred[prox_mask, 0])
    m_pos_prox = common.regression_metrics(test_df["z_mm"].values[prox_mask], pred[prox_mask, 1])
    print(f"[근접 구간만] strain R2={m_strain_prox['r2']:.4f} | position R2={m_pos_prox['r2']:.4f} "
          f"RMSE={m_pos_prox['rmse']:.3f}mm")

    m_strain_press = common.regression_metrics(test_df["strain_pct"].values[press_mask], pred[press_mask, 0])
    m_pos_press = common.regression_metrics(test_df["z_mm"].values[press_mask], pred[press_mask, 1])
    print(f"[압력 구간만] strain R2={m_strain_press['r2']:.4f} | position R2={m_pos_press['r2']:.4f} "
          f"RMSE={m_pos_press['rmse']:.3f}mm")

    # 압력 구간 position 오차를 Force 단위로도 참고 표시 (z<0 구간의 실제 힘 대비 오차 규모 감 잡기용)
    force_true = test_df["Force_N"].values[press_mask]
    print(f"    (참고: 압력구간 실제 Force 범위 {force_true.min():.2f}~{force_true.max():.2f}N)")

    # 모드 경계(접촉 시작 직전/직후) 근처에서 오차가 튀는지 확인
    near_boundary = np.abs(test_df["z_mm"].values) < 1.0
    if near_boundary.sum() > 5:
        m_boundary = common.regression_metrics(test_df["z_mm"].values[near_boundary], pred[near_boundary, 1])
        print(f"[모드 경계(|z|<1mm) 근처] position R2={m_boundary['r2']:.4f} RMSE={m_boundary['rmse']:.3f}mm "
              f"(n={near_boundary.sum()})")

    result = dict(
        feature_cols=feature_cols,
        overall=dict(strain=m_strain_all, position=m_pos_all),
        proximity_subset=dict(strain=m_strain_prox, position=m_pos_prox),
        pressure_subset=dict(strain=m_strain_press, position=m_pos_press),
    )
    common.save_result("candidate3_unified_mlp", result)


if __name__ == "__main__":
    main()
