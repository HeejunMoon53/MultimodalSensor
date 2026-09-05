"""
candidate2_gate_ema.py
후보 2: candidate1과 동일한 게이트+2-expert 구조에 인과적 EMA 이력 피처를 추가.
halflife는 fit_relaxation_tau.py에서 구한 tau_overall(≈1.013s, mms_20260806 단일 데이터셋 기준)로부터
halflife = tau * ln(2) ≈ 0.702s 로 설정.
"""

import candidate1_baseline_gate as c1
import common

TAU_OVERALL_S = 1.0125  # fit_relaxation_tau.py 결과 (mms_20260806 only)
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931  # halflife = tau * ln(2)

if __name__ == "__main__":
    print(f"[config] EMA halflife = {EMA_HALFLIFE_S:.3f}s (tau={TAU_OVERALL_S}s 기반)")
    c1.run(common.FEATURE_COLS_BASE.copy(),
           candidate_name="candidate2_gate_ema",
           ema_halflife=EMA_HALFLIFE_S)
