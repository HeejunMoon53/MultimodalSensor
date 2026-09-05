"""
medium-deep sklearn MLP → ONNX → stedgeai → stage1.c / stage2.c
"""
import sys, pickle, subprocess, shutil
sys.path.insert(0, r'C:\ai\pylibs')
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
from pathlib import Path
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
import onnxruntime as ort

HERE    = Path(__file__).parent
DS_DIR  = HERE / "data_acquisition" / "dataset"
CHK_DIR = HERE / "checkpoints"
OUT_DIR = HERE / "stm32_deploy_md_xcubeai"
OUT_DIR.mkdir(exist_ok=True)

STEDGEAI = r"C:\ai\xe\stedgeai.exe"
FW_XCUBE = Path(__file__).parent.parent / "TDMFirmware" / "X-CUBE-AI" / "App"

# ── 모델 로드 ──────────────────────────────────────────────────────────────────
with open(DS_DIR / "scalers_linear.pkl", "rb") as f: S  = pickle.load(f)
with open(CHK_DIR / "model_stage1_md.pkl", "rb") as f: M1 = pickle.load(f)
with open(CHK_DIR / "model_stage2_md.pkl", "rb") as f: M2 = pickle.load(f)

sc_dR = S["sc_dR"]; sc_dL = S["sc_dL"]
sc_eps = S["sc_eps"]; sc_d = S["sc_d"]

print(f"Stage1 arch: {[c.shape for c in M1.coefs_]}")
print(f"Stage2 arch: {[c.shape for c in M2.coefs_]}")

# ── ONNX 변환 ─────────────────────────────────────────────────────────────────
print("\n[1] Converting to ONNX float32...")
onnx_s1 = convert_sklearn(M1,
    initial_types=[("dR_norm", FloatTensorType([None, 1]))], target_opset=17)
onnx_s2 = convert_sklearn(M2,
    initial_types=[("dL_eps", FloatTensorType([None, 2]))],  target_opset=17)

s1_path = OUT_DIR / "stage1_md.onnx"
s2_path = OUT_DIR / "stage2_md.onnx"
onnx.save(onnx_s1, str(s1_path))
onnx.save(onnx_s2, str(s2_path))
print(f"  stage1_md.onnx  {s1_path.stat().st_size:,} B")
print(f"  stage2_md.onnx  {s2_path.stat().st_size:,} B")

# ── onnxruntime 수치 검증 ──────────────────────────────────────────────────────
print("\n[2] Validating ONNX vs sklearn...")
s1_in_name  = onnx_s1.graph.input[0].name
s2_in_name  = onnx_s2.graph.input[0].name
sess1 = ort.InferenceSession(str(s1_path))
sess2 = ort.InferenceSession(str(s2_path))

rng = np.random.default_rng(42)
dR_vals = rng.uniform(0, 20, 100).astype(np.float32)
dL_vals = rng.uniform(-5, 15, 100).astype(np.float32)
err_eps, err_d = [], []
for dR, dL in zip(dR_vals, dL_vals):
    dR_n = sc_dR.transform([[dR]]).astype(np.float32)
    e_sk = float(sc_eps.inverse_transform(M1.predict(dR_n).reshape(1,-1))[0,0])
    e_on = float(sc_eps.inverse_transform(
        sess1.run(None, {s1_in_name: dR_n})[0].reshape(1,-1))[0,0])
    err_eps.append(abs(e_sk - e_on))

    dL_n  = sc_dL.transform([[dL]]).astype(np.float32)
    eps_n = sc_eps.transform([[e_sk]]).astype(np.float32)
    X2    = np.hstack([dL_n, eps_n]).astype(np.float32)
    d_sk  = float(sc_d.inverse_transform(M2.predict(X2).reshape(1,-1))[0,0])
    d_on  = float(sc_d.inverse_transform(
        sess2.run(None, {s2_in_name: X2})[0].reshape(1,-1))[0,0])
    err_d.append(abs(d_sk - d_on))

print(f"  sklearn vs ONNX  Δε={np.mean(err_eps):.6f}%  Δd={np.mean(err_d):.6f}mm")

# ── stedgeai: ONNX float32 → INT8 C 코드 생성 ────────────────────────────────
print(f"\n[3] Running stedgeai generate...")
for model_path, name in [(s1_path, "stage1"), (s2_path, "stage2")]:
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
    print(f"  > {' '.join(cmd[1:4])} {name} ...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        # int8 quantize 옵션 없이 재시도 (float32 → stedgeai 내장 INT8 변환)
        cmd2 = [
            STEDGEAI, "generate",
            "--target", "stm32",
            "--name", name,
            "--model", str(model_path),
            "--output", str(OUT_DIR),
        ]
        print(f"  Retry without --quantize flag...")
        r = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='replace')

    print(f"  returncode: {r.returncode}")
    if r.stdout: print(r.stdout[-1500:])
    if r.stderr: print("STDERR:", r.stderr[-500:])

# ── 생성된 파일 확인 ───────────────────────────────────────────────────────────
print("\n[4] Generated files:")
for f in sorted(OUT_DIR.glob("*.c")) + sorted(OUT_DIR.glob("*.h")):
    print(f"  {f.name:40s}  {f.stat().st_size:>8,} B")

# ── TDMFirmware/X-CUBE-AI/App/ 으로 복사 ─────────────────────────────────────
print(f"\n[5] Copying to {FW_XCUBE} ...")
copied = []
for f in sorted(OUT_DIR.glob("stage*.c")) + sorted(OUT_DIR.glob("stage*.h")):
    dst = FW_XCUBE / f.name
    shutil.copy2(f, dst)
    copied.append(f.name)
    print(f"  {f.name} → {dst}")

if not copied:
    print("  WARNING: no stage*.c/h files found in output — check stedgeai output above")

print("\nDone.")
