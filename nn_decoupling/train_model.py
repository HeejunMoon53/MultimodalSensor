"""
2-Stage Decoupled MLP 비교 학습:
  1) Linear-d  (MLP baseline)
  2) Log-scale d  (MLP with log1p target)
  3) PINN  (NumpyMLP + physics gradient)

Stage 1: dR_pct -> eps_act_pct
Stage 2: (dL_pct, eps_hat) -> d_act_mm

PINN Physics model:
  R: dR = alpha1*eps + alpha2*eps^2
  L: dL = beta1*eps + beta2*exp(-k*d)

출력: dataset/training_report.html
"""
import base64, io, pickle, warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

DIR  = Path(__file__).parent
DATA = DIR / "data_acquisition" / "dataset"
OUT  = DATA

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

print(f"Train: {len(train):,}  Val: {len(val):,}  Test: {len(test):,}")

HIDDEN   = (128, 128, 64)
LR       = 1e-3
MAX_ITER = 2000
TOL      = 1e-6

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
C_MLP   = "#1F77B4"
C_LOG   = "#9467BD"
C_PINN  = "#E377C2"

# ═══════════════════════════════════════════════════════════════════════════════
# 물리 모델 파라미터 피팅 (PINN용)
# ═══════════════════════════════════════════════════════════════════════════════
_eps_all = np.concatenate([y_eps_train.ravel(), y_eps_val.ravel()])
_dR_all  = np.concatenate([X_train[:, 1], X_val[:, 1]])
_dL_all  = np.concatenate([X_train[:, 0], X_val[:, 0]])
_d_all   = np.concatenate([y_d_train.ravel(), y_d_val.ravel()])

def _r_model(eps, a1, a2):
    return a1 * eps + a2 * eps**2

def _l_model(Xed, b1, b2, k):
    eps, d = Xed
    return b1 * eps + b2 * np.exp(-k * d)

try:
    popt_r, _ = curve_fit(_r_model, _eps_all, _dR_all, p0=[0.5, 0.01])
    alpha1, alpha2 = popt_r
except Exception:
    alpha1, alpha2 = 0.5, 0.01

try:
    popt_l, _ = curve_fit(
        _l_model, (_eps_all, _d_all), _dL_all,
        p0=[0.05, -15.0, 0.08],
        bounds=([-5, -200, 0.001], [5, 0, 2]),
        maxfev=30000,
    )
    beta1, beta2, k_p = popt_l
except Exception as e:
    print(f"L physics fit fallback: {e}")
    beta1, beta2, k_p = 0.05, -15.0, 0.08

phys_r2_r = r2_score(_dR_all, _r_model(_eps_all, alpha1, alpha2))
phys_r2_l = r2_score(_dL_all, _l_model((_eps_all, _d_all), beta1, beta2, k_p))
print(f"Physics R: alpha1={alpha1:.4f}  alpha2={alpha2:.6f}  R2={phys_r2_r:.4f}")
print(f"Physics L: beta1={beta1:.4f}  beta2={beta2:.4f}  k={k_p:.4f}  R2={phys_r2_l:.4f}")


# ═══════════════════════════════════════════════════════════════════════════════
# NumpyMLP — Adam + 선택적 physics gradient
# ═══════════════════════════════════════════════════════════════════════════════
class NumpyMLP:
    def __init__(self, dims, lr=1e-3, seed=42):
        rng = np.random.default_rng(seed)
        self.W = [rng.normal(0, np.sqrt(2 / dims[i]), (dims[i], dims[i + 1]))
                  for i in range(len(dims) - 1)]
        self.b = [np.zeros(dims[i + 1]) for i in range(len(dims) - 1)]
        self.lr = lr
        self.loss_curve_ = []
        self.n_iter_ = 0
        self._mW = [np.zeros_like(w) for w in self.W]
        self._mb = [np.zeros_like(b) for b in self.b]
        self._vW = [np.zeros_like(w) for w in self.W]
        self._vb = [np.zeros_like(b) for b in self.b]
        self._t  = 0

    def _fwd(self, X):
        a = [X]
        for W, b in zip(self.W[:-1], self.b[:-1]):
            a.append(np.maximum(0, a[-1] @ W + b))
        a.append(a[-1] @ self.W[-1] + self.b[-1])
        return a

    def predict(self, X):
        return self._fwd(X)[-1]

    def _adam_step(self, a, delta):
        b1, b2, eps = 0.9, 0.999, 1e-8
        self._t += 1
        for i in range(len(self.W) - 1, -1, -1):
            n   = len(a[0])
            gW  = a[i].T @ delta / n
            gb  = delta.mean(axis=0)
            if i > 0:
                delta = (delta @ self.W[i].T) * (a[i] > 0)
            self._mW[i] = b1 * self._mW[i] + (1 - b1) * gW
            self._mb[i] = b1 * self._mb[i] + (1 - b1) * gb
            self._vW[i] = b2 * self._vW[i] + (1 - b2) * gW ** 2
            self._vb[i] = b2 * self._vb[i] + (1 - b2) * gb ** 2
            mW = self._mW[i] / (1 - b1 ** self._t)
            mb = self._mb[i] / (1 - b1 ** self._t)
            vW = self._vW[i] / (1 - b2 ** self._t)
            vb = self._vb[i] / (1 - b2 ** self._t)
            self.W[i] -= self.lr * mW / (np.sqrt(vW) + eps)
            self.b[i] -= self.lr * mb / (np.sqrt(vb) + eps)

    def fit(self, X, y, phys_grad_fn=None, lambda_phys=0.0,
            X_val=None, y_val=None, max_iter=2000, tol=1e-6,
            n_iter_no_change=50, batch_size=512):
        n = len(X)
        rng = np.random.default_rng(42)
        best_val = np.inf
        no_imp   = 0

        for it in range(max_iter):
            if it % 50 == 0:
                print(f"    epoch {it:4d}", end="\r")
            idx     = rng.permutation(n)
            ep_loss = 0.0
            nb      = 0
            for s in range(0, n, batch_size):
                bi = idx[s:s + batch_size]
                Xb, yb = X[bi], y[bi]
                a    = self._fwd(Xb)
                pred = a[-1]
                res  = pred - yb
                delta = 2 * res
                ep_loss += float((res ** 2).mean())
                if phys_grad_fn is not None and lambda_phys > 0:
                    pg    = phys_grad_fn(pred, Xb)
                    delta = delta + lambda_phys * 2 * pg
                delta = np.clip(delta, -5.0, 5.0)
                self._adam_step(a, delta)
                nb += 1

            self.loss_curve_.append(ep_loss / nb)

            if X_val is not None:
                vl = float(((self.predict(X_val) - y_val) ** 2).mean())
                if vl < best_val - tol:
                    best_val = vl
                    no_imp   = 0
                else:
                    no_imp += 1
                if no_imp >= n_iter_no_change:
                    break

        print()
        self.n_iter_ = it + 1
        return self


# ═══════════════════════════════════════════════════════════════════════════════
# run_pipeline — sklearn MLP (linear or log-d)
# ═══════════════════════════════════════════════════════════════════════════════
def run_pipeline(log_d: bool):
    tag = "log-d" if log_d else "linear"
    print(f"\n{'='*52}\n  Mode: {tag}\n{'='*52}")

    sc_dR  = StandardScaler().fit(X_train[:, 1:2])
    sc_dL  = StandardScaler().fit(X_train[:, 0:1])
    sc_eps = StandardScaler().fit(y_eps_train)

    if log_d:
        y_d_tr_raw = np.log1p(y_d_train)
        y_d_va_raw = np.log1p(y_d_val)
        y_d_te_raw = np.log1p(y_d_test)
    else:
        y_d_tr_raw = y_d_train
        y_d_va_raw = y_d_val
        y_d_te_raw = y_d_test

    sc_d = StandardScaler().fit(y_d_tr_raw)

    Xn_dR_tr = sc_dR.transform(X_train[:, 1:2])
    Xn_dR_va = sc_dR.transform(X_val  [:, 1:2])
    Xn_dR_te = sc_dR.transform(X_test [:, 1:2])
    yn_eps_tr = sc_eps.transform(y_eps_train)
    yn_d_tr   = sc_d.transform(y_d_tr_raw)

    def make_s2(X, eps_n):
        return np.hstack([sc_dL.transform(X[:, 0:1]), eps_n])

    print(f"[{tag}] Stage 1 ...")
    s1 = MLPRegressor(hidden_layer_sizes=HIDDEN, activation="relu",
                      solver="adam", learning_rate_init=LR,
                      max_iter=MAX_ITER, tol=TOL,
                      early_stopping=True, validation_fraction=0.1,
                      n_iter_no_change=50, random_state=42)
    s1.fit(Xn_dR_tr, yn_eps_tr.ravel())
    print(f"  -> {s1.n_iter_} iters")

    eps_hat_tr_n = s1.predict(Xn_dR_tr).reshape(-1, 1)

    print(f"[{tag}] Stage 2 ...")
    s2 = MLPRegressor(hidden_layer_sizes=HIDDEN, activation="relu",
                      solver="adam", learning_rate_init=LR,
                      max_iter=MAX_ITER, tol=TOL,
                      early_stopping=True, validation_fraction=0.1,
                      n_iter_no_change=50, random_state=42)
    s2.fit(make_s2(X_train, eps_hat_tr_n), yn_d_tr.ravel())
    print(f"  -> {s2.n_iter_} iters")

    def predict(X):
        dR_n  = sc_dR.transform(X[:, 1:2])
        eps_n = s1.predict(dR_n).reshape(-1, 1)
        d_n   = s2.predict(make_s2(X, eps_n)).reshape(-1, 1)
        eps_out = sc_eps.inverse_transform(eps_n).ravel()
        d_scaled = sc_d.inverse_transform(d_n).ravel()
        d_out   = np.expm1(d_scaled) if log_d else d_scaled
        return eps_out, d_out

    eps_tr, d_tr = predict(X_train)
    eps_va, d_va = predict(X_val)
    eps_te, d_te = predict(X_test)

    def m(t, p):
        return {"MAE": mean_absolute_error(t, p),
                "RMSE": np.sqrt(mean_squared_error(t, p)),
                "R2": r2_score(t, p),
                "MaxErr": np.max(np.abs(t - p))}

    metrics = {
        "eps_train": m(y_eps_train.ravel(), eps_tr),
        "eps_val":   m(y_eps_val.ravel(),   eps_va),
        "eps_test":  m(y_eps_test.ravel(),  eps_te),
        "d_train":   m(y_d_train.ravel(),   d_tr),
        "d_val":     m(y_d_val.ravel(),     d_va),
        "d_test":    m(y_d_test.ravel(),    d_te),
    }
    for k, v in metrics.items():
        print(f"  {k:12s}  MAE={v['MAE']:.3f}  R2={v['R2']:.4f}")

    with open(OUT / f"model_stage1_{tag}.pkl", "wb") as f: pickle.dump(s1, f)
    with open(OUT / f"model_stage2_{tag}.pkl", "wb") as f: pickle.dump(s2, f)
    with open(OUT / f"scalers_{tag}.pkl", "wb") as f:
        pickle.dump({"sc_dR": sc_dR, "sc_dL": sc_dL,
                     "sc_eps": sc_eps, "sc_d": sc_d, "log_d": log_d}, f)

    return {"tag": tag, "s1": s1, "s2": s2, "metrics": metrics,
            "preds": {"eps_tr": eps_tr, "eps_va": eps_va, "eps_te": eps_te,
                      "d_tr": d_tr, "d_va": d_va, "d_te": d_te}}


# ═══════════════════════════════════════════════════════════════════════════════
# run_pinn — NumpyMLP + physics gradient
# ═══════════════════════════════════════════════════════════════════════════════
def run_pinn(lambda_phys=0.1):
    tag = "pinn"
    print(f"\n{'='*52}\n  Mode: PINN (lambda={lambda_phys})\n{'='*52}")

    sc_dR  = StandardScaler().fit(X_train[:, 1:2])
    sc_dL  = StandardScaler().fit(X_train[:, 0:1])
    sc_eps = StandardScaler().fit(y_eps_train)
    sc_d   = StandardScaler().fit(y_d_train)

    Xn_dR_tr = sc_dR.transform(X_train[:, 1:2])
    Xn_dR_va = sc_dR.transform(X_val  [:, 1:2])
    Xn_dR_te = sc_dR.transform(X_test [:, 1:2])
    yn_eps_tr = sc_eps.transform(y_eps_train)
    yn_eps_va = sc_eps.transform(y_eps_val)
    yn_d_tr   = sc_d.transform(y_d_train)
    yn_d_va   = sc_d.transform(y_d_val)

    def phys_grad_s1(pred, Xb):
        eps = sc_eps.mean_[0] + pred.ravel() * sc_eps.scale_[0]
        dR  = sc_dR.mean_[0]  + Xb.ravel()  * sc_dR.scale_[0]
        dR_phys  = alpha1 * eps + alpha2 * eps ** 2
        phys_res = (dR_phys - dR) / sc_dR.scale_[0]
        d_res_d_epsn = (alpha1 + 2 * alpha2 * eps) * sc_eps.scale_[0] / sc_dR.scale_[0]
        return (phys_res * d_res_d_epsn).reshape(-1, 1)

    def phys_grad_s2(pred, Xb):
        d   = sc_d.mean_[0]   + pred.ravel() * sc_d.scale_[0]
        dL  = sc_dL.mean_[0]  + Xb[:, 0]    * sc_dL.scale_[0]
        eps = sc_eps.mean_[0] + Xb[:, 1]    * sc_eps.scale_[0]
        d_safe   = np.maximum(d, 0.0)
        dL_phys  = beta1 * eps + beta2 * np.exp(-k_p * d_safe)
        phys_res = (dL_phys - dL) / sc_dL.scale_[0]
        d_res_d_dn = (-k_p * beta2 * np.exp(-k_p * d_safe)) * sc_d.scale_[0] / sc_dL.scale_[0]
        return (phys_res * d_res_d_dn).reshape(-1, 1)

    print(f"[pinn] Stage 1 ...")
    s1 = NumpyMLP([1] + list(HIDDEN) + [1], lr=LR)
    s1.fit(Xn_dR_tr, yn_eps_tr,
           phys_grad_fn=phys_grad_s1, lambda_phys=lambda_phys,
           X_val=Xn_dR_va, y_val=yn_eps_va,
           max_iter=MAX_ITER, tol=TOL, n_iter_no_change=50)
    print(f"  -> {s1.n_iter_} iters")

    eps_hat_tr_n = s1.predict(Xn_dR_tr)
    eps_hat_va_n = s1.predict(Xn_dR_va)
    eps_hat_te_n = s1.predict(Xn_dR_te)

    def make_s2(X_raw, eps_n):
        return np.hstack([sc_dL.transform(X_raw[:, 0:1]), eps_n])

    X2_tr = make_s2(X_train, eps_hat_tr_n)
    X2_va = make_s2(X_val,   eps_hat_va_n)

    print(f"[pinn] Stage 2 ...")
    s2 = NumpyMLP([2] + list(HIDDEN) + [1], lr=LR)
    s2.fit(X2_tr, yn_d_tr,
           phys_grad_fn=phys_grad_s2, lambda_phys=lambda_phys,
           X_val=X2_va, y_val=yn_d_va,
           max_iter=MAX_ITER, tol=TOL, n_iter_no_change=50)
    print(f"  -> {s2.n_iter_} iters")

    def predict(X_raw):
        dR_n  = sc_dR.transform(X_raw[:, 1:2])
        eps_n = s1.predict(dR_n)
        d_n   = s2.predict(make_s2(X_raw, eps_n))
        eps_out = sc_eps.mean_[0] + eps_n.ravel() * sc_eps.scale_[0]
        d_out   = sc_d.mean_[0]   + d_n.ravel()   * sc_d.scale_[0]
        return eps_out, d_out

    eps_tr, d_tr = predict(X_train)
    eps_va, d_va = predict(X_val)
    eps_te, d_te = predict(X_test)

    def m(t, p):
        return {"MAE": mean_absolute_error(t, p),
                "RMSE": np.sqrt(mean_squared_error(t, p)),
                "R2": r2_score(t, p),
                "MaxErr": np.max(np.abs(t - p))}

    metrics = {
        "eps_train": m(y_eps_train.ravel(), eps_tr),
        "eps_val":   m(y_eps_val.ravel(),   eps_va),
        "eps_test":  m(y_eps_test.ravel(),  eps_te),
        "d_train":   m(y_d_train.ravel(),   d_tr),
        "d_val":     m(y_d_val.ravel(),     d_va),
        "d_test":    m(y_d_test.ravel(),    d_te),
    }
    for k, v in metrics.items():
        print(f"  {k:12s}  MAE={v['MAE']:.3f}  R2={v['R2']:.4f}")

    with open(OUT / f"model_stage1_{tag}.pkl", "wb") as f: pickle.dump(s1, f)
    with open(OUT / f"model_stage2_{tag}.pkl", "wb") as f: pickle.dump(s2, f)
    with open(OUT / f"scalers_{tag}.pkl", "wb") as f:
        pickle.dump({"sc_dR": sc_dR, "sc_dL": sc_dL, "sc_eps": sc_eps, "sc_d": sc_d,
                     "alpha1": alpha1, "alpha2": alpha2,
                     "beta1": beta1, "beta2": beta2, "k": k_p,
                     "lambda_phys": lambda_phys}, f)

    return {"tag": tag, "s1": s1, "s2": s2, "metrics": metrics,
            "preds": {"eps_tr": eps_tr, "eps_va": eps_va, "eps_te": eps_te,
                      "d_tr": d_tr, "d_va": d_va, "d_te": d_te}}


# ═══════════════════════════════════════════════════════════════════════════════
# run_end2end — Single MLP, 2 inputs (dL, dR) → 2 outputs (eps, d) simultaneously
# Stage2 없이 Stage1만으로 두 출력 동시 예측 (End-to-End baseline)
# ═══════════════════════════════════════════════════════════════════════════════
def run_end2end():
    tag = "e2e"
    print(f"\n{'='*52}\n  Mode: End-to-End (2in→2out, Stage1 only)\n{'='*52}")

    sc_X   = StandardScaler().fit(X_train)
    sc_eps = StandardScaler().fit(y_eps_train)
    sc_d   = StandardScaler().fit(y_d_train)

    Xn_tr = sc_X.transform(X_train)
    Xn_va = sc_X.transform(X_val)
    Xn_te = sc_X.transform(X_test)

    yn_eps_tr = sc_eps.transform(y_eps_train)
    yn_d_tr   = sc_d.transform(y_d_train)
    Y_tr = np.hstack([yn_eps_tr, yn_d_tr])

    print(f"[{tag}] Training MLP (2in→2out) ...")
    model = MLPRegressor(hidden_layer_sizes=HIDDEN, activation="relu",
                         solver="adam", learning_rate_init=LR,
                         max_iter=MAX_ITER, tol=TOL,
                         early_stopping=True, validation_fraction=0.1,
                         n_iter_no_change=50, random_state=42)
    model.fit(Xn_tr, Y_tr)
    print(f"  -> {model.n_iter_} iters")

    def predict(X):
        Xn  = sc_X.transform(X)
        Y_n = model.predict(Xn)
        eps_out = sc_eps.inverse_transform(Y_n[:, 0:1]).ravel()
        d_out   = sc_d.inverse_transform(Y_n[:, 1:2]).ravel()
        return eps_out, d_out

    eps_tr, d_tr = predict(X_train)
    eps_va, d_va = predict(X_val)
    eps_te, d_te = predict(X_test)

    def m(t, p):
        return {"MAE": mean_absolute_error(t, p),
                "RMSE": np.sqrt(mean_squared_error(t, p)),
                "R2": r2_score(t, p),
                "MaxErr": np.max(np.abs(t - p))}

    metrics = {
        "eps_train": m(y_eps_train.ravel(), eps_tr),
        "eps_val":   m(y_eps_val.ravel(),   eps_va),
        "eps_test":  m(y_eps_test.ravel(),  eps_te),
        "d_train":   m(y_d_train.ravel(),   d_tr),
        "d_val":     m(y_d_val.ravel(),     d_va),
        "d_test":    m(y_d_test.ravel(),    d_te),
    }
    for k, v in metrics.items():
        print(f"  {k:12s}  MAE={v['MAE']:.3f}  R2={v['R2']:.4f}")

    return {"tag": tag, "model": model, "metrics": metrics,
            "preds": {"eps_tr": eps_tr, "eps_va": eps_va, "eps_te": eps_te,
                      "d_tr": d_tr, "d_va": d_va, "d_te": d_te}}


# ═══════════════════════════════════════════════════════════════════════════════
# 학습 실행
# ═══════════════════════════════════════════════════════════════════════════════
LAMBDA_PHYS = 0.1

res_lin  = run_pipeline(log_d=False)
res_log  = run_pipeline(log_d=True)
res_pinn = run_pinn(lambda_phys=LAMBDA_PHYS)
res_e2e  = run_end2end()


# ═══════════════════════════════════════════════════════════════════════════════
# 공통 유틸
# ═══════════════════════════════════════════════════════════════════════════════
def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

D_BINS = np.arange(0, 39, 6)
d_ctrs = (D_BINS[:-1] + D_BINS[1:]) / 2
d_true_test = y_d_test.ravel()

EPS_E = np.linspace(0, 30, 13)
D_E   = np.linspace(0, 36, 13)

def err_map_2d(pred_eps, pred_d):
    ne, nd = len(EPS_E) - 1, len(D_E) - 1
    em_e = np.full((ne, nd), np.nan)
    em_d = np.full((ne, nd), np.nan)
    ei = np.clip(np.digitize(y_eps_test.ravel(), EPS_E) - 1, 0, ne - 1)
    di = np.clip(np.digitize(y_d_test.ravel(),   D_E)   - 1, 0, nd - 1)
    for i in range(ne):
        for j in range(nd):
            sel = (ei == i) & (di == j)
            if sel.sum():
                em_e[i, j] = mean_absolute_error(y_eps_test.ravel()[sel], pred_eps[sel])
                em_d[i, j] = mean_absolute_error(y_d_test.ravel()[sel],   pred_d[sel])
    return em_e, em_d

ext_2d = [D_E[0], D_E[-1], EPS_E[0], EPS_E[-1]]


# ═══════════════════════════════════════════════════════════════════════════════
# ── 섹션 1: Linear vs Log-d 비교 그래프 ──────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# (A) Loss curves — linear vs log-d
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, s_key, title, color in [
    (axes[0], "s1", "Stage 1: dR -> eps (공통)", COLOR_R),
    (axes[1], "s2", "Stage 2: (dL+eps_hat) -> d", COLOR_L),
]:
    mlp = res_lin[s_key]
    log = res_log[s_key]
    ax.plot(mlp.loss_curve_, color=color, lw=1.5, ls="-",  alpha=0.85, label="linear")
    ax.plot(log.loss_curve_, color=color, lw=1.5, ls="--", alpha=0.85, label="log-d")
    ax.set_xlabel("Epoch"); ax.set_ylabel("MSE (normalized)")
    ax.set_title(title, fontweight="bold")
    ax.set_yscale("log"); ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
plt.suptitle("Loss Curves — Linear vs Log-d", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_A_loss = fig_to_b64(fig)

# (B) Pred vs True — d only, linear vs log-d
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, res in [(axes[0], res_lin), (axes[1], res_log)]:
    d_te   = res["preds"]["d_te"]
    lim    = [-1, 38]
    r2  = r2_score(d_true_test, d_te)
    mae = mean_absolute_error(d_true_test, d_te)
    ax.scatter(d_true_test, d_te, s=5, alpha=0.35, color=COLOR_L)
    ax.plot(lim, lim, "k--", lw=1)
    ax.text(0.05, 0.93, f"R2={r2:.4f}\nMAE={mae:.3f} mm",
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    ax.set_xlabel("True Proximity [mm]"); ax.set_ylabel("Predicted [mm]")
    ax.set_title(f"Proximity — {res['tag']}", fontweight="bold")
    ax.set_xlim(lim); ax.set_ylim(lim); ax.grid(True, alpha=0.3)
plt.tight_layout()
b64_B_pred_d = fig_to_b64(fig)

# (C) MAE per bin — linear vs log-d
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, sig_key, true_arr, ylabel, color in [
    (axes[0], "d_te",   y_d_test.ravel(),   "Proximity MAE [mm]", COLOR_L),
    (axes[1], "eps_te", y_eps_test.ravel(), "Strain MAE [%]",     COLOR_R),
]:
    maes_lin, maes_log = [], []
    for lo, hi in zip(D_BINS[:-1], D_BINS[1:]):
        sel = (d_true_test >= lo) & (d_true_test < hi)
        if sel.sum() == 0:
            maes_lin.append(np.nan); maes_log.append(np.nan); continue
        maes_lin.append(mean_absolute_error(true_arr[sel], res_lin["preds"][sig_key][sel]))
        maes_log.append(mean_absolute_error(true_arr[sel], res_log["preds"][sig_key][sel]))
    w = (D_BINS[1] - D_BINS[0]) * 0.38
    ax.bar(d_ctrs - w/2, maes_lin, width=w, label="linear", color=color, alpha=0.55)
    ax.bar(d_ctrs + w/2, maes_log, width=w, label="log-d",  color=color, alpha=1.0)
    ax.set_xlabel("True Proximity bin [mm]"); ax.set_ylabel(ylabel)
    ax.set_title(ylabel.split(" MAE")[0] + " MAE per distance bin", fontweight="bold")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3, axis="y")
plt.suptitle("MAE by Distance Bin — Linear vs Log-d (Test)", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_C_bar = fig_to_b64(fig)

# (D) Residuals — linear vs log-d
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, res in [(axes[0], res_lin), (axes[1], res_log)]:
    d_te  = res["preds"]["d_te"]
    resid = d_te - d_true_test
    sc = ax.scatter(d_true_test, resid, s=4, alpha=0.25, c=d_true_test,
                    cmap="RdYlGn_r", vmin=0, vmax=36)
    plt.colorbar(sc, ax=ax, label="True d [mm]", shrink=0.85)
    ax.axhline(0, color="black", lw=1)
    sig2 = np.std(resid) * 2
    ax.axhline( sig2, color="gray", lw=0.8, ls="--", label=f"+-2sigma ({sig2:.2f} mm)")
    ax.axhline(-sig2, color="gray", lw=0.8, ls="--")
    ax.set_xlabel("True Proximity [mm]"); ax.set_ylabel("Residual [mm]")
    ax.set_title(f"Proximity Residuals — {res['tag']}", fontweight="bold")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
plt.tight_layout()
b64_D_resid = fig_to_b64(fig)

# (E) MAE heatmap — linear vs log-d
em_e_lin, em_d_lin = err_map_2d(res_lin["preds"]["eps_te"], res_lin["preds"]["d_te"])
em_e_log, em_d_log = err_map_2d(res_log["preds"]["eps_te"], res_log["preds"]["d_te"])

vmax_d_lg = np.nanmax([em_d_lin, em_d_log])
vmax_e_lg = np.nanmax([em_e_lin, em_e_log])

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
for ax, emap, title, vmax, cmap in [
    (axes[0,0], em_d_lin, "Proximity MAE [mm] — linear",  vmax_d_lg, "Greens"),
    (axes[0,1], em_d_log, "Proximity MAE [mm] — log-d",   vmax_d_lg, "Greens"),
    (axes[1,0], em_e_lin, "Strain MAE [%] — linear",      vmax_e_lg, "Oranges"),
    (axes[1,1], em_e_log, "Strain MAE [%] — log-d",       vmax_e_lg, "Oranges"),
]:
    im = ax.imshow(emap, origin="lower", aspect="auto", cmap=cmap,
                   vmin=0, vmax=vmax, extent=ext_2d)
    plt.colorbar(im, ax=ax, shrink=0.85)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel("Proximity [mm]"); ax.set_ylabel("Strain [%]")
plt.suptitle("MAE heatmap (eps x d) — Linear vs Log-d (Test)",
             fontsize=12, fontweight="bold")
plt.tight_layout()
b64_E_heatmap = fig_to_b64(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# ── 섹션 2: MLP vs PINN 비교 그래프 ─────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# (F) 물리 모델 피팅 시각화
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
eps_lin_fit = np.linspace(0, 30, 200)
d_lin_fit   = np.linspace(0, 36, 200)

ax = axes[0]
ax.scatter(_eps_all, _dR_all, s=3, alpha=0.08, color=COLOR_R, label="data")
ax.plot(eps_lin_fit, _r_model(eps_lin_fit, alpha1, alpha2), "r-", lw=2,
        label=f"fit: {alpha1:.3f}*eps + {alpha2:.5f}*eps^2")
ax.set_xlabel("Strain [%]"); ax.set_ylabel("dR_pct [%]")
ax.set_title(f"R Physics Fit  (R2={phys_r2_r:.4f})", fontweight="bold")
ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

ax = axes[1]
for eps_val, c in [(5, "#aaa"), (15, "#888"), (25, "#333")]:
    mask = (np.abs(_eps_all - eps_val) < 2.5)
    ax.scatter(_d_all[mask], _dL_all[mask], s=4, alpha=0.15, color=c)
    ax.plot(d_lin_fit, _l_model((np.full_like(d_lin_fit, eps_val), d_lin_fit),
                                 beta1, beta2, k_p),
            lw=2, color=c, label=f"fit eps={eps_val}%")
ax.set_xlabel("Proximity [mm]"); ax.set_ylabel("dL_pct [%]")
ax.set_title(f"L Physics Fit  (R2={phys_r2_l:.4f})", fontweight="bold")
ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

plt.suptitle("Physics Model Fitting", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_F_phys_fit = fig_to_b64(fig)

# (G) Loss curves — MLP vs PINN
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, s_key, title, color in [
    (axes[0], "s1", "Stage 1: dR -> eps", COLOR_R),
    (axes[1], "s2", "Stage 2: (dL+eps_hat) -> d", COLOR_L),
]:
    mlp_c  = res_lin[s_key].loss_curve_
    pinn_c = res_pinn[s_key].loss_curve_
    ax.plot(mlp_c,  color=C_MLP,  lw=1.5, ls="-",  alpha=0.85, label="MLP (linear)")
    ax.plot(pinn_c, color=C_PINN, lw=1.5, ls="--", alpha=0.85, label="PINN")
    ax.set_xlabel("Epoch"); ax.set_ylabel("MSE (normalized)")
    ax.set_title(title, fontweight="bold")
    ax.set_yscale("log"); ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
plt.suptitle("Loss Curves — MLP vs PINN", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_G_loss = fig_to_b64(fig)

# (H) Pred vs True — eps & d, MLP vs PINN
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
for row, (sig_key, true_vals, unit, color, lim) in enumerate([
    ("eps_te", y_eps_test.ravel(), "%",  COLOR_R, [-1, 31]),
    ("d_te",   y_d_test.ravel(),   "mm", COLOR_L, [-1, 38]),
]):
    for col, res in enumerate([res_lin, res_pinn]):
        ax   = axes[row, col]
        pred = res["preds"][sig_key]
        mae  = mean_absolute_error(true_vals, pred)
        r2   = r2_score(true_vals, pred)
        ax.scatter(true_vals, pred, s=4, alpha=0.3, color=color)
        ax.plot(lim, lim, "k--", lw=1)
        ax.text(0.05, 0.93, f"R2={r2:.4f}\nMAE={mae:.3f} {unit}",
                transform=ax.transAxes, fontsize=9, va="top",
                bbox=dict(boxstyle="round", fc="white", alpha=0.85))
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel(f"True [{unit}]"); ax.set_ylabel(f"Predicted [{unit}]")
        sig_name = "Strain" if row == 0 else "Proximity"
        ax.set_title(f"{sig_name} — {res['tag'].upper()}", fontweight="bold")
        ax.grid(True, alpha=0.3)
plt.suptitle("Pred vs True (Test set) — MLP vs PINN", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_H_pred = fig_to_b64(fig)

# (I) MAE per bin — MLP vs PINN
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, sig_key, true_arr, ylabel, color in [
    (axes[0], "d_te",   y_d_test.ravel(),   "Proximity MAE [mm]", COLOR_L),
    (axes[1], "eps_te", y_eps_test.ravel(), "Strain MAE [%]",     COLOR_R),
]:
    maes_mlp, maes_pinn = [], []
    for lo, hi in zip(D_BINS[:-1], D_BINS[1:]):
        sel = (d_true_test >= lo) & (d_true_test < hi)
        if sel.sum() == 0:
            maes_mlp.append(np.nan); maes_pinn.append(np.nan); continue
        maes_mlp.append( mean_absolute_error(true_arr[sel], res_lin["preds"][sig_key][sel]))
        maes_pinn.append(mean_absolute_error(true_arr[sel], res_pinn["preds"][sig_key][sel]))
    w = (D_BINS[1] - D_BINS[0]) * 0.38
    ax.bar(d_ctrs - w/2, maes_mlp,  width=w, label="MLP",  color=color, alpha=0.55)
    ax.bar(d_ctrs + w/2, maes_pinn, width=w, label="PINN", color=color, alpha=1.0)
    ax.set_xlabel("True Proximity bin [mm]"); ax.set_ylabel(ylabel)
    ax.set_title(ylabel.split(" MAE")[0] + " MAE per distance bin", fontweight="bold")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3, axis="y")
plt.suptitle("MAE by Distance Bin — MLP vs PINN (Test)", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_I_bar = fig_to_b64(fig)

# (J) Residuals — MLP vs PINN
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, res in [(axes[0], res_lin), (axes[1], res_pinn)]:
    d_te  = res["preds"]["d_te"]
    resid = d_te - d_true_test
    sc = ax.scatter(d_true_test, resid, s=4, alpha=0.25, c=d_true_test,
                    cmap="RdYlGn_r", vmin=0, vmax=36)
    plt.colorbar(sc, ax=ax, label="True d [mm]", shrink=0.85)
    ax.axhline(0, color="black", lw=1)
    sig2 = np.std(resid) * 2
    ax.axhline( sig2, color="gray", lw=0.8, ls="--", label=f"+-2sigma ({sig2:.2f} mm)")
    ax.axhline(-sig2, color="gray", lw=0.8, ls="--")
    ax.set_xlabel("True Proximity [mm]"); ax.set_ylabel("Residual [mm]")
    ax.set_title(f"Proximity Residuals — {res['tag'].upper()}", fontweight="bold")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
plt.tight_layout()
b64_J_resid = fig_to_b64(fig)

# (K) MAE heatmap — MLP vs PINN
em_e_mlp,  em_d_mlp  = err_map_2d(res_lin["preds"]["eps_te"],  res_lin["preds"]["d_te"])
em_e_pinn, em_d_pinn = err_map_2d(res_pinn["preds"]["eps_te"], res_pinn["preds"]["d_te"])

vmax_d_mp = np.nanmax([em_d_mlp, em_d_pinn])
vmax_e_mp = np.nanmax([em_e_mlp, em_e_pinn])

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
for ax, emap, title, vmax, cmap in [
    (axes[0,0], em_d_mlp,  "Proximity MAE [mm] — MLP",  vmax_d_mp, "Greens"),
    (axes[0,1], em_d_pinn, "Proximity MAE [mm] — PINN", vmax_d_mp, "Greens"),
    (axes[1,0], em_e_mlp,  "Strain MAE [%] — MLP",      vmax_e_mp, "Oranges"),
    (axes[1,1], em_e_pinn, "Strain MAE [%] — PINN",     vmax_e_mp, "Oranges"),
]:
    im = ax.imshow(emap, origin="lower", aspect="auto", cmap=cmap,
                   vmin=0, vmax=vmax, extent=ext_2d)
    plt.colorbar(im, ax=ax, shrink=0.85)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel("Proximity [mm]"); ax.set_ylabel("Strain [%]")
plt.suptitle("MAE heatmap (eps x d) — MLP vs PINN (Test)",
             fontsize=12, fontweight="bold")
plt.tight_layout()
b64_K_heatmap = fig_to_b64(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# ── 섹션 3: End-to-End (2in→2out) vs 2-Stage MLP 비교 그래프 ─────────────────
# ═══════════════════════════════════════════════════════════════════════════════
C_E2E = "#D62728"

# (L) Pred vs True — eps & d, 2-Stage(linear) vs E2E
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
for row, (sig_key, true_vals, unit, color, lim) in enumerate([
    ("eps_te", y_eps_test.ravel(), "%",  COLOR_R, [-1, 31]),
    ("d_te",   y_d_test.ravel(),   "mm", COLOR_L, [-1, 38]),
]):
    for col, (res, clr, lbl) in enumerate([
        (res_lin, C_MLP,  "2-Stage MLP"),
        (res_e2e, C_E2E,  "E2E (2in→2out)"),
    ]):
        ax   = axes[row, col]
        pred = res["preds"][sig_key]
        mae  = mean_absolute_error(true_vals, pred)
        r2   = r2_score(true_vals, pred)
        ax.scatter(true_vals, pred, s=4, alpha=0.3, color=clr)
        ax.plot(lim, lim, "k--", lw=1)
        ax.text(0.05, 0.93, f"R2={r2:.4f}\nMAE={mae:.3f} {unit}",
                transform=ax.transAxes, fontsize=9, va="top",
                bbox=dict(boxstyle="round", fc="white", alpha=0.85))
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel(f"True [{unit}]"); ax.set_ylabel(f"Predicted [{unit}]")
        sig_name = "Strain" if row == 0 else "Proximity"
        ax.set_title(f"{sig_name} — {lbl}", fontweight="bold")
        ax.grid(True, alpha=0.3)
plt.suptitle("Pred vs True (Test) — 2-Stage MLP vs End-to-End (2in→2out)",
             fontsize=12, fontweight="bold")
plt.tight_layout()
b64_L_pred = fig_to_b64(fig)

# (M) MAE heatmap — 2-Stage(linear) vs E2E
em_e_e2e, em_d_e2e = err_map_2d(res_e2e["preds"]["eps_te"], res_e2e["preds"]["d_te"])

vmax_d_me = np.nanmax([em_d_mlp, em_d_e2e])
vmax_e_me = np.nanmax([em_e_mlp, em_e_e2e])

fig, axes = plt.subplots(2, 2, figsize=(13, 9))
for ax, emap, title, vmax, cmap in [
    (axes[0,0], em_d_mlp,  "Proximity MAE [mm] — 2-Stage MLP",   vmax_d_me, "Greens"),
    (axes[0,1], em_d_e2e,  "Proximity MAE [mm] — E2E (2in→2out)", vmax_d_me, "Greens"),
    (axes[1,0], em_e_mlp,  "Strain MAE [%] — 2-Stage MLP",        vmax_e_me, "Oranges"),
    (axes[1,1], em_e_e2e,  "Strain MAE [%] — E2E (2in→2out)",     vmax_e_me, "Oranges"),
]:
    im = ax.imshow(emap, origin="lower", aspect="auto", cmap=cmap,
                   vmin=0, vmax=vmax, extent=ext_2d)
    plt.colorbar(im, ax=ax, shrink=0.85)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel("Proximity [mm]"); ax.set_ylabel("Strain [%]")
plt.suptitle("MAE heatmap (eps × d) — 2-Stage MLP vs E2E (Test)",
             fontsize=12, fontweight="bold")
plt.tight_layout()
b64_M_heatmap = fig_to_b64(fig)

# (N) MAE per bin — 2-Stage(linear) vs E2E
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, sig_key, true_arr, ylabel, color in [
    (axes[0], "d_te",   y_d_test.ravel(),   "Proximity MAE [mm]", COLOR_L),
    (axes[1], "eps_te", y_eps_test.ravel(), "Strain MAE [%]",     COLOR_R),
]:
    maes_2s, maes_e2e_b = [], []
    for lo, hi in zip(D_BINS[:-1], D_BINS[1:]):
        sel = (d_true_test >= lo) & (d_true_test < hi)
        if sel.sum() == 0:
            maes_2s.append(np.nan); maes_e2e_b.append(np.nan); continue
        maes_2s.append(   mean_absolute_error(true_arr[sel], res_lin["preds"][sig_key][sel]))
        maes_e2e_b.append(mean_absolute_error(true_arr[sel], res_e2e["preds"][sig_key][sel]))
    w = (D_BINS[1] - D_BINS[0]) * 0.38
    ax.bar(d_ctrs - w/2, maes_2s,    width=w, label="2-Stage MLP",    color=color, alpha=0.55)
    ax.bar(d_ctrs + w/2, maes_e2e_b, width=w, label="E2E (2in→2out)", color=C_E2E, alpha=0.80)
    ax.set_xlabel("True Proximity bin [mm]"); ax.set_ylabel(ylabel)
    ax.set_title(ylabel.split(" MAE")[0] + " MAE per distance bin", fontweight="bold")
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3, axis="y")
plt.suptitle("MAE by Distance Bin — 2-Stage MLP vs E2E (Test)", fontsize=12, fontweight="bold")
plt.tight_layout()
b64_N_bar = fig_to_b64(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# HTML 리포트
# ═══════════════════════════════════════════════════════════════════════════════
def mrow(label, mA, mB, key, tag_A="A", tag_B="B", higher_better=False):
    vA, vB = mA[key], mB[key]
    diff = vB - vA
    better = (diff < -0.0001) if not higher_better else (diff > 0.0001)
    worse  = (diff > 0.0001)  if not higher_better else (diff < -0.0001)
    col  = "#27ae60" if better else ("#c0392b" if worse else "#555")
    sign = "+" if diff > 0 else ""
    b_lbl = tag_B if better else (tag_A if worse else "-")
    return (f"<tr><td>{label}</td><td>{vA:.4f}</td>"
            f"<td>{vB:.4f} <span style='color:{col};font-size:.85em'>({sign}{diff:.4f})</span></td>"
            f"<td><b>{b_lbl}</b></td></tr>")

def metric_section(split_name, k_eps, k_d, res_A, res_B, tag_A, tag_B):
    me_A = res_A["metrics"][k_eps]; me_B = res_B["metrics"][k_eps]
    md_A = res_A["metrics"][k_d];   md_B = res_B["metrics"][k_d]
    return f"""
<h3>{split_name}</h3>
<table>
  <tr><th>지표</th><th>{tag_A}</th><th>{tag_B} (차이)</th><th>우세</th></tr>
  {mrow("Strain MAE [%]",        me_A, me_B, "MAE",    tag_A, tag_B)}
  {mrow("Strain RMSE [%]",       me_A, me_B, "RMSE",   tag_A, tag_B)}
  {mrow("Strain R2",             me_A, me_B, "R2",     tag_A, tag_B, True)}
  {mrow("Proximity MAE [mm]",    md_A, md_B, "MAE",    tag_A, tag_B)}
  {mrow("Proximity RMSE [mm]",   md_A, md_B, "RMSE",   tag_A, tag_B)}
  {mrow("Proximity R2",          md_A, md_B, "R2",     tag_A, tag_B, True)}
  {mrow("Proximity MaxErr [mm]", md_A, md_B, "MaxErr", tag_A, tag_B)}
</table>"""

now = datetime.now().strftime("%Y-%m-%d %H:%M")
ml  = res_lin["metrics"]
mg  = res_log["metrics"]
mp  = res_pinn["metrics"]
me  = res_e2e["metrics"]

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Training Report — Linear / Log-d / PINN</title>
<style>
  body{{font-family:'Segoe UI',sans-serif;margin:40px;max-width:1200px;color:#222}}
  h1{{border-bottom:3px solid #FF8C00;padding-bottom:8px}}
  h2{{margin-top:40px;border-left:4px solid #FF8C00;padding-left:10px;color:#333}}
  h2.pinn{{border-color:#E377C2}}
  h3{{color:#555;margin-top:18px}}
  table{{border-collapse:collapse;width:100%;margin-bottom:18px;font-size:.93em}}
  th{{background:#f4f4f4;padding:8px 12px;border:1px solid #ccc;text-align:left}}
  td{{padding:7px 12px;border:1px solid #e0e0e0}}
  tr:nth-child(even) td{{background:#fafafa}}
  .note{{font-size:.85em;color:#888;margin:-8px 0 14px}}
  .card-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px}}
  .card{{background:#f8f8f8;border:1px solid #ddd;border-radius:6px;padding:14px;text-align:center}}
  .card .num{{font-size:1.5em;font-weight:bold;color:#333}}
  .card .lbl{{font-size:.82em;color:#888;margin-top:4px}}
  .box{{background:#fffbf0;border-left:3px solid #FF8C00;padding:8px 14px;margin:6px 0;font-size:.92em}}
  .box.pinn{{border-color:#E377C2;background:#fff5fc}}
  .box.mlp{{border-color:#1F77B4;background:#f0f7ff}}
  .box.log{{border-color:#9467BD;background:#f8f0ff}}
  .box.e2e{{border-color:#D62728;background:#fff0f0}}
  h2.e2e{{border-color:#D62728}}
  .divider{{border:none;border-top:2px dashed #ddd;margin:40px 0}}
  img{{max-width:100%;border:1px solid #ddd;border-radius:4px;margin-bottom:8px}}
  code{{background:#f4f4f4;padding:1px 5px;border-radius:3px;font-size:.9em}}
  .param-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 18px}}
  .param{{background:#f8f8f8;border:1px solid #eee;border-radius:5px;padding:10px 14px;font-size:.9em}}
  .param .val{{font-size:1.2em;font-weight:bold;color:#333;margin-top:4px}}
</style>
</head>
<body>
<h1>Training Report — Linear / Log-d / PINN / E2E</h1>
<p style="color:#aaa;margin-top:-10px">Generated: {now} &nbsp;|&nbsp;
Architecture: MLP (128-128-64) &nbsp;|&nbsp; 2-Stage Decoupled + End-to-End</p>

<h2>종합 요약 (Test set MAE)</h2>
<div class="card-grid" style="grid-template-columns:repeat(4,1fr)">
  <div class="card">
    <div class="num">{ml['d_test']['MAE']:.3f} mm</div>
    <div class="lbl">Proximity MAE — Linear</div>
  </div>
  <div class="card">
    <div class="num">{mg['d_test']['MAE']:.3f} mm</div>
    <div class="lbl">Proximity MAE — Log-d</div>
  </div>
  <div class="card">
    <div class="num">{mp['d_test']['MAE']:.3f} mm</div>
    <div class="lbl">Proximity MAE — PINN</div>
  </div>
  <div class="card">
    <div class="num">{me['d_test']['MAE']:.3f} mm</div>
    <div class="lbl">Proximity MAE — E2E (2in→2out)</div>
  </div>
  <div class="card">
    <div class="num">{ml['eps_test']['MAE']:.3f} %</div>
    <div class="lbl">Strain MAE — Linear</div>
  </div>
  <div class="card">
    <div class="num">{mg['eps_test']['MAE']:.3f} %</div>
    <div class="lbl">Strain MAE — Log-d</div>
  </div>
  <div class="card">
    <div class="num">{mp['eps_test']['MAE']:.3f} %</div>
    <div class="lbl">Strain MAE — PINN</div>
  </div>
  <div class="card">
    <div class="num">{me['eps_test']['MAE']:.3f} %</div>
    <div class="lbl">Strain MAE — E2E (2in→2out)</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════ -->
<h2>Part 1 — Linear vs Log-scale d (sklearn MLP)</h2>
<!-- ═══════════════════════════════════════════════════ -->

<div class="box mlp">
  <b>Linear</b>: Stage 2 타겟 = <code>d_act_mm</code>. StandardScaler 정규화.
</div>
<div class="box log">
  <b>Log-d</b>: Stage 2 타겟 = <code>log1p(d_act_mm)</code>. 추론 시 <code>expm1()</code> 역변환.
  L-d 결합이 물리적으로 1/d^k 형태이므로 log 공간에서 더 선형에 가깝고,
  가까운 거리(0-10mm)에 더 높은 표현력을 부여.
</div>

<h2>1-1. 구조 비교</h2>
<table>
  <tr><th>항목</th><th>Linear</th><th>Log-d</th></tr>
  <tr><td>Stage 2 타겟</td><td>d_act_mm</td><td>log1p(d_act_mm)</td></tr>
  <tr><td>역변환</td><td>inverse_transform</td><td>inverse_transform + expm1</td></tr>
  <tr><td>Stage 1</td><td colspan="2" style="text-align:center">동일 (dR -> eps)</td></tr>
  <tr><td>Stage 1 iters</td><td>{res_lin['s1'].n_iter_}</td><td>{res_log['s1'].n_iter_}</td></tr>
  <tr><td>Stage 2 iters</td><td>{res_lin['s2'].n_iter_}</td><td>{res_log['s2'].n_iter_}</td></tr>
</table>

<h2>1-2. Loss Curves</h2>
<img src="data:image/png;base64,{b64_A_loss}" alt="loss_lg">

<h2>1-3. 성능 비교</h2>
<p class="note">빨간 = log-d가 더 나쁨 / 초록 = 더 좋음. 괄호 = linear 대비 차이.</p>
{metric_section("Test set",  "eps_test", "d_test",  res_lin, res_log, "linear", "log-d")}
{metric_section("Val set",   "eps_val",  "d_val",   res_lin, res_log, "linear", "log-d")}
{metric_section("Train set", "eps_train","d_train",  res_lin, res_log, "linear", "log-d")}

<h2>1-4. Proximity Pred vs True</h2>
<img src="data:image/png;base64,{b64_B_pred_d}" alt="pred_d_lg">

<h2>1-5. 거리 구간별 MAE 비교</h2>
<p class="note">6mm 간격 bin 기준. 먼 거리(24-36mm)에서 log-d 효과 확인.</p>
<img src="data:image/png;base64,{b64_C_bar}" alt="bar_lg">

<h2>1-6. Proximity Residuals</h2>
<p class="note">점 색상 = 실제 거리. 먼 거리(빨간 점)의 잔차 패턴 비교.</p>
<img src="data:image/png;base64,{b64_D_resid}" alt="resid_lg">

<h2>1-7. eps x d 공간 MAE 히트맵</h2>
<p class="note">같은 행은 동일 컬러 스케일.</p>
<img src="data:image/png;base64,{b64_E_heatmap}" alt="heatmap_lg">

<hr class="divider">

<!-- ═══════════════════════════════════════════════════ -->
<h2 class="pinn">Part 2 — MLP vs PINN (Physics-Informed)</h2>
<!-- ═══════════════════════════════════════════════════ -->

<div class="box mlp">
  <b>MLP (Linear, Baseline)</b>: sklearn MLPRegressor. Data loss(MSE)만으로 학습.
</div>
<div class="box pinn">
  <b>PINN</b>: NumPy + Adam 직접 구현. Data loss + Physics loss 동시 최적화.<br>
  <code>Loss = MSE_data + {LAMBDA_PHYS} * MSE_physics</code>
</div>

<h2 class="pinn">2-1. 물리 제약 (Physics Constraints)</h2>
<table>
  <tr><th>Stage</th><th>물리 모델</th><th>역할</th></tr>
  <tr>
    <td><b>Stage 1</b><br>dR → eps</td>
    <td><code>dR = &alpha;&#8321;&sdot;eps + &alpha;&#8322;&sdot;eps&sup2;</code></td>
    <td>예측된 eps가 저항 변화 물리 모델과 일치하도록 강제</td>
  </tr>
  <tr>
    <td><b>Stage 2</b><br>(dL, eps_hat) → d</td>
    <td><code>dL = &beta;&#8321;&sdot;eps + &beta;&#8322;&sdot;exp(-k&sdot;d)</code></td>
    <td>예측된 d가 인덕턴스-근접도 물리 모델과 일치하도록 강제<br>
    (지수 감쇠: gradient bounded, 수치적으로 안정)</td>
  </tr>
</table>

<h2 class="pinn">2-2. 물리 모델 피팅 결과</h2>
<div class="param-grid">
  <div class="param">&alpha;&#8321; (R linear)<div class="val">{alpha1:.4f}</div></div>
  <div class="param">&alpha;&#8322; (R quadratic)<div class="val">{alpha2:.6f}</div></div>
  <div class="param">R model R&sup2;<div class="val">{phys_r2_r:.4f}</div></div>
  <div class="param">&beta;&#8321; (L-eps)<div class="val">{beta1:.4f}</div></div>
  <div class="param">&beta;&#8322; (L-d amplitude)<div class="val">{beta2:.4f}</div></div>
  <div class="param">k (decay rate)<div class="val">{k_p:.4f} mm&#8315;&#185;</div></div>
  <div class="param">L model R&sup2;<div class="val">{phys_r2_l:.4f}</div></div>
  <div class="param">PINN lambda<div class="val">{LAMBDA_PHYS}</div></div>
  <div class="param">Stage 1/2 iters (PINN)<div class="val">{res_pinn['s1'].n_iter_} / {res_pinn['s2'].n_iter_}</div></div>
</div>
<img src="data:image/png;base64,{b64_F_phys_fit}" alt="phys_fit">

<h2 class="pinn">2-3. Loss Curves</h2>
<img src="data:image/png;base64,{b64_G_loss}" alt="loss_mp">

<h2 class="pinn">2-4. 성능 비교</h2>
<p class="note">빨간 = PINN이 더 나쁨 / 초록 = PINN이 더 좋음. 괄호 = MLP 대비 차이.</p>
{metric_section("Test set",  "eps_test", "d_test",  res_lin, res_pinn, "MLP", "PINN")}
{metric_section("Val set",   "eps_val",  "d_val",   res_lin, res_pinn, "MLP", "PINN")}
{metric_section("Train set", "eps_train","d_train",  res_lin, res_pinn, "MLP", "PINN")}

<h2 class="pinn">2-5. Pred vs True</h2>
<img src="data:image/png;base64,{b64_H_pred}" alt="pred_mp">

<h2 class="pinn">2-6. 거리 구간별 MAE 비교</h2>
<p class="note">6mm bin 기준. 먼 거리(24-36mm)에서 PINN 물리 제약 효과 확인.</p>
<img src="data:image/png;base64,{b64_I_bar}" alt="bar_mp">

<h2 class="pinn">2-7. Proximity Residuals</h2>
<img src="data:image/png;base64,{b64_J_resid}" alt="resid_mp">

<h2 class="pinn">2-8. eps x d 공간 MAE 히트맵</h2>
<p class="note">같은 행은 동일 컬러 스케일. 물리 제약이 어느 구간에서 효과적인지 확인.</p>
<img src="data:image/png;base64,{b64_K_heatmap}" alt="heatmap_mp">

<hr class="divider">

<!-- ═══════════════════════════════════════════════════ -->
<h2 class="e2e">Part 3 — 2-Stage MLP vs End-to-End (2in→2out, Stage1 only)</h2>
<!-- ═══════════════════════════════════════════════════ -->

<div class="box mlp">
  <b>2-Stage MLP (Baseline)</b>: Stage1: dR→eps (1in→1out), Stage2: (dL, eps_hat)→d (2in→1out).<br>
  물리적 인과관계(dR은 eps에만 지배적)를 반영한 직렬 디커플링 구조.
</div>
<div class="box e2e">
  <b>End-to-End (2in→2out)</b>: 단일 MLP로 (dL, dR) → (eps, d) 동시 예측.<br>
  Stage2 없이 Stage1만으로 두 출력 동시 학습. 구조 단순, 물리 계층 없음.
</div>

<h2 class="e2e">3-1. 구조 비교</h2>
<table>
  <tr><th>항목</th><th>2-Stage MLP</th><th>End-to-End (2in→2out)</th></tr>
  <tr><td>입력</td><td>Stage1: [dR] / Stage2: [dL, eps_hat]</td><td>[dL, dR]</td></tr>
  <tr><td>출력</td><td>Stage1: eps / Stage2: d (순차)</td><td>(eps, d) 동시 출력</td></tr>
  <tr><td>모델 수</td><td>2개 (직렬)</td><td>1개</td></tr>
  <tr><td>물리 계층</td><td>있음 (dR→eps 우선)</td><td>없음 (end-to-end)</td></tr>
  <tr><td>학습 iters</td><td>{res_lin['s1'].n_iter_} / {res_lin['s2'].n_iter_}</td><td>{res_e2e['model'].n_iter_}</td></tr>
</table>

<h2 class="e2e">3-2. 성능 비교</h2>
<p class="note">빨간 = E2E가 더 나쁨 / 초록 = E2E가 더 좋음. 괄호 = 2-Stage 대비 차이.</p>
{metric_section("Test set",  "eps_test", "d_test",  res_lin, res_e2e, "2-Stage", "E2E")}
{metric_section("Val set",   "eps_val",  "d_val",   res_lin, res_e2e, "2-Stage", "E2E")}
{metric_section("Train set", "eps_train","d_train",  res_lin, res_e2e, "2-Stage", "E2E")}

<h2 class="e2e">3-3. Pred vs True</h2>
<img src="data:image/png;base64,{b64_L_pred}" alt="pred_e2e">

<h2 class="e2e">3-4. 거리 구간별 MAE</h2>
<p class="note">6mm bin 기준. 디커플링 구조 유무에 따른 근접도 구간별 오차 차이 확인.</p>
<img src="data:image/png;base64,{b64_N_bar}" alt="bar_e2e">

<h2 class="e2e">3-5. eps × d 공간 MAE 히트맵</h2>
<p class="note">같은 행은 동일 컬러 스케일. 2-Stage와 E2E의 오차 분포 패턴 비교.</p>
<img src="data:image/png;base64,{b64_M_heatmap}" alt="heatmap_e2e">

</body>
</html>"""

report_path = OUT / "training_report.html"
report_path.write_text(html, encoding="utf-8")
print(f"\nSaved -> {report_path}")
print("Done.")
