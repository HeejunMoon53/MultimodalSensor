"""
plot_new_training_data.py
0909 저녁 재취득 학습용 데이터 시각화 (moe_monitor_20260909_214746 / _220210 / _222022)

이 스크립트는 온보드 모델 추정치(EI 아웃풋)는 그리지 않는다 — 순수 raw 신호
(strain_act_pct, proximity, Fz_act_N, dL_pct, dR_pct)만 사용하는, 학습 데이터
점검용 그래프다 (그림1/그림2/그림3 스타일 참고).

좌표 변환:
  - Proximity: Z_mm=0 일 때 실제 근접거리 24 mm  ->  prox_mm = Z_mm + 24
  - Strain:    센서 초기 길이 120 mm, YA_mm(=YB_mm) 축 기준 strain_act_pct 열을
               그대로 사용 (= (YA_mm+YB_mm)/120*100 과 사실상 동일함을 확인함)

파일별 처리:
  - moe_monitor_20260909_214746.csv (strain 연속 / proximity 이산)
  - moe_monitor_20260909_222022.csv (strain 이산 / proximity 연속)
    -> 근접+변형률 전용. 두 파일을 합쳐 그림1 스타일 6패널 격자(3D x3 + 2D x3,
       Proximity-Strain-dL/dR)를 만들고, 시간축 그래프는 그림2 스타일로 두 파일을
       나란히 4패널(Strain/Proximity/dL/dR)씩 그린다.

  - moe_monitor_20260909_220210.csv (압력 취득 세션)
    -> 3D 격자는 그림1의 Proximity 축을 Force(압력)로 바꿔 Force-Strain-dL/dR로
       그리되, mode==0(비접촉, 힘이 0에 가까운 노이즈 구간)은 제외하고 접촉
       구간(mode==1)만 사용한다.
       시간축 그래프는 그림3 스타일 5패널(Strain/Position/Force/dL/dR)로, 이번엔
       필터링 없이 전체 구간을 그대로 보여준다.

출력: new/output/ 아래
  surfaces_proximity_strain.png   - 그림1 스타일 6패널 (214746+222022 결합)
  timeseries_proximity_pair.png   - 그림2 스타일 2열 4패널 (214746 | 222022)
  surfaces_force_strain.png       - 그림1 스타일 6패널, Force-Strain (220210, 접촉 구간만)
  timeseries_pressure_full.png    - 그림3 스타일 5패널, 전 구간 (220210)
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (3D projection 등록)

# ── 색상 컨벤션 (CLAUDE.md) ──────────────────────────────────────────────────
COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_TENG = "#1F77B4"
COLOR_POS = "#7F7F7F"
COLOR_FORCE = "#1F77B4"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

PROX_OFFSET = 24.0   # Z_mm = 0 -> 실제 근접거리 24 mm
SMOOTH_WINDOW = 25    # dL/dR/Force 이동평균 창 (raw 데이터 자체는 그대로 유지)


# ── 1. 로드 ───────────────────────────────────────────────────────────────────

def load(fname):
    d = pd.read_csv(os.path.join(SCRIPT_DIR, fname))
    d = d[d["mode"].isin([0, 1])].copy()
    d = d[(d.strain_act_pct.between(-2, 35)) & (d.dL_pct.abs() < 150)
          & (d.dR_pct.abs() < 150) & (d.gate_proba.between(0, 1))]
    d = d.reset_index(drop=True)
    d["t"] = d.t_s - d.t_s.min()
    d["prox_mm"] = d.Z_mm + PROX_OFFSET
    off = d.loc[d["mode"] == 0, "Fz_act_N"].mean()
    d["F_true"] = -(d.Fz_act_N - off)
    for col in ("dL_pct", "dR_pct", "F_true"):
        d[f"{col}_smooth"] = d[col].rolling(SMOOTH_WINDOW, center=True,
                                             min_periods=1).mean()
    return d


# ── 2. 격자화 (그림1 스타일) ──────────────────────────────────────────────────

def grid(df, x_col, xb, sb):
    """df[x_col] (근접 또는 힘) x strain_act_pct 2D 격자에 dL_pct/dR_pct 평균을 채운다."""
    X, S = np.meshgrid((xb[:-1] + xb[1:]) / 2, (sb[:-1] + sb[1:]) / 2)
    ZL = np.full(X.shape, np.nan)
    ZR = np.full(X.shape, np.nan)
    xi = np.digitize(df[x_col], xb) - 1
    si = np.digitize(df.strain_act_pct, sb) - 1
    for a in range(X.shape[0]):
        for b in range(X.shape[1]):
            m = (si == a) & (xi == b)
            if m.sum() >= 1:
                ZL[a, b] = df.dL_pct_smooth[m].mean()
                ZR[a, b] = df.dR_pct_smooth[m].mean()

    def fill(Z):
        D = pd.DataFrame(Z)
        D = D.interpolate(axis=1, limit_direction="both")
        D = D.interpolate(axis=0, limit_direction="both")
        return D.values

    return X, S, fill(ZL), fill(ZR)


def plot_surfaces(X, S, ZL, ZR, x_label, out_name, title):
    """그림1 스타일 6패널: 3D(R,L,combined) 위, 2D heatmap(R,L)+contour(combined) 아래."""
    fig = plt.figure(figsize=(19, 11))

    ax1 = fig.add_subplot(2, 3, 1, projection="3d")
    ax1.plot_wireframe(X, S, ZR, color=COLOR_R, linewidth=0.6, rstride=1, cstride=1)
    ax1.set_xlabel(x_label)
    ax1.set_ylabel("Strain [%]")
    ax1.set_zlabel("$\\Delta$R/R$_0$ [%]")

    ax2 = fig.add_subplot(2, 3, 2, projection="3d")
    ax2.plot_wireframe(X, S, ZL, color=COLOR_L, linewidth=0.6, rstride=1, cstride=1)
    ax2.set_xlabel(x_label)
    ax2.set_ylabel("Strain [%]")
    ax2.set_zlabel("$\\Delta$L/L$_0$ [%]")

    ax3 = fig.add_subplot(2, 3, 3, projection="3d")
    ax3.plot_wireframe(X, S, ZR, color=COLOR_R, linewidth=0.5, rstride=1, cstride=1,
                       alpha=0.8)
    ax3.plot_wireframe(X, S, ZL, color=COLOR_L, linewidth=0.5, rstride=1, cstride=1,
                       alpha=0.8)
    ax3.set_xlabel(x_label)
    ax3.set_ylabel("Strain [%]")
    ax3.set_zlabel("$\\Delta$L/L$_0$, $\\Delta$R/R$_0$ [%]")

    ax4 = fig.add_subplot(2, 3, 4)
    Zm = np.ma.masked_invalid(ZR)
    pc = ax4.pcolormesh(X, S, Zm, cmap="Greens", shading="auto")
    fig.colorbar(pc, ax=ax4, pad=0.02, label="$\\Delta$R/R$_0$ [%]")
    ax4.set_title("$\\Delta$R / R$_0$ [%]")
    ax4.set_xlabel(x_label)
    ax4.set_ylabel("Strain [%]")

    ax5 = fig.add_subplot(2, 3, 5)
    Zm2 = np.ma.masked_invalid(ZL)
    v = float(np.nanmax(np.abs(ZL)))
    pc2 = ax5.pcolormesh(X, S, Zm2, cmap="Oranges", shading="auto", vmin=-v, vmax=v)
    fig.colorbar(pc2, ax=ax5, pad=0.02, label="$\\Delta$L/L$_0$ [%]")
    ax5.set_title("$\\Delta$L / L$_0$ [%]")
    ax5.set_xlabel(x_label)
    ax5.set_ylabel("Strain [%]")

    ax6 = fig.add_subplot(2, 3, 6)
    csL = ax6.contour(X, S, Zm2, colors=COLOR_L, linewidths=0.8, linestyles="dashed")
    csR = ax6.contour(X, S, Zm, colors=COLOR_R, linewidths=0.8, linestyles="dashed")
    ax6.clabel(csL, fontsize=6, fmt="%.0f")
    ax6.clabel(csR, fontsize=6, fmt="%.0f")
    ax6.plot([], [], color=COLOR_L, ls="--", label="$\\Delta$L / L$_0$ [%]")
    ax6.plot([], [], color=COLOR_R, ls="--", label="$\\Delta$R / R$_0$ [%]")
    ax6.legend(fontsize=8, loc="upper right")
    ax6.set_xlabel(x_label)
    ax6.set_ylabel("Strain [%]")

    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(OUT_DIR, out_name)
    fig.savefig(out, dpi=150)
    print(f"[save] {out}")
    plt.close(fig)


# ── 3. 시간 도메인: 그림2 스타일 (2열 x 4패널, raw only) ─────────────────────

def plot_timeseries_pair(sessions, out_name):
    fig, axes = plt.subplots(4, len(sessions), figsize=(11 * len(sessions), 11),
                             sharex="col")
    if len(sessions) == 1:
        axes = axes.reshape(4, 1)
    for col, (label, d) in enumerate(sessions):
        axes[0, col].plot(d.t, d.strain_act_pct, color=COLOR_POS, lw=0.8)
        axes[0, col].set_title(label, fontsize=11, fontweight="bold")
        axes[1, col].plot(d.t, d.prox_mm, color=COLOR_POS, lw=0.8)
        axes[2, col].plot(d.t, d.dL_pct_smooth, color=COLOR_L, lw=0.8)
        axes[3, col].plot(d.t, d.dR_pct_smooth, color=COLOR_R, lw=0.8)
        axes[3, col].set_xlabel("Time [s]")
        for ax in axes[:, col]:
            ax.grid(True, alpha=0.25)
            ax.axhline(0, color="black", lw=0.4, alpha=0.3)
    axes[0, 0].set_ylabel("Strain\n[%]", fontsize=10)
    axes[1, 0].set_ylabel("Proximity\n[mm]", fontsize=10)
    axes[2, 0].set_ylabel("$\\Delta$L / L$_0$\n[%]", fontsize=10)
    axes[3, 0].set_ylabel("$\\Delta$R / R$_0$\n[%]", fontsize=10)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, out_name)
    fig.savefig(out, dpi=150)
    print(f"[save] {out}")
    plt.close(fig)


# ── 4. 시간 도메인: 그림3 스타일 (5패널, 압력 세션 전 구간) ──────────────────

def plot_timeseries_full(d, title, out_name):
    fig, axes = plt.subplots(5, 1, figsize=(13, 12), sharex=True)
    fig.suptitle(title, fontsize=13, fontweight="bold")
    panels = [
        ("Strain\n[%]", d.strain_act_pct, COLOR_POS),
        ("Position\n[mm]", d.prox_mm, COLOR_POS),
        ("Force\n[N]", d.F_true_smooth, COLOR_FORCE),
        ("$\\Delta$L / L$_0$\n[%]", d.dL_pct_smooth, COLOR_L),
        ("$\\Delta$R / R$_0$\n[%]", d.dR_pct_smooth, COLOR_R),
    ]
    for ax, (label, y, color) in zip(axes, panels):
        ax.plot(d.t, y, color=color, lw=0.8)
        ax.set_ylabel(label, fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.axhline(0, color="black", lw=0.4, alpha=0.3)
    axes[-1].set_xlabel("Time [s]")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(OUT_DIR, out_name)
    fig.savefig(out, dpi=150)
    print(f"[save] {out}")
    plt.close(fig)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    d1 = load("moe_monitor_20260909_214746.csv")   # strain 연속 / proximity 이산
    d2 = load("moe_monitor_20260909_222022.csv")    # strain 이산 / proximity 연속
    d3 = load("moe_monitor_20260909_220210.csv")     # 압력 세션

    # --- 근접+변형률: 두 세션 시간축 (그림2 스타일) ---
    plot_timeseries_pair(
        [("214746: Strain continuous / Proximity discrete", d1),
         ("222022: Strain discrete / Proximity continuous", d2)],
        "timeseries_proximity_pair.png")

    # --- 근접+변형률: 두 세션을 합쳐 격자화 (그림1 스타일) ---
    prox_all = pd.concat([d1[d1["mode"] == 0], d2[d2["mode"] == 0]], ignore_index=True)
    print(f"[grid] proximity+strain combined n={len(prox_all)} "
          f"(prox {prox_all.prox_mm.min():.1f}-{prox_all.prox_mm.max():.1f} mm, "
          f"strain {prox_all.strain_act_pct.min():.1f}-{prox_all.strain_act_pct.max():.1f} %)")
    pb = np.arange(-0.5, prox_all.prox_mm.max() + 1.5, 1.2)
    sb = np.arange(-0.5, 31.5, 1.5)
    X, S, ZL, ZR = grid(prox_all, "prox_mm", pb, sb)
    plot_surfaces(X, S, ZL, ZR, "Proximity [mm]", "surfaces_proximity_strain.png",
                  "Proximity - Strain response surfaces (214746 + 222022 combined)")

    # --- 압력 세션: 3D 격자 (그림1의 Proximity 축 -> Force, 접촉 구간만) ---
    press = d3[d3["mode"] == 1].copy()
    n_before = len(press)
    print(f"[grid] pressure phase raw n={n_before}, F range "
          f"{press.F_true.min():.2f}-{press.F_true.max():.2f} N")
    fb = np.arange(-0.5, press.F_true.max() + 1.5, 1.0)
    sb2 = np.arange(-0.5, 31.5, 1.5)
    Xf, Sf, ZLf, ZRf = grid(press, "F_true", fb, sb2)
    plot_surfaces(Xf, Sf, ZLf, ZRf, "Force [N]", "surfaces_force_strain.png",
                  "Force - Strain response surfaces (220210, contact phase only, "
                  "zero-force proximity noise excluded)")

    # --- 압력 세션: 시간축 전 구간 (그림3 스타일) ---
    plot_timeseries_full(d3, "220210: Pressure session (full range)",
                          "timeseries_pressure_full.png")

    print("\n완료.")


if __name__ == "__main__":
    main()
