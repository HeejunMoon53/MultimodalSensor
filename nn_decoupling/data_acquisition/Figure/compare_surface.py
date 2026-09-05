"""
3D 선 그래프 및 2D 히트맵 시각화
격자: eps 24bins (0→30%, 1.25%/bin) × d 24bins (0→36mm, 1.5mm/bin)
  - eps=0, d=0 구간 포함 (데이터가 없는 셀은 NaN → 히트맵에 회색 표시)
  - 143611만 eps-grid visit capping 적용 (감속·정지 편향 제거)

출력:
  surface_3d.png  — 3D 선 그래프 (2×3)
  heatmap_2d.png  — 2D 히트맵 (2×3)
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from pathlib import Path

DIR = Path(__file__).parent
DATA_DIR = DIR.parent

# ── 색상 컨벤션 ──────────────────────────────────────────────────────────────
COLOR_L = "#FF8C00"   # 인덕턴스 L — 주황
COLOR_R = "#2CA02C"   # DC 저항 R  — 초록
C_A     = "#1F77B4"   # 140039 (Ramp) — 파랑
C_B     = "#E377C2"   # 143611 (Oscillate) — 분홍

# ── 데이터 로드 및 baseline 계산 ─────────────────────────────────────────────
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

# ── 격자 정의: 24×24 (eps=0 및 d=0 포함) ────────────────────────────────────
EPS_EDGES   = np.linspace(0, 30, 25)   # 24 bins, 1.25%/bin
D_EDGES     = np.linspace(0, 36, 25)   # 24 bins, 1.5mm/bin
eps_centers = (EPS_EDGES[:-1] + EPS_EDGES[1:]) / 2
d_centers   = (D_EDGES[:-1]  + D_EDGES[1:])  / 2

# ── 감속 편향 보정: 143611 eps-grid visit capping ─────────────────────────────
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
print(f"140039 samples: {len(dfA):,}   143611 after cap: {len(dfB):,}")

# ── 2D 격자 중앙값 계산 ───────────────────────────────────────────────────────
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

# ═══════════════════════════════════════════════════════════════════════════
# Figure 1: 3D 선 그래프  (2행 × 3열)
# ─── 시각화 전략 ───────────────────────────────────────────────────────────
# 140039(Ramp)  : eps를 천천히 올리며 d를 연속 스윔
#                 → d축 방향 선 (일정 변형률 수준에서 근접도 변화)
# 143611(Osc.)  : eps를 반복 왕복하며 d를 단계적으로 내림
#                 → eps축 방향 선 (일정 근접 거리에서 변형률 변화)
# Mixed         : 두 선 세트를 겹쳐서 격자 형성
# ═══════════════════════════════════════════════════════════════════════════
ELEV, AZIM = 22, -55

fig1 = plt.figure(figsize=(18, 11))
fig1.suptitle("3D Graph", fontsize=12, fontweight="bold")

row_cfg = [
    ("ΔL / L₀ [%]", gLA, gLB, COLOR_L),
    ("ΔR / R₀ [%]", gRA, gRB, COLOR_R),
]
col_titles = ["Strain:Discrete & Proximity:Continuous", "Strain:Continuous & Proximity:Discrete", "Mixed"]

for row_i, (zlabel, gA, gB, line_color) in enumerate(row_cfg):
    for col_i in range(3):
        ax = fig1.add_subplot(2, 3, row_i * 3 + col_i + 1, projection="3d")
        ax.set_xlabel("Proximity [mm]", fontsize=7, labelpad=1)
        ax.set_ylabel("Strain [%]",     fontsize=7, labelpad=1)
        ax.set_zlabel(zlabel,           fontsize=7, labelpad=1)
        ax.set_title(col_titles[col_i], fontsize=9, fontweight="bold")
        ax.tick_params(labelsize=6, pad=0)
        ax.view_init(elev=ELEV, azim=AZIM)

        # 140039: lines of constant eps along d-axis (solid)
        if col_i in (0, 2):
            for i, eps_c in enumerate(eps_centers):
                z = gA[i, :]
                valid = ~np.isnan(z)
                if valid.sum() > 1:
                    lbl = "140039 (Ramp)" if (col_i == 2 and row_i == 0 and i == 0) else ""
                    ax.plot(d_centers[valid],
                            np.full(valid.sum(), eps_c),
                            z[valid],
                            color=line_color, lw=1.2, alpha=0.75,
                            linestyle="-", label=lbl)

        # 143611: lines of constant d along eps-axis (dashed)
        if col_i in (1, 2):
            for j, d_c in enumerate(d_centers):
                z = gB[:, j]
                valid = ~np.isnan(z)
                if valid.sum() > 1:
                    lbl = "143611 (Oscillate)" if (col_i == 2 and row_i == 0 and j == 0) else ""
                    ax.plot(np.full(valid.sum(), d_c),
                            eps_centers[valid],
                            z[valid],
                            color=line_color, lw=1.2, alpha=0.75,
                            linestyle="--", label=lbl)


plt.tight_layout(rect=[0, 0, 1, 0.92])
fig1.savefig(DIR / "surface_3d.png", dpi=150, bbox_inches="tight")
plt.close(fig1)
print("Saved → surface_3d.png")

# ═══════════════════════════════════════════════════════════════════════════
# Figure 2: 2D 히트맵  (2행 × 3열)
# ─── Mixed 처리 ────────────────────────────────────────────────────────────
# 두 셀 모두 유효 → 평균값, 한쪽만 유효 → 해당 값, 둘 다 NaN → 회색 표시
# ═══════════════════════════════════════════════════════════════════════════
cmap_L = LinearSegmentedColormap.from_list("cmap_L", ["#fff5e6", COLOR_L, "#4A2000"])
cmap_R = LinearSegmentedColormap.from_list("cmap_R", ["#f0fff0", COLOR_R, "#0a3010"])

fig2, axes2 = plt.subplots(2, 3, figsize=(15, 9))
fig2.suptitle(
    "2D Heatmap",
    fontsize=11, fontweight="bold"
)

hmap_rows = [
    (gLA, gLB, gL_mix, "ΔL / L₀ [%]", cmap_L),
    (gRA, gRB, gR_mix, "ΔR / R₀ [%]", cmap_R),
]
col_labels = ["Strain:Discrete & Proximity:Continuous", "Strain:Continuous & Proximity:Discrete", "Mixed"]

ne_bins = len(EPS_EDGES) - 1
nd_bins = len(D_EDGES)   - 1

for row_i, (gA, gB, gM, label, cmap) in enumerate(hmap_rows):
    vmin = np.nanmin([gA, gB])
    vmax = np.nanmax([gA, gB])
    for col_i, (grid, ctitle) in enumerate(zip([gA, gB, gM], col_labels)):
        ax = axes2[row_i, col_i]
        im = ax.imshow(grid, origin="lower", aspect="auto",
                       vmin=vmin, vmax=vmax, cmap=cmap,
                       extent=[D_EDGES[0], D_EDGES[-1],
                                EPS_EDGES[0], EPS_EDGES[-1]])
        cbar = plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
        cbar.set_label(label, fontsize=8)
        ax.set_title(ctitle, fontsize=10, fontweight="bold")
        ax.set_xlabel("Proximity [mm]", fontsize=9)
        ax.set_ylabel("Strain [%]",     fontsize=9)

        # NaN 셀 → 회색 패치
        for i in range(ne_bins):
            for j in range(nd_bins):
                if np.isnan(grid[i, j]):
                    rect = plt.Rectangle(
                        (D_EDGES[j], EPS_EDGES[i]),
                        D_EDGES[j+1] - D_EDGES[j],
                        EPS_EDGES[i+1] - EPS_EDGES[i],
                        fill=True, color="lightgray", alpha=0.7, zorder=2
                    )
                    ax.add_patch(rect)

plt.tight_layout(rect=[0, 0, 1, 0.92])
fig2.savefig(DIR / "heatmap_2d.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("Saved → heatmap_2d.png")
print("Done.")
