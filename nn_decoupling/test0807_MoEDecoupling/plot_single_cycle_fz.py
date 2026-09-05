"""
plot_single_cycle_fz.py
새로 만든 센서(돌기 추가, mms_2026080X 데이터)에서 압력 사이클 하나를 골라
ΔL/L0(%) vs Fz(N), ΔR/R0(%) vs Fz(N) 산점도로 그린다.
(참고 이미지 스타일: 2단 패널, 주황/초록 산점도, x축 Fz(N))
"""
import os
import matplotlib.pyplot as plt
import common

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"

df = common.load_raw()
df = common.add_labels(df)

def plot_cycle(cycle_id, out_name):
    g = df[(df.cycle_id == cycle_id) & (df.phase == "pressure")].sort_values("t_s")
    print(f"cycle {cycle_id}: n={len(g)}  strain={g.strain_pct.iloc[0]:.1f}%  "
          f"Fz range=({g.Force_N.min():.2f}, {g.Force_N.max():.2f})N")

    fig, axes = plt.subplots(2, 1, figsize=(6.2, 7.4))
    fig.suptitle(f"strain = {g.strain_pct.iloc[0]:.1f}%", fontsize=11, y=0.995)

    axes[0].scatter(g.Force_N, g.dL_pct, s=6, color=COLOR_L, alpha=0.75)
    axes[0].set_title(r"$\Delta$L/L0(%)  vs  Fz(N)")
    axes[0].set_xlabel("Fz(N)"); axes[0].set_ylabel(r"$\Delta$L/L0(%)")
    axes[0].grid(alpha=0.25)

    axes[1].scatter(g.Force_N, g.dR_pct, s=6, color=COLOR_R, alpha=0.75)
    axes[1].set_title(r"$\Delta$R/R0(%)  vs  Fz(N)")
    axes[1].set_xlabel("Fz(N)"); axes[1].set_ylabel(r"$\Delta$R/R0(%)")
    axes[1].grid(alpha=0.25)

    plt.tight_layout()
    out = os.path.join(common.OUT_DIR, out_name)
    fig.savefig(out, dpi=160)
    print("[save]", out)


plot_cycle(0, "single_cycle_fz_scatter_strain0.png")     # strain 0%, 최대힘 10.11N
plot_cycle(266, "single_cycle_fz_scatter_strain30.png")  # strain 30%, 최대힘 9.21N
