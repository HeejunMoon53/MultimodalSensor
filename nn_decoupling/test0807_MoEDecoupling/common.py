"""
common.py
MoE(Mixture-of-Experts) 디커플링 후보 구조들이 공유하는 데이터 로드/피처/평가 유틸.

두 CSV(mms_20260805_172956.csv, mms_20260806_200653.csv)를 합쳐서 사용.
실배포 시 사용 가능한 입력은 오직 (dL_pct, dR_pct)와 그로부터 계산 가능한
인과적(causal) 이력 피처뿐 — z_mm, Force_N, strain_pct는 정답(label)로만 사용.

용어:
  phase       : "proximity"(비접촉, z_mm>=0) / "pressure"(접촉, z_mm<0)
  segment_id  : phase가 바뀔 때마다 새 구간
  cycle_id    : strain 스텝이 바뀔 때마다 새 사이클 (근접+압력 전체 1회 스윕)
  contact     : phase=="pressure"이면 1, 아니면 0  (게이트 정답 레이블)
"""

import glob
import os

import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "pressure_0805test", "test0805_dataset")
OUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

SENSOR_L0 = 120.0
MIN_SEGMENT_LEN = 30
MIN_CYCLE_LEN = 500
TEST_EVERY_N = 5           # 사이클 5개 중 1개를 held-out 테스트로 (파일별로 적용)

DEFAULT_EMA_HALFLIFE_S = 0.3   # τ 피팅 전 기본값 (fit_relaxation_tau.py가 더 정확한 값을 구함)

FEATURE_COLS_BASE = ["dL_pct", "dR_pct"]


# ── 1. 원본 데이터 로드 ───────────────────────────────────────────────────────

def load_raw():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "mms_*.csv")))
    if not files:
        raise FileNotFoundError(f"'{DATA_DIR}' 안에서 mms_*.csv를 찾을 수 없습니다.")
    # mms_20260805는 힘 범위가 좁고(0~4N) dwell이 짧아 데이터 품질이 낮아 학습에서 제외.
    # mms_20260806(힘 범위 0~10.1N, 긴 dwell)만 사용.
    files = [f for f in files if "20260805" not in os.path.basename(f)]
    if not files:
        raise FileNotFoundError(f"'{DATA_DIR}' 안에서 mms_20260806*.csv를 찾을 수 없습니다.")
    dfs = []
    for i, f in enumerate(files):
        d = pd.read_csv(f)
        d["file_id"] = i   # 파일별로 cycle_id가 겹치지 않도록 구분자
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)
    print(f"[load] {len(files)}개 파일: {[os.path.basename(f) for f in files]}  총 {len(df)}행")

    df["Force_N"] = -df["Fz_N"]
    df["strain_pct"] = (df["ya_mm"] + df["yb_mm"]) / SENSOR_L0 * 100.0

    # F/T 센서가 파일마다(세션마다) 살짝 다르게 영점이 안 맞아 있어서(taring 안 됨),
    # 비접촉 구간(z_mm>=0, 실제로 아무것도 안 닿아 있어야 하는 구간)의 평균이 0이 아니었다.
    # 파일별로 그 오프셋을 구해서 빼준다 (Fz_N 원본이 아니라 유도된 Force_N에만 적용).
    for fid, idx in df.groupby("file_id").groups.items():
        sub = df.loc[idx]
        offset = sub.loc[sub["z_mm"] >= 0, "Force_N"].mean()
        df.loc[idx, "Force_N"] = sub["Force_N"] - offset
        print(f"[tare] file_id={fid}: Force_N 오프셋 {offset:+.4f}N 보정")
    return df


# ── 2. phase / segment / cycle 라벨링 ────────────────────────────────────────

def add_labels(df):
    df = df.copy()
    phase = np.where(df["z_mm"].values >= 0, "proximity", "pressure")
    df["phase"] = phase
    df["contact"] = (phase == "pressure").astype(int)

    # segment_id, cycle_id는 file_id 안에서만 유효하므로 file별로 계산 후 전역 오프셋 부여
    seg_ids = np.zeros(len(df), dtype=np.int64)
    cyc_ids = np.zeros(len(df), dtype=np.int64)
    seg_offset = 0
    cyc_offset = 0
    for fid, idx in df.groupby("file_id").groups.items():
        idx = np.asarray(idx)
        sub_phase = df.loc[idx, "phase"].values
        s = (sub_phase != np.roll(sub_phase, 1)).cumsum()
        s[0] = 0
        seg_ids[idx] = s + seg_offset
        seg_offset += s.max() + 1

        sub_strain = df.loc[idx, "strain_pct"].round(3).values
        c = (sub_strain != np.roll(sub_strain, 1)).cumsum()
        c[0] = 0
        cyc_ids[idx] = c + cyc_offset
        cyc_offset += c.max() + 1

    df["segment_id"] = seg_ids
    df["cycle_id"] = cyc_ids
    return df


# ── 3. 인과적(causal) EMA 이력 피처 ──────────────────────────────────────────

def add_ema_features(df, halflife_s=DEFAULT_EMA_HALFLIFE_S, suffix=""):
    """segment_id별로 causal EMA(halflife=halflife_s)를 dL_pct/dR_pct에 적용.
    suffix를 주면 여러 시간상수를 동시에 붙일 수 있음 (candidate 5용)."""
    df = df.copy()
    col_L, col_R = f"dL_ema{suffix}", f"dR_ema{suffix}"
    ema_L, ema_R = np.zeros(len(df)), np.zeros(len(df))
    for _, g in df.groupby("segment_id"):
        idx = g.index
        times = pd.to_datetime(g["t_s"].values, unit="s")
        ema_L[idx] = (pd.Series(g["dL_pct"].values, index=times)
                      .ewm(halflife=pd.Timedelta(seconds=halflife_s), times=times).mean().values)
        ema_R[idx] = (pd.Series(g["dR_pct"].values, index=times)
                      .ewm(halflife=pd.Timedelta(seconds=halflife_s), times=times).mean().values)
    df[col_L] = ema_L
    df[col_R] = ema_R
    return df, [col_L, col_R]


# ── 4. train/test 분리 (사이클 단위, 파일 섞어서) ────────────────────────────

def split_by_cycle(df, min_len=MIN_CYCLE_LEN, test_every_n=TEST_EVERY_N, seed=0):
    sizes = df.groupby("cycle_id").size()
    real_cycles = sorted(sizes[sizes >= min_len].index.tolist())
    test_ids = set(real_cycles[test_every_n - 1::test_every_n])
    train_ids = set(real_cycles) - test_ids
    train_df = df[df.cycle_id.isin(train_ids)].copy()
    test_df = df[df.cycle_id.isin(test_ids)].copy()
    print(f"[split] cycles total={len(real_cycles)}  train={len(train_ids)}  test={sorted(test_ids)}")
    return train_df, test_df


# ── 5. 평가 유틸 ──────────────────────────────────────────────────────────────

def regression_metrics(y_true, y_pred):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    return dict(
        rmse=float(np.sqrt(mean_squared_error(y_true, y_pred))),
        mae=float(mean_absolute_error(y_true, y_pred)),
        r2=float(r2_score(y_true, y_pred)),
    )


def classification_metrics(y_true, y_pred):
    from sklearn.metrics import accuracy_score, f1_score
    return dict(
        acc=float(accuracy_score(y_true, y_pred)),
        f1=float(f1_score(y_true, y_pred)),
    )


RESULTS_JSON = os.path.join(OUT_DIR, "all_candidates_results.json")


def save_result(candidate_name, result_dict):
    import json
    all_results = {}
    if os.path.exists(RESULTS_JSON):
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            all_results = json.load(f)
    all_results[candidate_name] = result_dict
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"[save_result] {candidate_name} -> {RESULTS_JSON}")
