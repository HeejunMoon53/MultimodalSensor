"""그래프 (M8). 색: L 주황, R 초록, TENG 파랑 (CLAUDE.md), 참값 진회색, 추정값 보라."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from sim_gripper.control.controller import MATERIAL_TABLE

COLOR_L, COLOR_R, COLOR_TENG = "#FF8C00", "#2CA02C", "#1F77B4"
COLOR_TRUE, COLOR_EST = "#333333", "#7B4FBF"
PHASES = ["OPEN", "APPROACH", "GRASP", "HOLD", "RELEASE"]
PHASE_BG = {"APPROACH": "#F2F2F2", "GRASP": "#E6E6E6", "HOLD": "#D9D9D9", "RELEASE": "#F2F2F2"}

def _save(fig, path, dpi=130):
    """Windows에서 백신·인덱서가 잠깐 파일을 잡는 경우(OSError 22/13) 몇 번 재시도."""
    import time
    for k in range(5):
        try:
            fig.savefig(path, dpi=dpi)
            break
        except OSError:
            if k == 4:
                raise
            time.sleep(0.5)
    plt.close(fig)


plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#E5E5E5", "grid.linewidth": 0.6})


def _phase_shading(ax, df):
    ph = df.phase.values
    edges = np.flatnonzero(ph[1:] != ph[:-1]) + 1
    for a, b in zip(np.r_[0, edges], np.r_[edges, len(ph)]):
        if ph[a] in PHASE_BG:
            ax.axvspan(df.t.iloc[a], df.t.iloc[b - 1], color=PHASE_BG[ph[a]], lw=0, zorder=0)


def plot_timeline(df, finger, path):
    i, t = finger, df.t
    fig, axs = plt.subplots(6, 1, figsize=(9, 11), sharex=True)
    c = df[f"contact_{i}"].astype(bool)
    eps_hat = df[f"eps_hat_{i}"]
    axs[0].plot(t, df[f"eps_true_{i}"], color=COLOR_TRUE, lw=1.5, label="ε 참값")
    axs[0].plot(t, eps_hat, color=COLOR_EST, lw=1, alpha=0.8, label=r"$\hat{\varepsilon}$ 추정")
    axs[0].set_ylabel("인장 ε [%]")
    d_hat = df[f"value_{i}"].where(~c)
    axs[1].plot(t, df[f"d_true_{i}"].clip(upper=26), color=COLOR_TRUE, lw=1.5, label="d 참값")
    axs[1].plot(t, d_hat, color=COLOR_EST, lw=1, alpha=0.8, label=r"$\hat{d}$ 추정 (비접촉)")
    axs[1].set_ylabel("근접 d [mm]")
    F_hat = df[f"value_{i}"].where(c)
    axs[2].plot(t, df[f"F_true_{i}"], color=COLOR_TRUE, lw=1.5, label="F 참값")
    axs[2].plot(t, F_hat, color=COLOR_EST, lw=1, alpha=0.8, label=r"$\hat{F}$ 추정 (접촉)")
    mat = df[f"material_{i}"].iloc[-1]
    F_t, F_max = MATERIAL_TABLE.get(mat, MATERIAL_TABLE["dielectric"])
    axs[2].axhline(F_t, color=COLOR_TRUE, ls="--", lw=0.8)
    axs[2].axhline(F_max, color="#B00020", ls=":", lw=0.8)
    axs[2].text(t.iloc[-1], F_t, f" F_t {F_t} N", va="center", fontsize=8)
    axs[2].text(t.iloc[-1], F_max, f" F_max {F_max} N", va="center", fontsize=8)
    axs[2].set_ylabel("압축 힘 F [N]")
    axs[3].plot(t, df[f"dL_{i}"], color=COLOR_L, lw=1, label=r"$\Delta L/L_0$")
    axs[3].plot(t, df[f"dR_{i}"], color=COLOR_R, lw=1, label=r"$\Delta R/R_0$")
    axs[3].set_ylabel("원신호 [%]")
    axs[4].plot(t, df[f"V_{i}"], color=COLOR_TENG, lw=1, label="V_TENG")
    axs[4].set_ylabel("TENG [a.u.]")
    codes = {"unknown": 0, "dielectric": 1, "conductor": 2}
    axs[5].step(t, df[f"contact_{i}"], color=COLOR_EST, lw=1, where="post", label="contact (게이트∨TENG)")
    axs[5].step(t, df[f"material_{i}"].map(codes) * 0.5 + 1.5, color=COLOR_TRUE, lw=1.2, where="post",
                label="재질 (1.5 미정, 2 유전체, 2.5 도체)")
    axs[5].set_ylabel("상태")
    axs[5].set_xlabel("시간 [s]")
    for ax in axs:
        _phase_shading(ax, df)
        ax.legend(loc="upper left", fontsize=7, frameon=False)
    fig.suptitle(f"손가락 {i} 모달리티 타임라인 (배경: APPROACH·GRASP·HOLD·RELEASE)", fontsize=10)
    fig.tight_layout()
    _save(fig, path)


def plot_actuator_compare(results, path):
    fig, axs = plt.subplots(2, 1, figsize=(8, 5), sharex=True)
    styles = {"tendon": ("-", COLOR_TRUE), "pneumatic": ("--", COLOR_EST)}
    for name, df in results.items():
        ls, col = styles.get(name, ("-", COLOR_TRUE))
        axs[0].plot(df.t, df.F_true_0, ls=ls, color=col, lw=1.3, label=name)
        axs[1].plot(df.t, df.u_0, ls=ls, color=col, lw=1.3, label=name)
    axs[0].set_ylabel("F 참값 (손가락 0) [N]")
    axs[1].set_ylabel("명령 u")
    axs[1].set_xlabel("시간 [s]")
    for ax in axs:
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("E1 금속 원통: 텐던 vs 공압", fontsize=10)
    fig.tight_layout()
    _save(fig, path)


def plot_ideal_vs_pipeline(pairs, path):
    """pairs: {scenario: {"ideal": df, "pipeline": df}} — 손가락 0 힘 추정 비교."""
    fig, axs = plt.subplots(len(pairs), 1, figsize=(8, 3 * len(pairs)), sharex=True, squeeze=False)
    for ax, (name, d) in zip(axs[:, 0], pairs.items()):
        for mode, ls in (("ideal", "--"), ("pipeline", "-")):
            df = d[mode]
            ax.plot(df.t, df.F_true_0, ls=ls, color=COLOR_TRUE, lw=1.2, label=f"F 참값 ({mode})")
            ax.plot(df.t, df.value_0.where(df.contact_0.astype(bool)), ls=ls, color=COLOR_EST, lw=1,
                    label=rf"$\hat{{F}}$ ({mode})")
        ax.set_title(name, fontsize=9)
        ax.set_ylabel("F [N]")
        ax.legend(frameon=False, fontsize=7, ncol=2)
    axs[-1, 0].set_xlabel("시간 [s]")
    fig.suptitle("이상 센서 vs 전체 파이프라인 (순방향 모델 → TDM → v4 MoE)", fontsize=10)
    fig.tight_layout()
    _save(fig, path)


def plot_finger_compare(results, path):
    """E1 금속 원통: 손가락 종류별 힘·인장(참/추정)·명령 (손가락 0)."""
    fig, axs = plt.subplots(3, 1, figsize=(8, 7), sharex=True)
    styles = [("-", COLOR_TRUE), ("--", COLOR_EST)]
    for (name, df), (ls, col) in zip(results.items(), styles):
        axs[0].plot(df.t, df.F_true_0, ls=ls, color=col, lw=1.3, label=f"{name} F 참값")
        axs[1].plot(df.t, df.eps_true_0, ls=ls, color=col, lw=1.3, label=f"{name} ε 참값")
        axs[1].plot(df.t, df.eps_hat_0, ls=ls, color=col, lw=0.6, alpha=0.5, label=rf"{name} $\hat{{\varepsilon}}$")
        axs[2].plot(df.t, df.u_0, ls=ls, color=col, lw=1.3, label=name)
    axs[0].set_ylabel("F [N]")
    axs[1].set_ylabel("인장 ε [%]")
    axs[2].set_ylabel("명령 u")
    axs[2].set_xlabel("시간 [s]")
    for ax in axs:
        ax.legend(frameon=False, fontsize=7, ncol=2)
    fig.suptitle("E1 금속 원통: 판형 손가락 vs 60A 벨로즈 손가락 (손가락 0)", fontsize=10)
    fig.tight_layout()
    _save(fig, path)


def plot_bellows_calibration(path):
    """논문 Fig.9(굽힘)·Fig.7(차단력) vs 시뮬 보정 결과. 표 데이터(dict)도 반환."""
    from sim_gripper.model.calibrate_bellows import (FIG7_FORCE_N, FIG9_SLOPE_DEG_PER_KPA, P0_KPA,
                                                     blocked_force_N, free_bending_deg)
    Ps = np.arange(70, 201, 10) * 1e3
    bend = [free_bending_deg(P) for P in Ps]
    force = {P: blocked_force_N(P) for P in FIG7_FORCE_N}
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    axs[0].plot(Ps / 1e3, FIG9_SLOPE_DEG_PER_KPA * (Ps / 1e3 - P0_KPA), color=COLOR_TRUE, ls="--", lw=1.2,
                label="논문 Fig.9 (선형 근사)")
    axs[0].plot(Ps / 1e3, bend, color=COLOR_EST, marker="o", ms=4, lw=1.3, label="시뮬 (PRBM 8관절)")
    axs[0].set_xlabel("압력 [kPa]")
    axs[0].set_ylabel("추가 굽힘각 [°] (precurve 41° 제외)")
    axs[0].legend(frameon=False, fontsize=8)
    x = np.arange(len(FIG7_FORCE_N))
    axs[1].bar(x - 0.18, list(FIG7_FORCE_N.values()), 0.34, color=COLOR_TRUE, label="논문 Fig.7 (60A 평균)")
    axs[1].bar(x + 0.18, list(force.values()), 0.34, color=COLOR_EST, label="시뮬 (끝단 고정 반력)")
    axs[1].set_xticks(x, [f"{P / 1e3:.0f} kPa" for P in FIG7_FORCE_N])
    axs[1].set_ylabel("끝단 차단력 [N]")
    axs[1].legend(frameon=False, fontsize=8)
    fig.suptitle("60A 벨로즈 손가락 보정 (Meitani & Nisar, IEEE Access 2025)", fontsize=10)
    fig.tight_layout()
    _save(fig, path)
    return {"bending": [[P / 1e3, b, FIG9_SLOPE_DEG_PER_KPA * (P / 1e3 - P0_KPA)] for P, b in zip(Ps, bend)],
            "force": [[P / 1e3, f, FIG7_FORCE_N[P]] for P, f in force.items()]}
