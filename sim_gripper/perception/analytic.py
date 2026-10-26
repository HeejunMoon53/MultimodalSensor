"""해석적(경험식) 역산 기준선 — Embedded MoE와 비교용 (논문 F7).

경험 피팅 모델 (CLAUDE.md):
  ΔR/R₀ = a₀ + α₁ε + α₂ε²
  ΔL/L₀ = b₀ + β₁ε + β₂/(d+d₀)ᵏ + β₃·ε/(d+d₀)ᵏ
도체 근접 순방향 표(ε 0~30 %, d 0~24 mm)에 적합하고, 측정 (ΔL, ΔR) → (ε, d)를 2D 뉴턴법으로 푼다.
발산 판정: 30회 내 비수렴, 범위 이탈(ε ∉ [−5, 40], d ∉ [−2, 40]), |det J| < 1e−9.
"""
import numpy as np
from scipy.optimize import curve_fit

from sim_gripper.perception.moe import MoE
from sim_gripper.sensor.tdm import TdmSampler

EPS_GRID = np.arange(1.0, 30.0, 2.0)
D_GRID = np.arange(0.5, 24.0, 1.5)


def _model_L(x, b0, b1, b2, b3, d0, k):
    eps, d = x
    g = 1.0 / np.power(np.maximum(d + d0, 1e-6), k)
    return b0 + b1 * eps + b2 * g + b3 * eps * g


def _model_R(eps, a0, a1, a2):
    return a0 + a1 * eps + a2 * eps ** 2


def _r2(y, p):
    return float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))


def fit_empirical(fwd):
    E, D = np.meshgrid(np.arange(0, 30.1, 1.0), np.arange(0, 24.1, 1.0), indexing="ij")
    L = np.array([fwd.signals(e, d, 0.0, "conductor")[0] for e, d in zip(E.ravel(), D.ravel())])
    R = np.array([fwd.signals(e, 30.0, 0.0, "conductor")[1] for e in E[:, 0]])
    pL, _ = curve_fit(_model_L, (E.ravel(), D.ravel()), L, p0=[0, 1, -30, 0, 2, 1],
                      bounds=([-1e3, -1e2, -1e7, -1e5, 0.05, 0.2], [1e3, 1e2, 1e7, 1e5, 60, 8]), maxfev=20000)
    pR, _ = curve_fit(_model_R, E[:, 0], R)
    return {"pL": pL, "pR": pR, "r2_L": _r2(L, _model_L((E.ravel(), D.ravel()), *pL)),
            "r2_R": _r2(R, _model_R(E[:, 0], *pR))}


def invert(fit, dL, dR, x0=(15.0, 12.0), iters=30, tol=1e-6):
    """(ΔL, ΔR) → (ε, d, ok). 수치 야코비안 2D 뉴턴."""
    x = np.array(x0, float)
    f = lambda v: np.array([_model_L(v, *fit["pL"]) - dL, _model_R(v[0], *fit["pR"]) - dR])
    for _ in range(iters):
        r = f(x)
        if np.max(np.abs(r)) < tol:
            break
        h = 1e-5
        J = np.column_stack([(f(x + [h, 0]) - r) / h, (f(x + [0, h]) - r) / h])
        if abs(np.linalg.det(J)) < 1e-9:
            return float(x[0]), float(x[1]), False
        x = x - np.linalg.solve(J, r)
        if not (-5 <= x[0] <= 40 and -2 <= x[1] <= 40):
            return float(x[0]), float(x[1]), False
    ok = bool(np.max(np.abs(f(x))) < 1e-3)
    return float(x[0]), float(x[1]), ok


def error_map(fit, fwd, models=None, n_noise=20, seed=0, sigma=(0.116, 0.382)):
    """ε–d 격자에서 TDM 노이즈 입력에 대한 (해석적 역산, MoE) 거리 오차·발산률."""
    tdm, moe = TdmSampler(*sigma, seed), MoE(models=models) if models else MoE()
    shape = (len(EPS_GRID), len(D_GRID))
    out = {k: np.zeros(shape) for k in ("d_err", "eps_err", "fail_rate", "moe_d_err", "moe_eps_err")}
    for i, e in enumerate(EPS_GRID):
        for j, d in enumerate(D_GRID):
            L0, R0 = fwd.signals(e, d, 0.0, "conductor")
            de, dd, fails, me, md = [], [], 0, [], []
            for _ in range(n_noise):
                dL, dR = tdm.sample(L0, R0)
                ee, dh, ok = invert(fit, dL, dR)
                fails += not ok
                if ok:
                    de.append(abs(ee - e)), dd.append(abs(dh - d))
                moe.reset()
                moe.ema = (L0, R0)               # 정상상태 EMA = 평균 신호
                moe._prev = 0
                m = moe.step(dL, dR)
                me.append(abs(m.strain_pct - e)), md.append(abs(m.value - d) if not m.contact else 24.0)
            out["fail_rate"][i, j] = fails / n_noise
            out["d_err"][i, j] = np.mean(dd) if dd else np.nan
            out["eps_err"][i, j] = np.mean(de) if de else np.nan
            out["moe_d_err"][i, j], out["moe_eps_err"][i, j] = np.mean(md), np.mean(me)
    return out
