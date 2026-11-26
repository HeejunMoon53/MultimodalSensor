"""전달함수 관점 (자유 모드): 플랜트 G(z) 와 LQG + 적분 서보의 등가 보상기.

LQG (design_stoch.Lqg, 포화 없는 선형 구간) 를 보상기 상태 z = [x̂(k|k−1); x_I] 로 쓰면
  x̂ = (I − K_f C) x̂⁻ + K_f y,   u = −K x̂ + (K N_x + N_u) r − K_I x_I
  x_I⁺ = x_I + r − ε,           x̂⁻⁺ = A_d x̂ + B_d u
→ u(z) = F(z) r(z) − C_p(z) p(z) − C_ε(z) ε(z)   (2자유도, 1입력 2출력 보상기)
루프 L(z) = C_p G_p + C_ε G_ε (플랜트 입력에서 끊음), 폐루프 T(z) = ε/r.
실행: C:/ml_env/Scripts/python.exe design_tf.py → out/tf_bode.png, params tf
"""
import numpy as np
from scipy import signal

import paths  # noqa: F401
from design_det import ref_gains


def controller_ss(Ad, Bd, C, K, KI, Kf, eps_row=1):
    """보상기 상태공간 (Ac, Bc, Cc, Dc), 입력 [p, ε, r], 출력 u."""
    n = Ad.shape[0]
    K = np.atleast_2d(K)
    Nx, Nu = ref_gains(Ad, Bd, C[eps_row])
    Nr = float((K @ Nx).item() + Nu)
    I_KC = np.eye(n) - Kf @ C
    Cc = np.c_[-K @ I_KC, [[-KI]]]                       # u 의 상태 항
    Dc = np.c_[-K @ Kf, [[Nr]]]                          # u 의 직달 항 [p, ε, r]
    Bdc = Bd.reshape(n, 1)
    Ac = np.zeros((n + 1, n + 1))
    Ac[:n, :n] = Ad @ I_KC + Bdc @ Cc[:, :n]
    Ac[:n, n:] = Bdc @ Cc[:, n:]
    Ac[n, n] = 1.0
    Bc = np.zeros((n + 1, C.shape[0] + 1))
    Bc[:n, :] = np.c_[Ad @ Kf, np.zeros((n, 1))] + Bdc @ Dc
    Bc[n, eps_row], Bc[n, -1] = -1.0, 1.0
    return Ac, Bc, Cc, Dc


def tf_of(A, B, C, D, j, Ts):
    num, den = signal.ss2tf(A, B, C, D, input=j)
    return minreal(np.trim_zeros(np.round(num[0], 12), "f"), den, Ts)


def minreal(num, den, Ts, tol=1e-4):
    """같은 극·영점 상쇄 → 최소 실현 전달함수."""
    z, p, k = signal.tf2zpk(num, den)
    z, p = list(z), list(p)
    for zi in list(z):
        m = [i for i, pi in enumerate(p) if abs(pi - zi) < tol]
        if m:
            z.remove(zi); p.pop(m[0])
    return signal.dlti(*signal.zpk2tf(np.array(z), np.array(p), k), dt=Ts)


def zpk_str(sys, nd=3, var="z"):
    z, p, k = signal.tf2zpk(sys.num, sys.den)
    def fac(r):
        out = []
        for v in sorted(r, key=lambda c: (-c.real, c.imag)):
            if abs(v.imag) > 1e-9:
                if v.imag > 0:
                    out.append(f"({var}² − {2 * v.real:.{nd}g}{var} + {abs(v) ** 2:.{nd}g})")
            elif abs(v) < 1e-9:
                out.append(var)
            else:
                out.append(f"({var} − {v.real:.{nd}g})" if v.real > 0 else f"({var} + {-v.real:.{nd}g})")
        return "".join(out)
    return f"{k:.{nd}g}" + (f"·{fac(z)}" if len(z) else "") + f" / {fac(p)}"


def freq(sys_list, w):
    return [signal.dfreqresp(s, w)[1] for s in sys_list]


def margins_L(Lw, w, Ts):
    """음의 되먹임 L: 이득 교차의 위상 여유, 음의 실축 교차(나이퀴스트 끝점 포함)의 이득 여유."""
    mag = np.abs(Lw)
    i = np.where(np.diff(np.sign(mag - 1.0)) != 0)[0]
    pm = float(np.min((np.degrees(np.angle(Lw[i])) + 360) % 360 - 180)) if len(i) else np.inf
    wc = float(w[i[0]] / Ts) if len(i) else np.nan
    j = [k for k in np.where(np.diff(np.sign(Lw.imag)) != 0)[0] if Lw.real[k] < 0]
    if Lw.real[-1] < 0 and abs(Lw.imag[-1]) < 1e-9 * mag[-1]:
        j.append(len(Lw) - 1)                             # z = −1 (ω = π/T_s) 에서 실축
    gm = float(-20 * np.log10(np.min(mag[j]))) if len(j) else np.inf
    return gm, pm, wc


def design(P):
    M, D, S = P["model"], P["det"]["lqr"], P["stoch"]
    Ad, Bd, C, Ts = np.array(M["Ad"]), np.array(M["Bd"]), np.array(M["C"]), M["Ts"]
    K, KI, Kf = np.array(D["K"]), D["KI"], np.array(S["Kf"])
    Gp = tf_of(Ad, Bd, C[[0]], [[0]], 0, Ts)
    Ge = tf_of(Ad, Bd, C[[1]], [[0]], 0, Ts)
    Ac, Bc, Cc, Dc = controller_ss(Ad, Bd, C, K, KI, Kf)
    Cp = tf_of(Ac, Bc, -Cc, -Dc, 0, Ts)                  # u = −C_p p − C_ε ε + F r
    Ce = tf_of(Ac, Bc, -Cc, -Dc, 1, Ts)
    F = tf_of(Ac, Bc, Cc, Dc, 2, Ts)
    # 루프 L = C_p G_p + C_ε G_ε, 폐루프 ε/r = G_ε F / (1 + L): 직렬 상태공간으로 정확히
    n = Ad.shape[0]
    Acl = np.block([[Ad + Bd @ Dc[:, :2] @ C, Bd @ Cc], [Bc[:, :2] @ C, Ac]])
    Bcl = np.r_[Bd * Dc[0, 2], Bc[:, 2:]]
    T = tf_of(Acl, Bcl, np.c_[C[[1]], np.zeros((1, n + 1))], [[0]], 0, Ts)
    w = np.logspace(-3, np.log10(np.pi), 4000)
    gpw, gew, cpw, cew = freq([Gp, Ge, Cp, Ce], w)
    Lw = cpw * gpw + cew * gew
    gm, pm, wc = margins_L(Lw, w, Ts)
    phys = M["phys"]
    Gep = minreal(np.polymul(Ge.num, Gp.den), np.polymul(Ge.den, Gp.num), Ts)   # ε/p
    return dict(
        Gp_s=f"{phys['K_p']:.3g} / ({phys['tau_v']:.3g}s + 1)", Ge_s=f"{phys['K_f']:.3g} / ({phys['tau_f']:.3g}s + 1)",
        Gp=zpk_str(Gp), Gep=zpk_str(Gep), Ge=zpk_str(Ge), Cp=zpk_str(Cp), Ce=zpk_str(Ce), F=zpk_str(F), T=zpk_str(T),
        delay_pm_loss_deg=float(np.degrees(wc * (phys["theta_p"] + phys["theta_e"]))),   # 모델에 없는 지연 θ 의 ω_c 위상
        T_dc=float(np.real(signal.dfreqresp(T, [1e-6])[1][0])), cl_poles=np.abs(np.roots(T.den)).round(4).tolist(),
        gm_db=gm, pm_deg=pm, wc_rad_s=wc,
    ), dict(w=w / Ts, L=Lw, G=gew, T=signal.dfreqresp(T, w)[1], Ts=Ts, sys=dict(Gp=Gp, Ge=Ge, Cp=Cp, Ce=Ce, F=F, T=T))


def plot(fr, out, gm, pm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    w = fr["w"]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.0, 5.2), sharex=True)
    for y, lab, c in ((fr["G"], "플랜트 G_ε(z) = ε/u", "#7F7F7F"), (fr["L"], "루프 L(z) = C_p G_p + C_ε G_ε", "#1F4E79"),
                      (fr["T"], "폐루프 T(z) = ε/r", "#C55A11")):
        a1.semilogx(w, 20 * np.log10(np.abs(y)), lw=2, color=c, label=lab)
        a2.semilogx(w, np.degrees(np.unwrap(np.angle(y))), lw=2, color=c)
    a1.axhline(0, color="#BBBBBB", lw=0.8); a2.axhline(-180, color="#BBBBBB", lw=0.8)
    a1.set_ylabel("크기 [dB]"); a2.set_ylabel("위상 [°]"); a2.set_xlabel("ω [rad/s]  (나이퀴스트 π/T_s = 314)")
    a1.set_ylim(-60, 60); a1.legend(fontsize=8, frameon=False, loc="lower left")
    a1.set_title(f"LQG 등가 루프 (시뮬레이션 모델): GM {gm:.1f} dB, PM {pm:.1f}°", fontsize=10)
    a2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))   # 맑은 고딕에 수식 − 없음
    for a in (a1, a2):
        a.grid(True, which="both", color="#EEEEEE", lw=0.6)
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out, dpi=200); plt.close(fig)


def main():
    from paths import OUT, load_params, save_params
    P = load_params()
    res, fr = design(P)
    plot(fr, OUT / "tf_bode.png", res["gm_db"], res["pm_deg"])
    save_params("tf", res)
    for k, v in res.items():
        print(k, "=", v)


if __name__ == "__main__":
    main()
