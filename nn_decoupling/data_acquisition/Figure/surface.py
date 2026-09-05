"""
Mixed 데이터 집중 시각화
  surface_mixed.png : 3D 선 그래프 1×3 (ΔL / ΔR / ΔL+ΔR 겹침)
  heatmap_mixed.png : 2D 히트맵·컨투어 1×3 (ΔL / ΔR / 컨투어 겹침)
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from pathlib import Path

DIR = Path(__file__).parent
DATA_DIR = DIR.parent

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"

# ── 데이터 로드 & baseline ────────────────────────────────────────────────────
dfA = pd.read_csv(DATA_DIR / "collect_20260519_140039.csv")
dfB = pd.read_csv(DATA_DIR / "collect_20260519_143611.csv")

def estimate_baseline(df, n=200):
    ref = df[(df["eps_act_pct"] < 0.5) & (df["d_act_mm"] > 35)].head(n)
    return ref["ldc_raw"].median(), ref["r_raw"].median()

L0_A, R0_A = estimate_baseline(dfA)
L0_B, R0_B = estimate_baseline(dfB)

def recompute(df, L0, R0):
    df = df.copy()
    df["dL_pct"] = ((L0 / df["ldc_raw"]) ** 2 - 1.0) * 100.0
    df["dR_pct"] = ((df["r_raw"] - R0) / R0) * 100.0
    mask = (df["dL_pct"].abs() < 30) & (df["dR_pct"] > -5) & (df["dR_pct"] < 30)
    return df[mask].reset_index(drop=True)

dfA = recompute(dfA, L0_A, R0_A)
dfB = recompute(dfB, L0_B, R0_B)

# ── 격자 (plot_surface.py 와 동일) ───────────────────────────────────────────
EPS_EDGES   = np.linspace(0, 30, 25)
D_EDGES     = np.linspace(0, 36, 25)
eps_centers = (EPS_EDGES[:-1] + EPS_EDGES[1:]) / 2
d_centers   = (D_EDGES[:-1]  + D_EDGES[1:])  / 2

def cap_eps_visits(df, eps_edges, cap=50):
    eps_vals = df["eps_act_pct"].values
    ei = np.digitize(eps_vals, eps_edges) - 1
    ei = np.clip(ei, 0, len(eps_edges) - 2)
    keep_set = set()
    i, n = 0, len(df)
    while i < n:
        b = ei[i]; j = i
        while j < n and ei[j] == b:
            j += 1
        size = j - i
        if size <= cap:
            keep_set.update(range(i, j))
        else:
            lo, hi = float(eps_edges[b]), float(eps_edges[b + 1])
            grid = np.linspace(lo, hi, cap + 2)[1:-1]
            local_eps = eps_vals[i:j]
            for gp in grid:
                keep_set.add(i + int(np.argmin(np.abs(local_eps - gp))))
        i = j
    return df.iloc[sorted(keep_set)].reset_index(drop=True)

dfB = cap_eps_visits(dfB, EPS_EDGES, cap=50)

def bin2d(df):
    ei = np.digitize(df["eps_act_pct"].values, EPS_EDGES) - 1
    di = np.digitize(df["d_act_mm"].values,   D_EDGES)   - 1
    ne, nd = len(EPS_EDGES) - 1, len(D_EDGES) - 1
    gL = np.full((ne, nd), np.nan)
    gR = np.full((ne, nd), np.nan)
    for i in range(ne):
        for j in range(nd):
            sel = (ei == i) & (di == j)
            if sel.sum() > 2:
                gL[i, j] = df.loc[sel, "dL_pct"].median()
                gR[i, j] = df.loc[sel, "dR_pct"].median()
    return gL, gR

gLA, gRA = bin2d(dfA)
gLB, gRB = bin2d(dfB)

def mix_grids(gA, gB):
    g = np.full_like(gA, np.nan)
    both   = ~np.isnan(gA) & ~np.isnan(gB)
    only_A = ~np.isnan(gA) &  np.isnan(gB)
    only_B =  np.isnan(gA) & ~np.isnan(gB)
    g[both]   = (gA[both] + gB[both]) / 2
    g[only_A] = gA[only_A]
    g[only_B] = gB[only_B]
    return g

gL_mix = mix_grids(gLA, gLB)
gR_mix = mix_grids(gRA, gRB)

# ═══════════════════════════════════════════════════════════════════════════════
# surface_mixed.png  —  3D 선 그래프 1×3
# ═══════════════════════════════════════════════════════════════════════════════
ELEV, AZIM = 22, -55

def draw_lines(ax, gA, gB, color, lw=1.2, alpha=0.75):
    for i, eps_c in enumerate(eps_centers):
        z = gA[i, :]
        valid = ~np.isnan(z)
        if valid.sum() > 1:
            ax.plot(d_centers[valid], np.full(valid.sum(), eps_c), z[valid],
                    color=color, lw=lw, alpha=alpha, linestyle="-")
    for j, d_c in enumerate(d_centers):
        z = gB[:, j]
        valid = ~np.isnan(z)
        if valid.sum() > 1:
            ax.plot(np.full(valid.sum(), d_c), eps_centers[valid], z[valid],
                    color=color, lw=lw, alpha=alpha, linestyle="--")

fig1 = plt.figure(figsize=(18, 6))

# 1-a: Mixed ΔL
ax1a = fig1.add_subplot(1, 3, 1, projection="3d")
ax1a.set_title("ΔL / L₀ [%]", fontsize=10, fontweight="bold")
draw_lines(ax1a, gLA, gLB, COLOR_L)
ax1a.set_xlabel("Proximity [mm]", fontsize=7, labelpad=1)
ax1a.set_ylabel("Strain [%]",     fontsize=7, labelpad=1)
ax1a.set_zlabel("ΔL / L₀ [%]",   fontsize=7, labelpad=1)
ax1a.tick_params(labelsize=6, pad=0)
ax1a.view_init(elev=ELEV, azim=AZIM)

# 1-b: Mixed ΔR
ax1b = fig1.add_subplot(1, 3, 2, projection="3d")
ax1b.set_title("ΔR / R₀ [%]", fontsize=10, fontweight="bold")
draw_lines(ax1b, gRA, gRB, COLOR_R)
ax1b.set_xlabel("Proximity [mm]", fontsize=7, labelpad=1)
ax1b.set_ylabel("Strain [%]",     fontsize=7, labelpad=1)
ax1b.set_zlabel("ΔR / R₀ [%]",   fontsize=7, labelpad=1)
ax1b.tick_params(labelsize=6, pad=0)
ax1b.view_init(elev=ELEV, azim=AZIM)

# 1-c: ΔL + ΔR 겹침
ax1c = fig1.add_subplot(1, 3, 3, projection="3d")
ax1c.set_title("ΔL + ΔR", fontsize=10, fontweight="bold")
draw_lines(ax1c, gLA, gLB, COLOR_L)
draw_lines(ax1c, gRA, gRB, COLOR_R)
ax1c.set_xlabel("Proximity [mm]", fontsize=7, labelpad=1)
ax1c.set_ylabel("Strain [%]",     fontsize=7, labelpad=1)
ax1c.set_zlabel("Response [%]",   fontsize=7, labelpad=1)
ax1c.tick_params(labelsize=6, pad=0)
ax1c.view_init(elev=ELEV, azim=AZIM)
ax1c.legend(handles=[
    Line2D([0], [0], color=COLOR_L, lw=2, label="ΔL / L₀"),
    Line2D([0], [0], color=COLOR_R, lw=2, label="ΔR / R₀"),
], fontsize=7, loc="upper right")

plt.tight_layout()
fig1.savefig(DIR / "surface_mixed.png", dpi=150, bbox_inches="tight")
plt.close(fig1)
print("Saved → surface_mixed.png")

# ═══════════════════════════════════════════════════════════════════════════════
# heatmap_mixed.png  —  2D 히트맵·컨투어 1×3
# ═══════════════════════════════════════════════════════════════════════════════
cmap_L = LinearSegmentedColormap.from_list("cmap_L", ["#fff5e6", COLOR_L, "#4A2000"])
cmap_R = LinearSegmentedColormap.from_list("cmap_R", ["#f0fff0", COLOR_R, "#0a3010"])

EXT = [D_EDGES[0], D_EDGES[-1], EPS_EDGES[0], EPS_EDGES[-1]]

fig2, axes2 = plt.subplots(1, 3, figsize=(18, 6))

# 2-a: Mixed ΔL Heatmap
ax = axes2[0]
im = ax.imshow(gL_mix, origin="lower", aspect="auto",
               vmin=np.nanmin(gL_mix), vmax=np.nanmax(gL_mix),
               cmap=cmap_L, extent=EXT)
plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02).set_label("ΔL / L₀ [%]", fontsize=8)
ax.set_title("ΔL / L₀ [%]", fontsize=10, fontweight="bold")
ax.set_xlabel("Proximity [mm]", fontsize=9)
ax.set_ylabel("Strain [%]",     fontsize=9)
ax.set_box_aspect(1)

# 2-b: Mixed ΔR Heatmap
ax = axes2[1]
im = ax.imshow(gR_mix, origin="lower", aspect="auto",
               vmin=np.nanmin(gR_mix), vmax=np.nanmax(gR_mix),
               cmap=cmap_R, extent=EXT)
plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02).set_label("ΔR / R₀ [%]", fontsize=8)
ax.set_title("ΔR / R₀ [%]", fontsize=10, fontweight="bold")
ax.set_xlabel("Proximity [mm]", fontsize=9)
ax.set_ylabel("Strain [%]",     fontsize=9)
ax.set_box_aspect(1)

# 2-c: ΔL Contour(주황) + ΔR Contour(초록) 겹침 (1% 간격)
ax = axes2[2]
ax.set_facecolor("#f8f8f8")
lvl_L = np.arange(np.floor(np.nanmin(gL_mix)), np.ceil(np.nanmax(gL_mix)) + 1, 1.0)
lvl_R = np.arange(np.floor(np.nanmin(gR_mix)), np.ceil(np.nanmax(gR_mix)) + 1, 1.0)
cs_L = ax.contour(d_centers, eps_centers, gL_mix,
                  levels=lvl_L, colors=COLOR_L, linewidths=1.5, linestyles="dashed")
ax.clabel(cs_L, inline=True, fontsize=7, fmt="%d")
cs_R = ax.contour(d_centers, eps_centers, gR_mix,
                  levels=lvl_R, colors=COLOR_R, linewidths=1.5, linestyles="dashed")
ax.clabel(cs_R, inline=True, fontsize=7, fmt="%d")
ax.set_xlim(D_EDGES[0], D_EDGES[-1])
ax.set_ylim(EPS_EDGES[0], EPS_EDGES[-1])
ax.set_title("ΔL + ΔR Contour", fontsize=10, fontweight="bold")
ax.set_xlabel("Proximity [mm]", fontsize=9)
ax.set_ylabel("Strain [%]",     fontsize=9)
ax.set_box_aspect(1)
ax.legend(handles=[
    Line2D([0], [0], color=COLOR_L, lw=2, label="ΔL / L₀ [%]"),
    Line2D([0], [0], color=COLOR_R, lw=2, label="ΔR / R₀ [%]"),
], fontsize=8, loc="upper right")

plt.tight_layout()
fig2.savefig(DIR / "heatmap_mixed.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("Saved → heatmap_mixed.png")
print("Done.")
