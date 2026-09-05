"""
fit_relaxation_tau.py
dwell(깊이 고정) 구간의 완화(relaxation) 곡선에 지수함수를 피팅해서
시간상수 τ를 추정한다. candidate 2/4/5의 EMA halflife를 여기서 구한 값으로 결정.

모델: y(t) = a + b*exp(-t/tau)   (Kelvin-Voigt류 1차 완화)
"""

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

import common


def relax(t, a, b, tau):
    return a + b * np.exp(-t / tau)


def fit_one(t, y):
    a0 = y[-1]
    b0 = y[0] - y[-1]
    tau0 = max(t[-1] / 3, 0.05)
    try:
        popt, _ = curve_fit(relax, t, y, p0=[a0, b0, tau0],
                             bounds=([-np.inf, -np.inf, 0.01], [np.inf, np.inf, 10.0]),
                             maxfev=5000)
        pred = relax(t, *popt)
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        return popt[2], r2
    except Exception:
        return None, None


def main():
    df = common.load_raw()
    df = common.add_labels(df)

    rows = []
    for cid, g in df.groupby("cycle_id"):
        press = g[g.phase == "pressure"].sort_values("t_s")
        if len(press) < 30:
            continue
        dwell = press[press.z_mm <= press.z_mm.min() + 0.02]
        if len(dwell) < 15:
            continue
        t = dwell["t_s"].values - dwell["t_s"].values[0]
        for col in ("dL_pct", "dR_pct"):
            y = dwell[col].values
            tau, r2 = fit_one(t, y)
            if tau is not None:
                rows.append(dict(cycle=cid, channel=col, tau=tau, r2=r2, n=len(dwell),
                                  dwell_duration=t[-1]))

    res = pd.DataFrame(rows)
    print(f"피팅된 cycle x channel: {len(res)}개")
    print(res.groupby("channel")[["tau", "r2", "dwell_duration"]].describe().T)

    # 피팅 신뢰도(R2) 높은 것들만으로 대표 tau 산출
    good = res[res.r2 > 0.3]
    print(f"\nR2>0.3 인 신뢰할 만한 피팅: {len(good)}/{len(res)}")
    print(good.groupby("channel")["tau"].agg(["median", "mean", "std"]))

    tau_L = good[good.channel == "dL_pct"]["tau"].median()
    tau_R = good[good.channel == "dR_pct"]["tau"].median()
    tau_overall = good["tau"].median()
    print(f"\n=== 추정된 시간상수 ===")
    print(f"tau_L (median) = {tau_L:.3f} s")
    print(f"tau_R (median) = {tau_R:.3f} s")
    print(f"tau_overall (median) = {tau_overall:.3f} s")
    print(f"(참고: dwell 평균 길이 = {res.dwell_duration.mean():.3f} s -- 이보다 짧으면 완화가 다 안 끝났을 수 있음)")

    with open("tau_fit_result.txt", "w", encoding="utf-8") as f:
        f.write(f"tau_L={tau_L:.4f}\ntau_R={tau_R:.4f}\ntau_overall={tau_overall:.4f}\n")


if __name__ == "__main__":
    main()
