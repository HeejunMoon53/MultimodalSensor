"""
retrain_moe_v4.py
0909 저녁 재취득 데이터(214746 근접-변형률, 220210 압력-변형률, 222022 근접-변형률)로
게이트+2-expert(MoE) 재학습. retrain_moe_v3.py와 동일한 파이프라인/하이퍼파라미터를
그대로 따르되, 세 개의 세션 파일을 합쳐서 학습하고 이번 세션의 Z-축 규약(Z_mm=0 ->
실제 근접거리 24mm, prox_mm = Z_mm + 24)에 맞게 접촉 판정을 다시 잡는다.

학습 라벨은 보드가 실시간에 자체 판단한 값(strain_pct/value/mode/gate_proba)을 전혀
쓰지 않는다 — YA_mm 기반 strain_act_pct, Z_mm(-> prox_mm), Fz_act_N 같은 ground truth만
정답으로 쓴다 (retrain_moe_v3와 동일한 원칙).

압력 세션(220210)은 인장 >= 14% 구간에서 접촉 시 인덕턴스 saturation이 확인되었으므로
(사용자 확인), 접촉(contact=1) + strain_act_pct >= 14 인 행은 학습에서 제외한다.
비접촉 구간은 이 필터의 영향을 받지 않는다.

실행: C:/ml_env/Scripts/python nn_decoupling/test0909_realtime/new/retrain_moe_v4.py
"""
import sys
import json
import pickle
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
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
OUT_DIR = HERE / "stm32_deploy_moe_v4"
OUT_DIR.mkdir(exist_ok=True)

SESSIONS = {
    "214746": HERE / "moe_monitor_20260909_214746.csv",   # strain 연속 / proximity 이산
    "222022": HERE / "moe_monitor_20260909_222022.csv",    # strain 이산 / proximity 연속
    "220210": HERE / "moe_monitor_20260909_220210.csv",     # 압력 세션
}

STEDGEAI = r"C:\ai\xe\stedgeai.exe"

TAU_OVERALL_S = 1.0125
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN_EXPERT = (24, 16, 8)
HIDDEN_GATE = (8, 4)
SEED = 0
TEST_EVERY_N = 5
WINDOW_S = 10.0

PROX_OFFSET = 24.0            # Z_mm = 0 -> 실제 근접거리 24 mm
CONTACT_THRESHOLD_MM = 0.3    # prox_mm <= 0.3 이면 접촉 (Force_N 실측으로 확인)
SATURATION_STRAIN_PCT = 14.0  # 압력 시 인덕턴스 saturation 시작점 (사용자 확인)


def r2(y, p):
    y, p = np.asarray(y), np.asarray(p)
    sstot = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / sstot) if sstot > 0 else float("nan")


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


# ── 1) 데이터 로드 + 정리 (세션별로 로드 후 결합) ──────────────────────────────
print("[1] Loading + cleaning data...")
frames = []
for sid, path in SESSIONS.items():
    d = pd.read_csv(path)
    n0 = len(d)
    d = d[d["mode"].isin([0, 1])].reset_index(drop=True)
    value_ok = np.where(d["mode"] == 1, d["value"].between(-20, 20), d["value"].between(-20, 30))
    clean_mask = (
        d["gate_proba"].between(0, 1)
        & (d["dL_pct"].abs() < 50) & (d["dR_pct"].abs() < 50)
        & (d["dV_pct"].abs() < 200)
        & d["strain_act_pct"].between(-5, 35)
        & value_ok
    )
    d = d[clean_mask].reset_index(drop=True)
    d["session_id"] = sid
    print(f"  [{sid}] {n0} -> {len(d)} rows after cleaning")
    frames.append(d)

df = pd.concat(frames, ignore_index=True)
print(f"  combined: {len(df)} rows from {len(SESSIONS)} sessions")

df["strain_pct"] = df["strain_act_pct"]
df["prox_mm"] = df["Z_mm"] + PROX_OFFSET
df["dist_mm"] = df["prox_mm"]
df["contact"] = (df["prox_mm"] <= CONTACT_THRESHOLD_MM).astype(int)

force_offset = df.loc[df["contact"] == 0, "Fz_act_N"].mean()
df["Force_N"] = -(df["Fz_act_N"] - force_offset)
print(f"  Force_N residual offset removed: {force_offset:+.4f}N "
      f"(범위 {df['Force_N'].min():.2f}..{df['Force_N'].max():.2f}N)")
print(f"  contact=1 rows: {int(df['contact'].sum())} / {len(df)} "
      f"({100*df['contact'].mean():.1f}%)")

# 압력 saturation 구간 제외 (접촉 + strain>=14% 만)
sat_mask = (df["contact"] == 1) & (df["strain_pct"] >= SATURATION_STRAIN_PCT)
print(f"  excluding {int(sat_mask.sum())} contact rows with strain >= "
      f"{SATURATION_STRAIN_PCT}% (inductance saturation)")
df = df[~sat_mask].reset_index(drop=True)

# 세션 경계 + 접촉 상태 변화 둘 다에서 segment 분리 (EMA가 세션을 넘어 섞이지 않도록)
phase_changed = ((df["contact"] != df["contact"].shift(1))
                  | (df["session_id"] != df["session_id"].shift(1))).fillna(True)
df["segment_id"] = phase_changed.cumsum() - 1
print(f"  segments: {df['segment_id'].nunique()}")

df["cycle_id"] = df["session_id"] + "_" + (df["t_s"] // WINDOW_S).astype(int).astype(str)

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

# ── 3) train/test 분리 (10초 창 단위, 세션별로 매 5번째 창을 test로) ──────────
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
    sessions=list(SESSIONS.keys()),
    gate=dict(acc=gate_acc, f1=gate_f1),
    expert_a=dict(strain_r2=r2_a_strain, dist_r2=r2_a_dist,
                  strain_rmse=rmse(te_a['strain_pct'], pred_a[:, 0]),
                  dist_rmse=rmse(te_a['dist_mm'], pred_a[:, 1])),
    expert_b=dict(strain_r2=r2_b_strain, force_r2=r2_b_force,
                  strain_rmse=rmse(te_b['strain_pct'], pred_b[:, 0]),
                  force_rmse=rmse(te_b['Force_N'], pred_b[:, 1])),
    end_to_end_strain_r2=r2_e2e_strain,
    force_offset_removed=float(force_offset),
    ema_halflife_s=EMA_HALFLIFE_S,
    contact_threshold_mm=CONTACT_THRESHOLD_MM,
    saturation_strain_pct_excluded=SATURATION_STRAIN_PCT,
)
with open(OUT_DIR / "train_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(json.dumps(results, indent=2))

with open(OUT_DIR / "models.pkl", "wb") as f:
    pickle.dump(dict(gate=gate, expert_a=expert_a, expert_b=expert_b,
                      sc_gate=sc_gate, sc_a=sc_a, sc_b=sc_b,
                      gate_cols=gate_cols, feature_cols=feature_cols,
                      force_offset=force_offset), f)

# ── 7a) moe_params.h 생성 — TDMFirmware/Core/Inc/moe_params.h 와 정확히 같은 형식.
#        StandardScaler mean/scale은 gate.c/expert_a.c/expert_b.c 안에 들어있지
#        않고 moe_inference.c 에서 이 상수들로 직접 정규화하므로, 모델 .c/.h 만
#        교체하고 이 파일을 갱신하지 않으면 새 가중치에 옛 정규화가 적용되어
#        추론이 깨진다 — 반드시 같이 교체해야 한다.
MARGIN = 2.0
strain_lo, strain_hi = float(df["strain_pct"].min()) - MARGIN, float(df["strain_pct"].max()) + MARGIN
dist_lo, dist_hi = float(df.loc[df["contact"] == 0, "dist_mm"].min()) - MARGIN, \
    float(df.loc[df["contact"] == 0, "dist_mm"].max()) + MARGIN
force_lo, force_hi = float(df.loc[df["contact"] == 1, "Force_N"].min()) - MARGIN, \
    float(df.loc[df["contact"] == 1, "Force_N"].max()) + MARGIN

moe_params_h = f"""/* Auto-generated by retrain_moe_v4.py — do not edit by hand.
 * 게이트 + EMA 4-input MLP 배포 상수 — 0909 저녁 재취득본 (v4).
 * 데이터: {', '.join(str(p.name) for p in SESSIONS.values())} (정제/saturation 제외 후 {len(df)}행).
 *
 * v3 대비 바뀐 점:
 *   - 이번 세션 Z-축 규약: prox_mm = Z_mm + {PROX_OFFSET:g} (Z_mm=0 -> 실제 근접 {PROX_OFFSET:g}mm),
 *     접촉 판정은 prox_mm <= {CONTACT_THRESHOLD_MM:g}mm (Force_N 실측으로 확인).
 *   - 압력 세션에서 접촉 + strain >= {SATURATION_STRAIN_PCT:g}% (인덕턴스 saturation) 구간은
 *     학습에서 제외.
 *   - 오프라인 held-out 성능: gate acc {gate_acc:.4f} f1 {gate_f1:.4f} |
 *     strain R² {r2_a_strain:.4f}(A)/{r2_b_strain:.4f}(B) | dist R² {r2_a_dist:.4f} |
 *     force R² {r2_b_force:.4f} | end-to-end strain R² {r2_e2e_strain:.4f}
 *
 * [이전부터 유지] 게이트는 EMA 없이 원본 2-input(dL_pct, dR_pct)만 쓴다.
 * 전문가 A/B는 4-input(EMA 포함) 유지.
 */
#ifndef MOE_PARAMS_H
#define MOE_PARAMS_H

/* ─── 게이트 입력: [dL_pct, dR_pct] (EMA 없음) ────────────────────────────── */
/* ─── 전문가 A/B 입력: [dL_pct, dR_pct, dL_ema, dR_ema] ───────────────────── */

/* 게이트(접촉 분류기) StandardScaler — 2-input */
#define GATE_MEAN_0   {sc_gate.mean_[0]:.15g}f
#define GATE_MEAN_1   {sc_gate.mean_[1]:.15g}f
#define GATE_SCALE_0  {sc_gate.scale_[0]:.15g}f
#define GATE_SCALE_1  {sc_gate.scale_[1]:.15g}f

/* 전문가 A(근접, strain+distance) StandardScaler */
#define EA_MEAN_0   {sc_a.mean_[0]:.15g}f
#define EA_MEAN_1   {sc_a.mean_[1]:.15g}f
#define EA_MEAN_2   {sc_a.mean_[2]:.15g}f
#define EA_MEAN_3   {sc_a.mean_[3]:.15g}f
#define EA_SCALE_0  {sc_a.scale_[0]:.15g}f
#define EA_SCALE_1  {sc_a.scale_[1]:.15g}f
#define EA_SCALE_2  {sc_a.scale_[2]:.15g}f
#define EA_SCALE_3  {sc_a.scale_[3]:.15g}f

/* 전문가 B(압력, strain+force — force는 양수=누르는 방향) StandardScaler */
#define EB_MEAN_0   {sc_b.mean_[0]:.15g}f
#define EB_MEAN_1   {sc_b.mean_[1]:.15g}f
#define EB_MEAN_2   {sc_b.mean_[2]:.15g}f
#define EB_MEAN_3   {sc_b.mean_[3]:.15g}f
#define EB_SCALE_0  {sc_b.scale_[0]:.15g}f
#define EB_SCALE_1  {sc_b.scale_[1]:.15g}f
#define EB_SCALE_2  {sc_b.scale_[2]:.15g}f
#define EB_SCALE_3  {sc_b.scale_[3]:.15g}f

/* ─── EMA(이력) 피처 — 재귀식: y_n = y_(n-1) + alpha*(x_n - y_(n-1)) ──
 * tau = {TAU_OVERALL_S:g}s (v3와 동일 시간상수 유지)
 * TDM_PERIOD_TIME_US = 1000us(1ms) 고정이므로 alpha = 1 - exp(-dt/tau)도
 * 상수로 미리 계산해서 박아넣는다(런타임에 expf() 호출 불필요). */
#define EMA_ALPHA   {1 - np.exp(-0.001 / TAU_OVERALL_S):.8g}f  /* dt=1ms, tau={TAU_OVERALL_S:g}s */

/* ─── 게이트 임계값 ────────────────────────────────────────────────────────── */
#define GATE_CONTACT_THRESHOLD  0.5f  /* P(contact) >= 0.5 -> 압력 모드 */

/* ─── 출력 클램프 범위 (학습 데이터 실측 범위 + 여유 {MARGIN:g}) ─────────────────── */
#define STRAIN_MIN_PCT  {strain_lo:.4g}f
#define STRAIN_MAX_PCT  {strain_hi:.4g}f
/* 이번 세션 규약: dist_mm = prox_mm = Z_mm + {PROX_OFFSET:g} (0=접촉, 원거리 쪽이 양수) */
#define DIST_MIN_MM     {dist_lo:.4g}f
#define DIST_MAX_MM     {dist_hi:.4g}f
/* force 라벨은 "누르면 양수" 규약(실측 범위 {force_lo+MARGIN:.4g}..{force_hi-MARGIN:.4g}N) */
#define FORCE_MIN_N     {force_lo:.4g}f
#define FORCE_MAX_N     {force_hi:.4g}f

#endif /* MOE_PARAMS_H */
"""
with open(OUT_DIR / "moe_params.h", "w", encoding="utf-8") as f:
    f.write(moe_params_h)
print(f"\n[7a] [save] {OUT_DIR / 'moe_params.h'}")

# ── 7b) 학습 결과 그래프 (parity + 게이트 confusion) ──────────────────────────
print("\n[7b] Plotting training results...")
fig, axs = plt.subplots(1, 4, figsize=(18, 4.4))

axs[0].plot(te_a["strain_pct"], pred_a[:, 0], ".", ms=2.5, color="#FF8C00", alpha=0.4)
lim = [0, 32]
axs[0].plot(lim, lim, "k--", lw=1)
axs[0].set_xlabel("true strain (%)"); axs[0].set_ylabel("estimated strain (%)")
axs[0].set_title(f"Expert A strain\nR²={r2_a_strain:.3f} RMSE={rmse(te_a['strain_pct'],pred_a[:,0]):.2f}")

axs[1].plot(te_a["dist_mm"], pred_a[:, 1], ".", ms=2.5, color="#1F77B4", alpha=0.4)
lim = [0, float(te_a["dist_mm"].max())]
axs[1].plot(lim, lim, "k--", lw=1)
axs[1].set_xlabel("true proximity (mm)"); axs[1].set_ylabel("estimated proximity (mm)")
axs[1].set_title(f"Expert A proximity\nR²={r2_a_dist:.3f} RMSE={rmse(te_a['dist_mm'],pred_a[:,1]):.2f}")

axs[2].plot(te_b["strain_pct"], pred_b[:, 0], ".", ms=2.5, color="#FF8C00", alpha=0.4)
lim = [0, 32]
axs[2].plot(lim, lim, "k--", lw=1)
axs[2].set_xlabel("true strain (%)"); axs[2].set_ylabel("estimated strain (%)")
axs[2].set_title(f"Expert B strain (<{SATURATION_STRAIN_PCT:g}% only)\n"
                  f"R²={r2_b_strain:.3f} RMSE={rmse(te_b['strain_pct'],pred_b[:,0]):.2f}")

axs[3].plot(te_b["Force_N"], pred_b[:, 1], ".", ms=2.5, color="#D62728", alpha=0.4)
lim = [float(min(te_b["Force_N"].min(), 0)), float(te_b["Force_N"].max())]
axs[3].plot(lim, lim, "k--", lw=1)
axs[3].set_xlabel("true force (N)"); axs[3].set_ylabel("estimated force (N)")
axs[3].set_title(f"Expert B force\nR²={r2_b_force:.3f} RMSE={rmse(te_b['Force_N'],pred_b[:,1]):.2f}")

for ax in axs:
    ax.grid(True, alpha=0.25)
fig.suptitle(f"retrain_moe_v4 — gate acc={gate_acc:.3f} f1={gate_f1:.3f}  |  "
             f"end-to-end strain R²={r2_e2e_strain:.3f}", fontsize=12, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig(OUT_DIR / "train_results.png", dpi=150)
print(f"  [save] {OUT_DIR / 'train_results.png'}")
plt.close(fig)

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
