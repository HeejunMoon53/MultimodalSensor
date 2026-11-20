"""과제 6절: 외란 관측기 DOB (과제 PDF, 강의 전).

공칭 모델(식별 ARX): A(z⁻¹)·y(k) = z^{−nk}·B(z⁻¹)·u(k)
외란 추정:  d̂(k) = Q(z⁻¹)·[ (A/B)(z⁻¹)·y(k) − u(k − nk) ]
보정:       u(k)  = u_c(k) − d̂(k)
Q(s) = 1/(τ_q·s + 1)^r 를 ZOH 이산화. (A/B) 는 B의 영점이 단위원 안일 때 인과·안정이다.
연속 P_n⁻¹ 을 이산화하면 생기는 샘플링 영점(단위원 밖) 문제를 피하려고 이산 공칭 모델로 바로 만든다.
"""
from collections import deque

import numpy as np
from scipy import signal

import paths  # noqa: F401


def q_filter(tau_q, r):
    den = np.array([1.0])
    for _ in range(r):
        den = np.convolve(den, [tau_q, 1.0])
    return np.array([1.0]), den


class _Iir:
    def __init__(self, b, a):
        b, a = np.asarray(b, float), np.asarray(a, float)
        self.b, self.a = b / a[0], a / a[0]
        self.x = deque([0.0] * len(self.b), maxlen=len(self.b))
        self.y = deque([0.0] * max(len(self.a) - 1, 1), maxlen=max(len(self.a) - 1, 1))

    def __call__(self, v):
        self.x.appendleft(float(v))
        out = float(np.dot(self.b, self.x))
        if len(self.a) > 1:
            out -= float(np.dot(self.a[1:], list(self.y)[:len(self.a) - 1]))
        self.y.appendleft(out)
        return out


def _min_phase(b):
    """B의 단위원 밖 영점을 안으로 반사하고 DC 이득은 유지 (shortcut: 역필터 안정화용 근사)."""
    b = np.asarray(b, float)
    z = np.roots(b) if len(b) > 1 else np.array([])
    if np.all(np.abs(z) < 1.0):
        return b
    z = np.where(np.abs(z) >= 1.0, 1.0 / np.conj(z) * 0.999, z)
    nb = np.real(np.poly(z)) * b[0]
    return nb * (b.sum() / nb.sum())


class Dob:
    def __init__(self, a, b, nk, tau_q, Ts, r=2, y0=0.0, u0=0.0):
        A = np.r_[1.0, np.asarray(a, float)]
        B = _min_phase(b)
        nq, dq, _ = signal.cont2discrete(q_filter(tau_q, r), Ts, method="zoh")
        nq = np.squeeze(nq)
        self.H1 = _Iir(np.convolve(nq, A), np.convolve(dq, B))
        self.Hq = _Iir(nq, dq)
        self.ubuf = deque([0.0] * nk, maxlen=nk)
        self.y0, self.u0, self.tau_q = y0, u0, tau_q
        self.d_hat = 0.0

    def correct(self, u_c, y):
        u_old = self.ubuf[-1]
        self.d_hat = self.H1(y - self.y0) - self.Hq(u_old)
        u = u_c - self.d_hat
        self.ubuf.appendleft(u - self.u0)
        return u


def robust_bound(Pn, P_true_list, tau_q, r=2, w=np.logspace(-2, 3, 2000)):
    """강건 안정 조건 max_ω |Q(jω)·Δ(jω)| < 1,  P = P_n(1 + Δ). Pn, P: (num_s, den_s)."""
    _, Qj = signal.freqs(*q_filter(tau_q, r), worN=w)
    _, Pnj = signal.freqs(*Pn, worN=w)
    worst = 0.0
    for P in P_true_list:
        _, Pj = signal.freqs(*P, worN=w)
        worst = max(worst, float(np.max(np.abs(Qj * (Pj / Pnj - 1.0)))))
    return worst < 1.0, worst


def main():
    from paths import load_params, save_params
    P = load_params()
    Ge = P["sysid"]["G_eps"]
    phys = P["model"]["phys"]
    Ad, Ts = np.array(P["model"]["Ad"]), P["model"]["Ts"]
    lam_dom = float(np.min(np.abs(np.log(np.abs(np.linalg.eigvals(Ad))) / Ts)))
    # Q필터 차단 주파수 후보: 개루프 지배 극 |λ_dom| 의 1·2·4·8 배
    taus = [1.0 / (k * lam_dom) for k in (1.0, 2.0, 4.0, 8.0)]
    from analysis import physical_tf
    Pn = physical_tf(phys, "eps")
    # 섭동 플랜트(강성 ±30 % → 정적 이득 K_f ∓, τ_v ×2) + 실제에만 있는 순수 지연 θ_e (1차 Padé)
    pert = []
    for kf, tv in ((1.3, 1.0), (0.7, 1.0), (1.0, 2.0)):
        ph = dict(phys, K_f=phys["K_f"] / kf, tau_v=phys["tau_v"] * tv)
        pert.append(physical_tf(ph, "eps", delay=True))
    rob = {f"{t:.4f}": dict(zip(("ok", "worst"), robust_bound(Pn, pert, t))) for t in taus}
    ok = [t for t in taus if rob[f"{t:.4f}"]["ok"]]
    # 선택: 강건 조건을 만족하는 후보 중 개루프 대역의 2배 (τ_q = 1/(2|λ_dom|)).
    # 더 빠른 τ_q 는 S5 에서 ε̂ 잡음이 입력으로 들어와 오버슈트·입력 변동이 급증 (25 ms: 오버슈트 18 %).
    tau_sel = taus[1] if taus[1] in ok else (max(ok) if ok else max(taus))
    save_params("dob", dict(tau_q_list=taus, tau_q=tau_sel, r=2, robust=rob))
    print("DOB τ_q 후보", [round(t, 4) for t in taus], "선택", round(tau_sel, 4), rob)


if __name__ == "__main__":
    main()
