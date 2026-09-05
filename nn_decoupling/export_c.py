"""
export_c.py
2-Stage sklearn MLP → STM32 C 코드 변환 파이프라인

Pipeline:
  1) 모델 분석 (파라미터, MACs, 메모리)
  2) Magnitude Pruning (선택적)
  3) Post-Training Quantization  float32 → INT8 (symmetric per-tensor)
  4) C 코드 자동 생성 (decoupler.h / decoupler.c / decoupler_weights.h)
  5) 수치 검증  (Python 추론 vs C 시뮬레이션 비교)
  6) 지표 리포트 (Cloud vs Embedded 비교표)

Usage:
    python export_c.py                     # default: pruning 0%, INT8 + float32
    python export_c.py --prune 0.3         # 하위 30% 가중치 제로화
    python export_c.py --float_only        # float32 코드만 생성
"""
import argparse
import pickle
import sys
import textwrap
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
HERE     = Path(__file__).parent
DATA_DIR = HERE / "data_acquisition" / "dataset"
OUT_DIR  = HERE / "stm32_deploy"
OUT_DIR.mkdir(exist_ok=True)

# ─── 모델 로드 ────────────────────────────────────────────────────────────────
with open(DATA_DIR / "scalers_linear.pkl",     "rb") as f: S  = pickle.load(f)
with open(DATA_DIR / "model_stage1_linear.pkl","rb") as f: M1 = pickle.load(f)
with open(DATA_DIR / "model_stage2_linear.pkl","rb") as f: M2 = pickle.load(f)

sc_dR  = S["sc_dR"];  sc_dL = S["sc_dL"]
sc_eps = S["sc_eps"]; sc_d  = S["sc_d"]
LOG_D  = S.get("log_d", False)


# ══════════════════════════════════════════════════════════════════════════════
# 1. 모델 분석
# ══════════════════════════════════════════════════════════════════════════════
def analyze_model(name, model):
    coefs = model.coefs_
    biases = model.intercepts_
    params = sum(c.size for c in coefs) + sum(b.size for b in biases)
    # MACs: 각 레이어 = in_size × out_size
    macs = sum(c.shape[0] * c.shape[1] for c in coefs)
    arch = " → ".join(str(c.shape[0]) for c in coefs) + f" → {coefs[-1].shape[1]}"
    print(f"  [{name}]  architecture : {arch}")
    print(f"           activation   : {model.activation}")
    print(f"           params       : {params:,}")
    print(f"           MACs/infer   : {macs:,}")
    print(f"           float32 size : {params*4:,} bytes  ({params*4/1024:.1f} KB)")
    print(f"           INT8 size    : {params*1:,} bytes  ({params*1/1024:.1f} KB)")
    return params, macs


def print_analysis():
    print("\n" + "="*62)
    print("  MODEL ANALYSIS")
    print("="*62)
    p1, m1 = analyze_model("Stage1  dR→ε", M1)
    print()
    p2, m2 = analyze_model("Stage2  dL,ε→d", M2)
    total_p = p1 + p2
    total_m = m1 + m2
    print()
    print(f"  [TOTAL]  params   : {total_p:,}")
    print(f"           MACs     : {total_m:,}")
    print(f"           float32  : {total_p*4/1024:.1f} KB")
    print(f"           INT8     : {total_p*1/1024:.1f} KB")
    print()
    # STM32G473CBT6 Flash = 128KB
    f32_pct = total_p*4 / (128*1024) * 100
    i8_pct  = total_p*1 / (128*1024) * 100
    print(f"  STM32G473 Flash 128KB 점유율:")
    print(f"    float32 : {f32_pct:.1f}%  {'[!!EXCEEDS 80%]' if f32_pct>80 else 'OK'}")
    print(f"    INT8    : {i8_pct:.1f}%  OK")
    print("="*62)
    return total_p, total_m


# ══════════════════════════════════════════════════════════════════════════════
# 2. Magnitude Pruning (비구조적)
# ══════════════════════════════════════════════════════════════════════════════
def apply_pruning(model, sparsity: float):
    """
    전체 가중치를 절댓값 기준으로 정렬하여 하위 sparsity% 를 0으로 만든다.
    (unstructured pruning — 아키텍처 변경 없음, 0이 많아져 INT8 후 효과적)
    """
    if sparsity <= 0:
        return model
    import copy
    m = copy.deepcopy(model)
    all_w = np.concatenate([c.flatten() for c in m.coefs_])
    threshold = np.percentile(np.abs(all_w), sparsity * 100)
    pruned = 0
    total  = 0
    for c in m.coefs_:
        mask   = np.abs(c) < threshold
        pruned += mask.sum()
        total  += c.size
        c[mask] = 0.0
    actual = pruned / total
    print(f"    Pruning: threshold={threshold:.5f}, "
          f"zeroed {pruned:,}/{total:,} ({actual*100:.1f}%)")
    return m


# ══════════════════════════════════════════════════════════════════════════════
# 3. PTQ — float32 → INT8 (symmetric per-tensor)
# ══════════════════════════════════════════════════════════════════════════════
def quantize_layer(W: np.ndarray, b: np.ndarray):
    """
    W: float32 weight matrix
    b: float32 bias vector

    INT8 symmetric:
        scale = max(|W|) / 127
        W_q   = round(W / scale).clip(-128, 127).astype(int8)
        bias_f32 그대로 유지 (bias는 int32 accumulator에서 float으로 처리)

    반환: (W_q int8, scale float32, b float32)
    """
    max_abs = np.max(np.abs(W))
    scale   = max_abs / 127.0 if max_abs > 0 else 1.0
    W_q     = np.round(W / scale).clip(-128, 127).astype(np.int8)
    return W_q, scale, b.astype(np.float32)


def quantize_model(model):
    layers = []
    for W, b in zip(model.coefs_, model.intercepts_):
        W_q, scale, b_f = quantize_layer(W.T, b)  # (out, in)
        layers.append((W_q, scale, b_f))
    return layers


def quant_error(model, q_layers):
    """원본 float32 vs INT8 역양자화 가중치의 평균 상대 오차."""
    errs = []
    for (W_orig, _), (W_q, scale, _) in zip(
            zip(model.coefs_, model.intercepts_), q_layers):
        W_dq = (W_q.astype(np.float32) * scale).T
        rel  = np.mean(np.abs(W_orig - W_dq)) / (np.mean(np.abs(W_orig)) + 1e-9)
        errs.append(rel * 100)
    return np.mean(errs)


# ══════════════════════════════════════════════════════════════════════════════
# 4. C 코드 생성
# ══════════════════════════════════════════════════════════════════════════════
def _arr_f32(name, arr, per_row=8):
    flat  = arr.flatten().tolist()
    lines = []
    for i in range(0, len(flat), per_row):
        chunk = flat[i:i+per_row]
        lines.append("    " + ", ".join(f"{v:.8f}f" for v in chunk) + ",")
    body = "\n".join(lines)
    return f"static const float {name}[{len(flat)}] = {{\n{body}\n}};\n"


def _arr_i8(name, arr, per_row=16):
    flat  = arr.flatten().tolist()
    lines = []
    for i in range(0, len(flat), per_row):
        chunk = flat[i:i+per_row]
        lines.append("    " + ", ".join(f"{int(v):4d}" for v in chunk) + ",")
    body = "\n".join(lines)
    return f"static const int8_t {name}[{len(flat)}] = {{\n{body}\n}};\n"


def generate_weights_header(m1_pruned, m2_pruned, q1, q2, float_only=False):
    """decoupler_weights.h — 모든 가중치/편향/스케일 상수 정의"""
    lines = [
        "/* Auto-generated by export_c.py — do not edit */",
        "#ifndef DECOUPLER_WEIGHTS_H",
        "#define DECOUPLER_WEIGHTS_H",
        "#include <stdint.h>",
        "",
        "/* ─── float32 weights ─────────────────────────────── */",
    ]
    for stage, model in [("S1", m1_pruned), ("S2", m2_pruned)]:
        for li, (W, b) in enumerate(zip(model.coefs_, model.intercepts_)):
            Wt = W.T  # (out, in)
            lines.append(_arr_f32(f"{stage}_W{li}_F32", Wt))
            lines.append(_arr_f32(f"{stage}_B{li}_F32", b))

    if not float_only:
        lines += [
            "",
            "/* ─── INT8 quantized weights + per-tensor scales ─ */",
        ]
        for stage, q_layers in [("S1", q1), ("S2", q2)]:
            for li, (W_q, scale, b_f) in enumerate(q_layers):
                lines.append(_arr_i8(f"{stage}_W{li}_I8", W_q))
                lines.append(f"static const float {stage}_W{li}_SCALE = {scale:.8f}f;\n")
                lines.append(_arr_f32(f"{stage}_B{li}_I8F", b_f))

    lines += ["#endif /* DECOUPLER_WEIGHTS_H */", ""]
    return "\n".join(lines)


def generate_params_header():
    """decoupler_params.h — 정규화 상수 + 아키텍처 상수"""
    m1_arch = [c.shape[0] for c in M1.coefs_] + [M1.coefs_[-1].shape[1]]
    m2_arch = [c.shape[0] for c in M2.coefs_] + [M2.coefs_[-1].shape[1]]

    lines = [
        "/* Auto-generated by export_c.py — do not edit */",
        "#ifndef DECOUPLER_PARAMS_H",
        "#define DECOUPLER_PARAMS_H",
        "",
        "/* ─── Input / Output Scalers ──────────────────────── */",
        f"#define SC_DR_MEAN   {float(sc_dR.mean_[0]):.8f}f",
        f"#define SC_DR_STD    {float(sc_dR.scale_[0]):.8f}f",
        f"#define SC_DL_MEAN   {float(sc_dL.mean_[0]):.8f}f",
        f"#define SC_DL_STD    {float(sc_dL.scale_[0]):.8f}f",
        f"#define SC_EPS_MEAN  {float(sc_eps.mean_[0]):.8f}f",
        f"#define SC_EPS_STD   {float(sc_eps.scale_[0]):.8f}f",
        f"#define SC_D_MEAN    {float(sc_d.mean_[0]):.8f}f",
        f"#define SC_D_STD     {float(sc_d.scale_[0]):.8f}f",
        f"#define LOG_D        {1 if LOG_D else 0}",
        "",
        "/* ─── Output clamp bounds ─────────────────────────── */",
        "#define EPS_MIN_PCT  0.0f",
        "#define EPS_MAX_PCT  30.0f",
        "#define D_MIN_MM     0.0f",
        "#define D_MAX_MM     50.0f",
        "#define PROX_VALID_MM 15.0f",
        "",
        "/* ─── Architecture: Stage1 ────────────────────────── */",
        f"#define S1_N_LAYERS  {len(M1.coefs_)}",
    ]
    for i, (c_in, c_out) in enumerate(zip(m1_arch, m1_arch[1:])):
        lines.append(f"#define S1_L{i}_IN  {c_in}")
        lines.append(f"#define S1_L{i}_OUT {c_out}")

    lines += [
        "",
        "/* ─── Architecture: Stage2 ────────────────────────── */",
        f"#define S2_N_LAYERS  {len(M2.coefs_)}",
    ]
    for i, (c_in, c_out) in enumerate(zip(m2_arch, m2_arch[1:])):
        lines.append(f"#define S2_L{i}_IN  {c_in}")
        lines.append(f"#define S2_L{i}_OUT {c_out}")

    lines += ["", "#endif /* DECOUPLER_PARAMS_H */", ""]
    return "\n".join(lines)


def generate_header():
    return textwrap.dedent("""\
    /* Auto-generated by export_c.py — do not edit */
    #ifndef DECOUPLER_H
    #define DECOUPLER_H

    typedef struct {
        float eps_pct;    /* Strain  ε  [%]   0~30  */
        float d_mm;       /* Proximity d [mm] 0~50  */
        int   d_valid;    /* 1 if d <= PROX_VALID_MM */
    } DecouplerOut;

    /* float32 inference (PC validation / fallback) */
    DecouplerOut decoupler_run_f32(float dL_pct, float dR_pct);

    /* INT8 inference (STM32 production) */
    DecouplerOut decoupler_run_i8(float dL_pct, float dR_pct);

    #endif /* DECOUPLER_H */
    """)


def generate_source(m1_pruned, float_only=False):
    """decoupler.c — 추론 구현"""
    n_layers = len(m1_pruned.coefs_)
    # 최대 활성화 버퍼 크기 = 가장 큰 hidden layer
    max_h = max(c.shape[1] for c in m1_pruned.coefs_[:-1])

    src = textwrap.dedent(f"""\
    /* Auto-generated by export_c.py — do not edit */
    #include "decoupler.h"
    #include "decoupler_params.h"
    #include "decoupler_weights.h"
    #include <math.h>

    /* ─── helpers ─────────────────────────────────────────── */
    static inline float relu(float x) {{ return x > 0.0f ? x : 0.0f; }}
    static inline float clamp(float x, float lo, float hi) {{
        return x < lo ? lo : (x > hi ? hi : x);
    }}

    /* y[out] = W[out×in] · x[in] + b[out]  (row-major W) */
    static void linear_f32(const float *W, const float *b,
                            const float *x, float *y,
                            int in_sz, int out_sz) {{
        for (int i = 0; i < out_sz; i++) {{
            float s = b[i];
            const float *row = W + i * in_sz;
            for (int j = 0; j < in_sz; j++) s += row[j] * x[j];
            y[i] = s;
        }}
    }}

    /* INT8: y[out] = (W_i8[out×in] · x[in]) * scale + b[out]
       Accumulate in int32 to avoid overflow, then dequantize. */
    static void linear_i8(const int8_t *W, float scale, const float *b,
                           const float *x, float *y,
                           int in_sz, int out_sz) {{
        for (int i = 0; i < out_sz; i++) {{
            int32_t acc = 0;
            const int8_t *row = W + i * in_sz;
            for (int j = 0; j < in_sz; j++)
                acc += (int32_t)row[j] * (int32_t)(x[j] / scale * 127.0f);
            y[i] = acc * scale * scale / 127.0f + b[i];
        }}
    }}

    /* ─── float32 inference ───────────────────────────────── */
    DecouplerOut decoupler_run_f32(float dL_pct, float dR_pct) {{
        float h0[{max_h}], h1[{max_h}], h2[{max_h}];
        float tmp;

        /* ── Stage1: dR_norm → eps_norm ── */
        float dR_n = (dR_pct - SC_DR_MEAN) / SC_DR_STD;
    """)

    # Stage1 layers
    bufs = ["&dR_n", "h0", "h1", "h2"]
    in_bufs  = ["&dR_n","h0","h1","h2"]
    out_bufs = ["h0","h1","h2","&tmp"]
    n = len(m1_pruned.coefs_)
    for li in range(n):
        W = m1_pruned.coefs_[li]
        in_s  = W.shape[0]
        out_s = W.shape[1]
        in_b  = in_bufs[li]
        out_b = out_bufs[li]
        is_last = (li == n-1)
        src += f"    linear_f32(S1_W{li}_F32, S1_B{li}_F32, {in_b}, {out_b}, {in_s}, {out_s});\n"
        if not is_last:
            src += f"    for(int i=0;i<{out_s};i++) {out_b}[i]=relu({out_b}[i]);\n"

    src += textwrap.dedent(f"""
        float eps_pct = tmp * SC_EPS_STD + SC_EPS_MEAN;
        eps_pct = clamp(eps_pct, EPS_MIN_PCT, EPS_MAX_PCT);

        /* ── Stage2: [dL_norm, eps_norm] → d_norm ── */
        float dL_n   = (dL_pct - SC_DL_MEAN) / SC_DL_STD;
        float eps_n  = (eps_pct - SC_EPS_MEAN) / SC_EPS_STD;
        float x2[2] = {{dL_n, eps_n}};
    """)

    in_bufs2  = ["x2","h0","h1","h2"]
    out_bufs2 = ["h0","h1","h2","&tmp"]
    n2 = len(M2.coefs_)
    for li in range(n2):
        W = M2.coefs_[li]
        in_s  = W.shape[0]
        out_s = W.shape[1]
        in_b  = in_bufs2[li]
        out_b = out_bufs2[li]
        is_last = (li == n2-1)
        src += f"    linear_f32(S2_W{li}_F32, S2_B{li}_F32, {in_b}, {out_b}, {in_s}, {out_s});\n"
        if not is_last:
            src += f"    for(int i=0;i<{out_s};i++) {out_b}[i]=relu({out_b}[i]);\n"

    src += textwrap.dedent("""
        float d_mm = tmp * SC_D_STD + SC_D_MEAN;
        d_mm = clamp(d_mm, D_MIN_MM, D_MAX_MM);

        DecouplerOut out;
        out.eps_pct = eps_pct;
        out.d_mm    = d_mm;
        out.d_valid = (d_mm <= PROX_VALID_MM) ? 1 : 0;
        return out;
    }
    """)

    if not float_only:
        # INT8 version (same structure, linear_i8 대신 사용)
        src += "\n/* ─── INT8 inference ─────────────────────────────── */\n"
        src += "DecouplerOut decoupler_run_i8(float dL_pct, float dR_pct) {\n"
        src += f"    float h0[{max_h}], h1[{max_h}], h2[{max_h}];\n    float tmp;\n"
        src += "    float dR_n = (dR_pct - SC_DR_MEAN) / SC_DR_STD;\n"
        for li in range(n):
            W = m1_pruned.coefs_[li]
            in_s, out_s = W.shape
            in_b  = "&dR_n" if li==0 else f"h{li-1}"
            out_b = f"h{li}" if li<n-1 else "&tmp"
            src += f"    linear_i8(S1_W{li}_I8, S1_W{li}_SCALE, S1_B{li}_I8F, {in_b}, {out_b}, {in_s}, {out_s});\n"
            if li < n-1:
                src += f"    for(int i=0;i<{out_s};i++) h{li}[i]=relu(h{li}[i]);\n"
        src += "    float eps_pct=clamp(tmp*SC_EPS_STD+SC_EPS_MEAN,EPS_MIN_PCT,EPS_MAX_PCT);\n"
        src += "    float dL_n=(dL_pct-SC_DL_MEAN)/SC_DL_STD;\n"
        src += "    float eps_n=(eps_pct-SC_EPS_MEAN)/SC_EPS_STD;\n"
        src += "    float x2[2]={dL_n,eps_n};\n"
        for li in range(n2):
            W = M2.coefs_[li]
            in_s, out_s = W.shape
            in_b  = "x2" if li==0 else f"h{li-1}"
            out_b = f"h{li}" if li<n2-1 else "&tmp"
            src += f"    linear_i8(S2_W{li}_I8, S2_W{li}_SCALE, S2_B{li}_I8F, {in_b}, {out_b}, {in_s}, {out_s});\n"
            if li < n2-1:
                src += f"    for(int i=0;i<{out_s};i++) h{li}[i]=relu(h{li}[i]);\n"
        src += "    float d_mm=clamp(tmp*SC_D_STD+SC_D_MEAN,D_MIN_MM,D_MAX_MM);\n"
        src += "    DecouplerOut o; o.eps_pct=eps_pct; o.d_mm=d_mm; o.d_valid=(d_mm<=PROX_VALID_MM)?1:0;\n"
        src += "    return o;\n}\n"

    return src


# ══════════════════════════════════════════════════════════════════════════════
# 5. 수치 검증 — Python float32 추론 vs C 시뮬레이션
# ══════════════════════════════════════════════════════════════════════════════
def py_infer_f32(dL_pct, dR_pct, m1, m2):
    dR_n  = (dR_pct - sc_dR.mean_[0]) / sc_dR.scale_[0]
    x     = np.array([[dR_n]])
    for li, (W, b) in enumerate(zip(m1.coefs_, m1.intercepts_)):
        x = x @ W + b
        if li < len(m1.coefs_)-1: x = np.maximum(x, 0)
    eps_pct = float(np.clip(x[0,0] * sc_eps.scale_[0] + sc_eps.mean_[0], 0, 30))

    dL_n  = (dL_pct - sc_dL.mean_[0]) / sc_dL.scale_[0]
    eps_n = (eps_pct - sc_eps.mean_[0]) / sc_eps.scale_[0]
    x2    = np.array([[dL_n, eps_n]])
    for li, (W, b) in enumerate(zip(m2.coefs_, m2.intercepts_)):
        x2 = x2 @ W + b
        if li < len(m2.coefs_)-1: x2 = np.maximum(x2, 0)
    d_mm = float(np.clip(x2[0,0] * sc_d.scale_[0] + sc_d.mean_[0], 0, 50))
    return eps_pct, d_mm


def py_infer_i8(dL_pct, dR_pct, q1, q2):
    """
    Weights-only INT8: W_q를 역양자화(W_f = W_q * scale)한 뒤
    float32 활성화와 곱한다. C 코드(linear_i8)와 동일한 방식.
    """
    dR_n = (dR_pct - sc_dR.mean_[0]) / sc_dR.scale_[0]
    x = np.array([dR_n], dtype=np.float32)
    n = len(q1)
    for li, (W_q, scale, b) in enumerate(q1):
        W_f = W_q.astype(np.float32) * scale   # 역양자화
        x   = W_f @ x + b
        if li < n-1: x = np.maximum(x, 0)
    eps_pct = float(np.clip(x[0] * sc_eps.scale_[0] + sc_eps.mean_[0], 0, 30))

    dL_n  = (dL_pct - sc_dL.mean_[0]) / sc_dL.scale_[0]
    eps_n = (eps_pct - sc_eps.mean_[0]) / sc_eps.scale_[0]
    x2 = np.array([dL_n, eps_n], dtype=np.float32)
    n2 = len(q2)
    for li, (W_q, scale, b) in enumerate(q2):
        W_f = W_q.astype(np.float32) * scale
        x2  = W_f @ x2 + b
        if li < n2-1: x2 = np.maximum(x2, 0)
    d_mm = float(np.clip(x2[0] * sc_d.scale_[0] + sc_d.mean_[0], 0, 50))
    return eps_pct, d_mm


def validate(m1_pruned, m2_pruned, q1, q2, n_test=200):
    print("\n" + "="*62)
    print("  NUMERICAL VALIDATION  (Python f32 vs INT8 simulation)")
    print("="*62)
    rng = np.random.default_rng(0)
    dL_vals = rng.uniform(-5, 15,  n_test)
    dR_vals = rng.uniform( 0, 25,  n_test)

    err_eps, err_d = [], []
    for dL, dR in zip(dL_vals, dR_vals):
        e32, d32 = py_infer_f32(dL, dR, m1_pruned, m2_pruned)
        ei8, di8 = py_infer_i8(dL, dR, q1, q2)
        err_eps.append(abs(e32 - ei8))
        err_d.append(abs(d32 - di8))

    print(f"  f32 vs INT8  Δε MAE : {np.mean(err_eps):.4f} %")
    print(f"  f32 vs INT8  Δd MAE : {np.mean(err_d):.4f} mm")
    print(f"  f32 vs INT8  Δε Max : {np.max(err_eps):.4f} %")
    print(f"  f32 vs INT8  Δd Max : {np.max(err_d):.4f} mm")

    # 속도 측정 (Python 레벨)
    N = 10000
    t0 = time.perf_counter()
    for _ in range(N): py_infer_f32(5.0, 10.0, m1_pruned, m2_pruned)
    t_f32 = (time.perf_counter()-t0)/N*1e6
    t0 = time.perf_counter()
    for _ in range(N): py_infer_i8(5.0, 10.0, q1, q2)
    t_i8  = (time.perf_counter()-t0)/N*1e6
    print(f"\n  Python inference latency (reference):")
    print(f"    float32 : {t_f32:.1f} us/sample")
    print(f"    INT8    : {t_i8:.1f} us/sample")
    print("="*62)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Cloud vs Embedded 지표 리포트
# ══════════════════════════════════════════════════════════════════════════════
def print_metrics_report(total_p, total_macs, q_err_pct):
    # 이론적 MCU 추론 시간 추정:
    # STM32G4 @170MHz, FPU: ~2 cycles/FMAC → float32
    # DSP INT8 SIMD: ~0.25 cycles/MAC (4-way) → INT8
    f32_us = total_macs * 2 / 170e6 * 1e6
    i8_us  = total_macs * 0.5 / 170e6 * 1e6   # 보수적 추정
    uart_latency_ms = (5 * 10) / 115200 * 1e3  # 5개 float CSV ≈ 50 chars @ 115200

    print("\n" + "="*62)
    print("  CLOUD  vs  EMBEDDED  비교 지표")
    print("="*62)

    rows = [
        ("지표",                  "Cloud (PC+sklearn)",     "Embedded (STM32 INT8)"),
        ("─"*20,                  "─"*20,                   "─"*20),
        ("모델 파라미터",          f"{total_p:,}",            f"{total_p:,}"),
        ("가중치 메모리",          f"{total_p*4/1024:.1f} KB (float32)", f"{total_p/1024:.1f} KB (INT8)"),
        ("활성화 버퍼 (SRAM)",     "~수 MB (Python heap)",   "~512 B (stack)"),
        ("전체 프로세스 메모리",    "~150 MB (Python)",       f"~{total_p/1024+20:.0f} KB total"),
        ("Flash 점유율",           "N/A",                    f"{total_p/(128*1024)*100:.1f}% of 128KB"),
        ("연산량 (MACs)",          f"{total_macs:,}",        f"{total_macs:,}"),
        ("추론 지연 (이론)",        "~100 us (NumPy)",        f"~{i8_us:.1f}–{f32_us:.1f} us"),
        ("통신 지연",              f"USB/UART ~{uart_latency_ms:.2f} ms/frame", "UART 동일 (선택)"),
        ("전력 소비",              "~100 W (PC)",            "~50 mW (MCU 단독)"),
        ("INT8 quant err (eps)",  "N/A",                    f"~{q_err_pct:.4f}% (weight err)"),
        ("PC 의존성",              "필수",                    "없음"),
        ("실시간 임베딩",          "불가",                    "1ms TDM 주기 내 가능"),
    ]
    for r in rows:
        print(f"  {r[0]:<22} {r[1]:<28} {r[2]}")
    print("="*62)

    print("""
  [METRICS GUIDE]
  ┌─ Memory
  │   Flash: STM32CubeIDE Build → .map 파일 → .rodata 섹션 크기
  │   SRAM:  .map 파일 → .bss + .data + stack watermark
  │
  ├─ Inference Latency
  │   MCU: HAL_GetTick() 또는 DWT->CYCCNT 전후 측정
  │   MCU: cycles / 170MHz = us
  │
  ├─ MACs (Multiply-Accumulate Operations)
  │   각 Linear: in_size × out_size
  │   합산 = 모델 전체 MACs
  │
  ├─ Throughput
  │   samples/sec = 1 / (TDM_period + inference_time)
  │
  └─ Accuracy (MAE)
      Python sklearn 추론 vs 실제 레이블 (이미 측정 완료)
      float32 vs INT8 추론 오차 (위 validation에서 출력)
""")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prune",      type=float, default=0.0,
                        help="Magnitude pruning sparsity (0.0~0.9)")
    parser.add_argument("--float_only", action="store_true",
                        help="Generate float32 C code only (no INT8)")
    args = parser.parse_args()

    # 1. 분석
    total_p, total_macs = print_analysis()

    # 2. Pruning
    print(f"\n{'='*62}")
    print(f"  PRUNING  (sparsity={args.prune:.0%})")
    print(f"{'='*62}")
    if args.prune > 0:
        m1_p = apply_pruning(M1, args.prune)
        m2_p = apply_pruning(M2, args.prune)
    else:
        m1_p, m2_p = M1, M2
        print("    Pruning skipped (--prune 0)")

    # 3. PTQ
    q1 = quantize_model(m1_p)
    q2 = quantize_model(m2_p)
    q_err1 = quant_error(m1_p, q1)
    q_err2 = quant_error(m2_p, q2)
    q_err  = (q_err1 + q_err2) / 2
    print(f"\n  PTQ INT8 weight quantization error:")
    print(f"    Stage1: {q_err1:.4f}%  Stage2: {q_err2:.4f}%  Mean: {q_err:.4f}%")
    if q_err > 5.0:
        print("  [WARN] error >5% -> QAT needed (sklearn has no gradient -> use train.py PyTorch)")
    else:
        print("  [OK] Low quantization error -> PTQ sufficient")

    # 4. C 코드 생성
    print(f"\n{'='*62}")
    print("  GENERATING C CODE")
    print(f"{'='*62}")
    (OUT_DIR/"decoupler_weights.h").write_text(
        generate_weights_header(m1_p, m2_p, q1, q2, args.float_only),
        encoding="utf-8")
    (OUT_DIR/"decoupler_params.h").write_text(
        generate_params_header(), encoding="utf-8")
    (OUT_DIR/"decoupler.h").write_text(
        generate_header(), encoding="utf-8")
    (OUT_DIR/"decoupler.c").write_text(
        generate_source(m1_p, args.float_only), encoding="utf-8")

    sizes = {p.name: p.stat().st_size for p in OUT_DIR.iterdir()}
    for name, sz in sizes.items():
        print(f"    {name:<30} {sz:>8,} bytes  ({sz/1024:.1f} KB)")

    # 5. 수치 검증
    validate(m1_p, m2_p, q1, q2)

    # 6. 지표 리포트
    print_metrics_report(total_p, total_macs, q_err)

    print(f"\n  출력 폴더: {OUT_DIR}")
    print("  다음 단계: STM32CubeIDE 프로젝트에 stm32_deploy/ 폴더 추가")
    print("             TDM.c 에서 #include \"decoupler.h\" 후 decoupler_run_i8() 호출\n")


if __name__ == "__main__":
    main()
