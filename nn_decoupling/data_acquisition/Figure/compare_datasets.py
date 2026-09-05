"""
두 데이터셋이 같은 물리 조건(eps, d)에서 동일한 센서 응답을 보이는지 비교.
출력: compare_heatmap.png, compare_slices.png
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

DIR = Path(__file__).parent
DATA_DIR = DIR.parent

COLOR_L    = "#FF8C00"
COLOR_R    = "#2CA02C"
C_A        = "#1F77B4"   # 140039
C_B        = "#E377C2"   # 143611

# ── 공통 baseline 계산 후 dL/dR 재계산 ───────────────────────────────────────
def load_raw(fname):
    return pd.read_csv(DATA_DIR / fname)

dfA = load_raw("collect_20260519_140039.csv")
dfB = load_raw("collect_20260519_143611.csv")

def estimate_baseline(df, n=200):
    """eps≈0, d≈36mm 초기 구간의 중앙값으로 L0, R0 추정."""
    ref = df[(df["eps_act_pct"] < 0.5) & (df["d_act_mm"] > 35)].head(n)
    L0 = ref["ldc_raw"].median()
    R0 = ref["r_raw"].median()
    return L0, R0

L0_A, R0_A = estimate_baseline(dfA)
L0_B, R0_B = estimate_baseline(dfB)
print(f"140039: L0={L0_A:.0f}  R0={R0_A:.0f}")
print(f"143611: L0={L0_B:.0f}  R0={R0_B:.0f}")

def recompute(df, L0, R0):
    """각 파일의 L0/R0로 dL_pct, dR_pct 재계산 → 기준점에서 정확히 0."""
    df = df.copy()
    df["dL_pct"] = ((L0 / df["ldc_raw"]) ** 2 - 1.0) * 100.0
    df["dR_pct"] = ((df["r_raw"] - R0) / R0) * 100.0
    mask = (df["dL_pct"].abs() < 30) & (df["dR_pct"] > -5) & (df["dR_pct"] < 30)
    return df[mask].reset_index(drop=True)

dfA = recompute(dfA, L0_A, R0_A)
dfB = recompute(dfB, L0_B, R0_B)

# 데이터 부족 구간 제외:
#   140039 → eps=0% 부근 샘플 극소 / 143611 → d≈0mm 데이터 없음
dfA = dfA[(dfA["eps_act_pct"] >= 5) & (dfA["d_act_mm"] >= 5)].reset_index(drop=True)
dfB = dfB[(dfB["eps_act_pct"] >= 5) & (dfB["d_act_mm"] >= 5)].reset_index(drop=True)
print(f"140039 after trim: {len(dfA):,}")
print(f"143611 after trim: {len(dfB):,}")

# eps, d 격자 정의 (제외 구간 반영)
EPS_EDGES   = np.array([5, 10, 15, 20, 25, 30])         # 0-5% 제외
D_EDGES     = np.array([5, 10, 15, 20, 25, 30, 36])      # 1-5mm 제외

def cap_eps_visits(df, eps_edges, cap=30):
    """eps bin의 연속 방문마다 eps-grid 기준 샘플링 (time 기준 X).
    감속·정지로 eps≈0, eps≈30% 에 샘플이 몰려도 각 eps 값 1개씩만 선택."""
    eps_vals = df["eps_act_pct"].values
    ei = np.digitize(eps_vals, eps_edges) - 1
    ei = np.clip(ei, 0, len(eps_edges) - 2)
    keep_set = set()
    i, n = 0, len(df)
    while i < n:
        b = ei[i]
        j = i
        while j < n and ei[j] == b:
            j += 1
        size = j - i
        if size <= cap:
            keep_set.update(range(i, j))
        else:
            lo, hi = float(eps_edges[b]), float(eps_edges[b + 1])
            grid = np.linspace(lo, hi, cap + 2)[1:-1]   # 양 끝 제외
            local_eps = eps_vals[i:j]
            for gp in grid:
                idx_local = int(np.argmin(np.abs(local_eps - gp)))
                keep_set.add(i + idx_local)
        i = j
    return df.iloc[sorted(keep_set)].reset_index(drop=True)

# 140039(Ramp): eps 분포 균등 + d도 전체 커버 → capping 불필요
# 143611(Oscillate): eps=0%/30% 전환점에 샘플 편중 → eps-grid capping 적용
dfB = cap_eps_visits(dfB, EPS_EDGES, cap=30)
print(f"140039 samples: {len(dfA):,}")
print(f"143611 after visit-cap: {len(dfB):,}")

def bin2d(df):
    ei = np.digitize(df["eps_act_pct"].values, EPS_EDGES) - 1
    di = np.digitize(df["d_act_mm"].values,   D_EDGES)   - 1
    ne, nd = len(EPS_EDGES)-1, len(D_EDGES)-1
    dL_grid = np.full((ne, nd), np.nan)
    dR_grid = np.full((ne, nd), np.nan)
    cnt     = np.zeros((ne, nd), dtype=int)
    for i in range(ne):
        for j in range(nd):
            sel = (ei == i) & (di == j)
            if sel.sum() > 3:
                dL_grid[i, j] = df.loc[sel, "dL_pct"].median()
                dR_grid[i, j] = df.loc[sel, "dR_pct"].median()
                cnt[i, j]     = sel.sum()
    return dL_grid, dR_grid, cnt

gLA, gRA, cntA = bin2d(dfA)
gLB, gRB, cntB = bin2d(dfB)

eps_centers = (EPS_EDGES[:-1] + EPS_EDGES[1:]) / 2
d_centers   = (D_EDGES[:-1]  + D_EDGES[1:])  / 2

# ── Figure 1: 2D Heatmap 비교 ────────────────────────────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(16, 9))
fig.suptitle("Dataset Comparison — 2D Binned Mean\n"
             "Left: 140039 (Ramp)   ·   Center: 143611 (Oscillate)   ·   Right: Difference",
             fontsize=12, fontweight="bold")

pairs = [
    (gLA, gLB, "ΔL / L₀ [%]", COLOR_L),
    (gRA, gRB, "ΔR / R₀ [%]", COLOR_R),
]

for row, (gA, gB, label, _) in enumerate(pairs):
    diff  = gA - gB
    vmin  = np.nanmin([gA, gB])
    vmax  = np.nanmax([gA, gB])
    dabs  = np.nanmax(np.abs(diff))

    for col, (grid, title) in enumerate([
        (gA,   f"140039  {label}"),
        (gB,   f"143611  {label}"),
        (diff, f"Diff (A−B)  {label}"),
    ]):
        ax = axes[row, col]
        if col < 2:
            im = ax.imshow(grid, origin="lower", aspect="auto",
                           vmin=vmin, vmax=vmax, cmap="RdYlBu_r",
                           extent=[D_EDGES[0], D_EDGES[-1],
                                   EPS_EDGES[0], EPS_EDGES[-1]])
        else:
            im = ax.imshow(grid, origin="lower", aspect="auto",
                           vmin=-dabs, vmax=dabs, cmap="RdBu_r",
                           extent=[D_EDGES[0], D_EDGES[-1],
                                   EPS_EDGES[0], EPS_EDGES[-1]])
        plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("proximity [mm]", fontsize=9)
        ax.set_ylabel("strain [%]", fontsize=9)

plt.tight_layout()
fig.savefig(DIR / "compare_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("Saved → compare_heatmap.png")

# ── Figure 2: 연속 eps 구간 슬라이스 ────────────────────────────────────────
EPS_BINS     = list(zip(EPS_EDGES[:-1], EPS_EDGES[1:]))  # [(0,5),(5,10),...,(25,30)]
n_slices     = len(EPS_BINS)   # 6개
d_centers_sl = (D_EDGES[:-1] + D_EDGES[1:]) / 2

def bin_slice(df, eps_lo, eps_hi):
    """[eps_lo, eps_hi] 구간 샘플을 d bin별 중앙값 + Q25/Q75로 반환."""
    sel = (df["eps_act_pct"] >= eps_lo) & (df["eps_act_pct"] <= eps_hi)
    sub = df[sel]
    nd  = len(D_EDGES) - 1
    dL_med = np.full(nd, np.nan)
    dR_med = np.full(nd, np.nan)
    dL_q25 = np.full(nd, np.nan); dL_q75 = np.full(nd, np.nan)
    dR_q25 = np.full(nd, np.nan); dR_q75 = np.full(nd, np.nan)
    cnt    = np.zeros(nd, dtype=int)
    di = np.digitize(sub["d_act_mm"].values, D_EDGES) - 1
    for j in range(nd):
        s = di == j
        if s.sum() > 3:
            vL = sub["dL_pct"].values[s]
            vR = sub["dR_pct"].values[s]
            dL_med[j] = np.median(vL);  dR_med[j] = np.median(vR)
            dL_q25[j] = np.percentile(vL, 25); dL_q75[j] = np.percentile(vL, 75)
            dR_q25[j] = np.percentile(vR, 25); dR_q75[j] = np.percentile(vR, 75)
            cnt[j]    = s.sum()
    return (dL_med, dR_med,
            dL_q25, dL_q75, dR_q25, dR_q75,
            cnt, int(sel.sum()))

fig, axes = plt.subplots(2, n_slices, figsize=(3.5 * n_slices, 7),
                         sharex=True, sharey="row")
fig.suptitle("Datasets Compare)",
             fontsize=11, fontweight="bold")

legend_handles = []   # figure 공통 legend용

for col, (eps_lo, eps_hi) in enumerate(EPS_BINS):
    dLA, dRA, *_, nA = bin_slice(dfA, eps_lo, eps_hi)
    dLB, dRB, *_, nB = bin_slice(dfB, eps_lo, eps_hi)

    for row, (medA, medB, ylabel) in enumerate([
        (dLA, dLB, "ΔL / L₀ [%]"),
        (dRA, dRB, "ΔR / R₀ [%]"),
    ]):
        ax = axes[row, col]

        selA = (dfA["eps_act_pct"] >= eps_lo) & (dfA["eps_act_pct"] <= eps_hi)
        selB = (dfB["eps_act_pct"] >= eps_lo) & (dfB["eps_act_pct"] <= eps_hi)
        yk = "dL_pct" if row == 0 else "dR_pct"
        nA_sel = selA.sum()
        rng = np.random.default_rng(42)
        idxA = rng.choice(dfA.index[selA], size=min(2000, nA_sel), replace=False)
        ax.scatter(dfB.loc[selB, "d_act_mm"], dfB.loc[selB, yk],
                   s=3, color=C_B, alpha=0.20, zorder=2)
        ax.scatter(dfA.loc[idxA, "d_act_mm"], dfA.loc[idxA, yk],
                   s=2, color=C_A, alpha=0.10, zorder=3)

        mA, mB = ~np.isnan(medA), ~np.isnan(medB)
        if mB.any():
            h_B, = ax.plot(d_centers_sl[mB], medB[mB], "s--", color=C_B,
                           lw=1.5, ms=5, label="Strain:Continuous & Proximity:Discrete", zorder=4)
            if col == 0 and row == 0:
                legend_handles.append(h_B)
        if mA.any():
            h_A, = ax.plot(d_centers_sl[mA], medA[mA], "o-", color=C_A,
                           lw=2.0, ms=8, label="Strain:Discrete & Proximity:Continuous", zorder=5,
                           markeredgecolor="white", markeredgewidth=1.2)
            if col == 0 and row == 0:
                legend_handles.append(h_A)

        ax.axhline(0, color="gray", lw=0.6, ls=":")
        ax.set_xlim(D_EDGES[0], D_EDGES[-1])
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        ax.grid(True, which="major", ls="--", alpha=0.35)

        if row == 0:
            ax.set_title(f"strain: {eps_lo}–{eps_hi} %", fontsize=10)
        if col == 0:
            ax.set_ylabel(ylabel, fontsize=9)
        if row == 1:
            ax.set_xlabel("proximity [mm]", fontsize=9)

fig.legend(handles=legend_handles, loc="lower center",
           ncol=2, fontsize=9, frameon=True,
           bbox_to_anchor=(0.5, -0.02))
plt.tight_layout(rect=[0, 0.04, 1, 1])
fig.savefig(DIR / "compare_slices.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("Saved → compare_slices.png")
print("Done.")
