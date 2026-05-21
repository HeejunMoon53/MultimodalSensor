"""
data_analysis.py
새 데이터셋 (metal + hand/삼겹살) 3D 시각화 및 경향성 분석

실행:
    C:/ml_env/Scripts/python nn_decoupling/data_analysis.py

출력:
    nn_decoupling/figures/  →  3d_dL.png / 3d_dR.png / heatmap_dL.png / heatmap_dR.png
    nn_decoupling/report_new.html
"""

import os, glob, re, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401
from scipy.interpolate import griddata
import warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

# ── 경로 ──────────────────────────────────────────────────────────────────────
HERE      = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(HERE, 'data', 'metal')   # sync_acquisition 저장 루트

METAL_P1 = os.path.join(DATA_ROOT, 'metal', 'p1_strain_discrete')
HAND_P1  = os.path.join(DATA_ROOT, 'hand',  'p1_strain_discrete')
METAL_P2 = os.path.join(DATA_ROOT, 'metal', 'p2_proximity_discrete')
HAND_P2  = os.path.join(DATA_ROOT, 'hand',  'p2_proximity_discrete')

FIG_DIR  = os.path.join(HERE, 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

# ── 물리 파라미터 ──────────────────────────────────────────────────────────────
METAL_PROX_OFFSET = 52.0   # 스테이지 z=0 일 때 금속까지 거리 (mm)
HAND_PROX_OFFSET  = 30.0   # 스테이지 z=0 일 때 손까지 거리 (mm)
SENSOR_L0_MM      = 120.0  # 센서 초기 길이 (mm)

# ── 스타일 ────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'axes.titlepad': 10,
    'figure.dpi': 120,
})

METAL_COLOR = '#4c9be8'   # 파란계열
HAND_COLOR  = '#e87b4c'   # 주황계열


# ══════════════════════════════════════════════════════════════════════════════
# 데이터 로드
# ══════════════════════════════════════════════════════════════════════════════

def load_p1_dir(p1_dir: str, prox_offset: float, steady_only: bool = False) -> pd.DataFrame:
    """P1 폴더의 모든 CSV를 로드.
    steady_only=True 이면 is_steady==1 행만, False 이면 전체 행 반환.
    strain_mm = 2 × xa_mm (대칭 인장)
    proximity_mm = prox_offset + z_mm  (z는 음수)
    """
    rows = []
    for fpath in sorted(glob.glob(os.path.join(p1_dir, '*.csv'))):
        try:
            df = pd.read_csv(fpath)
            if steady_only:
                df = df[df['is_steady'] == 1]
            if len(df) < 5:
                continue
            df = df.copy()
            df['strain_mm']    = (df['xa_mm'].abs() * 2).round(2)
            df['proximity_mm'] = (prox_offset + df['z_mm']).round(2)
            rows.append(df)
        except Exception as e:
            print(f'  [skip] {os.path.basename(fpath)}: {e}')
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def load_p2_dir(p2_dir: str, prox_offset: float, steady_only: bool = False) -> pd.DataFrame:
    """P2 폴더의 모든 CSV를 로드.
    proximity discrete (파일당 z 고정), strain sweep.
    """
    rows = []
    for fpath in sorted(glob.glob(os.path.join(p2_dir, '*.csv'))):
        try:
            df = pd.read_csv(fpath)
            if steady_only:
                df = df[df['is_steady'] == 1]
            if len(df) < 5:
                continue
            df = df.copy()
            df['strain_mm']    = (df['xa_mm'].abs() * 2).round(2)
            df['proximity_mm'] = (prox_offset + df['z_mm']).round(2)
            rows.append(df)
        except Exception as e:
            print(f'  [skip] {os.path.basename(fpath)}: {e}')
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def compute_baseline(df: pd.DataFrame) -> tuple:
    """zero strain + max proximity 조건에서 L0, R0 추출."""
    ref = df[(df['strain_mm'] <= 0.5) &
             (df['proximity_mm'] >= df['proximity_mm'].max() - 3)]
    if len(ref) < 5:
        ref = df[df['strain_mm'] <= 0.5].head(50)
    L0 = float(ref['ldc_raw'].median())
    R0 = float(ref['r_raw'].median())
    return L0, R0


def add_delta(df: pd.DataFrame, L0: float, R0: float) -> pd.DataFrame:
    df = df.copy()
    df['dL_pct']    = ((L0 / df['ldc_raw'].clip(lower=1)) ** 2 - 1.0) * 100.0
    df['dR_pct']    = ((df['r_raw'] - R0) / R0) * 100.0
    df['strain_pct'] = df['strain_mm'] / SENSOR_L0_MM * 100.0   # mm → %
    return df


def bin_mean(df: pd.DataFrame,
             strain_bins_pct: np.ndarray,
             prox_bins: np.ndarray) -> tuple:
    """(strain_pct, proximity) 격자 평균 → S(%), P(mm), ZL, ZR 반환."""
    s_mid = (strain_bins_pct[:-1] + strain_bins_pct[1:]) / 2
    p_mid = (prox_bins[:-1]       + prox_bins[1:])       / 2
    S, P  = np.meshgrid(s_mid, p_mid)
    ZL = np.full_like(S, np.nan)
    ZR = np.full_like(S, np.nan)
    for si, sv in enumerate(s_mid):
        for pi, pv in enumerate(p_mid):
            sub = df[(df['strain_pct'].between(strain_bins_pct[si], strain_bins_pct[si+1])) &
                     (df['proximity_mm'].between(prox_bins[pi], prox_bins[pi+1]))]
            if len(sub) >= 3:
                ZL[pi, si] = sub['dL_pct'].mean()
                ZR[pi, si] = sub['dR_pct'].mean()
    return S, P, ZL, ZR


# ══════════════════════════════════════════════════════════════════════════════
# 메인: 데이터 로드 및 전처리
# ══════════════════════════════════════════════════════════════════════════════

print("▶ 데이터 로드 중...")
metal_p1 = load_p1_dir(METAL_P1, METAL_PROX_OFFSET, steady_only=False)
hand_p1  = load_p1_dir(HAND_P1,  HAND_PROX_OFFSET,  steady_only=False)
metal_p2 = load_p2_dir(METAL_P2, METAL_PROX_OFFSET, steady_only=False)
hand_p2  = load_p2_dir(HAND_P2,  HAND_PROX_OFFSET,  steady_only=False)

# 베이스라인 계산용 steady-only 서브셋
metal_p1_steady = load_p1_dir(METAL_P1, METAL_PROX_OFFSET, steady_only=True)
hand_p1_steady  = load_p1_dir(HAND_P1,  HAND_PROX_OFFSET,  steady_only=True)

print(f"  metal P1: {len(metal_p1):,}행  |  metal P2: {len(metal_p2):,}행")
print(f"  hand  P1: {len(hand_p1):,}행  |  hand  P2: {len(hand_p2):,}행")

# grid용: P1 + P2 합산
metal_all = pd.concat([metal_p1, metal_p2], ignore_index=True) if len(metal_p2) else metal_p1
hand_all  = pd.concat([hand_p1,  hand_p2],  ignore_index=True) if len(hand_p2)  else hand_p1

# 베이스라인 — 각 물체 세션별로 별도 계산
# L0: 인덕턴스 기준 (air condition, metal P1 max prox에서 추출)
# R0: 저항 기준 — 손 실험은 손 pre-tension 으로 약 +1% 오프셋 → 세션별 R0 분리
L0,      R0      = compute_baseline(metal_p1_steady)
L0_hand, R0_hand = compute_baseline(hand_p1_steady)
print(f"  베이스라인: L0(metal)={L0:.0f}  R0(metal)={R0:.0f}")
print(f"             L0(hand) ={L0_hand:.0f}  R0(hand) ={R0_hand:.0f}")

# 개별 데이터프레임에 dL/dR 추가 — hand는 hand 전용 베이스라인 사용
metal_p1 = add_delta(metal_p1, L0,      R0)
metal_p2 = add_delta(metal_p2, L0,      R0)
hand_p1  = add_delta(hand_p1,  L0_hand, R0_hand)
hand_p2  = add_delta(hand_p2,  L0_hand, R0_hand)

# grid용 합산도 재생성 (add_delta 이후)
metal_all = pd.concat([metal_p1, metal_p2], ignore_index=True) if len(metal_p2) else metal_p1
hand_all  = pd.concat([hand_p1,  hand_p2],  ignore_index=True) if len(hand_p2)  else hand_p1

# proximity 음수 제거 + hand P2 proximity≈0 불량 데이터 제거
metal_p1 = metal_p1[metal_p1['proximity_mm'] >= 0].reset_index(drop=True)
metal_p2 = metal_p2[metal_p2['proximity_mm'] >= 0].reset_index(drop=True)
hand_p1  = hand_p1 [hand_p1 ['proximity_mm'] >= 0].reset_index(drop=True)
hand_p2  = hand_p2 [hand_p2 ['proximity_mm'] >  1].reset_index(drop=True)  # prox≈0 마찰 오류 제거
metal_all = metal_all[metal_all['proximity_mm'] >= 0].reset_index(drop=True)
hand_all  = hand_all [hand_all ['proximity_mm'] >  1].reset_index(drop=True)

# 데이터 범위 확인
for tag, df in [('metal P1', metal_p1), ('metal P2', metal_p2),
                ('hand  P1', hand_p1),  ('hand  P2', hand_p2)]:
    if len(df) == 0: continue
    print(f"  {tag}: strain {df['strain_mm'].min():.0f}~{df['strain_mm'].max():.0f}mm  "
          f"prox {df['proximity_mm'].min():.1f}~{df['proximity_mm'].max():.1f}mm  "
          f"dL {df['dL_pct'].min():.1f}~{df['dL_pct'].max():.1f}%")


# ── 격자 생성 ─────────────────────────────────────────────────────────────────
# P1 strain 레벨: 0,2,4,...mm → 0,1.667,3.333,...%
# bin 경계를 -1,1,3,5,...mm 로 오프셋해서 각 strain 레벨이 bin 정중앙에 위치하도록 함
# (경계 = 데이터 값이면 between()이 양쪽 bin에 동시 포함 → 아티팩트 발생)
STRAIN_BINS_PCT = np.round(np.arange(-1, 39, 2) / SENSOR_L0_MM * 100, 4)
M_PROX_BINS = np.arange(0, 55, 1)    # metal: 0~52mm, 1mm 해상도
H_PROX_BINS = np.arange(0, 32, 1)    # hand:  0~30mm, 1mm 해상도

def fill_nan(Z):
    from scipy.interpolate import NearestNDInterpolator
    mask = ~np.isnan(Z)
    if mask.sum() < 4:
        return Z
    pts  = np.argwhere(mask)
    vals = Z[mask]
    interp = NearestNDInterpolator(pts, vals)
    Z_filled = Z.copy()
    nan_pts  = np.argwhere(np.isnan(Z))
    if len(nan_pts):
        Z_filled[np.isnan(Z)] = interp(nan_pts)
    return Z_filled

def make_grid(df, strain_bins, prox_bins):
    S, P, ZL, ZR = bin_mean(df, strain_bins, prox_bins)
    return S, P, fill_nan(ZL), fill_nan(ZR)

# P1만, P2만, P1+P2 합산 — 각각 격자 생성
Sm_p1, Pm_p1, ZmL_p1, ZmR_p1 = make_grid(metal_p1,  STRAIN_BINS_PCT, M_PROX_BINS)
Sm_p2, Pm_p2, ZmL_p2, ZmR_p2 = make_grid(metal_p2,  STRAIN_BINS_PCT, M_PROX_BINS)
Sm,    Pm,    ZmL,    ZmR    = make_grid(metal_all, STRAIN_BINS_PCT, M_PROX_BINS)

Sh_p1, Ph_p1, ZhL_p1, ZhR_p1 = make_grid(hand_p1,  STRAIN_BINS_PCT, H_PROX_BINS)
Sh_p2, Ph_p2, ZhL_p2, ZhR_p2 = make_grid(hand_p2,  STRAIN_BINS_PCT, H_PROX_BINS)
Sh,    Ph,    ZhL,    ZhR    = make_grid(hand_all, STRAIN_BINS_PCT, H_PROX_BINS)

# 요약 통계 (report용)
stats = {
    'metal_dL_min': metal_all['dL_pct'].min(),
    'metal_dL_max': metal_all['dL_pct'].max(),
    'metal_dR_min': metal_all['dR_pct'].min(),
    'metal_dR_max': metal_all['dR_pct'].max(),
    'hand_dL_min':  hand_all['dL_pct'].min(),
    'hand_dL_max':  hand_all['dL_pct'].max(),
    'hand_dR_min':  hand_all['dR_pct'].min(),
    'hand_dR_max':  hand_all['dR_pct'].max(),
    'L0': L0, 'R0': R0,
    'metal_rows': len(metal_all),
    'hand_rows':  len(hand_all),
}


# ══════════════════════════════════════════════════════════════════════════════
# 시각화 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def plot_strain_lines(ax, df, signal_col, ylabel, cmap_name, title):
    """P1용: 각 discrete strain 레벨 → proximity vs signal 곡선. (colorbar=strain %)"""
    strains = sorted(df['strain_pct'].unique())
    n = len(strains)
    cmap = plt.get_cmap(cmap_name)
    colors = [cmap(0.15 + 0.75 * i / max(n - 1, 1)) for i in range(n)]

    for i, sv in enumerate(strains):
        sub = df[df['strain_pct'] == sv].sort_values('proximity_mm').copy()
        sub['prox_bin'] = sub['proximity_mm'].round(0)
        smooth = sub.groupby('prox_bin')[signal_col].mean().reset_index()
        smooth.columns = ['prox', 'sig']
        ax.plot(smooth['prox'], smooth['sig'],
                color=colors[i], linewidth=1.4, alpha=0.85)

    ax.set_xlabel('Proximity (mm)')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.25, linewidth=0.6)

    sm = plt.cm.ScalarMappable(cmap=cmap_name,
                                norm=plt.Normalize(vmin=strains[0], vmax=strains[-1]))
    sm.set_array([])
    plt.colorbar(sm, ax=ax, label='Strain (%)', fraction=0.046, pad=0.04)


def plot_proximity_lines(ax, df, signal_col, ylabel, cmap_name, title):
    """P2용: 각 discrete proximity 레벨 → strain(%) vs signal 곡선."""
    df = df.copy()
    df['prox_grp'] = (df['proximity_mm'] / 2).round() * 2
    proxes = sorted(df['prox_grp'].unique())
    n = len(proxes)
    cmap = plt.get_cmap(cmap_name)
    colors = [cmap(0.15 + 0.75 * i / max(n - 1, 1)) for i in range(n)]

    for i, pv in enumerate(proxes):
        sub = df[df['prox_grp'] == pv].sort_values('strain_pct').copy()
        sub['strain_bin'] = sub['strain_pct'].round(1)
        smooth = sub.groupby('strain_bin')[signal_col].mean().reset_index()
        smooth.columns = ['strain', 'sig']
        ax.plot(smooth['strain'], smooth['sig'],
                color=colors[i], linewidth=1.4, alpha=0.85)

    ax.set_xlabel('Strain (%)')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.25, linewidth=0.6)

    sm = plt.cm.ScalarMappable(cmap=cmap_name,
                                norm=plt.Normalize(vmin=proxes[0], vmax=proxes[-1]))
    sm.set_array([])
    plt.colorbar(sm, ax=ax, label='Proximity (mm)', fraction=0.046, pad=0.04)


def grid_heatmap(ax, S, P, Z, cmap, title, zlabel, vmin=None, vmax=None):
    """2D 격자 등고선 히트맵. X=Proximity(mm), Y=Strain(%)."""
    im = ax.contourf(P, S, Z, levels=20, cmap=cmap, vmin=vmin, vmax=vmax)
    cs = ax.contour( P, S, Z, levels=10, colors='white', linewidths=0.5, alpha=0.45)
    ax.clabel(cs, inline=True, fontsize=7, fmt='%.1f')
    ax.set_xlabel('Proximity (mm)')
    ax.set_ylabel('Strain (%)')
    ax.set_title(title)
    return im


def surf_3d(ax, S_pct, P_mm, Z, cmap, title, zlabel, alpha=0.80):
    """3D 서피스. X=Proximity(mm), Y=Strain(%), Z=signal."""
    ax.plot_surface(P_mm, S_pct, Z, cmap=cmap, alpha=alpha,
                    edgecolor='none', linewidth=0, antialiased=True)
    ax.set_xlabel('Proximity (mm)', labelpad=5)
    ax.set_ylabel('Strain (%)', labelpad=5)
    ax.set_zlabel(zlabel, labelpad=5)
    ax.set_title(title, pad=6)
    ax.view_init(elev=25, azim=-50)


# ══════════════════════════════════════════════════════════════════════════════
# Figure 0a: Metal 3D — P1 / P2 / 합산 (3행×2열)
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Metal 3D 피규어 생성...")
fig = plt.figure(figsize=(14, 17))
fig.suptitle('Metal (도체) — 3D Surface\n'
             '행: P1 only | P2 only | P1+P2 합산     열: ΔL/L₀ | ΔR/R₀',
             fontsize=13, fontweight='bold')

_metal_sets = [
    (Sm_p1, Pm_p1, ZmL_p1, ZmR_p1, 'P1 only'),
    (Sm_p2, Pm_p2, ZmL_p2, ZmR_p2, 'P2 only'),
    (Sm,    Pm,    ZmL,    ZmR,    'P1+P2 합산'),
]
for row, (S, P, ZL, ZR, lbl) in enumerate(_metal_sets):
    ax1 = fig.add_subplot(3, 2, row * 2 + 1, projection='3d')
    ax2 = fig.add_subplot(3, 2, row * 2 + 2, projection='3d')
    surf_3d(ax1, S, P, ZL, 'Blues',  f'ΔL/L₀ (%) — {lbl}', 'ΔL/L₀ (%)')
    surf_3d(ax2, S, P, ZR, 'Greens', f'ΔR/R₀ (%) — {lbl}', 'ΔR/R₀ (%)')
    for ax in [ax1, ax2]:
        ax.set_box_aspect([1, 1, 0.7])

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'metal_3d.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/metal_3d.png")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 0b: Hand 3D — P1 / P2 / 합산 (3행×2열)
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Hand 3D 피규어 생성...")
fig = plt.figure(figsize=(14, 17))
fig.suptitle('Hand/삼겹살 (유전체) — 3D Surface\n'
             '행: P1 only | P2 only | P1+P2 합산     열: ΔL/L₀ | ΔR/R₀',
             fontsize=13, fontweight='bold')

_hand_sets = [
    (Sh_p1, Ph_p1, ZhL_p1, ZhR_p1, 'P1 only'),
    (Sh_p2, Ph_p2, ZhL_p2, ZhR_p2, 'P2 only'),
    (Sh,    Ph,    ZhL,    ZhR,    'P1+P2 합산'),
]
for row, (S, P, ZL, ZR, lbl) in enumerate(_hand_sets):
    ax1 = fig.add_subplot(3, 2, row * 2 + 1, projection='3d')
    ax2 = fig.add_subplot(3, 2, row * 2 + 2, projection='3d')
    surf_3d(ax1, S, P, ZL, 'Oranges', f'ΔL/L₀ (%) — {lbl}', 'ΔL/L₀ (%)')
    surf_3d(ax2, S, P, ZR, 'YlOrRd',  f'ΔR/R₀ (%) — {lbl}', 'ΔR/R₀ (%)')
    for ax in [ax1, ax2]:
        ax.set_box_aspect([1, 1, 0.7])

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'hand_3d.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/hand_3d.png")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 1: Metal Lines (P1: proximity sweep | P2: strain sweep) — 2×2
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Metal lines 피규어 생성...")
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle('Metal (도체) — Line Plots\n'
             'Top: P1 (strain 고정, proximity sweep)  |  Bottom: P2 (proximity 고정, strain sweep)',
             fontsize=13, fontweight='bold')

plot_strain_lines   (axes[0,0], metal_p1, 'dL_pct', 'ΔL/L₀ (%)', 'Blues',
                     'P1 — ΔL/L₀ vs Proximity  (각 선=고정 strain)')
plot_strain_lines   (axes[0,1], metal_p1, 'dR_pct', 'ΔR/R₀ (%)', 'Greens',
                     'P1 — ΔR/R₀ vs Proximity  (각 선=고정 strain)')
plot_proximity_lines(axes[1,0], metal_p2, 'dL_pct', 'ΔL/L₀ (%)', 'Blues',
                     'P2 — ΔL/L₀ vs Strain  (각 선=고정 proximity)')
plot_proximity_lines(axes[1,1], metal_p2, 'dR_pct', 'ΔR/R₀ (%)', 'Greens',
                     'P2 — ΔR/R₀ vs Strain  (각 선=고정 proximity)')

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'metal_lines.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/metal_lines.png")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 2: Metal Grid Heatmap — P1 / P2 / P1+P2 비교 (2행×3열)
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Metal grid 피규어 생성...")
fig, axes = plt.subplots(2, 3, figsize=(22, 11))
fig.suptitle('Metal (도체) — 2D Grid Heatmap  (X: Proximity mm  |  Y: Strain %)\n'
             '열: P1 only | P2 only | P1+P2 합산     행: ΔL | ΔR',
             fontsize=13, fontweight='bold')

# 공통 색상 범위 (P1/P2/합산 비교를 위해 같은 scale 사용)
vLm = (float(np.nanmin([ZmL_p1, ZmL_p2, ZmL])), float(np.nanmax([ZmL_p1, ZmL_p2, ZmL])))
vRm = (float(np.nanmin([ZmR_p1, ZmR_p2, ZmR])), float(np.nanmax([ZmR_p1, ZmR_p2, ZmR])))

for col, (S, P, ZL, ZR, lbl) in enumerate([
        (Sm_p1, Pm_p1, ZmL_p1, ZmR_p1, 'P1 only'),
        (Sm_p2, Pm_p2, ZmL_p2, ZmR_p2, 'P2 only'),
        (Sm,    Pm,    ZmL,    ZmR,    'P1+P2 합산')]):
    im0 = grid_heatmap(axes[0, col], S, P, ZL, 'RdBu_r', f'ΔL/L₀ (%) — {lbl}', 'ΔL/L₀ (%)', *vLm)
    im1 = grid_heatmap(axes[1, col], S, P, ZR, 'PuOr',   f'ΔR/R₀ (%) — {lbl}', 'ΔR/R₀ (%)', *vRm)
    plt.colorbar(im0, ax=axes[0, col], fraction=0.046, pad=0.04, label='ΔL/L₀ (%)')
    plt.colorbar(im1, ax=axes[1, col], fraction=0.046, pad=0.04, label='ΔR/R₀ (%)')

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'metal_grid.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/metal_grid.png")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 3: Hand Lines — 2×2
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Hand lines 피규어 생성...")
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle('Hand/삼겹살 (유전체) — Line Plots\n'
             'Top: P1 (strain 고정, proximity sweep)  |  Bottom: P2 (proximity 고정, strain sweep)',
             fontsize=13, fontweight='bold')

plot_strain_lines   (axes[0,0], hand_p1, 'dL_pct', 'ΔL/L₀ (%)', 'Oranges',
                     'P1 — ΔL/L₀ vs Proximity  (각 선=고정 strain)')
plot_strain_lines   (axes[0,1], hand_p1, 'dR_pct', 'ΔR/R₀ (%)', 'YlOrRd',
                     'P1 — ΔR/R₀ vs Proximity  (각 선=고정 strain)')
plot_proximity_lines(axes[1,0], hand_p2, 'dL_pct', 'ΔL/L₀ (%)', 'Oranges',
                     'P2 — ΔL/L₀ vs Strain  (각 선=고정 proximity)')
plot_proximity_lines(axes[1,1], hand_p2, 'dR_pct', 'ΔR/R₀ (%)', 'YlOrRd',
                     'P2 — ΔR/R₀ vs Strain  (각 선=고정 proximity)')

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'hand_lines.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/hand_lines.png")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 4: Hand Grid Heatmap — P1 / P2 / P1+P2 비교 (2행×3열)
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Hand grid 피규어 생성...")
fig, axes = plt.subplots(2, 3, figsize=(22, 11))
fig.suptitle('Hand/삼겹살 (유전체) — 2D Grid Heatmap  (X: Proximity mm  |  Y: Strain %)\n'
             '열: P1 only | P2 only | P1+P2 합산     행: ΔL | ΔR',
             fontsize=13, fontweight='bold')

vLh = (float(np.nanmin([ZhL_p1, ZhL_p2, ZhL])), float(np.nanmax([ZhL_p1, ZhL_p2, ZhL])))
vRh = (float(np.nanmin([ZhR_p1, ZhR_p2, ZhR])), float(np.nanmax([ZhR_p1, ZhR_p2, ZhR])))

for col, (S, P, ZL, ZR, lbl) in enumerate([
        (Sh_p1, Ph_p1, ZhL_p1, ZhR_p1, 'P1 only'),
        (Sh_p2, Ph_p2, ZhL_p2, ZhR_p2, 'P2 only'),
        (Sh,    Ph,    ZhL,    ZhR,    'P1+P2 합산')]):
    im0 = grid_heatmap(axes[0, col], S, P, ZL, 'RdBu_r', f'ΔL/L₀ (%) — {lbl}', 'ΔL/L₀ (%)', *vLh)
    im1 = grid_heatmap(axes[1, col], S, P, ZR, 'PuOr',   f'ΔR/R₀ (%) — {lbl}', 'ΔR/R₀ (%)', *vRh)
    plt.colorbar(im0, ax=axes[0, col], fraction=0.046, pad=0.04, label='ΔL/L₀ (%)')
    plt.colorbar(im1, ax=axes[1, col], fraction=0.046, pad=0.04, label='ΔR/R₀ (%)')

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'hand_grid.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/hand_grid.png")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 5: Overlapped Contour — ΔL (filled) + ΔR (line) 겹침 (1×2: metal | hand)
# ══════════════════════════════════════════════════════════════════════════════
print("▶ Overlapped contour 피규어 생성...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
fig.suptitle('ΔL/L₀ (filled) & ΔR/R₀ (line contour) Overlapped\n'
             'X: Proximity (mm)  |  Y: Strain (%)',
             fontsize=13, fontweight='bold')

_overlap_sets = [
    (axes[0], Sm, Pm, ZmL, ZmR, 'Metal (도체)', 'RdBu_r', '#2ca02c'),
    (axes[1], Sh, Ph, ZhL, ZhR, 'Hand/삼겹살 (유전체)', 'PuOr',   '#d62728'),
]
for ax, S, P, ZL, ZR, title, cmap_L, col_R in _overlap_sets:
    # ΔL: filled contour (배경)
    cf = ax.contourf(P, S, ZL, levels=20, cmap=cmap_L, alpha=0.85)
    plt.colorbar(cf, ax=ax, label='ΔL/L₀ (%)', fraction=0.046, pad=0.04)

    # ΔR: line contour (겹침)
    n_lev = 12
    vR_min, vR_max = float(np.nanmin(ZR)), float(np.nanmax(ZR))
    levels_R = np.linspace(vR_min, vR_max, n_lev)
    cs = ax.contour(P, S, ZR, levels=levels_R, colors=col_R,
                    linewidths=1.6, linestyles='solid', alpha=0.85)
    ax.clabel(cs, inline=True, fontsize=8, fmt='%.1f%%',
              manual=False, inline_spacing=4)

    ax.set_xlabel('Proximity (mm)')
    ax.set_ylabel('Strain (%)')
    ax.set_title(title)
    ax.grid(True, alpha=0.15, linewidth=0.5)

    # 범례 proxy
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [Patch(facecolor='gray', alpha=0.6, label='ΔL/L₀ (filled)'),
               Line2D([0], [0], color=col_R, linewidth=1.8, label='ΔR/R₀ (contour)')]
    ax.legend(handles=handles, loc='upper right', fontsize=9)

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'overlap_contour.png'), bbox_inches='tight', dpi=130)
plt.close(fig)
print("  → figures/overlap_contour.png")


# ══════════════════════════════════════════════════════════════════════════════
# 수치 분석 (report용)
# ══════════════════════════════════════════════════════════════════════════════

def analyze_axis_sensitivity(df, axis_col, signal_col, label):
    """한 축을 고정하고 다른 축에 대한 민감도 분석."""
    groups = df.groupby(axis_col)[signal_col]
    result = groups.mean().reset_index()
    result.columns = [axis_col, 'mean']
    return result

# metal ΔL: strain 민감도 (proximity 중간 구간)
metal_mid_prox = metal_all[metal_all['proximity_mm'].between(20, 30)]
dL_vs_strain_metal = analyze_axis_sensitivity(
    metal_mid_prox.assign(strain_bin=metal_mid_prox['strain_mm'].round(0)),
    'strain_bin', 'dL_pct', 'ΔL')

# metal ΔL: proximity 민감도 (strain 0)
metal_s0 = metal_all[metal_all['strain_mm'] <= 1]
dL_vs_prox_metal = analyze_axis_sensitivity(
    metal_s0.assign(prox_bin=metal_s0['proximity_mm'].round(0).clip(0)),
    'prox_bin', 'dL_pct', 'ΔL')

# β₁ 추정: ΔL vs strain (선형 기울기)
from numpy.polynomial import polynomial as Poly
if len(dL_vs_strain_metal) > 3:
    c_dL_s = np.polyfit(dL_vs_strain_metal['strain_bin'],
                         dL_vs_strain_metal['mean'], 1)
    beta1_est = c_dL_s[0]   # %/mm
else:
    beta1_est = float('nan')

# α₁ 추정: ΔR vs strain
metal_s0_R = metal_all[metal_all['proximity_mm'] > 40]
dR_vs_strain = analyze_axis_sensitivity(
    metal_s0_R.assign(strain_bin=metal_s0_R['strain_mm'].round(0)),
    'strain_bin', 'dR_pct', 'ΔR')
if len(dR_vs_strain) > 3:
    c_dR_s = np.polyfit(dR_vs_strain['strain_bin'],
                         dR_vs_strain['mean'], 1)
    alpha1_est = c_dR_s[0]
else:
    alpha1_est = float('nan')

# hand vs metal ΔL 비교 (strain=0, 공통 proximity 구간)
common_prox = np.arange(2, 28, 2)
hand_s0   = hand_all [hand_all ['strain_mm'] <= 1]
metal_s0b = metal_all[metal_all['strain_mm'] <= 1]

hand_ldc_trend  = hand_s0 .groupby(hand_s0 ['proximity_mm'].round(0))['dL_pct'].mean()
metal_ldc_trend = metal_s0b.groupby(metal_s0b['proximity_mm'].round(0))['dL_pct'].mean()

print(f"\n  dL 민감도(b1) ~= {beta1_est:.4f} %/mm (strain, 중간 근접 구간)")
print(f"  dR 민감도(a1) ~= {alpha1_est:.4f} %/mm (strain, 원거리)")


# ══════════════════════════════════════════════════════════════════════════════
# Report HTML 작성
# ══════════════════════════════════════════════════════════════════════════════
print("\n▶ report_new.html 생성...")

def img_b64(path):
    import base64
    with open(path, 'rb') as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

FIG = {k: img_b64(os.path.join(FIG_DIR, k))
       for k in ['metal_3d.png', 'metal_lines.png', 'metal_grid.png',
                 'hand_3d.png',  'hand_lines.png',  'hand_grid.png',
                 'overlap_contour.png']}

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>New Dataset Analysis — Metal &amp; Hand</title>
<style>
:root {{
  --bg:#1e1e2e; --bg2:#181825; --bg3:#313244;
  --text:#cdd6f4; --text2:#a6adc8;
  --blue:#89b4fa; --green:#a6e3a1; --yellow:#f9e2af;
  --mauve:#cba6f7; --red:#f38ba8; --teal:#94e2d5;
  --orange:#fab387; --border:#45475a;
}}
* {{ box-sizing: border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--text);
        font-family:'Segoe UI',Consolas,sans-serif; font-size:15px; line-height:1.7; }}
.wrap {{ max-width:1400px; margin:0 auto; padding:40px 24px; }}
h1 {{ font-size:2rem; color:var(--blue); border-bottom:2px solid var(--border); padding-bottom:12px; margin-bottom:8px; }}
h2 {{ font-size:1.4rem; color:var(--mauve); margin:36px 0 12px; border-left:4px solid var(--mauve); padding-left:12px; }}
h3 {{ font-size:1.1rem; color:var(--teal); margin:20px 0 8px; }}
p  {{ color:var(--text2); margin-bottom:10px; }}
.meta {{ color:var(--text2); font-size:13px; margin-bottom:28px; }}
.card {{ background:var(--bg2); border:1px solid var(--border); border-radius:10px;
         padding:20px 24px; margin:16px 0; }}
.kv-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; margin:12px 0; }}
.kv {{ background:var(--bg3); border-radius:8px; padding:12px 16px; }}
.kv-label {{ font-size:11px; color:var(--text2); letter-spacing:1px; font-weight:600; }}
.kv-val {{ font-size:22px; font-weight:700; font-family:Consolas; color:var(--blue); }}
.kv-val.green {{ color:var(--green); }} .kv-val.yellow {{ color:var(--yellow); }}
.kv-val.orange {{ color:var(--orange); }} .kv-val.red {{ color:var(--red); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:var(--bg3); color:var(--text); padding:8px 14px; border:1px solid var(--border); }}
td {{ padding:7px 14px; border:1px solid var(--border); color:var(--text2); font-family:Consolas; }}
tr:nth-child(even) td {{ background:var(--bg3); }}
.img-row {{ display:grid; grid-template-columns:1fr; gap:16px; margin:16px 0; }}
.img-row.two {{ grid-template-columns:1fr 1fr; }}
img {{ width:100%; border-radius:8px; border:1px solid var(--border); }}
.tag {{ display:inline-block; border-radius:6px; padding:2px 10px; font-size:12px;
        font-weight:700; margin:2px 4px 2px 0; }}
.tag.blue {{ background:rgba(137,180,250,.18); color:var(--blue); border:1px solid var(--blue); }}
.tag.orange {{ background:rgba(250,179,135,.18); color:var(--orange); border:1px solid var(--orange); }}
.tag.green {{ background:rgba(166,227,161,.18); color:var(--green); border:1px solid var(--green); }}
.note {{ background:rgba(137,180,250,.08); border-left:4px solid var(--blue);
         border-radius:0 8px 8px 0; padding:12px 18px; margin:14px 0; font-size:14px; }}
.warn {{ background:rgba(249,226,175,.08); border-left:4px solid var(--yellow);
         border-radius:0 8px 8px 0; padding:12px 18px; margin:14px 0; }}
code {{ background:var(--bg3); color:var(--green); border-radius:4px; padding:1px 7px; font-family:Consolas; font-size:13px; }}
</style>
</head>
<body><div class="wrap">

<h1>New Dataset Analysis — Metal &amp; Hand (삼겹살)</h1>
<p class="meta">생성일: 2026-05-13 &nbsp;|&nbsp; 데이터: nn_decoupling/data/metal/ &nbsp;|&nbsp;
센서 초기 길이: {SENSOR_L0_MM:.0f} mm &nbsp;|&nbsp; Strain 범위: 0~36 mm (30%)</p>

<!-- ═══════════════════════════════════════════ 데이터셋 개요 ═════ -->
<h2>1. 데이터셋 개요</h2>
<div class="card">
  <h3>실험 설계</h3>
  <table>
    <tr><th>항목</th><th>Metal (도체)</th><th>Hand/삼겹살 (유전체)</th></tr>
    <tr><td>근접 범위</td><td>52 mm → 2 mm (Z: 0→−50 mm)</td><td>30 mm → 0 mm (Z: 0→−30 mm)</td></tr>
    <tr><td>변형률 범위</td><td>0 → 36 mm (30%), 2 mm 간격, 19 레벨</td><td>0 → 36 mm (30%), 2 mm 간격, 19 레벨</td></tr>
    <tr><td>프로토콜 P1</td><td>변형률 고정 → Z 연속 스윕</td><td>변형률 고정 → Z 연속 스윕</td></tr>
    <tr><td>프로토콜 P2</td><td>Z 고정 (2 mm 간격) → 변형률 스윕</td><td>Z 고정 (2 mm 간격) → 변형률 스윕</td></tr>
    <tr><td>Steady-state 행 수</td><td>{stats['metal_rows']:,}</td><td>{stats['hand_rows']:,}</td></tr>
  </table>
  <div class="kv-grid" style="margin-top:16px;">
    <div class="kv"><div class="kv-label">L₀ (베이스라인 LDC)</div>
      <div class="kv-val">{stats['L0']:.0f}</div></div>
    <div class="kv"><div class="kv-label">R₀ (베이스라인 ADC)</div>
      <div class="kv-val green">{stats['R0']:.0f}</div></div>
    <div class="kv"><div class="kv-label">Metal ΔL 범위</div>
      <div class="kv-val yellow">{stats['metal_dL_min']:.2f}% ~ {stats['metal_dL_max']:.2f}%</div></div>
    <div class="kv"><div class="kv-label">Metal ΔR 범위</div>
      <div class="kv-val green">{stats['metal_dR_min']:.2f}% ~ {stats['metal_dR_max']:.2f}%</div></div>
    <div class="kv"><div class="kv-label">Hand ΔL 범위</div>
      <div class="kv-val orange">{stats['hand_dL_min']:.2f}% ~ {stats['hand_dL_max']:.2f}%</div></div>
    <div class="kv"><div class="kv-label">Hand ΔR 범위</div>
      <div class="kv-val orange">{stats['hand_dR_min']:.2f}% ~ {stats['hand_dR_max']:.2f}%</div></div>
  </div>
  <div class="note">
    <b>베이스라인 정의:</b> Metal P1, strain=0 mm, proximity≈50 mm 조건의 steady-state 샘플 중앙값.<br>
    <code>ΔL/L₀ = (L₀/f)² − 1</code> &nbsp;(f = ldc_raw, LDC1614 공진 주파수 카운터)<br>
    <code>ΔR/R₀ = (r_raw − R₀) / R₀</code>
  </div>
</div>

<!-- ═══════════════════════════════════════════ Metal ═════ -->
<h2>2. Metal (도체) — Strain별 Proximity 곡선</h2>
<div class="card">
  <div class="img-row">
    <img src="{FIG['metal_lines.png']}" alt="Metal lines">
  </div>
  <h3>관찰 결과</h3>
  <p>
    <span class="tag blue">ΔL/L₀ (Metal)</span>
    각 선이 하나의 strain 레벨. strain=0에서 근접 시 ΔL이 <b>감소</b> (와전류, β₂ &lt; 0).
    strain이 커질수록 곡선 전체가 위로 이동하며, 고 strain에서는 근접해도 ΔL이 양수로 유지된다.
  </p>
  <p>
    <span class="tag green">ΔR/R₀ (Metal)</span>
    proximity에 거의 무관하고 strain에만 비례 증가 → 각 선이 거의 수평 (ΔR ≈ f(strain only)).
  </p>
  <p style="font-family:Consolas; font-size:13px; color:var(--text2);">
    β₁ ≈ <b>{beta1_est:.4f} %/mm</b> (ΔL vs strain) &nbsp;|&nbsp;
    α₁ ≈ <b>{alpha1_est:.4f} %/mm</b> (ΔR vs strain)
  </p>
</div>

<h2>3. Metal (도체) — 2D Grid Heatmap</h2>
<div class="card">
  <div class="img-row">
    <img src="{FIG['metal_grid.png']}" alt="Metal grid">
  </div>
</div>

<!-- ═══════════════════════════════════════════ Hand ═════ -->
<h2>4. Hand/삼겹살 (유전체) — Strain별 Proximity 곡선</h2>
<div class="card">
  <div class="img-row">
    <img src="{FIG['hand_lines.png']}" alt="Hand lines">
  </div>
  <h3>관찰 결과</h3>
  <p>
    <span class="tag orange">ΔL/L₀ (Hand)</span>
    전 proximity 구간에서 ΔL &gt; 0 (기생 정전용량). proximity 의존성은 metal보다 약하고
    strain 의존성이 지배적이다. 근접 범위가 0~30 mm로 좁다.
  </p>
  <p>
    <span class="tag orange">ΔR/R₀ (Hand)</span>
    Metal과 유사하게 strain 지배적. proximity 효과 미미.
  </p>
  <div class="note">
    <b>디커플링 핵심:</b> Metal은 ΔL 곡선이 proximity에 따라 내려가고 (β₂ &lt; 0),
    Hand는 거의 평탄하거나 약하게 올라간다 (β₂ &gt; 0). sign(ΔL_corrected)로 물체 구별 가능.
  </div>
  <div class="warn">
    <b>주의:</b> Hand proximity 신호가 매우 약함 (8~21 mm 구간, 0.8%/13mm).
    더 넓은 proximity 범위 재실험 또는 주파수 최적화 검토 필요.
  </div>
</div>

<h2>5. Hand/삼겹살 (유전체) — 2D Grid Heatmap</h2>
<div class="card">
  <div class="img-row">
    <img src="{FIG['hand_grid.png']}" alt="Hand grid">
  </div>
</div>

<h2>6. ΔL & ΔR Overlapped Contour — Metal vs Hand</h2>
<div class="card">
  <p>
    ΔL/L₀ (filled contour) 위에 ΔR/R₀ (선 등고선)를 겹쳐 그린 그림.
    두 신호의 등고선이 <b>서로 다른 방향</b>으로 교차할수록 디커플링이 용이하다.
  </p>
  <div class="img-row">
    <img src="{FIG['overlap_contour.png']}" alt="Overlapped contour">
  </div>
  <div class="note">
    <b>Metal:</b> ΔL 등고선은 proximity 방향으로 급변 (근접할수록 음수), ΔR 등고선은 strain 방향으로 평행 → 두 신호가 서로 다른 변수를 인코딩 ✓<br>
    <b>Hand:</b> ΔL과 ΔR 등고선이 유사한 방향(strain 지배) → 근접도 분리가 상대적으로 어려움
  </div>
</div>

<!-- ═══════════════════════════════════════════ 물리 모델 해석 ═════ -->
<h2>7. 물리 모델 해석 및 디커플링 전략</h2>
<div class="card">
  <h3>6-1. 경험적 피팅 모델 재확인</h3>
  <table>
    <tr><th>신호</th><th>경험 모델</th><th>주요 인자</th><th>물체 의존성</th></tr>
    <tr>
      <td>ΔR/R₀</td>
      <td><code>α₁ε + α₂ε²</code></td>
      <td>변형률 ε 지배</td>
      <td>거의 없음 (Metal ≈ Hand)</td>
    </tr>
    <tr>
      <td>ΔL/L₀ (Metal)</td>
      <td><code>β₁ε + β₂/(d+d₀)ᵏ + β₃ε·f(d)</code>, β₂ &lt; 0</td>
      <td>근접도 + 변형률</td>
      <td>β₂ &lt; 0 (와전류 감쇠)</td>
    </tr>
    <tr>
      <td>ΔL/L₀ (Hand)</td>
      <td>동일 형태, β₂ &gt; 0</td>
      <td>근접도 + 변형률</td>
      <td>β₂ &gt; 0 (기생 정전용량)</td>
    </tr>
  </table>

  <h3 style="margin-top:18px;">6-2. 2단계 PINN 디커플링 전략 (업데이트)</h3>
  <div class="note">
    <b>Stage 1:</b> ΔR → ε̂ &nbsp; (물체 독립, 단일 모델)<br>
    <b>Classifier:</b> sign(ΔL − k·ΔR) → {'{Metal | Hand | None}'}<br>
    <b>Stage 2-M:</b> (ΔL, ε̂) → d̂ &nbsp; (Metal 전용 모델, β₂ &lt; 0)<br>
    <b>Stage 2-H:</b> (ΔL × scale, ε̂) → d̂ &nbsp; (Hand 전용 모델, β₂ &gt; 0)
  </div>
  <p>
    Metal과 Hand의 β₂ 부호가 반대이므로, <b>단일 모델로 혼합 학습 시 물리 손실 기울기가 충돌</b>한다.
    따라서 분류기로 물체를 먼저 판별한 후 각각의 전용 모델을 적용하는 것이 안정적이다.
  </p>

  <h3 style="margin-top:18px;">6-3. 새 데이터셋 vs 이전 데이터셋 차이</h3>
  <table>
    <tr><th></th><th>이전 (0332_DecouplingTest)</th><th>신규 (sync_acquisition)</th></tr>
    <tr><td>취득 방식</td><td>비동기, 피크 추출 후 보간</td><td>PC 동기화, is_steady 태깅</td></tr>
    <tr><td>가감속 처리</td><td>수동 피크 기반 자르기</td><td>firmware accel 기반 자동 제외</td></tr>
    <tr><td>물체 종류</td><td>금속만</td><td>금속 + 삼겹살(유전체)</td></tr>
    <tr><td>Strain 프로토콜</td><td>P1만 (Discrete ε, Sweep d)</td><td>P1 + P2 (교차 커버리지)</td></tr>
    <tr><td>신호</td><td>IIR 필터 적용값</td><td>Raw ADC 값</td></tr>
  </table>
</div>

<!-- ═══════════════════════════════════════════ 다음 단계 ═════ -->
<h2>8. 다음 단계</h2>
<div class="card">
  <ul style="color:var(--text2); line-height:2.2;">
    <li><span class="tag blue">학습</span> Metal 전용 PINN (Stage1: ΔR→ε, Stage2-M: (ΔL,ε)→d)</li>
    <li><span class="tag orange">학습</span> Hand 전용 PINN (Stage2-H: β₂ &gt; 0 피팅)</li>
    <li><span class="tag green">분류기</span> sign(ΔL_corrected) 기반 물체 판별 임계값 데이터 기반 최적화</li>
    <li><span class="tag blue">검증</span> P2 데이터(고정 근접, 연속 변형률)로 Cross-protocol 일반화 확인</li>
    <li><span class="tag green">임베딩</span> Metal 모델 → ONNX → STM32 X-CUBE-AI INT8</li>
  </ul>
</div>

<p class="meta" style="margin-top:36px; text-align:center;">
  Generated by data_analysis.py &nbsp;|&nbsp; BiRC Lab, Korea University
</p>
</div></body></html>
"""

report_path = os.path.join(HERE, 'report_new.html')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"  → {report_path}")
print("\n[완료]")
print(f"  figures/: 3d_dL.png, 3d_dR.png, heatmap_dL.png, heatmap_dR.png")
print(f"  report_new.html")
