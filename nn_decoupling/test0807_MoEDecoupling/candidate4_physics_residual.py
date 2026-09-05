"""
candidate4_physics_residual.py
후보 4: 물리모델(순방향) + 잔차 보정 하이브리드.

model.py의 PhysicsLoss는 원래 R_theory(ε)=α1ε+α2ε² (교차항 없음)를 가정하지만,
이번 조사에서 압력 모드의 R은 ε×F 교차항이 강하게 존재함을 확인했으므로:

  R_theory_press(ε, F) = γ1*ε + γ2*ε² + γ3*ε*F      (γ3가 새로 추가된 교차항)
  L_theory_press(ε, F) = δ1*ε + δ2*F + δ3*ε*F        (L도 동일한 형태로 시도)

이 순방향 물리식은 F에 대해 선형이므로 closed-form 역산이 가능:
  F_phys = (dR - γ1*ε - γ2*ε²) / (γ3*ε)

단계:
  1) 순방향 물리 파라미터를 최소자승으로 학습 데이터에 피팅
  2) "순수 물리 역산"만으로 F를 복원했을 때 정확도 확인 (NN 전혀 없음, 상한/하한 참고용)
     - ε을 정답으로 준 경우(oracle) / 별도 회귀로 추정한 경우 두 가지로 확인
  3) 물리 역산값을 잔차보정 MLP의 입력 피처로 추가해서, 순수 데이터 기반(candidate2)
     대비 더 나아지는지 확인 (물리 잔차 하이브리드)
"""

import numpy as np
from scipy.optimize import least_squares
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import common

TAU_OVERALL_S = 1.0125  # fit_relaxation_tau.py 결과 (mms_20260806 only)
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN = (24, 16, 8)


def fit_cross_term_physics(eps, F, y):
    """y = g1*eps + g2*eps^2 + g3*eps*F  (선형 최소자승)"""
    X = np.column_stack([eps, eps ** 2, eps * F])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef  # [g1, g2, g3]


def physics_predict_y(coef, eps, F):
    g1, g2, g3 = coef
    return g1 * eps + g2 * eps ** 2 + g3 * eps * F


def physics_invert_F(coef, eps, y, eps_floor=1e-3):
    """y = g1*eps + g2*eps^2 + g3*eps*F  ->  F = (y - g1*eps - g2*eps^2) / (g3*eps)"""
    g1, g2, g3 = coef
    eps_safe = np.where(np.abs(eps) < eps_floor, np.sign(eps) * eps_floor + eps_floor, eps)
    return (y - g1 * eps_safe - g2 * eps_safe ** 2) / (g3 * eps_safe)


def main():
    df = common.load_raw()
    df = common.add_labels(df)
    df, ema_cols = common.add_ema_features(df, halflife_s=EMA_HALFLIFE_S)
    train_df, test_df = common.split_by_cycle(df)

    tr_b = train_df[train_df.phase == "pressure"]
    te_b = test_df[test_df.phase == "pressure"]

    # eps 단위: strain_pct는 %, 물리식은 비율(0~0.3)이 더 안정적 -> /100
    eps_tr = tr_b["strain_pct"].values / 100.0
    eps_te = te_b["strain_pct"].values / 100.0
    F_tr, F_te = tr_b["Force_N"].values, te_b["Force_N"].values
    dR_tr, dR_te = tr_b["dR_pct"].values, te_b["dR_pct"].values
    dL_tr, dL_te = tr_b["dL_pct"].values, te_b["dL_pct"].values

    # ── 1) 순방향 물리 피팅 ─────────────────────────────────────────────────
    coef_R = fit_cross_term_physics(eps_tr, F_tr, dR_tr)
    coef_L = fit_cross_term_physics(eps_tr, F_tr, dL_tr)
    print(f"[물리 피팅] R_theory: g1={coef_R[0]:.3f} g2={coef_R[1]:.3f} g3(εF 교차항)={coef_R[2]:.3f}")
    print(f"[물리 피팅] L_theory: g1={coef_L[0]:.3f} g2={coef_L[1]:.3f} g3(εF 교차항)={coef_L[2]:.3f}")

    dR_fit_pred = physics_predict_y(coef_R, eps_tr, F_tr)
    m_R_fit = common.regression_metrics(dR_tr, dR_fit_pred)
    print(f"    R_theory 순방향 적합도(학습셋 자체) R2={m_R_fit['r2']:.4f}  (교차항 있는 식이 얼마나 잘 맞는지)")

    # ── 2) 순수 물리 역산만으로 F 복원 (NN 없음) ───────────────────────────
    F_phys_oracle_eps = physics_invert_F(coef_R, eps_te, dR_te)          # eps는 정답 사용 (상한 참고)
    m_phys_oracle = common.regression_metrics(F_te, F_phys_oracle_eps)
    print(f"[물리역산만, eps=정답] F R2={m_phys_oracle['r2']:.4f} RMSE={m_phys_oracle['rmse']:.3f}N")

    # eps을 별도 선형회귀(dR만으로)로 추정한 뒤 역산 (좀 더 현실적인 파이프라인)
    eps_est_model = LinearRegression().fit(tr_b[["dR_pct"]].values, eps_tr)
    eps_est_te = eps_est_model.predict(te_b[["dR_pct"]].values)
    F_phys_est_eps = physics_invert_F(coef_R, eps_est_te, dR_te)
    m_phys_est = common.regression_metrics(F_te, F_phys_est_eps)
    print(f"[물리역산만, eps=추정] F R2={m_phys_est['r2']:.4f} RMSE={m_phys_est['rmse']:.3f}N  "
          f"(eps 추정 오차가 F 역산에 얼마나 증폭되는지 확인)")

    # ── 3) 물리잔차 하이브리드: 물리역산값을 피처로 추가한 residual MLP ──────
    feature_cols = common.FEATURE_COLS_BASE + ema_cols
    F_phys_tr_feat = physics_invert_F(coef_R, eps_tr, dR_tr)   # 학습셋도 동일 방식(추정 eps 아님, 정답 eps로 피처 생성)
    # 실전 배포 관점에선 eps도 추정값이어야 하므로, eps_est로 물리역산 피처를 생성 (train도 동일 기준)
    eps_est_tr = eps_est_model.predict(tr_b[["dR_pct"]].values)
    F_phys_feat_tr = physics_invert_F(coef_R, eps_est_tr, dR_tr)
    F_phys_feat_te = physics_invert_F(coef_R, eps_est_te, dR_te)

    X_tr = np.column_stack([tr_b[feature_cols].values, F_phys_feat_tr])
    X_te = np.column_stack([te_b[feature_cols].values, F_phys_feat_te])

    residual_model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN, activation="tanh", solver="adam",
                      max_iter=4000, random_state=0, early_stopping=True, n_iter_no_change=40),
    )
    residual_model.fit(X_tr, np.column_stack([eps_tr * 100.0, F_tr]))
    pred = residual_model.predict(X_te)
    m_hybrid_strain = common.regression_metrics(eps_te * 100.0, pred[:, 0])
    m_hybrid_force = common.regression_metrics(F_te, pred[:, 1])
    print(f"[물리+잔차 하이브리드] strain R2={m_hybrid_strain['r2']:.4f} RMSE={m_hybrid_strain['rmse']:.3f}%p | "
          f"force R2={m_hybrid_force['r2']:.4f} RMSE={m_hybrid_force['rmse']:.3f}N")

    # 순수 데이터 기반(물리 피처 없는) MLP와 바로 비교할 수 있게 동일 조건으로 하나 더
    plain_model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN, activation="tanh", solver="adam",
                      max_iter=4000, random_state=0, early_stopping=True, n_iter_no_change=40),
    )
    plain_model.fit(tr_b[feature_cols].values, np.column_stack([eps_tr * 100.0, F_tr]))
    pred_plain = plain_model.predict(te_b[feature_cols].values)
    m_plain_strain = common.regression_metrics(eps_te * 100.0, pred_plain[:, 0])
    m_plain_force = common.regression_metrics(F_te, pred_plain[:, 1])
    print(f"[비교: 물리피처 없는 순수 MLP(candidate2 Expert B와 동일 조건)] "
          f"strain R2={m_plain_strain['r2']:.4f} | force R2={m_plain_force['r2']:.4f}")

    result = dict(
        physics_coef=dict(R=coef_R.tolist(), L=coef_L.tolist()),
        physics_forward_fit_R2=m_R_fit,
        physics_only_oracle_eps=m_phys_oracle,
        physics_only_estimated_eps=m_phys_est,
        hybrid=dict(strain=m_hybrid_strain, force=m_hybrid_force),
        plain_mlp_same_features_minus_physics=dict(strain=m_plain_strain, force=m_plain_force),
    )
    common.save_result("candidate4_physics_residual", result)


if __name__ == "__main__":
    main()
