"""과제 4절: 결정론적 제어 — 극배치(Ackermann, 적분 확장), 관측기, LQR (강의 Lec8, Lec9, P2_Lec1).

모든 설계는 동작점 (p₀, ε₀, u₀) 주변 편차 좌표에서 한다: δx = x − x₀, δu = u − u₀.
"""
import numpy as np
from scipy import linalg, signal

import paths  # noqa: F401
from analysis import ctrb


def augment_integral(Ad, Bd, C_eps):
    """x_I(k+1) = x_I(k) + (r(k) − ε(k))  → [x; x_I]."""
    n = Ad.shape[0]
    Aa = np.block([[Ad, np.zeros((n, 1))], [-C_eps.reshape(1, n), np.ones((1, 1))]])
    Ba = np.vstack([Bd, [[0.0]]])
    Ga = np.vstack([np.zeros((n, 1)), [[1.0]]])
    return Aa, Ba, Ga


def _check_stable(poles):
    poles = np.asarray(poles, complex)
    if np.any(np.abs(poles) >= 1.0):
        raise ValueError(f"목표 극 |z| ≥ 1 (불안정): {poles}")
    return poles


def acker(A, B, poles_z):
    """K = [0 … 0 1]·𝒞⁻¹·α_d(A)  (Lec8_1 p36–39)."""
    p = _check_stable(poles_z)
    n = A.shape[0]
    alpha = np.real(np.poly(p))
    aA = sum(c * np.linalg.matrix_power(A, n - i) for i, c in enumerate(alpha))
    e = np.zeros((1, n)); e[0, -1] = 1.0
    return e @ np.linalg.solve(ctrb(A, B), aA)


def ref_gains(Ad, Bd, C_eps):
    """기준 피드포워드 (Lec8_1 p55–57 'F 선택'): 정상상태 x_ss = N_x·r, u_ss = N_u·r.
    [A_d − I, B_d; C_ε, 0]·[N_x; N_u] = [0; 1]"""
    n = Ad.shape[0]
    M = np.block([[Ad - np.eye(n), Bd], [C_eps.reshape(1, n), np.zeros((1, 1))]])
    sol = np.linalg.solve(M, np.r_[np.zeros(n), 1.0])
    return sol[:n], float(sol[n])


def poles_from_spec(zeta, wn, Ts, extra=()):
    s = [-zeta * wn + 1j * wn * np.sqrt(1 - zeta ** 2), -zeta * wn - 1j * wn * np.sqrt(1 - zeta ** 2), *extra]
    return np.exp(np.array(s, complex) * Ts)


def observer_gain(A, C, poles_z):
    """쌍대: A − L·C 의 극 배치. 출력 1개면 Ackermann, 여러 개면 place_poles."""
    p = _check_stable(poles_z)
    if C.shape[0] == 1:
        return acker(A.T, C.T, p).T
    return signal.place_poles(A.T, C.T, p).gain_matrix.T


def dlqr(A, B, Q, R):
    """이산 대수 리카티 방정식(DARE) → K = (R + BᵀPB)⁻¹BᵀPA."""
    P = linalg.solve_discrete_are(A, B, Q, R)
    K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)
    return K, P


def bryson(x_max, u_max):
    return np.diag(1.0 / np.asarray(x_max, float) ** 2), np.array([[1.0 / u_max ** 2]])


def margins(A, B, K, Ts, n=20000):
    """입력에서 끊은 루프 L(z) = K(zI − A)⁻¹B 의 이득·위상 여유."""
    w = np.linspace(1e-4, np.pi / Ts, n)
    I = np.eye(A.shape[0])
    L = np.array([(K @ np.linalg.solve(np.exp(1j * wi * Ts) * I - A, B)).item() for wi in w])
    ph = np.unwrap(np.angle(L))
    mag = np.abs(L)
    gm = np.inf
    idx = np.where(np.diff(np.sign(ph + np.pi)))[0]
    if len(idx):
        gm = -20 * np.log10(mag[idx[0]])
    pm = np.inf
    idx = np.where(np.diff(np.sign(mag - 1.0)))[0]
    if len(idx):
        pm = 180.0 + np.degrees(ph[idx[0]])
    return float(gm), float(pm)


class StateFeedback:
    """u = u₀ − K·δx̂ − K_I·x_I  (포화 시 적분 정지: 조건부 적분 anti-windup).

    L 이 None 이면 상태를 직접 받는다(`x_true`, 시뮬 정답 = '전 상태 측정' 기준선).
    mode: "apriori"  x̂(k+1) = A x̂ + B u + L(y − C x̂)         (예측형, Lec8_2 p50)
          "aposteriori"  측정 직후 보정 후 제어에 사용          (Lec8_2 p56)
    """

    def __init__(self, Ad, Bd, C, K, KI, L=None, x0=None, u0=0.0, mode="apriori", u_lim=(0.0, 30.0), eps_row=1):
        self.Ad, self.Bd, self.C, self.K, self.KI, self.L = Ad, Bd, C, np.atleast_2d(K), float(KI), L
        self.x0 = np.zeros(Ad.shape[0]) if x0 is None else np.asarray(x0, float)
        self.y0 = self.C @ self.x0
        self.u0, self.mode, self.u_lim, self.eps_row = u0, mode, u_lim, eps_row
        self.Nx, self.Nu = ref_gains(Ad, Bd, C[eps_row])
        self.reset()

    def reset(self):
        self.xh = np.zeros(self.Ad.shape[0])
        self.xI = 0.0
        self.u_prev = 0.0

    def u(self, y, r, x_true=None):
        dy = np.asarray(y, float) - self.y0
        if self.L is None:
            dx = np.asarray(x_true, float) - self.x0
        else:
            if self.mode == "aposteriori":
                self.xh = self.xh + self.L @ (dy - self.C @ self.xh)
            dx = self.xh
        dr = r - self.y0[self.eps_row]
        e = dr - dy[self.eps_row]
        du = float(-(self.K @ (dx - self.Nx * dr)).item() + self.Nu * dr - self.KI * self.xI)
        u = self.u0 + du
        sat = min(max(u, self.u_lim[0]), self.u_lim[1])
        if sat == u or np.sign(e) != np.sign(u - sat):
            self.xI += e
        du = sat - self.u0
        if self.L is not None:
            if self.mode == "apriori":
                self.xh = self.Ad @ self.xh + self.Bd[:, 0] * du + self.L @ (dy - self.C @ self.xh)
            else:
                self.xh = self.Ad @ self.xh + self.Bd[:, 0] * du
        return sat


V0_EPS = 20.0  # 기준 변형률 속도 한계 v₀ [%/s] (가정값, 노란 칸) — Bryson ε̇ 가중과 상위 루프 v_max 기준


def load_model(P):
    M = P["model"]
    return (np.array(M["Ad"]), np.array(M["Bd"]), np.array(M["C"]), M["Ts"], np.array(M["x0"]), M["u0"], M["phys"])


def main():
    from paths import load_params, save_params
    P = load_params()
    Ad, Bd, C, Ts, x0, u0, phys = load_model(P)
    Aa, Ba, _ = augment_integral(Ad, Bd, C[1])
    # 극배치: 지배 극 쌍 ζ = 0.8, ω_n = 개루프 지배 극 크기 |λ_dom| × 1.5, 나머지 2개는 3배 빠른 실수 극
    lam = np.log(np.abs(np.linalg.eigvals(Ad))) / Ts
    wn = 1.5 * float(np.min(np.abs(lam)))
    n_aug = Ad.shape[0] + 1
    pp = poles_from_spec(0.8, wn, Ts, extra=tuple(-3 * 0.8 * wn * (1 + 0.1 * i) for i in range(n_aug - 2)))
    Kpp = acker(Aa, Ba, pp)
    # 관측기: 제어기 빠른 극보다 2배 빠른 실수 극 n 개
    n = Ad.shape[0]
    obs_p = np.exp(-2 * 0.8 * wn * (3 + 0.3 * np.arange(n)) * Ts)  # 제어기 극의 2배 (센서 잡음 때문에 4배 → 2배)
    L = observer_gain(Ad, C, obs_p)
    # LQR: Bryson — δp 15 kPa, δε 2 % (ε̂ 잡음 σ≈0.4 % 의 5배), (ε̇ v₀), x_I 50 (2 % × 25 샘플), δu 15 kPa
    Q, R = bryson([15.0, 2.0] + ([V0_EPS] if n == 3 else []) + [50.0], 15.0)
    Klq, Pr = dlqr(Aa, Ba, Q, R)
    gm, pm = margins(Aa, Ba, Klq, Ts)
    gpp, ppm = margins(Aa, Ba, Kpp, Ts)
    cl = lambda K: [[float(z.real), float(z.imag)] for z in np.linalg.eigvals(Aa - Ba @ K)]
    save_params("det", dict(
        pp=dict(poles=cl(Kpp), K=Kpp[:, :-1].tolist(), KI=float(Kpp[0, -1]), gm_db=gpp, pm_deg=ppm,
                spec=dict(zeta=0.8, wn=wn)),
        obs=dict(poles=obs_p.tolist(), L=L.tolist()),
        lqr=dict(Q=np.diag(Q).tolist(), R=float(R[0, 0]), K=Klq[:, :-1].tolist(), KI=float(Klq[0, -1]),
                 P=Pr.tolist(), poles=cl(Klq), gm_db=gm, pm_deg=pm),
        v0=V0_EPS))
    print(f"PP K={Kpp.round(3)}  LQR K={Klq.round(3)}  LQR GM={gm:.1f} dB PM={pm:.1f}°")


if __name__ == "__main__":
    main()
