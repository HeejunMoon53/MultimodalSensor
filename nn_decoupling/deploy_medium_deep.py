"""
deploy_medium_deep.py
medium-deep (978 params) 모델 학습 → INT8 C코드 생성 → STM32 지표 계산
"""
import sys, pickle, json, textwrap, time
sys.path.insert(0, r'C:\ai\pylibs')
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
import warnings; warnings.filterwarnings('ignore')

HERE     = Path(__file__).parent
DS_DIR   = HERE / "data_acquisition" / "dataset"
CHK_DIR  = HERE / "checkpoints"
OUT_DIR  = HERE / "stm32_deploy_md"
OUT_DIR.mkdir(exist_ok=True)

# ── 색상 (CLAUDE.md) ──────────────────────────────────────────────────────────
COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"

# ═══════════════════════════════════════════════════════════════════════════════
# 1. 데이터 로드 + 스케일러 (sklearn 현재 모델과 동일 스케일러 재사용)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("  1. DATA LOADING")
print("=" * 60)

train = pd.read_csv(DS_DIR / "train.csv")
val   = pd.read_csv(DS_DIR / "val.csv")
test  = pd.read_csv(DS_DIR / "test.csv")

with open(DS_DIR / "scalers_linear.pkl", "rb") as f:
    S = pickle.load(f)
sc_dR = S["sc_dR"]; sc_dL = S["sc_dL"]
sc_eps = S["sc_eps"]; sc_d = S["sc_d"]

def prepare(df):
    X1 = sc_dR.transform(df[["dR_pct"]].values)
    y1 = sc_eps.transform(df[["eps_act_pct"]].values).ravel()
    eps_hat = sc_eps.transform(df[["eps_act_pct"]].values)
    dL_n    = sc_dL.transform(df[["dL_pct"]].values)
    X2 = np.hstack([dL_n, eps_hat])
    y2 = sc_d.transform(df[["d_act_mm"]].values).ravel()
    return X1, y1, X2, y2

X1_tr, y1_tr, X2_tr, y2_tr = prepare(train)
X1_va, y1_va, X2_va, y2_va = prepare(val)
X1_te, y1_te, X2_te, y2_te = prepare(test)

print(f"  train {len(train):,}  val {len(val):,}  test {len(test):,}")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. medium-deep 학습  S1: 1→16→8→4→1  S2: 2→32→16→8→1
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  2. TRAINING medium-deep  (S1: 1→16→8→4→1 / S2: 2→32→16→8→1)")
print("=" * 60)

MLP_KW = dict(activation='relu', solver='adam', max_iter=2000,
              early_stopping=True, n_iter_no_change=50,
              validation_fraction=0.1, random_state=42, verbose=False)

t0 = time.time()
M1 = MLPRegressor(hidden_layer_sizes=(16, 8, 4), **MLP_KW)
M1.fit(X1_tr, y1_tr)
t1 = time.time()
M2 = MLPRegressor(hidden_layer_sizes=(32, 16, 8), **MLP_KW)
M2.fit(X2_tr, y2_tr)
t2 = time.time()

print(f"  Stage1 trained  iters={M1.n_iter_}  time={t1-t0:.1f}s")
print(f"  Stage2 trained  iters={M2.n_iter_}  time={t2-t1:.1f}s")

# ── 파라미터 집계 ──────────────────────────────────────────────────────────────
def count_params(m):
    return sum(w.size for w in m.coefs_) + sum(b.size for b in m.intercepts_)

def count_macs(m):
    return sum(w.shape[0]*w.shape[1] for w in m.coefs_)

p1 = count_params(M1); macs1 = count_macs(M1)
p2 = count_params(M2); macs2 = count_macs(M2)
print(f"\n  S1 params={p1}  MACs={macs1}")
print(f"  S2 params={p2}  MACs={macs2}")
print(f"  Total params={p1+p2}  MACs={macs1+macs2}")

# ── 정확도 평가 (test set) ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  3. TEST SET EVALUATION")
print("=" * 60)

eps_pred_n = M1.predict(X1_te)
# Stage2 입력: 실제 dL + 예측 eps_hat (파이프라인 방식)
eps_hat_te = eps_pred_n.reshape(-1, 1)
X2_te_pred = np.hstack([sc_dL.transform(test[["dL_pct"]].values), eps_hat_te])
d_pred_n   = M2.predict(X2_te_pred)

eps_pred = sc_eps.inverse_transform(eps_pred_n.reshape(-1,1)).ravel()
d_pred   = sc_d.inverse_transform(d_pred_n.reshape(-1,1)).ravel()
eps_act  = test["eps_act_pct"].values
d_act    = test["d_act_mm"].values

mae_eps = mean_absolute_error(eps_act, eps_pred)
mae_d   = mean_absolute_error(d_act,   d_pred)
mae_d15 = mean_absolute_error(d_act[d_act<=15], d_pred[d_act<=15])

print(f"  MAE eps : {mae_eps:.4f} %")
print(f"  MAE d   : {mae_d:.4f} mm")
print(f"  MAE d15 : {mae_d15:.4f} mm")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. INT8 PTQ  (per-layer symmetric, weight-only)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  4. POST-TRAINING QUANTIZATION  INT8 per-layer")
print("=" * 60)

def quantize_model(model):
    layers = []
    for W, b in zip(model.coefs_, model.intercepts_):
        Wt = W.T.copy()   # (out, in)
        absmax = np.max(np.abs(Wt))
        scale  = absmax / 127.0 if absmax > 0 else 1.0
        Wq     = np.round(Wt / scale).clip(-128, 127).astype(np.int8)
        layers.append({"Wq": Wq, "scale": float(scale), "b": b.astype(np.float32)})
    return layers

q1 = quantize_model(M1)
q2 = quantize_model(M2)

def infer_i8(q_layers, x_in):
    x = np.array(x_in, dtype=np.float32)
    for li, lyr in enumerate(q_layers):
        Wf = lyr["Wq"].astype(np.float32) * lyr["scale"]
        x  = Wf @ x + lyr["b"]
        if li < len(q_layers) - 1:
            x = np.maximum(x, 0)
    return x

# INT8 추론 오차
eps_i8_list, d_i8_list = [], []
for i in range(len(test)):
    dR_n = float(X1_te[i, 0])
    dL_n = float(X2_te_pred[i, 0])
    e_n  = float(infer_i8(q1, [dR_n]))
    e_ph = float(np.clip(e_n * sc_eps.scale_[0] + sc_eps.mean_[0], 0, 30))
    en2  = (e_ph - sc_eps.mean_[0]) / sc_eps.scale_[0]
    d_n  = float(infer_i8(q2, [dL_n, en2]))
    d_ph = float(np.clip(d_n * sc_d.scale_[0] + sc_d.mean_[0], 0, 50))
    eps_i8_list.append(e_ph)
    d_i8_list.append(d_ph)

mae_eps_i8 = mean_absolute_error(eps_act, eps_i8_list)
mae_d_i8   = mean_absolute_error(d_act,   d_i8_list)
delta_eps  = mae_eps_i8 - mae_eps
delta_d    = mae_d_i8   - mae_d
print(f"  MAE eps (INT8) : {mae_eps_i8:.4f} %   (delta +{delta_eps:.4f})")
print(f"  MAE d   (INT8) : {mae_d_i8:.4f} mm  (delta +{delta_d:.4f})")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. INT8 scales for STM32 (activation quantization — per-tensor, symmetric)
#    STM32에서 aktivation도 INT8으로 처리하기 위한 scale 계산
#    scale = max(|activation|) / 127  (교정 데이터: train set)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  5. ACTIVATION SCALES  (500 calibration samples)")
print("=" * 60)

rng = np.random.default_rng(0)
cal_idx  = rng.choice(len(X1_tr), 500, replace=False)
s1_in_calib  = X1_tr[cal_idx]     # dR_norm
s2_in_calib  = X2_tr[cal_idx]     # [dL_norm, eps_norm]
s1_out_calib = M1.predict(s1_in_calib)   # eps_norm
s2_out_calib = M2.predict(s2_in_calib)   # d_norm

def act_scale(vals):
    return float(np.max(np.abs(vals)) / 127.0)

S1_IN_SCALE  = act_scale(s1_in_calib)
S1_OUT_SCALE = act_scale(s1_out_calib)
S2_IN_SCALE  = act_scale(s2_in_calib)
S2_OUT_SCALE = act_scale(s2_out_calib)

print(f"  S1_IN_SCALE  = {S1_IN_SCALE:.9f}")
print(f"  S1_OUT_SCALE = {S1_OUT_SCALE:.9f}")
print(f"  S2_IN_SCALE  = {S2_IN_SCALE:.9f}")
print(f"  S2_OUT_SCALE = {S2_OUT_SCALE:.9f}")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. C 코드 생성  (standalone — X-CUBE-AI 불필요)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  6. GENERATING STANDALONE C CODE")
print("=" * 60)

def arr_i8(name, mat, per_row=16):
    flat = mat.flatten().tolist()
    rows = []
    for i in range(0, len(flat), per_row):
        rows.append("    " + ", ".join(f"{int(v):4d}" for v in flat[i:i+per_row]) + ",")
    return f"static const int8_t {name}[{len(flat)}] = {{\n" + "\n".join(rows) + "\n};\n"

def arr_f32(name, arr, per_row=8):
    flat = arr.flatten().tolist()
    rows = []
    for i in range(0, len(flat), per_row):
        rows.append("    " + ", ".join(f"{v:.8f}f" for v in flat[i:i+per_row]) + ",")
    return f"static const float {name}[{len(flat)}] = {{\n" + "\n".join(rows) + "\n};\n"

# ── nn_weights_md.h ───────────────────────────────────────────────────────────
wh_lines = [
    "/* Auto-generated by deploy_medium_deep.py  DO NOT EDIT */",
    "#ifndef NN_WEIGHTS_MD_H",
    "#define NN_WEIGHTS_MD_H",
    "#include <stdint.h>",
    "",
    "/* Stage1: 1->16->8->4->1  Stage2: 2->32->16->8->1 */",
    "",
    "/* ── INT8 per-layer symmetric quantization scales ── */",
]
for stage, q in [("S1", q1), ("S2", q2)]:
    for li, lyr in enumerate(q):
        wh_lines.append(f"#define {stage}_W{li}_SCALE  {lyr['scale']:.9f}f")
wh_lines.append("")

for stage, q in [("S1", q1), ("S2", q2)]:
    for li, lyr in enumerate(q):
        wh_lines.append(arr_i8(f"{stage}_W{li}", lyr["Wq"]))
        wh_lines.append(arr_f32(f"{stage}_B{li}", lyr["b"]))

wh_lines += ["#endif /* NN_WEIGHTS_MD_H */\n"]
wh_content = "\n".join(wh_lines)
(OUT_DIR / "nn_weights_md.h").write_text(wh_content, encoding="utf-8")
wh_size = (OUT_DIR / "nn_weights_md.h").stat().st_size
print(f"  nn_weights_md.h  {wh_size:,} bytes")

# ── nn_inference_md.h ─────────────────────────────────────────────────────────
hdr = textwrap.dedent("""\
/* Auto-generated by deploy_medium_deep.py  DO NOT EDIT */
#ifndef NN_INFERENCE_MD_H
#define NN_INFERENCE_MD_H

typedef struct {
    float eps_pct;
    float d_mm;
    int   d_valid;
    float stage1_us;
    float stage2_us;
} NNOutMD;

void nn_md_init(void);
NNOutMD nn_md_run(float dL_pct, float dR_pct);

#endif /* NN_INFERENCE_MD_H */
""")
(OUT_DIR / "nn_inference_md.h").write_text(hdr, encoding="utf-8")

# ── nn_inference_md.c ─────────────────────────────────────────────────────────
# 아키텍처 기반 코드 생성 (반복 구조)
def gen_stage(stage, q, in_size, name_prefix):
    lines = []
    for li, lyr in enumerate(q):
        out_sz = lyr["b"].shape[0]
        in_sz  = lyr["Wq"].shape[1]
        is_last = (li == len(q) - 1)
        out_var = f"h{li}" if not is_last else "tmp"
        in_var  = f"in_vec" if li == 0 else f"h{li-1}"
        lines += [
            f"    /* Layer {li}: {in_sz}->{out_sz} */",
            f"    for (int i = 0; i < {out_sz}; i++) {{",
            f"        int32_t acc = 0;",
            f"        for (int j = 0; j < {in_sz}; j++)",
            f"            acc += (int32_t){stage}_W{li}[i * {in_sz} + j] *",
            f"                   (int32_t)({in_var}[j] / {stage}_W{li}_SCALE * 127.0f);",
            f"        {out_var}{'[i]' if not is_last else ''} = acc * {stage}_W{li}_SCALE * {stage}_W{li}_SCALE / 127.0f + {stage}_B{li}[i];",
        ]
        if not is_last:
            lines += [
                f"        if ({out_var}[i] < 0.0f) {out_var}[i] = 0.0f;  /* ReLU */",
            ]
        lines.append("    }")
    return "\n".join(lines)

max_h1 = max(lyr["Wq"].shape[0] for lyr in q1[:-1])
max_h2 = max(lyr["Wq"].shape[0] for lyr in q2[:-1])
max_h  = max(max_h1, max_h2)

s1_code = gen_stage("S1", q1, 1, "s1")
s2_code = gen_stage("S2", q2, 2, "s2")

src = f"""\
/* Auto-generated by deploy_medium_deep.py  DO NOT EDIT */
/* Stage1: 1->16->8->4->1  Stage2: 2->32->16->8->1  Total 978 params */
#include "nn_inference_md.h"
#include "nn_weights_md.h"
#include "main.h"    /* DWT->CYCCNT */
#include "decoupler_params.h"  /* SC_DR_MEAN etc. */

#ifndef DWT_BASE
#define DWT_BASE ((DWT_Type*)0xE0001000UL)
#endif

void nn_md_init(void) {{ /* no runtime init needed — weights in Flash/SRAM */ }}

NNOutMD nn_md_run(float dL_pct, float dR_pct)
{{
    float h0[{max_h}], h1[{max_h}], h2[{max_h}];
    float tmp = 0.0f;

    /* ── Stage1: dR_norm -> eps_norm ── */
    float in_vec[1];
    in_vec[0] = (dR_pct - SC_DR_MEAN) / SC_DR_STD;

    uint32_t t_s1 = DWT->CYCCNT;
{s1_code}
    uint32_t cyc_s1 = DWT->CYCCNT - t_s1;

    float eps_pct = tmp * SC_EPS_STD + SC_EPS_MEAN;
    if (eps_pct < 0.0f)  eps_pct = 0.0f;
    if (eps_pct > 30.0f) eps_pct = 30.0f;

    /* ── Stage2: [dL_norm, eps_norm] -> d_norm ── */
    in_vec[0] = (dL_pct - SC_DL_MEAN) / SC_DL_STD;
    in_vec[1] = (eps_pct - SC_EPS_MEAN) / SC_EPS_STD;

    uint32_t t_s2 = DWT->CYCCNT;
{s2_code}
    uint32_t cyc_s2 = DWT->CYCCNT - t_s2;

    float d_mm = tmp * SC_D_STD + SC_D_MEAN;
    if (d_mm < 0.0f)  d_mm = 0.0f;
    if (d_mm > 50.0f) d_mm = 50.0f;

    NNOutMD out;
    out.eps_pct  = eps_pct;
    out.d_mm     = d_mm;
    out.d_valid  = (d_mm <= 15.0f) ? 1 : 0;
    out.stage1_us = (float)cyc_s1 / 170.0f;
    out.stage2_us = (float)cyc_s2 / 170.0f;
    return out;
}}
"""
(OUT_DIR / "nn_inference_md.c").write_text(src, encoding="utf-8")
src_size = (OUT_DIR / "nn_inference_md.c").stat().st_size
print(f"  nn_inference_md.c  {src_size:,} bytes")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. STM32 메모리 / Latency 이론 추정
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  7. STM32 METRIC ESTIMATION")
print("=" * 60)

SKLEARN_MEAS = {
    "flash_b": 112488, "sram_b": 15312,
    "latency_us": 1068.0, "macs": 50306,
    "cycles_per_mac": 3.56,
    "mae_eps": 0.3435, "mae_d": 1.7830,
    "mae_d_i8": 1.783 + 0.032,
}

# medium-deep weights in Flash (INT8)
w_i8_bytes  = sum(lyr["Wq"].size for lyr in q1 + q2)
b_f32_bytes = sum(lyr["b"].size * 4 for lyr in q1 + q2)
scale_bytes = (len(q1) + len(q2)) * 4

# 코드 크기 추정: nn_inference_md.c → 컴파일 후 ~3KB (Thumb-2 code density)
code_bytes_est = 3000

flash_md = w_i8_bytes + b_f32_bytes + scale_bytes + code_bytes_est
sram_md  = max_h * 4 * 3 + 16 * 4  # activation buffers + stack overhead

# cycles/MAC 개선: 978 bytes 가중치 → STM32G4 I-Cache(32KB)에 완전 수용
# → Flash wait-state 없음 → cycles/MAC ≈ 2.0 (SMLAD DSP)
CYCLES_PER_MAC_MD = 2.0
total_macs_md = macs1 + macs2
latency_md_us = total_macs_md * CYCLES_PER_MAC_MD / 170e6 * 1e6

print(f"\n  [medium-deep 추정값]")
print(f"  INT8 weights      : {w_i8_bytes:,} B")
print(f"  float32 biases    : {b_f32_bytes:,} B")
print(f"  scales+misc       : {scale_bytes:,} B")
print(f"  code (estimate)   : {code_bytes_est:,} B")
print(f"  Flash total est.  : {flash_md:,} B  ({flash_md/1024:.1f} KB)")
print(f"  SRAM act. buffers : {sram_md:,} B")
print(f"  MACs              : {total_macs_md:,}")
print(f"  cycles/MAC (est.) : {CYCLES_PER_MAC_MD}")
print(f"  Latency est.      : {latency_md_us:.1f} us")

print(f"\n  [비교: sklearn 현재 모델 — 실측값]")
print(f"  Flash total       : {SKLEARN_MEAS['flash_b']:,} B  ({SKLEARN_MEAS['flash_b']/1024:.1f} KB)")
print(f"  SRAM              : {SKLEARN_MEAS['sram_b']:,} B  ({SKLEARN_MEAS['sram_b']/1024:.1f} KB)")
print(f"  MACs              : {SKLEARN_MEAS['macs']:,}")
print(f"  cycles/MAC        : {SKLEARN_MEAS['cycles_per_mac']}")
print(f"  Latency (DWT)     : {SKLEARN_MEAS['latency_us']:.0f} us")

speedup   = SKLEARN_MEAS["latency_us"] / latency_md_us
flash_red = SKLEARN_MEAS["flash_b"] / flash_md
sram_red  = SKLEARN_MEAS["sram_b"] / sram_md
macs_red  = SKLEARN_MEAS["macs"] / total_macs_md

print(f"\n  [개선 비율]")
print(f"  Flash 절감    : {flash_red:.1f}x  ({(1-flash_md/SKLEARN_MEAS['flash_b'])*100:.1f}% reduction)")
print(f"  SRAM 절감     : {sram_red:.1f}x")
print(f"  MACs 감소     : {macs_red:.1f}x")
print(f"  Latency 개선  : {speedup:.1f}x")
print(f"  MAE d 차이    : {mae_d - SKLEARN_MEAS['mae_d']:+.4f} mm ({mae_d:.4f} vs {SKLEARN_MEAS['mae_d']:.4f})")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. 결과 저장
# ═══════════════════════════════════════════════════════════════════════════════
results = {
    "medium_deep": {
        "params": p1 + p2, "macs": total_macs_md,
        "mae_eps_f32": round(mae_eps, 4), "mae_d_f32": round(mae_d, 4),
        "mae_d15_f32": round(mae_d15, 4),
        "mae_eps_i8": round(mae_eps_i8, 4), "mae_d_i8": round(mae_d_i8, 4),
        "delta_eps_i8": round(delta_eps, 4), "delta_d_i8": round(delta_d, 4),
        "flash_b_est": flash_md, "sram_b_est": sram_md,
        "latency_us_est": round(latency_md_us, 1),
        "cycles_per_mac_est": CYCLES_PER_MAC_MD,
        "S1_IN_SCALE": round(S1_IN_SCALE, 9), "S1_OUT_SCALE": round(S1_OUT_SCALE, 9),
        "S2_IN_SCALE": round(S2_IN_SCALE, 9), "S2_OUT_SCALE": round(S2_OUT_SCALE, 9),
        "w_i8_bytes": w_i8_bytes, "b_f32_bytes": b_f32_bytes,
    },
    "sklearn": {
        "params": 50306, "macs": 50306,
        "mae_eps_f32": 0.3435, "mae_d_f32": 1.7830, "mae_d15_f32": 0.3009,
        "flash_b_meas": SKLEARN_MEAS["flash_b"], "sram_b_meas": SKLEARN_MEAS["sram_b"],
        "latency_us_meas": SKLEARN_MEAS["latency_us"],
        "cycles_per_mac_meas": SKLEARN_MEAS["cycles_per_mac"],
    },
    "speedup": round(speedup, 1),
    "flash_reduction": round(flash_red, 1),
    "sram_reduction": round(sram_red, 1),
    "macs_reduction": round(macs_red, 1),
}

results_path = CHK_DIR / "medium_deep_deploy_results.json"
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n  Results saved: {results_path}")

# 모델 저장
with open(CHK_DIR / "model_stage1_md.pkl", "wb") as f: pickle.dump(M1, f)
with open(CHK_DIR / "model_stage2_md.pkl", "wb") as f: pickle.dump(M2, f)
print(f"  Models saved: model_stage1_md.pkl, model_stage2_md.pkl")

print("\n" + "=" * 60)
print("  DONE")
print("=" * 60)
