"""과제 5절: 칼만 필터·LQG (강의 P2_Lec4, 표기 그대로: W, V, M(k), Z(k), B_w).

측정 갱신: x̂(k|k) = x̂(k|k−1) + M Cᵀ(CMCᵀ+V)⁻¹(y − Cx̂(k|k−1)),  Z = M − MCᵀ(CMCᵀ+V)⁻¹CM
시간 갱신: x̂(k+1|k) = A x̂(k|k) + B u,                              M(k+1) = A Z Aᵀ + B_w W B_wᵀ
"""
import numpy as np
from scipy import linalg

import paths  # noqa: F401


class Kalman:
    def __init__(self, Ad, Bd, C, Bw, W, V, x0, M0):
        self.Ad, self.Bd, self.C, self.Bw, self.W, self.V = Ad, Bd, C, Bw, W, V
        self.x_prior, self.M = np.asarray(x0, float).copy(), np.asarray(M0, float).copy()
        self.x_post, self.Z = self.x_prior.copy(), self.M.copy()

    def update(self, y):
        S = self.C @ self.M @ self.C.T + self.V
        G = self.M @ self.C.T @ np.linalg.inv(S)
        self.x_post = self.x_prior + G @ (np.asarray(y, float) - self.C @ self.x_prior)
        self.Z = self.M - G @ self.C @ self.M
        return self.x_post

    def predict(self, u):
        self.x_prior = self.Ad @ self.x_post + self.Bd[:, 0] * float(u)
        self.M = self.Ad @ self.Z @ self.Ad.T + self.Bw @ self.W @ self.Bw.T
        return self.x_prior


def steady_kalman(Ad, C, Bw, W, V):
    """정상상태 예측 공분산 M (LQR 리카티의 쌍대) 과 필터 이득 Kf = MCᵀ(CMCᵀ+V)⁻¹."""
    M = linalg.solve_discrete_are(Ad.T, C.T, Bw @ W @ Bw.T, V)
    Kf = M @ C.T @ np.linalg.inv(C @ M @ C.T + V)
    return Kf, M


class Lqg:
    """LQR 이득 + 칼만 사후 추정 x̂(k|k) (분리 원리). 편차 좌표, 조건부 적분 anti-windup."""

    def __init__(self, K, KI, kalman, x0, u0, u_lim=(0.0, 30.0), eps_row=1):
        self.K, self.KI, self.kf = np.atleast_2d(K), float(KI), kalman
        self.x0, self.u0, self.u_lim, self.eps_row = np.asarray(x0, float), u0, u_lim, eps_row
        self.y0 = kalman.C @ self.x0
        self._init = (kalman.x_prior.copy(), kalman.M.copy())
        from design_det import ref_gains
        self.Nx, self.Nu = ref_gains(kalman.Ad, kalman.Bd, kalman.C[eps_row])
        self.reset()

    def reset(self):
        self.kf.x_prior, self.kf.M = self._init[0].copy(), self._init[1].copy()
        self.xI = 0.0
        self._bump = None

    def bumpless(self, x_abs, u_prev):
        """모드 전환 복귀: 상태를 이어받고, 다음 u() 가 u_prev 와 같도록 x_I 를 정한다."""
        self.kf.x_prior, self._bump = np.asarray(x_abs, float) - self.x0, float(u_prev)

    def u(self, y, r, x_true=None):
        dy = np.asarray(y, float) - self.y0
        xh = self.kf.update(dy)
        dr = r - self.y0[self.eps_row]
        e = dr - dy[self.eps_row]
        fb = float(-(self.K @ (xh - self.Nx * dr)).item() + self.Nu * dr)
        if self._bump is not None:
            self.xI, self._bump = (self.u0 + fb - self._bump) / self.KI, None
        u = self.u0 + fb - self.KI * self.xI
        sat = min(max(u, self.u_lim[0]), self.u_lim[1])
        if sat == u or np.sign(e) != np.sign(u - sat):
            self.xI += e
        self.kf.predict(sat - self.u0)
        return sat


class RangeKF:
    """근접 거리 d 와 접근 속도 ḋ (등속 모델, 가속도를 공정 잡음으로)."""

    def __init__(self, Ts, q_acc, r_d):
        T = Ts
        self.A = np.array([[1, T], [0, 1.0]])
        self.Bw = np.array([[T ** 2 / 2], [T]])
        self.W = np.array([[q_acc ** 2]])
        self.C = np.array([[1.0, 0.0]])
        self.V = np.array([[r_d ** 2]])
        self.x, self.M, self.started = np.zeros(2), np.diag([100.0, 100.0]), False

    def step(self, d_meas):
        if not self.started:
            self.x[0], self.started = float(d_meas), True
        S = self.C @ self.M @ self.C.T + self.V
        G = self.M @ self.C.T / S
        self.x = self.x + (G * (d_meas - self.C @ self.x)).ravel()
        Z = self.M - G @ self.C @ self.M
        d, v = float(self.x[0]), float(self.x[1])
        self.x = self.A @ self.x
        self.M = self.A @ Z @ self.A.T + self.Bw @ self.W @ self.Bw.T
        return d, v


def main():
    from paths import OUT, load_params, save_params
    P = load_params()
    M = P["model"]
    Ad, Bd, C = np.array(M["Ad"]), np.array(M["Bd"]), np.array(M["C"])
    V = np.diag(np.array(P["noise"]["var"]))          # S4 정지 잡음 (run_compare S4)
    # W: 출력 오차 잔차 = 측정 잡음 V + 공정 잡음의 정상 분산 W/(1 − λ²)  (AR(1) 근사, λ = 해당 모드 이산 극)
    n = Ad.shape[0]
    r_eps = P["sysid"]["G_eps"]["resid_var"]
    r_p = P["sysid"]["G_p"]["resid_var"]
    lam = np.sort(np.abs(np.linalg.eigvals(Ad)))          # [빠른 극(ITV), 느린 극(손가락)]
    w_p = max(r_p - V[0, 0], 1e-6) * (1 - lam[0] ** 2)
    w_e = max(r_eps - V[1, 1], 1e-6) * (1 - lam[-1] ** 2)
    W = np.diag([w_p, w_e] + ([w_e / M["Ts"] ** 2 * 0.01] if n == 3 else []))
    Bw = np.eye(n)
    Kf, Mss = steady_kalman(Ad, C, Bw, W, V)
    save_params("stoch", dict(V=np.diag(V).tolist(), W=np.diag(W).tolist(), Kf=Kf.tolist(), M=Mss.tolist(),
                              W_scale_sweep=[0.1, 1.0, 10.0]))
    print("Kalman Kf =", Kf.round(4).tolist())
    _ = OUT


if __name__ == "__main__":
    main()
