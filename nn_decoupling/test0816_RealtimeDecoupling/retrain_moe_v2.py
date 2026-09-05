"""
retrain_moe_v2.py
0817 새로 수집한 데이터(moe_monitor_20260817_002534.csv, realtime_train_seq2.txt로
수집)로 게이트+2-expert(MoE, 후보2 구조) 모델을 재학습하고 ONNX -> STM32 C 코드까지
생성한다.

기존 nn_decoupling/stm32_deploy_moe/ 와 TDMFirmware/X-CUBE-AI/App/ 은 이 스크립트가
직접 건드리지 않는다 — 전부 이 폴더(test0816_RealtimeDecoupling) 안의
stm32_deploy_moe_v2/ 에서만 작업해서, 마음에 안 들면 그냥 이 폴더를 무시하면
바로 이전 상태로 돌아갈 수 있다. (펌웨어에 실제로 얹는 건 별도 copy_to_firmware.py에서
명시적으로 백업까지 하고 진행한다.)

학습 데이터 라벨은 보드가 실시간에 자체 판단한 strain_pct/value/mode/gate_proba를
전혀 쓰지 않는다 — YA_mm 기반 strain_act_pct, Z_mm, Fz_act_N 같은 ground truth만
정답으로 쓴다.

실행: C:/ml_env/Scripts/python nn_decoupling/test0816_RealtimeDecoupling/retrain_moe_v2.py
"""
import sys
import json
import pickle
import subprocess
import shutil
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
CSV_PATH = HERE / "moe_monitor_20260817_002534.csv"
OUT_DIR = HERE / "stm32_deploy_moe_v2"
OUT_DIR.mkdir(exist_ok=True)

STEDGEAI = r"C:\ai\xe\stedgeai.exe"

SENSOR_L0 = 120.0
TAU_OVERALL_S = 1.0125                       # 기존 배포 모델과 동일 시간상수 유지
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN_EXPERT = (24, 16, 8)
HIDDEN_GATE = (8, 4)
SEED = 0
TEST_EVERY_N = 5
WINDOW_S = 10.0    # held-out 분리 단위 — 이 데이터는 strain 스텝 기반 cycle_id 대신
                   # 시간 윈도우로 자른다 (Block2는 strain이 연속으로 스윕돼서
                   # common.py식 "strain 값 바뀔 때마다 새 cycle" 정의가 안 맞음)


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
df = df[df["mode"].isin([0, 1])].reset_index(drop=True)   # UART 손상 행 제거
print(f"  {n0} -> {len(df)} rows after dropping corrupted-mode rows ({n0-len(df)} removed)")

# 극단 이상치(UART 손상 행) 제거 — 저항 IIR 필터를 뺀 뒤로 dR_pct가 raw라 UART
# 손상/ADC 글리치가 그대로 남는다. dR_pct=49826, strain_pct=260, value=83790,
# gate_proba=595 같은 튐이 발견됐다 — mode 필드만으로는 다 못 거른다(mode는 멀쩡한데
# 다른 필드가 깨진 행이 있음). gate_proba는 확률이라 [0,1] 밖이면 무조건 손상이고,
# 나머지는 물리적으로 불가능한 범위로 거른다.
# value 범위는 mode별로 다르게 건다 — press(mode=1)의 실제 힘은 FORCE 클램프상
# 대략 -14~14N 범위인데 value=+21 같은 튐이 남아있었다(부호/모드가 뒤집힌 값이라
# 나머지 press 값들과 크기·부호가 확연히 다름). prox(mode=0)는 거리(0~27mm)라
# 위쪽 여유를 더 둔다.
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

df["strain_pct"] = df["strain_act_pct"]     # 이미 YA/YB 기준으로 정확히 계산돼 기록됨

# 이번 세션은 ZERO를 "물체에서 25mm 떨어진 위치(far)"에서 잡았다 — 즉 기록된 Z_mm은
# far 기준 상대값이고, 실제 접촉은 Z_mm이 약 -25 부근에 도달했을 때 일어난다
# (Force_N이 Z_mm<=-24.5에서만 유의미하게 커지는 것으로 실측 확인됨: 그 이상 구간은
# 전부 평균 힘이 0에 가까움). 이전(0816) 데이터셋은 ZERO를 접촉 지점에서 잡아서
# Z_mm 자체가 곧 "접촉까지 남은 거리"였는데, 이번엔 그 관계가 25mm만큼 밀려있다.
Z_FAR_OFFSET_MM = 25.0
CONTACT_THRESHOLD_MM = -24.5   # 약간의 여유를 둔 접촉 판정 기준
df["dist_mm"] = df["Z_mm"] + Z_FAR_OFFSET_MM     # 0=접촉, 25=최대 근접거리(원거리)
df["contact"] = (df["Z_mm"] <= CONTACT_THRESHOLD_MM).astype(int)

# 힘 오프셋 잔차 보정 — TARE_FZ가 세션 시작 시 한 번 잡아주지만 그 이후 드리프트가
# 남아있을 수 있어 비접촉 구간 평균을 한 번 더 빼준다 (common.py와 동일 아이디어)
# 부호 반전: RFT 원시값(Fz_act_N)은 이번 세션엔 누를수록 더 음수로 나왔다(이전
# 세션·구모델과 반대) — "누르면 힘이 양수로 커진다"는 직관적 규약으로 통일한다.
force_offset = df.loc[df["contact"] == 0, "Fz_act_N"].mean()
df["Force_N"] = -(df["Fz_act_N"] - force_offset)
print(f"  Force_N residual offset removed: {force_offset:+.4f}N (부호 반전 적용) "
      f"(범위 {df['Force_N'].min():.2f}..{df['Force_N'].max():.2f}N)")
print(f"  contact=1 rows: {int(df['contact'].sum())} / {len(df)} "
      f"({100*df['contact'].mean():.1f}%)")

# segment_id: 접촉/비접촉 전환마다 새 구간 (EMA 리셋 경계, common.py와 동일 규칙)
phase_changed = (df["contact"] != df["contact"].shift(1)).fillna(True)
df["segment_id"] = phase_changed.cumsum() - 1
print(f"  segments: {df['segment_id'].nunique()}")

# cycle_id: 시간 윈도우 기준 held-out 분리용
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

# ── 3) train/test 분리 (시간 윈도우 5개 중 1개 held-out) ──────────────────────
cycles = sorted(df["cycle_id"].unique())
test_ids = set(cycles[TEST_EVERY_N - 1::TEST_EVERY_N])
train_df = df[~df["cycle_id"].isin(test_ids)].copy()
test_df = df[df["cycle_id"].isin(test_ids)].copy()
print(f"[3] Split: {len(cycles)} time-windows({WINDOW_S}s) -> "
      f"train={len(train_df)} test={len(test_df)}")

# ── 4) 게이트 (2-input, EMA 없음 — 실기 검증으로 확정된 구조 유지) ────────────
print("[4] Training gate (2-input, no EMA)...")
sc_gate = StandardScaler().fit(train_df[gate_cols].values)
gate = MLPClassifier(hidden_layer_sizes=HIDDEN_GATE, activation="tanh", solver="adam",
                      max_iter=3000, random_state=SEED, early_stopping=True, n_iter_no_change=30)
gate.fit(sc_gate.transform(train_df[gate_cols].values), train_df["contact"].values)
gate_pred = gate.predict(sc_gate.transform(test_df[gate_cols].values))
gate_acc = float((gate_pred == test_df["contact"].values).mean())
gate_f1 = float(f1_score(test_df["contact"].values, gate_pred))
print(f"  gate test acc={gate_acc:.4f}  f1={gate_f1:.4f}")

# ── 5) Expert A: proximity (strain, dist_mm — 0=접촉, 25=원거리) ─────────────
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

# ── 6) Expert B: pressure (strain, Force_N) ──────────────────────────────────
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

# ── 7) End-to-end (학습된 게이트로 라우팅) ────────────────────────────────────
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
    z_far_offset_mm=Z_FAR_OFFSET_MM,
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
print("펌웨어에 실제로 얹으려면 copy_to_firmware.py를 따로 실행하세요 (백업 후 복사).")
