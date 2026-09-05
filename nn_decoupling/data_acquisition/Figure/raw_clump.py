"""
cap 적용 전 원본 데이터의 3D scatter — 전환점 과밀 구간 시각화
출력: dataset/raw_clump.png
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from pathlib import Path

DIR = Path(__file__).parent
OUT = DIR / "dataset"
OUT.mkdir(exist_ok=True)

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"

# ── 데이터 로드 & 신호 계산 (cap 없음) ───────────────────────────────────────
def load(fname, color):
    df = pd.read_csv(DIR / fname)
    ref = df[(df["eps_act_pct"] < 0.5) & (df["d_act_mm"] > 35)].head(200)
    L0, R0 = ref["ldc_raw"].median(), ref["r_raw"].median()
    df["dL_pct"] = ((L0 / df["ldc_raw"]) ** 2 - 1.0) * 100.0
    df["dR_pct"] = ((df["r_raw"] - R0) / R0) * 100.0
    mask = (df["dL_pct"].abs() < 30) & (df["dR_pct"] > -5) & (df["dR_pct"] < 30)
    return df[mask].reset_index(drop=True)

dfA = load("collect_20260519_140039.csv", None)
dfB = load("collect_20260519_143611.csv", None)
df_all = pd.concat([dfA, dfB], ignore_index=True)
n_total = len(df_all)
print(f"140039: {len(dfA):,}   143611: {len(dfB):,}   total: {n_total:,}")

ELEV, AZIM = 22, -55

fig = plt.figure(figsize=(14, 6))
fig.suptitle("Raw data before cap — clumping at turning points", fontsize=13, fontweight="bold")

for col, (zcol, zlabel, color) in enumerate([
    ("dL_pct", "ΔL / L0 [%]", COLOR_L),
    ("dR_pct", "ΔR / R0 [%]", COLOR_R),
]):
    ax = fig.add_subplot(1, 2, col + 1, projection="3d")

    ax.scatter(df_all["d_act_mm"], df_all["eps_act_pct"], df_all[zcol],
               c=color, s=10, alpha=0.01, edgecolors="none")

    ax.set_xlabel("Proximity [mm]", fontsize=7, labelpad=1)
    ax.set_ylabel("Strain [%]",     fontsize=7, labelpad=1)
    ax.set_zlabel(zlabel,           fontsize=7, labelpad=1)
    ax.set_title(zlabel, fontsize=11, fontweight="bold")
    ax.tick_params(labelsize=6, pad=0)
    ax.view_init(elev=ELEV, azim=AZIM)

    # ax.text2D(0.02, 0.97, f"n = {n_total:,} (both datasets)",
    #           transform=ax.transAxes, fontsize=7, verticalalignment="top",
    #           bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.75))

plt.tight_layout(rect=[0, 0, 1, 0.93])
out = OUT / "raw_clump.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved → {out}")
