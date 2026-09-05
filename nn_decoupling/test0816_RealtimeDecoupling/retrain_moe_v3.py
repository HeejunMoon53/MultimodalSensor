"""
retrain_moe_v3.py
0819 sync 버그 수정(+STM32 500Hz->100Hz 데시메이션) 이후 재수집한 데이터
(moe_monitor_20260819_141013.csv)로 게이트+2-expert(MoE, 후보2 구조) 재학습.

retrain_moe_v2.py와 거의 동일한 파이프라인이지만 이번 세션은 Z-축 영점 규약이
다르다 — ZERO를 접촉 지점 자체에서 잡아서 Z_mm=0이 접촉, Z_mm>0이 원거리(최대
25mm)다(0817 데이터의 "25mm 앞에서 영점" 규약과 다름). 접촉 판정 임계값은
Force_N 실측으로 재확인함(Z=-0.2~0mm에서 힘이 baseline 근처로 복귀).

학습 데이터 라벨은 보드가 실시간에 자체 판단한 strain_pct/value/mode/gate_proba를
전혀 쓰지 않는다 — YA_mm 기반 strain_act_pct, Z_mm, Fz_act_N 같은 ground truth만
정답으로 쓴다.

실행: C:/ml_env/Scripts/python nn_decoupling/test0816_RealtimeDecoupling/retrain_moe_v3.py
"""
import sys
import json
import pickle
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
import onnxruntime as ort

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
CSV_PATH = HERE / "moe_monitor_20260819_141013.csv"
OUT_DIR = HERE / "stm32_deploy_moe_v3"
OUT_DIR.mkdir(exist_ok=True)

STEDGEAI = r"C:\ai\xe\stedgeai.exe"

TAU_OVERALL_S = 1.0125
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN_EXPERT = (24, 16, 8)
HIDDEN_GATE = (8, 4)
SEED = 0
TEST_EVERY_N = 5
WINDOW_S = 10.0

# 이번 세션 Z-축 규약: ZERO가 접촉 지점 자체 (0817의 "25mm 앞에서 영점"과 다름)
CONTACT_THRESHOLD_MM = -0.2   # Force_N 실측으로 확인 (Z<=-0.2에서 힘이 유의미하게 커짐)


def r2(y, p):
    y, p = np.asarray(y), np.asarray(p)
    sstot = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / sstot) if sstot > 0 else float("nan")


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


# ── 1) 데이터 로드 + 정리 ────────────────────────────────────────────────────
print("[1] Loading + cleaning data...")
df = pd.read_csv(CSV_PATH)
n0 = len(df)
df = df[df["mode"].isin([0, 1])].reset_index(drop=True)
print(f"  {n0} -> {len(df)} rows after dropping corrupted-mode rows ({n0-len(df)} removed)")

n_before_outlier = len(df)
value_ok = np.where(df["mode"] == 1, df["value"].between(-20, 20), df["value"].between(-20, 30))
clean_mask = (
    df["gate_proba"].between(0, 1)
    & (df["dL_pct"].abs() < 50) & (df["dR_pct"].abs() < 50)
    & (df["dV_pct"].abs() < 200)
    & df["strain_pct"].between(-5, 35)
    & value_ok
)
df = df[clean_mask].reset_index(drop=True)
print(f"  {n_before_outlier} -> {len(df)} rows after dropping UART-corrupted rows "
      f"({n_before_outlier-len(df)} removed)")

df["strain_pct"] = df["strain_act_pct"]

# 이번 세션: Z_mm=0이 접촉, Z_mm>0이 원거리 (오프셋 없음)
df["dist_mm"] = df["Z_mm"]
df["contact"] = (df["Z_mm"] <= CONTACT_THRESHOLD_MM).astype(int)

force_offset = df.loc[df["contact"] == 0, "Fz_act_N"].mean()
df["Force_N"] = -(df["Fz_act_N"] - force_offset)
print(f"  Force_N residual offset removed: {force_offset:+.4f}N (부호 반전 적용) "
      f"(범위 {df['Force_N'].min():.2f}..{df['Force_N'].max():.2f}N)")
print(f"  contact=1 rows: {int(df['contact'].sum())} / {len(df)} "
      f"({100*df['contact'].mean():.1f}%)")

phase_changed = (df["contact"] != df["contact"].shift(1)).fillna(True)
df["segment_id"] = phase_changed.cumsum() - 1
print(f"  segments: {df['segment_id'].nunique()}")

df["cycle_id"] = (df["t_s"] // WINDOW_S).astype(int)

# ── 2) 인과적 EMA 피처 ───────────────────────────────────────────────────────
print("[2] Adding causal EMA features (halflife={:.3f}s)...".format(EMA_HALFLIFE_S))
ema_L = np.zeros(len(df))
ema_R = np.zeros(len(df))
for _, g in df.groupby("segment_id"):
    idx = g.index
    times = pd.to_datetime(g["t_s"].values, unit="s")
    ema_L[idx] = (pd.Series(g["dL_pct"].values, index=times)
                  .ewm(halflife=pd.Timedelta(seconds=EMA_HALFLIFE_S), times=times).mean().values)
    ema_R[idx] = (pd.Series(g["dR_pct"].values, index=times)
                  .ewm(halflife=pd.Timedelta(seconds=EMA_HALFLIFE_S), times=times).mean().values)
df["dL_ema"] = ema_L
df["dR_ema"] = ema_R

gate_cols = ["dL_pct", "dR_pct"]
feature_cols = ["dL_pct", "dR_pct", "dL_ema", "dR_ema"]

# ── 3) train/test 분리 ────────────────────────────────────────────────────
cycles = sorted(df["cycle_id"].unique())
test_ids = set(cycles[TEST_EVERY_N - 1::TEST_EVERY_N])
train_df = df[~df["cycle_id"].isin(test_ids)].copy()
test_df = df[df["cycle_id"].isin(test_ids)].copy()
print(f"[3] Split: {len(cycles)} time-windows({WINDOW_S}s) -> "
      f"train={len(train_df)} test={len(test_df)}")

# ── 4) 게이트 ─────────────────────────────────────────────────────────────
print("[4] Training gate (2-input, no EMA)...")
sc_gate = StandardScaler().fit(train_df[gate_cols].values)
gate = MLPClassifier(hidden_layer_sizes=HIDDEN_GATE, activation="tanh", solver="adam",
                      max_iter=3000, random_state=SEED, early_stopping=True, n_iter_no_change=30)
gate.fit(sc_gate.transform(train_df[gate_cols].values), train_df["contact"].values)
gate_pred = gate.predict(sc_gate.transform(test_df[gate_cols].values))
gate_acc = float((gate_pred == test_df["contact"].values).mean())
gate_f1 = float(f1_score(test_df["contact"].values, gate_pred))
print(f"  gate test acc={gate_acc:.4f}  f1={gate_f1:.4f}")

# ── 5) Expert A: proximity ────────────────────────────────────────────────
print("[5] Training expert_a (proximity)...")
tr_a = train_df[train_df["contact"] == 0]
te_a = test_df[test_df["contact"] == 0]
sc_a = StandardScaler().fit(tr_a[feature_cols].values)
expert_a = MLPRegressor(hidden_layer_sizes=HIDDEN_EXPERT, activation="tanh", solver="adam",
                         max_iter=4000, random_state=SEED, early_stopping=True, n_iter_no_change=40)
expert_a.fit(sc_a.transform(tr_a[feature_cols].values), tr_a[["strain_pct", "dist_mm"]].values)
pred_a = expert_a.predict(sc_a.transform(te_a[feature_cols].values))
r2_a_strain = r2(te_a["strain_pct"].values, pred_a[:, 0])
r2_a_dist = r2(te_a["dist_mm"].values, pred_a[:, 1])
print(f"  n_train={len(tr_a)} n_test={len(te_a)}")
print(f"  expert_a strain R2={r2_a_strain:.4f} RMSE={rmse(te_a['strain_pct'],pred_a[:,0]):.3f}%p | "
      f"dist R2={r2_a_dist:.4f} RMSE={rmse(te_a['dist_mm'],pred_a[:,1]):.3f}mm")

# ── 6) Expert B: pressure ─────────────────────────────────────────────────
print("[6] Training expert_b (pressure)...")
tr_b = train_df[train_df["contact"] == 1]
te_b = test_df[test_df["contact"] == 1]
print(f"  n_train={len(tr_b)} n_test={len(te_b)}")
sc_b = StandardScaler().fit(tr_b[feature_cols].values)
expert_b = MLPRegressor(hidden_layer_sizes=HIDDEN_EXPERT, activation="tanh", solver="adam",
                         max_iter=4000, random_state=SEED, early_stopping=True, n_iter_no_change=40)
expert_b.fit(sc_b.transform(tr_b[feature_cols].values), tr_b[["strain_pct", "Force_N"]].values)
pred_b = expert_b.predict(sc_b.transform(te_b[feature_cols].values))
r2_b_strain = r2(te_b["strain_pct"].values, pred_b[:, 0])
r2_b_force = r2(te_b["Force_N"].values, pred_b[:, 1])
print(f"  expert_b strain R2={r2_b_strain:.4f} RMSE={rmse(te_b['strain_pct'],pred_b[:,0]):.3f}%p | "
      f"force R2={r2_b_force:.4f} RMSE={rmse(te_b['Force_N'],pred_b[:,1]):.3f}N")

# ── 7) End-to-end ─────────────────────────────────────────────────────────
Xg_test = sc_gate.transform(test_df[gate_cols].values)
gate_route = gate.predict(Xg_test)
Xf_test = test_df[feature_cols].values
strain_pred = np.where(
    gate_route == 0,
    expert_a.predict(sc_a.transform(Xf_test))[:, 0],
    expert_b.predict(sc_b.transform(Xf_test))[:, 0],
)
r2_e2e_strain = r2(test_df["strain_pct"].values, strain_pred)
print(f"[7] End-to-end strain (게이트 라우팅 포함) R2={r2_e2e_strain:.4f}")

results = dict(
    n_rows=len(df), n_train=len(train_df), n_test=len(test_df),
    gate=dict(acc=gate_acc, f1=gate_f1),
    expert_a=dict(strain_r2=r2_a_strain, dist_r2=r2_a_dist,
                  strain_rmse=rmse(te_a['strain_pct'],pred_a[:,0]), dist_rmse=rmse(te_a['dist_mm'],pred_a[:,1])),
    expert_b=dict(strain_r2=r2_b_strain, force_r2=r2_b_force,
                  strain_rmse=rmse(te_b['strain_pct'],pred_b[:,0]), force_rmse=rmse(te_b['Force_N'],pred_b[:,1])),
    end_to_end_strain_r2=r2_e2e_strain,
    force_offset_removed=float(force_offset),
    ema_halflife_s=EMA_HALFLIFE_S,
    contact_threshold_mm=CONTACT_THRESHOLD_MM,
)
with open(OUT_DIR / "train_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(json.dumps(results, indent=2))

with open(OUT_DIR / "models.pkl", "wb") as f:
    pickle.dump(dict(gate=gate, expert_a=expert_a, expert_b=expert_b,
                      sc_gate=sc_gate, sc_a=sc_a, sc_b=sc_b,
                      gate_cols=gate_cols, feature_cols=feature_cols,
                      force_offset=force_offset), f)

# ── 8) ONNX 변환 ─────────────────────────────────────────────────────────────
print("\n[8] Converting to ONNX float32...")
onnx_gate = convert_sklearn(
    gate, initial_types=[("x", FloatTensorType([None, 2]))], target_opset=17,
    options={id(gate): {"zipmap": False}},
)
onnx_a = convert_sklearn(expert_a, initial_types=[("x", FloatTensorType([None, 4]))], target_opset=17)
onnx_b = convert_sklearn(expert_b, initial_types=[("x", FloatTensorType([None, 4]))], target_opset=17)

paths = {"gate": OUT_DIR / "gate.onnx", "expert_a": OUT_DIR / "expert_a.onnx", "expert_b": OUT_DIR / "expert_b.onnx"}
onnx.save(onnx_gate, str(paths["gate"]))
onnx.save(onnx_a, str(paths["expert_a"]))
onnx.save(onnx_b, str(paths["expert_b"]))
for name, p in paths.items():
    print(f"  {p.name:16s} {p.stat().st_size:,} B")

# ── 9) onnxruntime 수치 검증 ──────────────────────────────────────────────────
print("\n[9] Validating ONNX vs sklearn...")
rng = np.random.default_rng(42)
X_raw = np.column_stack([
    rng.uniform(-40, 20, 200), rng.uniform(0, 45, 200),
    rng.uniform(-40, 20, 200), rng.uniform(0, 45, 200),
]).astype(np.float32)

sess_gate = ort.InferenceSession(str(paths["gate"]))
sess_a = ort.InferenceSession(str(paths["expert_a"]))
sess_b = ort.InferenceSession(str(paths["expert_b"]))

Xg = sc_gate.transform(X_raw[:, :2]).astype(np.float32)
sk_gate_proba = gate.predict_proba(Xg)[:, 1]
on_gate_out = sess_gate.run(None, {"x": Xg})
on_gate_proba = on_gate_out[1][:, 1] if on_gate_out[1].ndim == 2 else on_gate_out[1].reshape(-1)
print(f"  gate  |sklearn-onnx| proba max err = {np.max(np.abs(sk_gate_proba - on_gate_proba)):.6f}")

Xa = sc_a.transform(X_raw).astype(np.float32)
sk_a = expert_a.predict(Xa)
on_a = sess_a.run(None, {"x": Xa})[0].reshape(sk_a.shape)
print(f"  expert_a |sklearn-onnx| max err = {np.max(np.abs(sk_a - on_a)):.6f}")

Xb = sc_b.transform(X_raw).astype(np.float32)
sk_b = expert_b.predict(Xb)
on_b = sess_b.run(None, {"x": Xb})[0].reshape(sk_b.shape)
print(f"  expert_b |sklearn-onnx| max err = {np.max(np.abs(sk_b - on_b)):.6f}")

# ── 10) stedgeai: ONNX -> STM32 C 코드 ────────────────────────────────────────
print("\n[10] Running stedgeai generate...")
for name, model_path in paths.items():
    cmd = [STEDGEAI, "generate", "--target", "stm32", "--name", name,
           "--model", str(model_path), "--compression", "none", "--quantize", "int8",
           "--output", str(OUT_DIR), "--workspace", str(OUT_DIR / "workspace")]
    print(f"  > generate {name} (int8) ...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("    int8 실패, float32로 재시도...")
        cmd2 = [STEDGEAI, "generate", "--target", "stm32", "--name", name,
                "--model", str(model_path), "--output", str(OUT_DIR)]
        r = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"    returncode={r.returncode}")
    if r.returncode != 0:
        print("    STDOUT tail:", r.stdout[-1500:] if r.stdout else "")
        print("    STDERR tail:", r.stderr[-1500:] if r.stderr else "")

print("\n[11] Generated files:")
for f in sorted(OUT_DIR.glob("*.c")) + sorted(OUT_DIR.glob("*.h")):
    print(f"  {f.name:40s} {f.stat().st_size:>8,} B")

print(f"\nDone. Output dir: {OUT_DIR}")
print("펌웨어에 실제로 얹으려면 별도로 백업 후 복사하세요.")
