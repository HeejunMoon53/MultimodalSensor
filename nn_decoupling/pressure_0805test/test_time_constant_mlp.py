"""
test_time_constant_mlp.py
"그냥 한 거" vs "시간상수(EMA) 넣은 거" 두 MLP를 간단 비교 (테스트용).

배경: 압력(pressure) 구간에서 dwell(깊이 고정) 중 dL/dR이 계속 드리프트하고,
released 후에는 거의 원위치로 돌아오는 가역적 점탄성 완화(relaxation)가 확인됨.
이게 로딩/언로딩 경로 차이(히스테리시스)의 원인.

비교:
  Model A (baseline)     : X = [dL_pct, dR_pct]                    -> Force_N
  Model B (time-constant) : X = [dL_pct, dR_pct, dL_ema, dR_ema]    -> Force_N
    dL_ema/dR_ema = 각 press 구간 내에서 halflife=0.3s로 지수이동평균
    (= 최근 로딩 이력을 담은 "완화 상태" 프록시. 실배포 시에도 dL/dR만으로 계산 가능)

주의: 이 환경에서 torch가 DLL 로드 실패라 sklearn.MLPRegressor로 대체
      (model.py의 SinglePINNMLP와 동일하게 hidden=(24,16,8), tanh).
"""

import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_FORCE = "#1F77B4"
COLOR_BASELINE = "#1F77B4"  # 파랑 (CLAUDE.md 색상 컨벤션의 Force/TENG 파랑 재사용)
COLOR_TC = "#D62728"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "test0805_dataset")
OUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

SENSOR_L0 = 120.0
MIN_SEGMENT_LEN = 30
EMA_HALFLIFE_S = 0.702   # fit_relaxation_tau.py 결과(tau=1.0125s, mms_20260806 only) 기반
TEST_EVERY_N = 5       # segment 5개 중 1개를 테스트로 사용 (변형률 범위 골고루 섞이도록)
HIDDEN = (24, 16, 8)   # model.py SinglePINNMLP와 동일 스펙


def load_pressure_data():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "mms_*.csv")))
    # mms_20260805는 힘 범위가 좁고(0~4N) dwell이 짧아 데이터 품질이 낮아 학습에서 제외.
    files = [f for f in files if "20260805" not in os.path.basename(f)]
    dfs = []
    for f in files:
        d = pd.read_csv(f)
        d["Force_N"] = -d["Fz_N"]
        # F/T 센서 세션별 영점 오프셋 보정 (비접촉 구간 평균을 0으로)
        offset = d.loc[d["z_mm"] >= 0, "Force_N"].mean()
        d["Force_N"] = d["Force_N"] - offset
        print(f"[tare] {os.path.basename(f)}: Force_N 오프셋 {offset:+.4f}N 보정")
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)
    df["strain_pct"] = (df["ya_mm"] + df["yb_mm"]) / SENSOR_L0 * 100.0

    phase = np.where(df["z_mm"].values >= 0, "proximity", "pressure")
    seg_id = (phase != np.roll(phase, 1)).cumsum()
    seg_id[0] = 0
    df["phase"] = phase
    df["segment_id"] = seg_id

    press = df[df["phase"] == "pressure"].copy()

    # segment별 EMA (halflife 시간 기준, 불균등 샘플링 보정)
    ema_L, ema_R = [], []
    for _, g in press.groupby("segment_id"):
        times = pd.to_datetime(g["t_s"].values, unit="s")
        s = pd.Series(g["dL_pct"].values, index=times)
        ema_L.append(s.ewm(halflife=pd.Timedelta(seconds=EMA_HALFLIFE_S), times=times).mean().values)
        s = pd.Series(g["dR_pct"].values, index=times)
        ema_R.append(s.ewm(halflife=pd.Timedelta(seconds=EMA_HALFLIFE_S), times=times).mean().values)
    press["dL_ema"] = np.concatenate(ema_L)
    press["dR_ema"] = np.concatenate(ema_R)

    return press


def make_split(press):
    seg_ids = sorted(s for s, g in press.groupby("segment_id") if len(g) >= MIN_SEGMENT_LEN)
    test_ids = set(seg_ids[TEST_EVERY_N - 1::TEST_EVERY_N])
    train_ids = set(seg_ids) - test_ids
    print(f"[split] segments total={len(seg_ids)}  train={len(train_ids)}  test={sorted(test_ids)}")
    is_train = press["segment_id"].isin(train_ids) & press["segment_id"].isin(seg_ids)
    is_test = press["segment_id"].isin(test_ids)
    return press[is_train].copy(), press[is_test].copy(), sorted(test_ids)


def fit_and_eval(train_df, test_df, feature_cols, name):
    Xtr = train_df[feature_cols].values
    ytr = train_df["Force_N"].values
    Xte = test_df[feature_cols].values
    yte = test_df["Force_N"].values

    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN, activation="tanh",
                      solver="adam", max_iter=3000, random_state=0,
                      early_stopping=True, n_iter_no_change=30),
    )
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)

    rmse = np.sqrt(mean_squared_error(yte, pred))
    mae = mean_absolute_error(yte, pred)
    r2 = r2_score(yte, pred)
    print(f"[{name}] features={feature_cols}")
    print(f"   RMSE={rmse:.3f} N | MAE={mae:.3f} N | R2={r2:.4f}")
    return model, dict(rmse=rmse, mae=mae, r2=r2)


def plot_comparison(test_df, test_ids, model_a, model_b, feat_a, feat_b, metrics_a, metrics_b):
    # 최근(9N까지) 데이터를 보여주기 위해, held-out 구간 중 최대 힘이 가장 큰 세그먼트를 선택
    force_max_by_sid = test_df.groupby("segment_id")["Force_N"].max()
    sid = force_max_by_sid.loc[list(test_ids)].idxmax()
    g = test_df[test_df["segment_id"] == sid].reset_index(drop=True)
    t = g["t_s"].values - g["t_s"].values[0]

    pred_a = model_a.predict(g[feat_a].values)
    pred_b = model_b.predict(g[feat_b].values)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    ax = axes[0]
    ax.plot(t, g["Force_N"], color="black", linewidth=2.0, label="Actual (F/T sensor)")
    ax.plot(t, pred_a, color=COLOR_BASELINE, linewidth=1.4, linestyle="--",
            label=f"Model A: baseline (RMSE {metrics_a['rmse']:.2f}N)")
    ax.plot(t, pred_b, color=COLOR_TC, linewidth=1.4,
            label=f"Model B: +time-constant (RMSE {metrics_b['rmse']:.2f}N)")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Force [N]")
    ax.set_title(f"Held-out test segment (strain={g['strain_pct'].iloc[0]:.1f}%)")
    ax.legend(fontsize=9); ax.grid(alpha=0.25)

    # 로딩(누르는 중) vs 언로딩(떼는 중) 구간을 depth 기준으로 나눠서 히스테리시스 루프 비교
    ax = axes[1]
    imin = g["z_mm"].idxmin()
    ax.plot(g["z_mm"].iloc[:imin+1], g["Force_N"].iloc[:imin+1], color="black", linewidth=2.0, label="Actual: loading")
    ax.plot(g["z_mm"].iloc[imin:],   g["Force_N"].iloc[imin:],   color="black", linewidth=2.0, linestyle=":", label="Actual: release")
    ax.plot(g["z_mm"].iloc[:imin+1], pred_a[:imin+1], color=COLOR_BASELINE, linewidth=1.4, label="Model A: loading")
    ax.plot(g["z_mm"].iloc[imin:],   pred_a[imin:],   color=COLOR_BASELINE, linewidth=1.4, linestyle=":", label="Model A: release")
    ax.plot(g["z_mm"].iloc[:imin+1], pred_b[:imin+1], color=COLOR_TC, linewidth=1.4, label="Model B: loading")
    ax.plot(g["z_mm"].iloc[imin:],   pred_b[imin:],   color=COLOR_TC, linewidth=1.4, linestyle=":", label="Model B: release")
    ax.invert_xaxis()
    ax.set_xlabel("Depth z [mm] (0 -> -1.2mm)"); ax.set_ylabel("Force [N]")
    ax.set_title("Hysteresis loop: actual vs Model A vs Model B")
    ax.legend(fontsize=8); ax.grid(alpha=0.25)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "test_time_constant_mlp_comparison.png")
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")
    plt.close(fig)


def main():
    press = load_pressure_data()
    train_df, test_df, test_ids = make_split(press)

    feat_a = ["dL_pct", "dR_pct"]
    feat_b = ["dL_pct", "dR_pct", "dL_ema", "dR_ema"]

    model_a, metrics_a = fit_and_eval(train_df, test_df, feat_a, "Model A (baseline)")
    model_b, metrics_b = fit_and_eval(train_df, test_df, feat_b, "Model B (+time-constant EMA)")

    print()
    print("=== 요약 ===")
    print(f"Baseline        RMSE={metrics_a['rmse']:.3f}N  MAE={metrics_a['mae']:.3f}N  R2={metrics_a['r2']:.4f}")
    print(f"+time-constant  RMSE={metrics_b['rmse']:.3f}N  MAE={metrics_b['mae']:.3f}N  R2={metrics_b['r2']:.4f}")
    improve = (metrics_a['rmse'] - metrics_b['rmse']) / metrics_a['rmse'] * 100
    print(f"RMSE 개선: {improve:.1f}%")

    plot_comparison(test_df, test_ids, model_a, model_b, feat_a, feat_b, metrics_a, metrics_b)


if __name__ == "__main__":
    main()
