"""과제 3절: 상태공간 실현·이산화·안정성(Lyapunov)·가제어/가관측 (강의 Lec3–Lec7).

물리 상태 x = [p, ε, ε̇]  (p: ITV 출력 압력 kPa, ε: 센서 변형률 %)
  ITV    : τ_v·ṗ = −p + u
  손가락 : ε̈ + 2ζω_n·ε̇ + ω_n²·ε = ω_n²·K_f·p
"""
import numpy as np
from scipy import linalg

import paths  # noqa: F401


def physical_ss(tau_v, K_f, wn, zeta):
    A = np.array([[-1 / tau_v, 0, 0], [0, 0, 1], [wn ** 2 * K_f, -wn ** 2, -2 * zeta * wn]], float)
    B = np.array([[1 / tau_v], [0], [0]])
    C = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    return A, B, C


def physical_ss2(tau_v, K_p, K_f, tau_f):
    """과감쇠 손가락(1차)일 때: x = [p, ε],  τ_f ε̇ = −ε + K_f p."""
    A = np.array([[-1 / tau_v, 0], [K_f / tau_f, -1 / tau_f]], float)
    B = np.array([[K_p / tau_v], [0]])
    return A, B, np.eye(2)


def model_ss(phys):
    if phys.get("order", 3) == 2:
        return physical_ss2(phys["tau_v"], phys["K_p"], phys["K_f"], phys["tau_f"])
    return physical_ss_full(phys["tau_v"], phys["K_p"], phys["K_f"], phys["wn"], phys["zeta"])


def ctrb_canonical(num, den):
    """가제어 정준형 (Lec3_3 p23): 마지막 행 = −[a₀ … a_{n−1}], B = e_n, C = [b₀ … ]."""
    den = np.asarray(den, float) / den[0]
    n = len(den) - 1
    num = np.r_[np.zeros(n + 1 - len(num)), num] / 1.0
    A = np.eye(n, k=1)
    A[-1, :] = -den[1:][::-1]
    B = np.zeros((n, 1)); B[-1] = 1.0
    b = num[1:] - num[0] * den[1:]          # 엄밀하지 않은 진 부분 제거
    C = b[::-1][None, :]
    D = np.array([[num[0]]])
    return A, B, C, D


def similarity(A1, A2):
    """Q⁻¹·A1·Q = A2 인 Q (두 행렬이 대각화 가능하고 고유값이 같을 때)."""
    w1, V1 = np.linalg.eig(A1)
    w2, V2 = np.linalg.eig(A2)
    V1, V2 = V1[:, np.argsort(w1)], V2[:, np.argsort(w2)]
    return np.real_if_close(V1 @ np.linalg.inv(V2))


def c2d(A, B, Ts):
    """ZOH: Ad = e^{A·Ts}, Bd = ∫₀^Ts e^{Aτ}dτ·B (확대 행렬 지수)."""
    n, m = B.shape
    M = np.zeros((n + m, n + m))
    M[:n, :n], M[:n, n:] = A, B
    E = linalg.expm(M * Ts)
    return E[:n, :n], E[:n, n:]


def dlyap(A, Q):
    """X − A·X·Aᵀ = Q 의 해. A에 A_dᵀ를 넣으면 A_dᵀ·P·A_d − P = −Q."""
    return linalg.solve_discrete_lyapunov(A, Q)


def is_pd(P):
    P = (P + P.T) / 2
    return bool(np.all(np.linalg.eigvalsh(P) > 0))


def ctrb(A, B):
    return np.hstack([np.linalg.matrix_power(A, k) @ B for k in range(A.shape[0])])


def obsv(A, C):
    return np.vstack([C @ np.linalg.matrix_power(A, k) for k in range(A.shape[0])])


def rank(M, tol=1e-9):
    s = np.linalg.svd(M, compute_uv=False)
    return int(np.sum(s > tol * max(s[0], 1e-300)))


def gramian_obsv(A, C, N=500):
    W, Ak = np.zeros((A.shape[0],) * 2), np.eye(A.shape[0])
    for _ in range(N):
        W += Ak.T @ C.T @ C @ Ak
        Ak = A @ Ak
    return W


def kalman_decomp(A, B, C):
    """가제어 부분공간(range 𝒞)과 비가관측 부분공간(null 𝒪)의 기저 (Lec7_3)."""
    Rc = linalg.orth(ctrb(A, B))
    No = linalg.null_space(obsv(A, C))
    return dict(dim_ctrb=Rc.shape[1], dim_unobs=No.shape[1], ctrb_basis=Rc, unobs_basis=No)


def _freq(num, den, w, Ts=None):
    """연속 (Ts=None) 또는 이산 (z = e^{jωTs}, 계수는 z 내림차순) 주파수 응답."""
    s = np.exp(1j * w * Ts) if Ts else 1j * w
    return np.polyval(num, s) / np.polyval(den, s)


def fit_physical(G_p, G_eps, Ts=None, w=np.logspace(-1, np.log10(30.0), 120)):
    """식별한 G_p, G_ε 의 주파수 응답에 물리 모델(+순수 지연)을 최소제곱으로 맞춘다.

    G_p = K_p e^{−sθ_p}/(τ_v s + 1),   G_ε = K_p K_f ω_n² e^{−sθ_e}/((τ_v s + 1)(s² + 2ζω_n s + ω_n²))
    Ts 를 주면 G_p, G_ε 는 이산 G(z) 계수로 본다 (지연 nk 의 z=0 극 때문에 d2c 대신 직접 비교).
    지연 θ 는 상태공간에는 넣지 않고 보고·강건성 검토에 쓴다.
    """
    from scipy.optimize import least_squares
    Hp, He = _freq(*G_p, w, Ts), _freq(*G_eps, w, Ts)

    def model(th):
        tau, Kp, Kf, wn, z, tp, te = th
        s = 1j * w
        gp = Kp / (tau * s + 1)
        ge = gp * Kf * wn ** 2 / (s ** 2 + 2 * z * wn * s + wn ** 2)
        return gp * np.exp(-s * tp), ge * np.exp(-s * te)

    def res(th):
        gp, ge = model(th)
        r = [np.log(gp / Hp), np.log(ge / He)]
        r = [np.r_[x.real, np.angle(np.exp(1j * x.imag))] for x in r]
        return np.concatenate(r)

    Kp0 = float(abs(Hp[0])); Kf0 = float(abs(He[0]) / max(Kp0, 1e-9))
    best = None
    for wn0 in (3.0, 10.0, 30.0):
        sol = least_squares(res, [0.05, Kp0, Kf0, wn0, 0.7, 0.01, 0.03],
                            bounds=([1e-3, 1e-3, 1e-4, 0.1, 0.05, 0, 0], [5, 10, 100, 2000, 50, 0.3, 1.0]))
        if best is None or sol.cost < best.cost:
            best = sol
    tau, Kp, Kf, wn, z, tp, te = best.x
    gp, ge = model(best.x)
    err = float(np.sqrt(np.mean(np.abs(np.log(ge / He)) ** 2)))
    out = dict(order=3, tau_v=float(tau), K_p=float(Kp), K_f=float(Kf), wn=float(wn), zeta=float(z),
               theta_p=float(tp), theta_e=float(te), fit_rms_log=err)
    if z > 3.0:  # 과감쇠: 손가락을 1차(τ_f)로 다시 맞춘다 → x = [p, ε] (스펙 3절)
        def model1(th):
            tau, Kp, Kf, tf, tp, te = th
            s = 1j * w
            gp = Kp / (tau * s + 1)
            return gp * np.exp(-s * tp), gp * Kf / (tf * s + 1) * np.exp(-s * te)

        def res1(th):
            gp, ge = model1(th)
            r = [np.log(gp / Hp), np.log(ge / He)]
            return np.concatenate([np.r_[x.real, np.angle(np.exp(1j * x.imag))] for x in r])
        sol = least_squares(res1, [tau, Kp, Kf, 0.2, tp, te], bounds=([1e-3, 1e-3, 1e-4, 1e-3, 0, 0], [5, 10, 100, 10, 0.3, 1.0]))
        tau, Kp, Kf, tf, tp, te = sol.x
        ge = model1(sol.x)[1]
        out = dict(order=2, tau_v=float(tau), K_p=float(Kp), K_f=float(Kf), tau_f=float(tf), theta_p=float(tp),
                   theta_e=float(te), fit_rms_log=float(np.sqrt(np.mean(np.abs(np.log(ge / He)) ** 2))),
                   order3_rejected=dict(wn=float(wn), zeta=float(z)))
    return out


def physical_tf(phys, out="eps", delay=False):
    """물리 모델의 연속 전달함수 (num, den). delay=True 면 1차 Padé 로 θ 근사."""
    A, B, C = model_ss(phys)
    from scipy import signal
    n, d = signal.ss2tf(A, B, C[1:2] if out == "eps" else C[:1], [[0]])
    n = np.trim_zeros(np.round(n[0], 12), "f")
    if delay:
        th = phys["theta_e" if out == "eps" else "theta_p"]
        n, d = np.convolve(n, [-th / 2, 1]), np.convolve(d, [th / 2, 1])
    return n, d


def physical_ss_full(tau_v, K_p, K_f, wn, zeta):
    A, B, C = physical_ss(tau_v, K_f, wn, zeta)
    return A, B * K_p, C


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from paths import OUT, load_params, save_params
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
    P = load_params()
    sy, Ts = P["sysid"], 0.01
    phys = fit_physical((sy["G_p"]["num_z"], sy["G_p"]["den_z"]), (sy["G_eps"]["num_z"], sy["G_eps"]["den_z"]), Ts=Ts)
    A, B, C = model_ss(phys)
    n = A.shape[0]
    Ad, Bd = c2d(A, B, Ts)
    eig_c, eig_d = np.linalg.eigvals(A), np.linalg.eigvals(Ad)
    Pl = dlyap(Ad.T, np.eye(n))
    obs = {"p": C[:1], "eps": C[1:2], "both": C}
    rk = {k: rank(obsv(Ad, c)) for k, c in obs.items()}
    gsv = {k: float(np.linalg.svd(gramian_obsv(Ad, c), compute_uv=False)[-1]) for k, c in obs.items()}
    kd = kalman_decomp(Ad, Bd, C[:1])
    x0 = np.r_[sy["G_p"]["y0"], sy["G_eps"]["y0"], np.zeros(n - 2)]
    save_params("model", dict(n=n, phys=phys, A=A.tolist(), B=B.tolist(), C=C.tolist(), Ad=Ad.tolist(), Bd=Bd.tolist(),
                              Ts=Ts, x0=x0.tolist(), u0=sy["G_eps"]["u0"],
                              eig_c=[[float(e.real), float(e.imag)] for e in eig_c],
                              eig_d_abs=[float(abs(e)) for e in eig_d], lyap_P=Pl.tolist(), lyap_pd=is_pd(Pl),
                              rank_ctrb=rank(ctrb(Ad, Bd)), rank_obsv=rk, gram_min_sv=gsv,
                              kalman_p_only=dict(dim_ctrb=kd["dim_ctrb"], dim_unobs=kd["dim_unobs"])))
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    th = np.linspace(0, 2 * np.pi, 200)
    ax[0].plot(np.cos(th), np.sin(th), c="gray", lw=0.8)
    ax[0].plot(eig_d.real, eig_d.imag, "x", ms=10, mew=2, c="#c0392b")
    ax[0].set(aspect="equal", title="개루프 이산 극 (Ts = 10 ms)", xlabel="Re z", ylabel="Im z")
    ax[0].set_xlim(-1.1, 1.1); ax[0].set_ylim(-1.1, 1.1)
    ks = list(gsv)
    ax[1].bar(["압력 p만", "센서 ε만", "p + ε"], [max(gsv[k], 1e-16) for k in ks], color=["#999", "#2CA02C", "#444"])
    ax[1].set_yscale("log"); ax[1].set_title("가관측 그래미안 최소 특이값 (작을수록 관측 어려움)")
    for i, k in enumerate(ks):
        ax[1].text(i, max(gsv[k], 1e-16), f"rank {rk[k]}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("상태공간 해석 (시뮬레이션)", fontsize=10); fig.tight_layout()
    fig.savefig(OUT / "analysis_poles_obsv.png", dpi=150)
    print("model:", phys, "rank obsv", rk, "lyap_pd", is_pd(Pl))


if __name__ == "__main__":
    main()
