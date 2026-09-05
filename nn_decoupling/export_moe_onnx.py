"""
export_moe_onnx.py
후보 2(게이트+EMA MLP, mms_20260806 단일 데이터셋 기준)의 3개 네트워크
(게이트, 근접 전문가, 압력 전문가)를 학습하고 ONNX로 변환한 뒤,
stedgeai로 STM32 C 코드를 생성해서 TDMFirmware/X-CUBE-AI/App/에 배치한다.

기존 stm32_deploy_md_xcubeai/export_md_onnx.py와 동일한 패턴(sklearn -> ONNX
-> stedgeai generate -> TDMFirmware로 복사)을 따르되, 대상 모델은 2단계
(R->strain, L+strain->distance) 정적 디커플러가 아니라 오늘 세션에서 만든
게이트+전문가(MoE) 구조다. StandardScaler는 ONNX 그래프에 넣지 않고(구 파이프라인과
동일한 방식) mean_/scale_를 따로 뽑아 C 헤더 상수로 박아넣는다 — 정규화는
펌웨어에서 직접 (x-mean)/std로 계산.

[실기 테스트 후 수정] 게이트는 EMA 없이 원본 2-input(dL_pct, dR_pct)만 쓴다.
접촉 여부는 즉각적인 물리적 전환인데, EMA(τ≈1초)가 실제 탭/릴리스 속도보다
느려서 "뗀 뒤에도 게이트가 계속 접촉으로 유지되는" 자기강화 루프가 생겼기
때문 — 게이트 판단이 stale EMA에 좌우되면, 그 판단이 안 바뀌는 한 EMA 리셋도
안 걸려서 영영 안 풀리는 구조였다. 전문가 A/B는 이력이 실제로 도움되는
회귀 출력이라 4-input(EMA 포함)을 그대로 유지한다.
"""
import sys
import subprocess
import shutil
import pickle
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
import onnxruntime as ort

HERE = Path(__file__).parent
MOE_DIR = HERE / "test0807_MoEDecoupling"
sys.path.insert(0, str(MOE_DIR))
import common  # noqa: E402

OUT_DIR = HERE / "stm32_deploy_moe"
OUT_DIR.mkdir(exist_ok=True)

STEDGEAI = r"C:\ai\xe\stedgeai.exe"
FW_XCUBE = HERE.parent / "TDMFirmware" / "X-CUBE-AI" / "App"

TAU_OVERALL_S = 1.0125
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN_EXPERT = (24, 16, 8)
HIDDEN_GATE = (8, 4)
SEED = 0

# ── 1) 데이터 로드 + 학습 (candidate2_gate_ema.py와 동일 로직, 3개 모델 각각
#      독립적인 StandardScaler를 씀 — candidate1_baseline_gate.py의 build_gate()/
#      build_expert() 파이프라인과 정확히 동일한 규칙) ─────────────────────────
print("[1] Loading data + training gate / expert_a / expert_b ...")
df = common.load_raw()
df = common.add_labels(df)
df, ema_cols = common.add_ema_features(df, halflife_s=EMA_HALFLIFE_S)
feature_cols = common.FEATURE_COLS_BASE + ema_cols  # [dL_pct, dR_pct, dL_ema, dR_ema]

train_df, test_df = common.split_by_cycle(df)

gate_cols = common.FEATURE_COLS_BASE  # [dL_pct, dR_pct] — EMA 없음(실기 검증 결과 반영)
sc_gate = StandardScaler().fit(train_df[gate_cols].values)
gate = MLPClassifier(hidden_layer_sizes=HIDDEN_GATE, activation="tanh", solver="adam",
                      max_iter=3000, random_state=SEED, early_stopping=True, n_iter_no_change=30)
gate.fit(sc_gate.transform(train_df[gate_cols].values), train_df["contact"].values)
gate_acc = gate.score(sc_gate.transform(test_df[gate_cols].values), test_df["contact"].values)
print(f"  [gate] test acc={gate_acc:.4f}  hidden={HIDDEN_GATE}  n_layers_coefs={[c.shape for c in gate.coefs_]}")

tr_a = train_df[train_df.phase == "proximity"]
te_a = test_df[test_df.phase == "proximity"]
sc_a = StandardScaler().fit(tr_a[feature_cols].values)
expert_a = MLPRegressor(hidden_layer_sizes=HIDDEN_EXPERT, activation="tanh", solver="adam",
                         max_iter=4000, random_state=SEED, early_stopping=True, n_iter_no_change=40)
expert_a.fit(sc_a.transform(tr_a[feature_cols].values), tr_a[["strain_pct", "z_mm"]].values)
pred_a = expert_a.predict(sc_a.transform(te_a[feature_cols].values))
r2_a_strain = 1 - np.sum((te_a["strain_pct"].values - pred_a[:, 0]) ** 2) / np.sum((te_a["strain_pct"].values - te_a["strain_pct"].values.mean()) ** 2)
r2_a_dist = 1 - np.sum((te_a["z_mm"].values - pred_a[:, 1]) ** 2) / np.sum((te_a["z_mm"].values - te_a["z_mm"].values.mean()) ** 2)
print(f"  [expert_a/proximity] strain R2={r2_a_strain:.4f}  dist R2={r2_a_dist:.4f}")

tr_b = train_df[train_df.phase == "pressure"]
te_b = test_df[test_df.phase == "pressure"]
sc_b = StandardScaler().fit(tr_b[feature_cols].values)
expert_b = MLPRegressor(hidden_layer_sizes=HIDDEN_EXPERT, activation="tanh", solver="adam",
                         max_iter=4000, random_state=SEED, early_stopping=True, n_iter_no_change=40)
expert_b.fit(sc_b.transform(tr_b[feature_cols].values), tr_b[["strain_pct", "Force_N"]].values)
pred_b = expert_b.predict(sc_b.transform(te_b[feature_cols].values))
r2_b_strain = 1 - np.sum((te_b["strain_pct"].values - pred_b[:, 0]) ** 2) / np.sum((te_b["strain_pct"].values - te_b["strain_pct"].values.mean()) ** 2)
r2_b_force = 1 - np.sum((te_b["Force_N"].values - pred_b[:, 1]) ** 2) / np.sum((te_b["Force_N"].values - te_b["Force_N"].values.mean()) ** 2)
print(f"  [expert_b/pressure]  strain R2={r2_b_strain:.4f}  force R2={r2_b_force:.4f}")

with open(OUT_DIR / "models.pkl", "wb") as f:
    pickle.dump(dict(gate=gate, expert_a=expert_a, expert_b=expert_b,
                      sc_gate=sc_gate, sc_a=sc_a, sc_b=sc_b,
                      gate_cols=gate_cols, feature_cols=feature_cols), f)

# ── 2) ONNX 변환 (StandardScaler는 그래프에 안 넣음 — 펌웨어에서 직접 정규화) ────
print("\n[2] Converting to ONNX float32...")
onnx_gate = convert_sklearn(
    gate, initial_types=[("x", FloatTensorType([None, 2]))], target_opset=17,
    options={id(gate): {"zipmap": False}},
)
onnx_a = convert_sklearn(expert_a, initial_types=[("x", FloatTensorType([None, 4]))], target_opset=17)
onnx_b = convert_sklearn(expert_b, initial_types=[("x", FloatTensorType([None, 4]))], target_opset=17)

paths = {
    "gate": OUT_DIR / "gate.onnx",
    "expert_a": OUT_DIR / "expert_a.onnx",
    "expert_b": OUT_DIR / "expert_b.onnx",
}
onnx.save(onnx_gate, str(paths["gate"]))
onnx.save(onnx_a, str(paths["expert_a"]))
onnx.save(onnx_b, str(paths["expert_b"]))
for name, p in paths.items():
    print(f"  {p.name:16s} {p.stat().st_size:,} B")
    m = onnx.load(str(p))
    print(f"    inputs:  {[(i.name, [d.dim_value for d in i.type.tensor_type.shape.dim]) for i in m.graph.input]}")
    print(f"    outputs: {[(o.name, [d.dim_value for d in o.type.tensor_type.shape.dim]) for o in m.graph.output]}")

# ── 3) onnxruntime 수치 검증 (sklearn vs ONNX) ──────────────────────────────
print("\n[3] Validating ONNX vs sklearn...")
rng = np.random.default_rng(42)
X_raw = np.column_stack([
    rng.uniform(-40, 20, 200),
    rng.uniform(0, 45, 200),
    rng.uniform(-40, 20, 200),
    rng.uniform(0, 45, 200),
]).astype(np.float32)

sess_gate = ort.InferenceSession(str(paths["gate"]))
sess_a = ort.InferenceSession(str(paths["expert_a"]))
sess_b = ort.InferenceSession(str(paths["expert_b"]))

Xg = sc_gate.transform(X_raw[:, :2]).astype(np.float32)
sk_gate_proba = gate.predict_proba(Xg)[:, 1]
on_gate_out = sess_gate.run(None, {"x": Xg})
print(f"  gate onnx outputs: {[o.shape for o in on_gate_out]}")
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

# ── 4) stedgeai: ONNX float32 -> STM32 C 코드 생성 ──────────────────────────
print("\n[4] Running stedgeai generate...")
generated_ok = {}
for name, model_path in paths.items():
    cmd = [
        STEDGEAI, "generate",
        "--target", "stm32",
        "--name", name,
        "--model", str(model_path),
        "--compression", "none",
        "--quantize", "int8",
        "--output", str(OUT_DIR),
        "--workspace", str(OUT_DIR / "workspace"),
    ]
    print(f"  > generate {name} (int8) ...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        cmd2 = [STEDGEAI, "generate", "--target", "stm32", "--name", name,
                "--model", str(model_path), "--output", str(OUT_DIR)]
        print("    retry without --quantize (float32) ...")
        r = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8", errors="replace")
    generated_ok[name] = (r.returncode == 0)
    print(f"    returncode={r.returncode}")
    if r.returncode != 0:
        print("    STDOUT tail:", r.stdout[-1500:] if r.stdout else "")
        print("    STDERR tail:", r.stderr[-1500:] if r.stderr else "")

print("\n[5] Generated files:")
for f in sorted(OUT_DIR.glob("*.c")) + sorted(OUT_DIR.glob("*.h")):
    print(f"  {f.name:40s} {f.stat().st_size:>8,} B")

print(f"\n[6] Copying to {FW_XCUBE} ...")
FW_XCUBE.mkdir(parents=True, exist_ok=True)
copied = []
for name in paths:
    for f in sorted(OUT_DIR.glob(f"{name}*.c")) + sorted(OUT_DIR.glob(f"{name}*.h")):
        dst = FW_XCUBE / f.name
        shutil.copy2(f, dst)
        copied.append(f.name)
if copied:
    print(f"  copied {len(copied)} files: {copied}")
else:
    print("  WARNING: nothing copied — check stedgeai output above")

# ── 7) C 헤더용 스케일러 상수 + EMA 상수 출력 ────────────────────────────────
print("\n[7] Scaler constants (for moe_params.h):")


def dump_scaler(tag, sc):
    print(f"  {tag}: mean={sc.mean_.tolist()}  scale={sc.scale_.tolist()}")


dump_scaler("gate", sc_gate)
dump_scaler("expert_a", sc_a)
dump_scaler("expert_b", sc_b)
alpha = 1.0 - np.exp(-0.001 / EMA_HALFLIFE_S * np.log(2) / np.log(2))  # placeholder, real calc below
alpha_ema = 1.0 - np.exp(-0.001 / TAU_OVERALL_S)  # dt=1ms(TDM 주기), tau=1.0125s
print(f"  EMA: tau={TAU_OVERALL_S}s halflife={EMA_HALFLIFE_S:.4f}s alpha(dt=1ms)={alpha_ema:.8f}")

print("\nDone.")
