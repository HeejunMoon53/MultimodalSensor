"""
gen_validation.py
X-CUBE-AI Validation inputs/outputs CSV 생성

Stage1: dR_norm(1) → eps_norm(1)
Stage2: dL_eps(2)  → d_norm(1)
"""
import sys, pickle
sys.path.insert(0, 'C:\\ai\\lib')

import numpy as np
import pandas as pd
from pathlib import Path

HERE     = Path(__file__).parent
DATA_DIR = HERE / "data_acquisition" / "dataset"
OUT_DIR  = HERE / "stm32_deploy"
OUT_DIR.mkdir(exist_ok=True)

with open(DATA_DIR / "scalers_linear.pkl",      "rb") as f: S  = pickle.load(f)
with open(DATA_DIR / "model_stage1_linear.pkl", "rb") as f: M1 = pickle.load(f)
with open(DATA_DIR / "model_stage2_linear.pkl", "rb") as f: M2 = pickle.load(f)

sc_dR  = S["sc_dR"];  sc_dL = S["sc_dL"]
sc_eps = S["sc_eps"]; sc_d  = S["sc_d"]

N = 200  # 샘플 수
rng = np.random.default_rng(42)

# 물리적으로 의미 있는 범위 (실제 센서 측정 범위)
dR_pct_vals = rng.uniform(0.0, 25.0, N).astype(np.float32)   # ΔR/R₀ [%]
dL_pct_vals = rng.uniform(-5.0, 15.0, N).astype(np.float32)  # ΔL/L₀ [%]

# ── 정규화된 입력 계산 ────────────────────────────────────────────────────────
dR_norm = sc_dR.transform(dR_pct_vals.reshape(-1, 1)).astype(np.float32)  # (N,1)
dL_norm = sc_dL.transform(dL_pct_vals.reshape(-1, 1)).astype(np.float32)  # (N,1)

# ── Stage1 sklearn 추론 → eps_norm ────────────────────────────────────────────
eps_norm = M1.predict(dR_norm).reshape(-1, 1).astype(np.float32)           # (N,1)

# ── Stage2 입력 조합: [dL_norm, eps_norm] ─────────────────────────────────────
dL_eps = np.hstack([dL_norm, eps_norm]).astype(np.float32)                 # (N,2)

# ── Stage2 sklearn 추론 → d_norm ──────────────────────────────────────────────
d_norm = M2.predict(dL_eps).reshape(-1, 1).astype(np.float32)              # (N,1)

# ── X-CUBE-AI 포맷으로 저장 (헤더 없음, float32) ─────────────────────────────
# Stage1 input: dR_norm  [N, 1]
np.savetxt(OUT_DIR / "val_s1_input.csv",  dR_norm,  delimiter=",", fmt="%.8f")
# Stage1 output: eps_norm [N, 1]
np.savetxt(OUT_DIR / "val_s1_output.csv", eps_norm, delimiter=",", fmt="%.8f")

# Stage2 input: [dL_norm, eps_norm] [N, 2]
np.savetxt(OUT_DIR / "val_s2_input.csv",  dL_eps,   delimiter=",", fmt="%.8f")
# Stage2 output: d_norm [N, 1]
np.savetxt(OUT_DIR / "val_s2_output.csv", d_norm,   delimiter=",", fmt="%.8f")

# ── 통계 출력 ─────────────────────────────────────────────────────────────────
print("Generated validation files:")
for fname in ["val_s1_input.csv","val_s1_output.csv","val_s2_input.csv","val_s2_output.csv"]:
    p = OUT_DIR / fname
    print(f"  {fname:<25} {p.stat().st_size:>8,} bytes")

print(f"\nSamples: {N}")
print(f"dR_pct range : {dR_pct_vals.min():.2f} ~ {dR_pct_vals.max():.2f} %")
print(f"dL_pct range : {dL_pct_vals.min():.2f} ~ {dL_pct_vals.max():.2f} %")
print(f"dR_norm range: {dR_norm.min():.3f} ~ {dR_norm.max():.3f}")
print(f"dL_norm range: {dL_norm.min():.3f} ~ {dL_norm.max():.3f}")
print(f"eps_norm range:{eps_norm.min():.3f} ~ {eps_norm.max():.3f}")
print(f"d_norm range : {d_norm.min():.3f} ~ {d_norm.max():.3f}")
print()
print("X-CUBE-AI 설정:")
print("  Stage1  Validation inputs  → val_s1_input.csv")
print("          Validation outputs → val_s1_output.csv")
print("  Stage2  Validation inputs  → val_s2_input.csv")
print("          Validation outputs → val_s2_output.csv")
print()
print(f"Files saved to: {OUT_DIR}")
