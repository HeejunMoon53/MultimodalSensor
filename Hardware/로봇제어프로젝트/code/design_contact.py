"""접촉 모드 (스펙 12절): 상태 x = [p, ε_f] 그대로, 출력만 F = k_eq·(ε_f − ε_c) 로 바뀐다.

- 가관측성 (과제 3절): 접촉 중 ε 만 측정하면 출력 이득 g → 0 (막힌 손가락) 에서 관측 불가, F̂ 를 쓰면 유지
- 접촉용 LQR (4절): C_F = [0, k_eq] 로 적분 확장 → k_eq 격자에서 DARE, 실행 중 보간 (게인 스케줄)
- RLS (P2 Lec3 최소제곱의 재귀형): F̂ = k_eq·ε_f,m + c, ε_f,m 은 측정 p 로 돌린 개루프 모델 (k_eq 와 독립)
- 칼만 (5절): F̂ 를 ε_f 측정으로 환산 ε̃_f = (F̂ − c)/k̂_eq, V_ε = V_F / k̂_eq²
"""
import numpy as np

import paths  # noqa: F401
from analysis import gramian_obsv
from design_det import augment_integral, bryson, dlqr, ref_gains
from design_stoch import Kalman

DF_TOL = 0.4      # Bryson 힘 오차 허용 [N] (가정값)
N_INT = 25        # 적분 상태 허용 = DF_TOL × 25 샘플 (자유 모드와 같은 규칙)
EPS_C_BAND = 4.0  # 접촉점 ε_c 추정 허용 범위 ± [%] (진입 순간 값 기준, 가정값)


def contact_C(k_eq, g):
    """접촉 모드 출력 행렬 (편차): 행 = [p, F, ε]."""
    return np.array([[1.0, 0.0], [0.0, k_eq], [0.0, g]])


def contact_obsv(Ad, k_eq, g):
    """출력 조합별 가관측성 그래미안 최소 특이값."""
    C = contact_C(k_eq, g)
    sets = {"p": C[:1], "F": C[1:2], "eps": C[2:3], "p+F": C[:2]}
    return {k: float(np.linalg.svd(gramian_obsv(Ad, c), compute_uv=False)[-1]) for k, c in sets.items()}


def contact_lqr(Ad, Bd, k_eq, dF=DF_TOL, u_max=15.0):
    """적분 확장 (x_I += F_ref − F) + Bryson [δp 15 kPa, δε_f 2 %, x_I dF·25] → (K, K_I, Aa, Ba)."""
    Aa, Ba, _ = augment_integral(Ad, Bd, np.array([0.0, k_eq]))
    Q, R = bryson([15.0, 2.0, dF * N_INT], u_max)
    K, _ = dlqr(Aa, Ba, Q, R)
    return K[:, :-1], float(K[0, -1]), Aa, Ba


def make_schedule(Ad, Bd, grid):
    """k_eq 격자에서 미리 푼 게인을 선형 보간 (격자 밖은 끝값)."""
    grid = np.sort(np.asarray(grid, float))
    Ks, KIs = zip(*[contact_lqr(Ad, Bd, k)[:2] for k in grid])
    Ks, KIs = np.array([k.ravel() for k in Ks]), np.array(KIs)

    def sched(k):
        k = float(np.clip(k, grid[0], grid[-1]))
        return np.array([[np.interp(k, grid, Ks[:, j]) for j in range(Ks.shape[1])]]), float(np.interp(k, grid, KIs))
    sched.grid = grid
    return sched


class Rls:
    """재귀 최소제곱 (망각 계수 λ): θ ← θ + P φ (y − φᵀθ)/(λ + φᵀPφ),  P ← (P − PφφᵀP/(λ + φᵀPφ))/λ."""

    def __init__(self, theta0, lam=0.99, P0=None, p_max=1e4):
        self.theta = np.asarray(theta0, float).copy()
        self.P = np.diag(P0 if P0 is not None else [1.0] * len(self.theta)).astype(float)
        self.lam, self.p_max = lam, p_max

    def update(self, phi, y):
        phi = np.asarray(phi, float)
        Pphi = self.P @ phi
        g = Pphi / (self.lam + phi @ Pphi)
        self.theta = self.theta + g * (float(y) - phi @ self.theta)
        self.P = (self.P - np.outer(g, Pphi)) / self.lam
        if np.trace(self.P) > self.p_max:  # 여기 부족 시 공분산 폭주 방지
            self.P *= self.p_max / np.trace(self.P)
        return self.theta


class ContactLqg:
    """접촉 모드 힘 추종: u = u₀ − K(k̂)(x̂ − N_x r) + N_u r − K_I(k̂)·x_I,  r = (F_ref − ĉ)/k̂ − ε₀,  x_I += F_ref − F̂.

    use_rls=False 이면 k̂ = k_nom 고정, ĉ 는 진입 순간 ε_c 로만 정한다 (공칭 설계).
    dob_factory(y0, u0) → Dob: 같은 ARX(u → ε_f) 에 ε̃_f 를 넣는다 (진입마다 새로, 무충격).
    """

    def __init__(self, Ad, Bd, x0, u0, phys, sched, k_nom, V_p, V_F, W, use_rls=True, dob_factory=None,
                 u_lim=(0.0, 30.0), lam=0.999, F_min=0.2, k_lim=None):
        self.Ad, self.Bd, self.x0, self.u0 = Ad, Bd, np.asarray(x0, float), u0
        self.sched, self.k_nom, self.V_p, self.V_F = sched, k_nom, V_p, V_F
        self.use_rls, self.dob_factory, self.u_lim = use_rls, dob_factory, u_lim
        self.lam, self.F_min = lam, F_min
        self.k_lim = k_lim or (float(sched.grid[0]), float(sched.grid[-1]))  # 투영 범위 = 게인 격자 (물리적 사전 범위)
        self.kf = Kalman(Ad, Bd, np.eye(2), np.eye(2), np.diag(W), np.diag([V_p, V_F / k_nom ** 2]), np.zeros(2), np.eye(2))
        self.Nx, self.Nu = ref_gains(Ad, Bd, np.array([0.0, 1.0]))
        self.k_eq, self.c = k_nom, 0.0

    def enter(self, x_abs, u_prev):
        """접촉 진입: 상태는 자유 모드 추정을 이어받고, ε_c = 현재 ε_f, x_I 는 첫 u() 에서 무충격으로 정한다."""
        dx = np.asarray(x_abs, float) - self.x0
        self.kf.x_prior, self.kf.M = dx.copy(), np.eye(2) * 0.1
        self.efm = float(dx[1])
        eps_c = float(x_abs[1])
        self.k_eq, self.c = self.k_nom, -self.k_nom * eps_c
        self.rls = Rls([self.k_eq, self.c], lam=self.lam, P0=[0.005, 5.0])  # 느린 적응: F̂ 잡음 σ≈0.25 N
        self.eps_c0 = eps_c
        self.u_prev, self.xI, self._bump = float(u_prev), 0.0, True
        self.dob = None

    def u(self, p, F_hat, F_ref, eps_hat=None):
        dp = float(p) - self.x0[0]
        if self.use_rls and F_hat > self.F_min:
            k, c = self.rls.update([self.efm + self.x0[1], 1.0], F_hat)
            # 투영 RLS: k̂ ∈ 게인 격자, ε̂_c = −ĉ/k̂ ∈ 진입값 ± EPS_C_BAND (센서 오류에 파라미터가 끌려가지 않게)
            k = float(np.clip(k, *self.k_lim))
            ec = float(np.clip(-c / k, self.eps_c0 - EPS_C_BAND, self.eps_c0 + EPS_C_BAND))
            self.rls.theta[:] = (k, -k * ec)
            self.k_eq, self.c = k, -k * ec
        k, c = self.k_eq, self.c
        ytil = (F_hat - c) / k - self.x0[1]                    # F̂ → ε_f 측정 (편차)
        self.kf.V = np.diag([self.V_p, self.V_F / k ** 2])
        xh = self.kf.update([dp, ytil])
        K, KI = self.sched(k)
        dr = (F_ref - c) / k - self.x0[1]
        fb = float(-(K @ (xh - self.Nx * dr)).item() + self.Nu * dr)
        if self._bump:                                         # u(진입) = u_prev 가 되게 x_I 초기화
            self.xI, self._bump = (self.u0 + fb - self.u_prev) / KI, False
            if self.dob_factory is not None:
                self.dob = self.dob_factory(ytil + self.x0[1], self.u_prev)
        uc = self.u0 + fb - KI * self.xI
        u = self.dob.correct(uc, ytil + self.x0[1]) if self.dob is not None else uc
        sat = min(max(u, self.u_lim[0]), self.u_lim[1])
        e = F_ref - F_hat
        if sat == u or np.sign(e) != np.sign(u - sat):
            self.xI += e
        du = sat - self.u0
        self.kf.predict(du)
        self.efm = self.Ad[1, 0] * dp + self.Ad[1, 1] * self.efm + self.Bd[1, 0] * du
        self.u_prev = sat
        return sat


def main():
    """가관측성 비교 그림 + 접촉용 게인 격자 → params["contact_design"]."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from design_det import load_model
    from paths import OUT, load_params, save_params
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "mathtext.fontset": "dejavusans"})
    P = load_params()
    Ad, Bd, *_ = load_model(P)
    ct = P.get("contact", {})
    keqs = [v["k_eq"] for v in ct.get("geometry", [])] or [0.3, 0.5]
    grid = [round(x, 3) for x in np.linspace(0.8 * min(keqs), 1.2 * max(keqs), 5)]
    k_nom = float(ct.get("conductor", {}).get("k_eq", np.median(keqs)))
    gs = np.logspace(-3, 0, 40)
    so = [contact_obsv(Ad, k_nom, g) for g in gs]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.loglog(gs, [s["eps"] for s in so], c="#2CA02C", label="센서 ε 만 (접촉 중)")
    ax.loglog(gs, [s["F"] for s in so], c="#c0392b", label="센서 F 만")
    ax.loglog(gs, [s["p"] for s in so], c="#999", ls="--", label="p 만")
    for v in ct.get("geometry", []):
        ax.axvline(v["g"], c="#2CA02C", lw=0.5, alpha=0.5)
    from matplotlib.ticker import FuncFormatter
    for axis in (ax.xaxis, ax.yaxis):  # 로그 눈금을 1e−3 대신 1e-3 (맑은 고딕 수식 글꼴 깨짐 회피)
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"1e{np.log10(v):.0f}"))
    ax.set_xlabel("ε 출력 이득 g = k_eq / k_env  (0 = 손가락이 막힘)")
    ax.set_ylabel("가관측성 그래미안 최소 특이값")
    ax.set_title("접촉 모드 가관측성 (세로선 = S8 측정 g, 시뮬레이션)", fontsize=9)
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT / "contact_obsv.png", dpi=150)
    gains = {f"{k:.3f}": dict(zip(("K", "KI"), (lambda r: (r[0].tolist(), r[1]))(contact_lqr(Ad, Bd, k)))) for k in grid}
    save_params("contact_design", dict(k_nom=k_nom, grid=grid, gains=gains, dF_tol=DF_TOL,
                                       obsv_at_g01=contact_obsv(Ad, k_nom, 0.01), obsv_at_g03=contact_obsv(Ad, k_nom, 0.3)))
    print("contact grid", grid, "k_nom", k_nom)


if __name__ == "__main__":
    main()
