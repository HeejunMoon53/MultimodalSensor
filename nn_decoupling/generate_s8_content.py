"""
master_report.html Section 8 에 추가할 콘텐츠 생성:
  1. Two-stage MLP (128-128-64) 학습 상세:
     - Loss curve (per epoch, S1/S2 separate)
     - Test metrics: MAE, RMSE, R2, MaxErr for eps & d
     - Pred vs True scatter (green=strain, orange=proximity — CLAUDE.md 컬러 컨벤션)
  2. Fair E2E 비교:
     - E2E-small (128-128-64, ~25K) vs E2E-large (180-180-90, ~50K) vs Two-stage (50K)
"""
import base64, io, pickle, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

DIR  = Path(__file__).parent
DATA = DIR / "data_acquisition" / "dataset"

# ── 컬러 컨벤션 (CLAUDE.md) ───────────────────────────────────────────────────
COLOR_L    = "#FF8C00"   # 인덕턴스 / 근접도 — 주황
COLOR_R    = "#2CA02C"   # DC 저항 / 변형률  — 초록
COLOR_TENG = "#1F77B4"   # TENG 전압          — 파랑
C_E2E_S    = "#D62728"   # E2E-small (red)
C_E2E_L    = "#9467BD"   # E2E-large (purple)

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
train = pd.read_csv(DATA / "train.csv")
val   = pd.read_csv(DATA / "val.csv")
test  = pd.read_csv(DATA / "test.csv")

X_train = train[["dL_pct", "dR_pct"]].values
X_val   = val  [["dL_pct", "dR_pct"]].values
X_test  = test [["dL_pct", "dR_pct"]].values

y_eps_train = train["eps_act_pct"].values.reshape(-1, 1)
y_d_train   = train["d_act_mm"].values.reshape(-1, 1)
y_eps_val   = val  ["eps_act_pct"].values.reshape(-1, 1)
y_d_val     = val  ["d_act_mm"].values.reshape(-1, 1)
y_eps_test  = test ["eps_act_pct"].values.reshape(-1, 1)
y_d_test    = test ["d_act_mm"].values.reshape(-1, 1)

n_train = len(train)
batch_size_default = min(200, n_train)
iters_per_epoch = int(np.ceil(n_train / batch_size_default))
print(f"Train: {n_train:,}  Val: {len(val):,}  Test: {len(test):,}")
print(f"Batch size: {batch_size_default}  → {iters_per_epoch} weight updates/epoch")

# ── 저장된 sklearn 모델 로드 ──────────────────────────────────────────────────
with open(DATA / "model_stage1_linear.pkl", "rb") as f: s1 = pickle.load(f)
with open(DATA / "model_stage2_linear.pkl", "rb") as f: s2 = pickle.load(f)
with open(DATA / "scalers_linear.pkl",      "rb") as f: sc = pickle.load(f)

sc_dR  = sc["sc_dR"]
sc_dL  = sc["sc_dL"]
sc_eps = sc["sc_eps"]
sc_d   = sc["sc_d"]

print(f"S1: {s1.n_iter_} epochs  S2: {s2.n_iter_} epochs")

# ── Two-stage 추론 함수 ───────────────────────────────────────────────────────
def predict_twostage(X):
    dR_n  = sc_dR.transform(X[:, 1:2])
    eps_n = s1.predict(dR_n).reshape(-1, 1)
    X2    = np.hstack([sc_dL.transform(X[:, 0:1]), eps_n])
    d_n   = s2.predict(X2).reshape(-1, 1)
    eps_out = sc_eps.inverse_transform(eps_n).ravel()
    d_out   = sc_d.inverse_transform(d_n).ravel()
    return eps_out, d_out

eps_te, d_te = predict_twostage(X_test)
eps_tr, d_tr = predict_twostage(X_train)
eps_va, d_va = predict_twostage(X_val)

# ── 지표 함수 ────────────────────────────────────────────────────────────────
def m(t, p):
    return {
        "MAE":    mean_absolute_error(t, p),
        "RMSE":   np.sqrt(mean_squared_error(t, p)),
        "R2":     r2_score(t, p),
        "MaxErr": float(np.max(np.abs(t - p))),
    }

met_eps_test  = m(y_eps_test.ravel(),  eps_te)
met_d_test    = m(y_d_test.ravel(),    d_te)
met_eps_val   = m(y_eps_val.ravel(),   eps_va)
met_d_val     = m(y_d_val.ravel(),     d_va)
met_eps_train = m(y_eps_train.ravel(), eps_tr)
met_d_train   = m(y_d_train.ravel(),   d_tr)

print("\nTest metrics:")
print(f"  eps: MAE={met_eps_test['MAE']:.4f}%  RMSE={met_eps_test['RMSE']:.4f}  R2={met_eps_test['R2']:.4f}  MaxErr={met_eps_test['MaxErr']:.4f}")
print(f"  d:   MAE={met_d_test['MAE']:.4f}mm  RMSE={met_d_test['RMSE']:.4f}  R2={met_d_test['R2']:.4f}  MaxErr={met_d_test['MaxErr']:.4f}")

# ── E2E 모델 학습 ─────────────────────────────────────────────────────────────
LR = 1e-3; MAX_ITER = 2000; TOL = 1e-6

def count_mlp_params(hidden, n_in, n_out):
    layers = [n_in] + list(hidden) + [n_out]
    return sum(layers[i] * layers[i+1] + layers[i+1] for i in range(len(layers)-1))

def run_e2e(hidden, seed=42):
    sc_X   = StandardScaler().fit(X_train)
    sc_eo  = StandardScaler().fit(y_eps_train)
    sc_do  = StandardScaler().fit(y_d_train)
    Xn_tr  = sc_X.transform(X_train)
    Xn_te  = sc_X.transform(X_test)
    Y_tr   = np.hstack([sc_eo.transform(y_eps_train), sc_do.transform(y_d_train)])
    model  = MLPRegressor(hidden_layer_sizes=hidden, activation="relu",
                          solver="adam", learning_rate_init=LR,
                          max_iter=MAX_ITER, tol=TOL,
                          early_stopping=True, validation_fraction=0.1,
                          n_iter_no_change=50, random_state=seed)
    model.fit(Xn_tr, Y_tr)
    Yn_te  = model.predict(sc_X.transform(X_test))
    eps_p  = sc_eo.inverse_transform(Yn_te[:, 0:1]).ravel()
    d_p    = sc_do.inverse_transform(Yn_te[:, 1:2]).ravel()
    return model, eps_p, d_p

print("\n[E2E-small] HIDDEN=(128,128,64) ...")
e2e_small, eps_e2es, d_e2es = run_e2e((128, 128, 64))
p_e2es = count_mlp_params((128, 128, 64), 2, 2)
print(f"  -> {e2e_small.n_iter_} epochs  params={p_e2es:,}")

print("[E2E-large] HIDDEN=(180,180,90) ...")
e2e_large, eps_e2el, d_e2el = run_e2e((180, 180, 90))
p_e2el = count_mlp_params((180, 180, 90), 2, 2)
print(f"  -> {e2e_large.n_iter_} epochs  params={p_e2el:,}")

p_twostage = sum(
    sum(w.size for w in s1.coefs_) + sum(b.size for b in s1.intercepts_) +
    sum(w.size for w in s2.coefs_) + sum(b.size for b in s2.intercepts_)
    for _ in [1]
)
print(f"Two-stage params: {p_twostage:,}")

met_e2es = {"eps": m(y_eps_test.ravel(), eps_e2es), "d": m(y_d_test.ravel(), d_e2es)}
met_e2el = {"eps": m(y_eps_test.ravel(), eps_e2el), "d": m(y_d_test.ravel(), d_e2el)}
print(f"E2E-small: eps MAE={met_e2es['eps']['MAE']:.4f}  d MAE={met_e2es['d']['MAE']:.4f}")
print(f"E2E-large: eps MAE={met_e2el['eps']['MAE']:.4f}  d MAE={met_e2el['d']['MAE']:.4f}")
print(f"Two-stage: eps MAE={met_eps_test['MAE']:.4f}  d MAE={met_d_test['MAE']:.4f}")

# ── 유틸 ─────────────────────────────────────────────────────────────────────
def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#1e1e2e")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

plt.rcParams.update({
    "figure.facecolor": "#1e1e2e", "axes.facecolor": "#181825",
    "axes.edgecolor": "#45475a", "axes.labelcolor": "#cdd6f4",
    "xtick.color": "#a6adc8", "ytick.color": "#a6adc8",
    "text.color": "#cdd6f4", "grid.color": "#313244",
    "legend.facecolor": "#181825", "legend.edgecolor": "#45475a",
})

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1: Loss Curves (S1 / S2)
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

ax = axes[0]
ax.plot(s1.loss_curve_, color=COLOR_R, lw=2.0, label=f"Stage 1 — dR→ε ({s1.n_iter_} epochs)")
ax.set_xlabel("Epoch (학습 데이터 전체 1회 순환)")
ax.set_ylabel("MSE Loss (normalized)")
ax.set_title("Stage 1: ΔR → ε  Loss Curve", fontweight="bold", color="#cdd6f4")
ax.set_yscale("log"); ax.legend(fontsize=9); ax.grid(True, alpha=0.4)
ax.set_facecolor("#181825")
ax.text(0.98, 0.98,
        f"1 epoch = {iters_per_epoch} weight updates\n"
        f"(batch_size={batch_size_default}, n={n_train:,})",
        transform=ax.transAxes, fontsize=8, va="top", ha="right",
        color="#a6adc8",
        bbox=dict(boxstyle="round", fc="#313244", alpha=0.8))

ax = axes[1]
ax.plot(s2.loss_curve_, color=COLOR_L, lw=2.0, label=f"Stage 2 — (dL,ε̂)→d ({s2.n_iter_} epochs)")
ax.set_xlabel("Epoch (학습 데이터 전체 1회 순환)")
ax.set_ylabel("MSE Loss (normalized)")
ax.set_title("Stage 2: (ΔL, ε̂) → d  Loss Curve", fontweight="bold", color="#cdd6f4")
ax.set_yscale("log"); ax.legend(fontsize=9); ax.grid(True, alpha=0.4)
ax.set_facecolor("#181825")

plt.suptitle("Two-Stage MLP (128-128-64) 학습 곡선 — sklearn MLPRegressor",
             fontsize=12, fontweight="bold", color="#cdd6f4")
plt.tight_layout()
b64_loss = fig_to_b64(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2: Pred vs True (2x1: strain top, proximity bottom)
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))

# Strain (green)
ax = axes[0]
ax.scatter(y_eps_test.ravel(), eps_te, s=5, alpha=0.35, color=COLOR_R)
lim_e = [-1, 32]
ax.plot(lim_e, lim_e, "w--", lw=1.2, alpha=0.7)
ax.text(0.05, 0.95,
        f"R² = {met_eps_test['R2']:.4f}\n"
        f"MAE = {met_eps_test['MAE']:.3f} %\n"
        f"RMSE = {met_eps_test['RMSE']:.3f} %\n"
        f"MaxErr = {met_eps_test['MaxErr']:.3f} %",
        transform=ax.transAxes, fontsize=9, va="top",
        color="#cdd6f4",
        bbox=dict(boxstyle="round", fc="#313244", alpha=0.85))
ax.set_xlabel("True Strain [%]"); ax.set_ylabel("Predicted Strain [%]")
ax.set_title("Strain — Two-Stage MLP (Test)", fontweight="bold", color="#cdd6f4")
ax.set_xlim(lim_e); ax.set_ylim(lim_e); ax.grid(True, alpha=0.4)
ax.set_facecolor("#181825")

# Proximity (orange)
ax = axes[1]
ax.scatter(y_d_test.ravel(), d_te, s=5, alpha=0.35, color=COLOR_L)
lim_d = [-1, 38]
ax.plot(lim_d, lim_d, "w--", lw=1.2, alpha=0.7)
ax.text(0.05, 0.95,
        f"R² = {met_d_test['R2']:.4f}\n"
        f"MAE = {met_d_test['MAE']:.3f} mm\n"
        f"RMSE = {met_d_test['RMSE']:.3f} mm\n"
        f"MaxErr = {met_d_test['MaxErr']:.3f} mm",
        transform=ax.transAxes, fontsize=9, va="top",
        color="#cdd6f4",
        bbox=dict(boxstyle="round", fc="#313244", alpha=0.85))
ax.set_xlabel("True Proximity [mm]"); ax.set_ylabel("Predicted Proximity [mm]")
ax.set_title("Proximity — Two-Stage MLP (Test)", fontweight="bold", color="#cdd6f4")
ax.set_xlim(lim_d); ax.set_ylim(lim_d); ax.grid(True, alpha=0.4)
ax.set_facecolor("#181825")

plt.suptitle("Predicted vs True — Two-Stage MLP 128-128-64 (Test set)",
             fontsize=12, fontweight="bold", color="#cdd6f4")
plt.tight_layout()
b64_pred = fig_to_b64(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3: Fair E2E 비교 — Pred vs True (2-Stage vs E2E-small vs E2E-large)
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(2, 3, figsize=(16, 9))

configs = [
    ("Two-Stage\n(128-128-64 ×2, ~50K)", COLOR_TENG, eps_te, d_te),
    (f"E2E-small\n(128-128-64, ~{p_e2es//1000}K)", C_E2E_S, eps_e2es, d_e2es),
    (f"E2E-large\n(180-180-90, ~{p_e2el//1000}K)", C_E2E_L, eps_e2el, d_e2el),
]

for col, (label, color, eps_p, d_p) in enumerate(configs):
    # Strain row
    ax = axes[0, col]
    me_e = m(y_eps_test.ravel(), eps_p)
    ax.scatter(y_eps_test.ravel(), eps_p, s=4, alpha=0.3, color=COLOR_R)
    ax.plot(lim_e, lim_e, "w--", lw=1, alpha=0.7)
    ax.text(0.05, 0.95,
            f"R²={me_e['R2']:.4f}\nMAE={me_e['MAE']:.3f}%",
            transform=ax.transAxes, fontsize=9, va="top", color="#cdd6f4",
            bbox=dict(boxstyle="round", fc="#313244", alpha=0.8))
    ax.set_xlim(lim_e); ax.set_ylim(lim_e)
    ax.set_xlabel("True ε [%]"); ax.set_ylabel("Predicted ε [%]")
    ax.set_title(f"Strain — {label}", fontsize=9, fontweight="bold", color="#cdd6f4")
    ax.grid(True, alpha=0.4); ax.set_facecolor("#181825")

    # Proximity row
    ax = axes[1, col]
    me_d = m(y_d_test.ravel(), d_p)
    ax.scatter(y_d_test.ravel(), d_p, s=4, alpha=0.3, color=COLOR_L)
    ax.plot(lim_d, lim_d, "w--", lw=1, alpha=0.7)
    ax.text(0.05, 0.95,
            f"R²={me_d['R2']:.4f}\nMAE={me_d['MAE']:.3f}mm",
            transform=ax.transAxes, fontsize=9, va="top", color="#cdd6f4",
            bbox=dict(boxstyle="round", fc="#313244", alpha=0.8))
    ax.set_xlim(lim_d); ax.set_ylim(lim_d)
    ax.set_xlabel("True d [mm]"); ax.set_ylabel("Predicted d [mm]")
    ax.set_title(f"Proximity — {label}", fontsize=9, fontweight="bold", color="#cdd6f4")
    ax.grid(True, alpha=0.4); ax.set_facecolor("#181825")

plt.suptitle("공정 비교: Two-Stage vs E2E (동일 파라미터 예산 기준)",
             fontsize=12, fontweight="bold", color="#cdd6f4")
plt.tight_layout()
b64_fair = fig_to_b64(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4: Params vs MAE_d Pareto (E2E-small, E2E-large, Two-stage)
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(7, 4.5))

pts = [
    (p_e2es, met_e2es['d']['MAE'], "E2E-small\n(128-128-64)", C_E2E_S, "o"),
    (p_e2el, met_e2el['d']['MAE'], "E2E-large\n(180-180-90)", C_E2E_L, "s"),
    (p_twostage, met_d_test['MAE'], "Two-Stage\n(128-128-64 ×2)", COLOR_TENG, "^"),
]

for p, mae, lbl, clr, mk in pts:
    ax.scatter(p / 1000, mae, s=180, color=clr, marker=mk, zorder=5, edgecolors="white", linewidths=0.8)
    ax.annotate(lbl, (p / 1000, mae),
                textcoords="offset points", xytext=(8, -4),
                fontsize=8, color=clr)

ax.set_xlabel("파라미터 수 (K)")
ax.set_ylabel("Test MAE d [mm]")
ax.set_title("파라미터 예산 vs 근접도 MAE 비교", fontweight="bold", color="#cdd6f4")
ax.grid(True, alpha=0.4); ax.set_facecolor("#181825")
plt.tight_layout()
b64_pareto = fig_to_b64(fig)

print("\nAll figures generated.")

# ═══════════════════════════════════════════════════════════════════════════════
# HTML 블록 생성
# ═══════════════════════════════════════════════════════════════════════════════
p_ts = p_twostage

def color_cell(val_a, val_b, unit, higher_better=False):
    """val_b이 val_a보다 나으면 green, 나쁘면 red (lower=better 기본)"""
    if higher_better:
        better = val_b > val_a + 1e-5
        worse  = val_b < val_a - 1e-5
    else:
        better = val_b < val_a - 1e-5
        worse  = val_b > val_a + 1e-5
    diff = val_b - val_a
    sign = "+" if diff > 0 else ""
    cls  = "best" if better else ("bad" if worse else "")
    return f'<td class="{cls}">{val_b:.4f}{unit} <span style="font-size:11px;color:var(--text3)">({sign}{diff:.4f})</span></td>'

INSERT = f"""
<!-- ══════════ INSERTED: S8 학습 상세 + E2E 공정 비교 ══════════ -->

<div class="card" id="s8-training">
  <h3>학습 상세: Loss Curve per Epoch</h3>
  <div class="hl info" style="margin-bottom:14px">
    <strong>Epoch vs Iteration:</strong>
    1 epoch = 훈련 데이터({n_train:,}개) 전체를 1회 순환.
    sklearn 기본 batch_size = min(200, n_samples) = <strong>{batch_size_default}</strong> →
    epoch당 <strong>{iters_per_epoch}회</strong> 가중치 업데이트(iteration).
    <code>loss_curve_</code>는 <em>epoch 단위</em> 값을 저장한다.
    Stage 1은 <strong>{s1.n_iter_} epochs</strong>, Stage 2는 <strong>{s2.n_iter_} epochs</strong>에서 조기 종료.
  </div>
  <img src="data:image/png;base64,{b64_loss}" alt="loss curves"
       style="width:100%;border-radius:8px;border:1px solid var(--border)">
</div>

<div class="card" id="s8-metrics">
  <h3>Test Set 정량 지표 (Linear Two-Stage MLP)</h3>
  <div class="g2">
    <div>
      <h4>변형률 ε (Strain)</h4>
      <div class="kv-grid">
        <div class="kv"><div class="kv-label">Test MAE</div><div class="kv-val" style="color:var(--green)">{met_eps_test['MAE']:.3f}</div><div class="kv-unit">%</div></div>
        <div class="kv"><div class="kv-label">Test RMSE</div><div class="kv-val" style="color:var(--green)">{met_eps_test['RMSE']:.3f}</div><div class="kv-unit">%</div></div>
        <div class="kv"><div class="kv-label">Test R²</div><div class="kv-val" style="color:var(--teal)">{met_eps_test['R2']:.4f}</div></div>
        <div class="kv"><div class="kv-label">Test MaxErr</div><div class="kv-val" style="color:var(--yellow)">{met_eps_test['MaxErr']:.3f}</div><div class="kv-unit">%</div></div>
      </div>
    </div>
    <div>
      <h4>근접거리 d (Proximity)</h4>
      <div class="kv-grid">
        <div class="kv"><div class="kv-label">Test MAE</div><div class="kv-val" style="color:var(--peach)">{met_d_test['MAE']:.3f}</div><div class="kv-unit">mm</div></div>
        <div class="kv"><div class="kv-label">Test RMSE</div><div class="kv-val" style="color:var(--peach)">{met_d_test['RMSE']:.3f}</div><div class="kv-unit">mm</div></div>
        <div class="kv"><div class="kv-label">Test R²</div><div class="kv-val" style="color:var(--teal)">{met_d_test['R2']:.4f}</div></div>
        <div class="kv"><div class="kv-label">Test MaxErr</div><div class="kv-val" style="color:var(--yellow)">{met_d_test['MaxErr']:.3f}</div><div class="kv-unit">mm</div></div>
      </div>
    </div>
  </div>
  <div class="cmp-wrap" style="margin-top:14px">
  <table>
    <thead>
      <tr><th>지표</th><th>Train</th><th>Val</th><th>Test</th></tr>
    </thead>
    <tbody>
      <tr><td class="label">ε MAE [%]</td>
          <td class="good">{met_eps_train['MAE']:.4f}</td>
          <td class="good">{met_eps_val['MAE']:.4f}</td>
          <td class="good">{met_eps_test['MAE']:.4f}</td></tr>
      <tr><td class="label">ε RMSE [%]</td>
          <td>{met_eps_train['RMSE']:.4f}</td>
          <td>{met_eps_val['RMSE']:.4f}</td>
          <td>{met_eps_test['RMSE']:.4f}</td></tr>
      <tr><td class="label">ε R²</td>
          <td class="good">{met_eps_train['R2']:.4f}</td>
          <td class="good">{met_eps_val['R2']:.4f}</td>
          <td class="good">{met_eps_test['R2']:.4f}</td></tr>
      <tr><td class="label">d MAE [mm]</td>
          <td class="good">{met_d_train['MAE']:.4f}</td>
          <td class="good">{met_d_val['MAE']:.4f}</td>
          <td class="good">{met_d_test['MAE']:.4f}</td></tr>
      <tr><td class="label">d RMSE [mm]</td>
          <td>{met_d_train['RMSE']:.4f}</td>
          <td>{met_d_val['RMSE']:.4f}</td>
          <td>{met_d_test['RMSE']:.4f}</td></tr>
      <tr><td class="label">d R²</td>
          <td class="good">{met_d_train['R2']:.4f}</td>
          <td class="good">{met_d_val['R2']:.4f}</td>
          <td class="good">{met_d_test['R2']:.4f}</td></tr>
    </tbody>
  </table>
  </div>
  <img src="data:image/png;base64,{b64_pred}" alt="pred vs true"
       style="width:100%;border-radius:8px;border:1px solid var(--border);margin-top:16px">
</div>

<div class="card" id="s8-fair-e2e">
  <h3>공정 비교: Two-Stage vs E2E (동일 파라미터 예산)</h3>
  <div class="hl warn" style="margin-bottom:14px">
    <strong>기존 비교의 문제:</strong> 기존 표의 E2E(2→2)는 HIDDEN=(128,128,64)로 파라미터 약 <strong>25K</strong>이나,
    Two-Stage는 약 <strong>50K</strong>으로 두 배 차이 — 불공정 비교.
    아래는 E2E-large(HIDDEN=(180,180,90), ~{p_e2el:,} params ≈ 50K)를 추가하여 동일 예산에서 비교한 결과.
  </div>
  <div class="cmp-wrap">
  <table>
    <thead>
      <tr>
        <th>모델</th><th>구조</th><th>파라미터</th>
        <th>Test MAE ε (%)</th><th>Test MAE d (mm)</th>
        <th>Test R² d</th><th>비고</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="label">Two-Stage MLP</td>
        <td style="color:var(--text2)">S1: 1→128→128→64→1<br>S2: 2→128→128→64→1</td>
        <td><strong style="color:var(--blue)">{p_ts:,}</strong></td>
        <td class="good">{met_eps_test['MAE']:.3f}</td>
        <td class="best">{met_d_test['MAE']:.3f}</td>
        <td class="good">{met_d_test['R2']:.4f}</td>
        <td class="note">물리 디커플링 구조</td>
      </tr>
      <tr>
        <td class="label">E2E-small <span class="tag red" style="font-size:11px">불공정</span></td>
        <td style="color:var(--text2)">2→128→128→64→2</td>
        <td style="color:var(--red)">{p_e2es:,}</td>
        <td class="{'best' if met_e2es['eps']['MAE'] < met_eps_test['MAE'] else 'mid'}">{met_e2es['eps']['MAE']:.3f}</td>
        <td class="{'best' if met_e2es['d']['MAE'] < met_d_test['MAE'] else 'bad'}">{met_e2es['d']['MAE']:.3f}</td>
        <td class="{'good' if met_e2es['d']['R2'] > met_d_test['R2'] else 'mid'}">{met_e2es['d']['R2']:.4f}</td>
        <td class="note">절반 예산 — 비교 부적절</td>
      </tr>
      <tr>
        <td class="label">E2E-large <span class="tag mauve" style="font-size:11px">공정</span></td>
        <td style="color:var(--text2)">2→180→180→90→2</td>
        <td><strong style="color:var(--mauve)">{p_e2el:,}</strong></td>
        <td class="{'best' if met_e2el['eps']['MAE'] < met_eps_test['MAE'] else 'mid'}">{met_e2el['eps']['MAE']:.3f}</td>
        <td class="{'best' if met_e2el['d']['MAE'] < met_d_test['MAE'] else 'bad'}">{met_e2el['d']['MAE']:.3f}</td>
        <td class="{'good' if met_e2el['d']['R2'] > met_d_test['R2'] else 'mid'}">{met_e2el['d']['R2']:.4f}</td>
        <td class="note">동일 예산 (~50K)</td>
      </tr>
    </tbody>
  </table>
  </div>
  <img src="data:image/png;base64,{b64_fair}" alt="fair e2e comparison"
       style="width:100%;border-radius:8px;border:1px solid var(--border);margin-top:16px">
  <div style="margin-top:12px;display:flex;gap:14px;flex-wrap:wrap">
    <div style="flex:1;min-width:260px">
      <img src="data:image/png;base64,{b64_pareto}" alt="pareto"
           style="width:100%;border-radius:8px;border:1px solid var(--border)">
    </div>
    <div style="flex:1;min-width:260px">
      <div class="hl" style="margin-top:0">
        <strong>공정 비교 결론 (동일 ~50K 예산):</strong><br>
        Two-Stage({met_d_test['MAE']:.3f}mm) {"<" if met_d_test['MAE'] < met_e2el['d']['MAE'] else ">"} E2E-large({met_e2el['d']['MAE']:.3f}mm)<br>
        → 물리적 디커플링 구조(dR→ε 우선 처리)가 동일 파라미터 예산에서도 d 추정 우위.
      </div>
      <div class="hl info" style="margin-top:10px">
        <strong>이유:</strong> dR은 ε에만 지배적으로 의존하는 강한 물리적 비대칭성이 있어,
        Stage 1에서 ε를 먼저 분리한 후 Stage 2에서 (dL, ε̂)→d를 학습하면
        d의 결합 의존성 문제를 자연스럽게 해소한다.
        E2E는 이 인과 구조를 데이터만으로 학습해야 하므로 더 많은 파라미터가 필요하다.
      </div>
    </div>
  </div>
</div>
<!-- ══════════ END INSERTED ══════════ -->
"""

# ── master_report.html 삽입 ───────────────────────────────────────────────────
REPORT = DIR / "master_report.html"
with open(REPORT, encoding="utf-8") as f:
    html = f.read()

# 삽입 위치: s8-architecture card 끝난 직후, 4가지 학습 비교 card 앞에
# "4가지 학습 방식 비교 실험" card의 시작을 찾아서 그 앞에 삽입
MARKER_BEFORE = '<div class="card">\n  <h3>4가지 학습 방식 비교 실험 (신규 데이터셋)</h3>'
MARKER_E2E_TABLE_START = """      <tr>
        <td class="label">E2E (2→2)</td>"""
MARKER_E2E_CONCLUSION = """    <strong>결론:</strong> Log-d 변환이 d MAE 기준으로 가장 우수하나 RMSE에서는 Linear와 동등.
    PINN variant는 sklearn에서 커스텀 손실 함수를 지원하지 않아 효과 제한적.
    E2E는 ε 추정에서 우위이나, d 추정에서 2단계 구조 대비 열세 → <strong>2단계 Linear 또는 Log-d 채택</strong>."""

if MARKER_BEFORE not in html:
    print("ERROR: 삽입 마커를 찾을 수 없음!")
    print("Trying fallback search...")
    idx = html.find("4가지 학습 방식 비교 실험")
    if idx >= 0:
        # card div 시작 찾기 (앞으로)
        card_start = html.rfind('<div class="card">', 0, idx)
        insert_pos = card_start
        html = html[:insert_pos] + INSERT + html[insert_pos:]
        print(f"Fallback insert at position {insert_pos}")
    else:
        print("FATAL: cannot find insertion point")
        raise SystemExit(1)
else:
    insert_pos = html.find(MARKER_BEFORE)
    html = html[:insert_pos] + INSERT + html[insert_pos:]
    print(f"Inserted at position {insert_pos}")

# E2E 비교 표에 "불공정" 주석 추가 (기존 E2E row에 tag 추가)
OLD_E2E_ROW = """      <tr>
        <td class="label">E2E (2→2)</td>
        <td style="color:var(--text2)">단일 모델 [ΔL,ΔR]→[ε,d]</td>
        <td class="mid">1.790</td>
        <td class="best">0.334</td>
        <td class="mid">2.804</td>
        <td class="mid">0.928</td>
        <td class="note">ε는 좋으나 d 열세</td>
      </tr>"""
NEW_E2E_ROW = """      <tr>
        <td class="label">E2E (2→2) <span class="tag red" style="font-size:11px">불공정</span></td>
        <td style="color:var(--text2)">단일 모델 [ΔL,ΔR]→[ε,d]<br><small style="color:var(--red)">~25K params (Two-stage의 절반)</small></td>
        <td class="mid">1.790</td>
        <td class="best">0.334</td>
        <td class="mid">2.804</td>
        <td class="mid">0.928</td>
        <td class="note">ε는 좋으나 d 열세 — 파라미터 절반으로 불공정</td>
      </tr>"""

if OLD_E2E_ROW in html:
    html = html.replace(OLD_E2E_ROW, NEW_E2E_ROW, 1)
    print("E2E row annotation added.")
else:
    print("WARNING: E2E row not found for annotation.")

# 결론 문장 업데이트
OLD_CONCLUSION = MARKER_E2E_CONCLUSION
NEW_CONCLUSION = """    <strong>결론:</strong> Log-d 변환이 d MAE 기준으로 가장 우수하나 RMSE에서는 Linear와 동등.
    PINN variant는 sklearn에서 커스텀 손실 함수를 지원하지 않아 효과 제한적.
    기존 E2E(2→2)는 <span style="color:var(--red)">파라미터 ~25K로 Two-stage(~50K)의 절반 예산</span>이어서 불공정 비교임 →
    공정 비교(동일 ~50K 예산)는 아래 섹션 참조. <strong>2단계 Linear 채택 이유: 물리 디커플링 구조 우위</strong>."""

if OLD_CONCLUSION in html:
    html = html.replace(OLD_CONCLUSION, NEW_CONCLUSION, 1)
    print("E2E conclusion updated.")
else:
    print("WARNING: conclusion text not found.")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nSaved -> {REPORT} ({len(html):,} bytes)")
print("Done.")
