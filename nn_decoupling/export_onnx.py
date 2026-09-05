"""
export_onnx.py
sklearn 2-Stage MLP → ONNX 변환 + X-CUBE-AI 검증
"""
import sys, pickle
sys.path.insert(0, 'C:\\ai\\lib')

import numpy as np
from pathlib import Path
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
import onnxruntime as ort

HERE     = Path(__file__).parent
DATA_DIR = HERE / "data_acquisition" / "dataset"
OUT_DIR  = HERE / "stm32_deploy"
OUT_DIR.mkdir(exist_ok=True)

# ── 모델 로드 ────────────────────────────────────────────────────────────────
with open(DATA_DIR / "scalers_linear.pkl",      "rb") as f: S  = pickle.load(f)
with open(DATA_DIR / "model_stage1_linear.pkl", "rb") as f: M1 = pickle.load(f)
with open(DATA_DIR / "model_stage2_linear.pkl", "rb") as f: M2 = pickle.load(f)

sc_dR  = S["sc_dR"];  sc_dL = S["sc_dL"]
sc_eps = S["sc_eps"]; sc_d  = S["sc_d"]

# ── Stage1 ONNX 변환: dR_norm(1) → eps_norm(1) ──────────────────────────────
print("Converting Stage1...")
onnx_s1 = convert_sklearn(
    M1,
    initial_types=[("dR_norm", FloatTensorType([None, 1]))],
    target_opset=17,
)
s1_path = OUT_DIR / "stage1.onnx"
onnx.save(onnx_s1, str(s1_path))
print(f"  Saved: {s1_path}  ({s1_path.stat().st_size:,} bytes)")
s1_in  = onnx_s1.graph.input[0].name
s1_out = onnx_s1.graph.output[0].name
print(f"  Input: {s1_in}  Output: {s1_out}")

# ── Stage2 ONNX 변환: [dL_norm, eps_norm](2) → d_norm(1) ────────────────────
print("Converting Stage2...")
onnx_s2 = convert_sklearn(
    M2,
    initial_types=[("dL_eps", FloatTensorType([None, 2]))],
    target_opset=17,
)
s2_path = OUT_DIR / "stage2.onnx"
onnx.save(onnx_s2, str(s2_path))
print(f"  Saved: {s2_path}  ({s2_path.stat().st_size:,} bytes)")
s2_in  = onnx_s2.graph.input[0].name
s2_out = onnx_s2.graph.output[0].name
print(f"  Input: {s2_in}  Output: {s2_out}")

# ── onnxruntime으로 수치 검증 ────────────────────────────────────────────────
print("\nValidation (onnxruntime vs sklearn)...")

sess1 = ort.InferenceSession(str(s1_path))
sess2 = ort.InferenceSession(str(s2_path))

rng = np.random.default_rng(42)
dL_vals = rng.uniform(-5, 15, 50).astype(np.float32)
dR_vals = rng.uniform(0,  25, 50).astype(np.float32)

err_eps, err_d = [], []
for dL, dR in zip(dL_vals, dR_vals):
    # sklearn 추론
    dR_n  = sc_dR.transform([[dR]])
    eps_n = M1.predict(dR_n).reshape(1, 1)
    eps   = float(np.clip(sc_eps.inverse_transform(eps_n)[0,0], 0, 30))

    dL_n  = sc_dL.transform([[dL]])
    d_n   = M2.predict(np.hstack([dL_n, eps_n])).reshape(1, 1)
    d     = float(np.clip(sc_d.inverse_transform(d_n)[0,0], 0, 50))

    # ONNX 추론
    dR_norm_in = sc_dR.transform([[dR]]).astype(np.float32)
    eps_n_ort  = sess1.run(None, {s1_in: dR_norm_in})[0]
    eps_ort    = float(np.clip(
        sc_eps.inverse_transform(eps_n_ort.reshape(1,-1))[0,0], 0, 30))

    dL_norm_in = sc_dL.transform([[dL]]).astype(np.float32)
    eps_n_ort_r = eps_n_ort.reshape(1,-1)
    dl_eps_in  = np.hstack([dL_norm_in, eps_n_ort_r]).astype(np.float32)
    d_n_ort    = sess2.run(None, {s2_in: dl_eps_in})[0]
    d_ort      = float(np.clip(sc_d.inverse_transform(d_n_ort.reshape(1,-1))[0,0], 0, 50))

    err_eps.append(abs(eps - eps_ort))
    err_d.append(abs(d - d_ort))

print(f"  sklearn vs ONNX  delta_eps MAE : {np.mean(err_eps):.6f} %")
print(f"  sklearn vs ONNX  delta_d   MAE : {np.mean(err_d):.6f} mm")

# ── ONNX 모델 정보 출력 ───────────────────────────────────────────────────────
print("\n--- Stage1 ONNX graph ---")
for n in onnx_s1.graph.node:
    print(f"  {n.op_type:20s} {list(n.input)} -> {list(n.output)}")

print("\n--- Stage2 ONNX graph ---")
for n in onnx_s2.graph.node:
    print(f"  {n.op_type:20s} {list(n.input)} -> {list(n.output)}")

print(f"""
==========================================================
  X-CUBE-AI 사용 절차
==========================================================
  1. STM32CubeIDE 1.19.0 실행
  2. Help -> Install New Software
     -> https://sw-center.st.com/stm32cubeai/
     -> X-CUBE-AI 설치 후 IDE 재시작

  3. 기존 TDMFirmware 프로젝트 열기
  4. Project -> Properties -> C/C++ Build -> Settings
     -> Tool Settings -> MCU GCC Compiler -> Add Include:
        $(ProjectRoot)/X-CUBE-AI/App
        $(ProjectRoot)/Middlewares/ST/AI/Inc

  5. Help -> STM32Cube AI Studio (또는 상단 메뉴 AI)
     -> Add network
     -> Model: {s1_path}  (Stage1)
     -> Compression: INT8  Quantization: Per-tensor
     -> Inputs:  dR_norm  [1, 1]  float32
     -> Generate Code

  6. Stage2도 동일하게 추가
     -> Model: {s2_path}

  7. 생성된 network.c / network_data.c 빌드 확인
     .map 파일에서 Flash / SRAM 점유량 확인

  생성된 ONNX 파일:
    Stage1: {s1_path}
    Stage2: {s2_path}
==========================================================
""")
