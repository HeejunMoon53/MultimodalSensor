"""과제 2절: 시스템 식별 (ARX 최소제곱, 강의 P2_Lec3).

y(k) = −a₁y(k−1) − … − a_n y(k−n) + b₁u(k−nk) + … + b_m u(k−nk−m+1) + e(k)
θ̂ = (ΦᵀΦ)⁻¹ΦᵀY  (np.linalg.lstsq 로 수치 안정하게 계산)
"""
import numpy as np
from scipy import linalg, signal

import paths  # noqa: F401


# ---------------- 가진 신호 ----------------
def prbs(n, bits, amp, seed, hold=1):
    """최대 길이 수열(m-sequence) ±amp, 각 비트를 hold 샘플 유지."""
    rng = np.random.default_rng(seed)
    state = rng.integers(0, 2, bits)
    if not state.any():
        state[0] = 1
    seq = signal.max_len_seq(bits, state=state, length=int(np.ceil(n / hold)))[0]
    return amp * (2.0 * np.repeat(seq, hold)[:n] - 1.0)


def chirp(t, f0=0.05, f1=5.0, amp=3.0):
    return amp * signal.chirp(t, f0=f0, t1=t[-1], f1=f1, method="logarithmic")


# ---------------- ARX ----------------
def _regressors(y, u, na, nb, nk):
    k0 = max(na, nb + nk - 1)
    rows = [np.r_[-y[k - na:k][::-1], u[k - nk - nb + 1:k - nk + 1][::-1]] for k in range(k0, len(y))]
    return np.array(rows), y[k0:]


def arx_ls(y, u, na, nb, nk=1):
    y, u = np.asarray(y, float), np.asarray(u, float)
    Phi, Y = _regressors(y, u, na, nb, nk)
    if np.linalg.cond(Phi) > 1e10:
        raise ValueError("가진 부족: 회귀 행렬 Φ가 특이에 가깝다 (입력에 변화가 없다)")
    th = np.linalg.lstsq(Phi, Y, rcond=None)[0]
    return th[:na], th[na:]


def simulate_arx(a, b, nk, u, y0):
    """잡음 없는 자유 시뮬레이션 (출력 오차 검증용)."""
    na, nb = len(a), len(b)
    y = np.zeros(len(u))
    y[:na] = np.asarray(y0, float)[:na] if na else y[:0]
    for k in range(max(na, nb + nk - 1), len(u)):
        y[k] = -np.dot(a, y[k - na:k][::-1]) + np.dot(b, u[k - nk - nb + 1:k - nk + 1][::-1])
    return y


def fit_pct(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(100.0 * (1.0 - np.linalg.norm(y - yhat) / np.linalg.norm(y - y.mean())))


def aic(y, yhat, n_par):
    e = np.asarray(y) - np.asarray(yhat)
    return float(len(e) * np.log(np.mean(e ** 2)) + 2 * n_par)


def select_order(y_id, u_id, y_val, u_val, max_order=4, nk_list=(1, 2, 3)):
    """검증 적합도(자유 시뮬레이션)가 최고값의 1 %p 안인 가장 작은 차수."""
    table = []
    for na in range(1, max_order + 1):
        for nb in range(1, na + 1):
            for nk in nk_list:
                try:
                    a, b = arx_ls(y_id, u_id, na, nb, nk)
                except ValueError:
                    continue
                if np.any(np.abs(np.roots(np.r_[1.0, a])) >= 1.0):
                    continue  # 불안정 모델은 버린다
                yh = simulate_arx(a, b, nk, u_val, y_val[:na])
                table.append(dict(na=na, nb=nb, nk=nk, fit=fit_pct(y_val, yh),
                                  aic=aic(y_val, yh, na + nb), a=a.tolist(), b=b.tolist()))
    best = max(r["fit"] for r in table)
    pick = min((r for r in table if r["fit"] >= best - 1.0), key=lambda r: (r["na"] + r["nb"], r["nk"]))
    return dict(pick=pick, table=table)


def arx_to_tf(a, b, nk):
    """G(z) 계수 (z의 내림차순 다항식)."""
    na, nb = len(a), len(b)
    n = max(na, nb + nk - 1)
    den = np.r_[1.0, a, np.zeros(n - na)]
    num = np.r_[np.zeros(nk), b, np.zeros(n + 1 - nk - nb)]
    return num, den


# ---------------- 연속↔이산 ----------------
def c2d_tf(nums, dens, Ts):
    numz, denz, _ = signal.cont2discrete((nums, dens), Ts, method="zoh")
    return np.atleast_1d(np.squeeze(numz)), np.atleast_1d(denz)


def d2c_zoh(numz, denz, Ts):
    """ZOH 역변환: [[Ad, Bd],[0, I]] = expm([[A, B],[0, 0]]·Ts) → logm."""
    Ad, Bd, C, D = signal.tf2ss(numz, denz)
    n = Ad.shape[0]
    M = np.zeros((n + 1, n + 1))
    M[:n, :n], M[:n, n:] = Ad, Bd
    M[n, n] = 1.0
    L = np.real(linalg.logm(M)) / Ts
    nums, dens = signal.ss2tf(L[:n, :n], L[:n, n:], C, D)
    nums = np.trim_zeros(np.squeeze(nums), "f")
    nums[np.abs(nums) < 1e-9 * np.abs(nums).max()] = 0.0
    return np.trim_zeros(nums, "f"), dens


# ---------------- 가상 실험 S1–S3 (스펙 6절) ----------------
P0 = 15.0     # 동작점 [kPa]
AMP = 5.0     # 가진 크기 ±[kPa] (MoE ε 오차 표준편차 ≈ 0.4 % 보다 ε 가진이 충분히 크게)


def _run(pl, u_seq):
    rows = []
    for u in u_seq:
        o = pl.step(np.array([u]))
        tr = pl.truth()
        rows.append([pl.t, u, o.p_mon[0], o.eps_hat[0], tr.p[0], tr.p_c[0], tr.eps[0], tr.tip_deg[0]])
    return np.array(rows)


COLS = "t,u,p_mon,eps_hat,p_true,p_c,eps_true,tip_deg"


def run_experiments(plant_factory, Ts=0.01):
    """plant_factory() → 손가락 1개 Plant. 반환: dict(S1, S2, S3_id, S3_val) 배열 (열 = COLS)."""
    n = lambda s: int(round(s / Ts))
    out = {}
    lv = list(range(0, 31, 3)) + list(range(27, -1, -3))
    out["S1"] = _run(plant_factory(), np.repeat(lv, n(2.0)).astype(float))
    # 장착 보정 (B단계 R1에 해당): 각 단 마지막 0.5 s 평균으로 ε̂ = a·ε + b 맞춤 → 이후 실험은 보정된 ε̂
    s1 = out["S1"]; k = (np.arange(len(s1)) % n(2.0)) >= n(1.5)
    a_, b_ = np.polyfit(s1[k, 6], s1[k, 3], 1)
    paths.save_params("sensor_cal", {"a": float(a_), "b": float(b_)})
    pre = np.full(n(3.0), P0)
    out["S2"] = _run(plant_factory(), np.r_[pre, np.full(n(3.0), P0 + AMP), np.full(n(3.0), P0),
                                            np.full(n(3.0), P0 - AMP), np.full(n(3.0), P0)])
    t = np.arange(n(20.0)) * Ts
    u_id = np.r_[pre, P0 + prbs(n(60.0), 8, AMP, 1, hold=25)]
    u_val = np.r_[pre, P0 + prbs(n(30.0), 8, AMP, 2, hold=25), P0 + chirp(t, 0.05, 2.0, AMP)]
    out["S3_id"] = _run(plant_factory(), u_id)
    out["S3_val"] = _run(plant_factory(), u_val)
    for k, v in out.items():
        np.savetxt(paths.OUT / f"sysid_{k}.csv", v, delimiter=",", header=COLS, comments="")
    return out


def identify(data, col, Ts=0.01, skip_s=3.0):
    """S3 데이터 → 편차 좌표 ARX, 차수 선택, G(z), G(s)."""
    k0 = int(skip_s / Ts)
    idd, val = data["S3_id"][k0:], data["S3_val"][k0:]
    y0, u0 = idd[:, col].mean(), P0
    sel = select_order(idd[:, col] - y0, idd[:, 1] - u0, val[:, col] - y0, val[:, 1] - u0)
    pk = sel["pick"]
    numz, denz = arx_to_tf(np.array(pk["a"]), np.array(pk["b"]), pk["nk"])
    nums, dens = d2c_zoh(numz, denz, Ts) if pk["nk"] == 1 else ([], [])  # 지연 nk>1 은 z=0 극 → d2c 불가
    tcol = {2: 4, 3: 6}[col]                                           # 정답 열 (p_true, eps_true)
    yh = simulate_arx(np.array(pk["a"]), np.array(pk["b"]), pk["nk"], val[:, 1] - u0, val[:pk["na"], col] - y0)
    resid_var = float(np.var(val[:, col] - y0 - yh))
    fit_true = fit_pct(val[:, tcol] - y0, yh)
    return dict(fit_true_pct=fit_true, resid_var=resid_var, a=pk["a"], b=pk["b"], nk=pk["nk"], na=pk["na"], nb=pk["nb"], fit_val_pct=pk["fit"],
                num_z=numz.tolist(), den_z=denz.tolist(), num_s=np.atleast_1d(nums).tolist(),
                den_s=np.atleast_1d(dens).tolist(), y0=float(y0), u0=u0,
                table=[{k: r[k] for k in ("na", "nb", "nk", "fit", "aic")} for r in sel["table"]])


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from paths import OUT, save_params
    from plant import Plant, Scenario
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
    OUT.mkdir(exist_ok=True)
    data = run_experiments(lambda: Plant(Scenario(fingers=1), seed=0))
    Gp, Ge = identify(data, 2), identify(data, 3)
    save_params("sysid", dict(G_p=Gp, G_eps=Ge, p0=P0, amp=AMP, Ts=0.01))
    # 그림: S1 정적 맵, S2 계단, S3 검증
    s1, s2, val = data["S1"], data["S2"], data["S3_val"]
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    ax[0].plot(s1[:, 1], s1[:, 2], ".", ms=2, c="#555", label="p_mon")
    ax[0].plot(s1[:, 1], s1[:, 6], ".", ms=2, c="#2CA02C", label="ε (정답)")
    ax[0].set(xlabel="지령 u [kPa]", ylabel="p [kPa] / ε [%]", title="S1 정적 맵 (상승·하강)"); ax[0].legend(fontsize=8)
    ax[1].plot(s2[:, 0], s2[:, 1], c="k", lw=0.8, label="u"); ax[1].plot(s2[:, 0], s2[:, 2], c="#555", label="p_mon")
    ax[1].plot(s2[:, 0], s2[:, 3], c="#2CA02C", label="ε (MoE)"); ax[1].set(xlabel="t [s]", title="S2 계단 응답"); ax[1].legend(fontsize=8)
    k0 = 300
    t, u, y = val[k0:, 0], val[k0:, 1] - P0, val[k0:, 3] - Ge["y0"]
    yh = simulate_arx(np.array(Ge["a"]), np.array(Ge["b"]), Ge["nk"], u, y[:Ge["na"]])
    ax[2].plot(t, y, c="#2CA02C", lw=0.8, label="측정 ε (MoE)"); ax[2].plot(t, yh, c="k", lw=0.8, label="식별 모델")
    ax[2].plot(t, val[k0:, 6] - Ge["y0"], c="#999", lw=0.8, label="정답 ε")
    ax[2].set(xlabel="t [s]", ylabel="δε [%]", title=f"S3 검증: fit {Ge['fit_val_pct']:.1f} % (측정) / {Ge['fit_true_pct']:.1f} % (정답)"); ax[2].legend(fontsize=8)
    fig.suptitle("시스템 식별 (시뮬레이션)", fontsize=10); fig.tight_layout(); fig.savefig(OUT / "sysid_S1_S3.png", dpi=150)
    print(f"G_eps: na={Ge['na']} nb={Ge['nb']} nk={Ge['nk']} fit_val={Ge['fit_val_pct']:.1f} % (정답 ε 대비 {Ge['fit_true_pct']:.1f} %) |  "
          f"G_p: fit_val={Gp['fit_val_pct']:.1f} %")


if __name__ == "__main__":
    main()
