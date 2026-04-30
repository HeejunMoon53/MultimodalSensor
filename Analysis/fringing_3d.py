"""
Square vs Hexagonal Spiral — Neumann Inductance, Conformal Fringe Capacitance,
                              3D Biot-Savart Fringing Field
=============================================================================
수식 근거:
  L  — Neumann 부분 인덕턴스 (Rosa formula + 내부 인덕턴스)
  C  — Schwarz-Christoffel 등각 사상 + 제1종 타원 적분
  Bz — Biot-Savart 적분 (planar coil, I=1A)

단위 정책: 좌표·길이는 mm, 물리 수식 내부는 SI(m) 로 변환해서 계산.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.special import ellipk
from mpl_toolkits.mplot3d import Axes3D   # noqa: F401

matplotlib.rcParams['font.family'] = 'DejaVu Sans'

# ── 공통 파라미터 ─────────────────────────────────────────────────────
AREA  = 100.0  # mm² (동일 면적 비교)
TURNS = 5
W     = 0.5    # 선폭    [mm]
S     = 0.2    # 간격    [mm]
T     = 0.2    # 두께    [mm]  EGaIn DIW 기준
EPS_R = 3.0    # 기판 유전율 (PDMS / 실리콘)
RHO   = 29.4e-8  # EGaIn 비저항 [Ω·m]
FREQ  = 5.0    # MHz  (LDC1614)

# ─────────────────────────────────────────────────────────────────────
# [1] 형상 생성
# ─────────────────────────────────────────────────────────────────────
def generate_polygon_spiral(sides, turns, area_mm2, w_mm, s_mm):
    """
    N각형 Archimedean 나선 생성 (동일 apothem 피치 = w+s).

    외접원 반지름 R_start 는 면적 조건으로 역산:
      Square  (N=4): area = 2 R²         → R = √(area/2)
      Hexagon (N=6): area = (3√3/2) R²   → R = √(area / 1.5√3)

    인접 턴 간 apothem 간격 = pitch
      → 외접원 반지름 감소량/턴 = pitch / cos(π/N)
    """
    pitch = w_mm + s_mm
    if sides == 4:
        R_start = np.sqrt(area_mm2 / 2.0)
    else:
        R_start = np.sqrt(area_mm2 / (1.5 * np.sqrt(3)))

    dR     = pitch / np.cos(np.pi / sides)          # 턴당 R 감소량
    theta0 = np.pi / sides if sides == 4 else 0.0   # 사각형은 45° 회전

    verts = []
    for i in range(turns * sides + 1):
        theta = i * (2 * np.pi / sides) + theta0
        R     = R_start - (i / sides) * dR
        if R < pitch:
            break
        verts.append([R * np.cos(theta), R * np.sin(theta)])
    return np.array(verts)


def discretize(verts, dl_max=0.1):
    """최대 세그먼트 길이가 dl_max [mm] 이하가 되도록 세분화."""
    pts = [verts[0]]
    for i in range(len(verts) - 1):
        p1, p2 = verts[i], verts[i + 1]
        n = max(1, int(np.ceil(np.linalg.norm(p2 - p1) / dl_max)))
        for j in range(1, n + 1):
            pts.append(p1 + (p2 - p1) * (j / n))
    return np.array(pts)


# ─────────────────────────────────────────────────────────────────────
# [2] Neumann 부분 인덕턴스 (단위: nH)
# ─────────────────────────────────────────────────────────────────────
def calc_L_neumann(verts_mm, w_mm, t_mm=T):
    """
    Neumann 공식 기반 부분 인덕턴스 수치 적분.

    자기 인덕턴스 (Rosa 공식, 직사각형 단면 도선):
        L_self_i = (μ₀ lᵢ)/(2π) × [ln(2lᵢ/r_eff) − 1 + μᵣ/4]
        r_eff    = 0.2235 (w + t)        Ruehli (1972) — 직사각형→등가 원형 반지름
        μᵣ/4 = 0.25                      내부 인덕턴스 (비자성 재료)

    상호 인덕턴스 (Neumann 중점 근사):
        M_ij = (μ₀/4π) × (dlᵢ·dlⱼ) / |rᵢ−rⱼ|     i ≠ j
        |rᵢ−rⱼ| < r_eff 인 쌍은 0으로 처리 (특이점 방지)

    주의:
      - 좌표 verts_mm [mm] → 내부에서 [m] 변환 후 계산
      - 세그먼트가 매우 짧을 때 ln 이 음수가 되는 현상 방지:
          ln(max(2l/r_eff, e)) ≥ 1  보장
    """
    mu0   = 4e-7 * np.pi
    r_eff = 0.2235 * (w_mm + t_mm) * 1e-3       # [m]

    segs = np.diff(verts_mm, axis=0) * 1e-3      # dl 벡터 [m]
    lens = np.linalg.norm(segs, axis=1)           # 세그먼트 길이 [m]
    mids = (verts_mm[:-1] + verts_mm[1:]) * 0.5e-3  # 중점 [m]

    # 자기 인덕턴스 — ln 클리핑으로 음수 방지
    L_self = (mu0 / (2 * np.pi)) * lens * (
        np.log(np.maximum(2 * lens / r_eff, np.e)) - 1.0 + 0.25
    )

    # 상호 인덕턴스 행렬
    dot_ij = segs @ segs.T                              # dlᵢ·dlⱼ  [m²]
    diff   = mids[:, None, :] - mids[None, :, :]       # rᵢ−rⱼ    [m]
    dist   = np.linalg.norm(diff, axis=2)               # |rᵢ−rⱼ|  [m]

    np.fill_diagonal(dist, np.inf)                      # 대각(자기) 제외
    M_mat = (mu0 / (4 * np.pi)) * dot_ij / dist        # [H]
    M_mat[dist < r_eff] = 0.0                           # 도체 내부 근접 쌍 제거

    return (L_self.sum() + M_mat.sum()) * 1e9            # [nH]


# ─────────────────────────────────────────────────────────────────────
# [3] Schwarz-Christoffel 등각 사상 — 터널 간 Fringe 커패시턴스 (단위: pF)
# ─────────────────────────────────────────────────────────────────────
def calc_C_fringe(verts_mm, sides, w_mm, s_mm, eps_r=EPS_R):
    """
    인접 턴 사이 fringe 커패시턴스 수치 계산.

    기하학: 폭 w, 간격 s 인 두 평행 코플라너 스트립 on 기판

    Schwarz-Christoffel 변환 모듈러스:
        k  = s / (s + 2w)         — 내측 간격 / 전체 외측 폭 비율
        k' = √(1 − k²)

    단위 길이당 커패시턴스 (기판 아래 + 공기 위, 두 반공간 기여 합산):
        C/L = ε₀ (1 + εᵣ) K(k') / K(k)

        *구 버전 C/L = ε₀ εeff K(k')/K(k) 는 2× 과소평가 (반공간 1개만 포함)

    scipy.special.ellipk(m) 는 m = k² 를 인자로 받음:
        K(k)  = ellipk(k²)
        K(k') = ellipk(k'²) = ellipk(1 − k²)
    """
    eps0    = 8.854e-12
    k       = s_mm / (s_mm + 2 * w_mm)
    K_k     = ellipk(k ** 2)
    K_kp    = ellipk(1.0 - k ** 2)          # K(k') — 올바른 보완 모듈러스 인자

    C_per_m = eps0 * (1 + eps_r) * (K_kp / K_k)   # [F/m]

    # 상호 커패시턴스에 기여하는 평행 도선 총 길이
    # 가장 바깥쪽 1턴(이웃 없음)은 제외 → segments[sides:] 합산
    seg_lens = np.linalg.norm(np.diff(verts_mm, axis=0), axis=1)  # [mm]
    L_par    = seg_lens[sides:].sum() * 1e-3                        # [m]

    return C_per_m * L_par * 1e12    # [pF]


# ─────────────────────────────────────────────────────────────────────
# [4] Biot-Savart Bz 3D 장 계산
# ─────────────────────────────────────────────────────────────────────
def bz_field(Xm_mm, Ym_mm, Zm_mm, xc_mm, yc_mm):
    """
    평면 전류 필라멘트(z=0)에서 발생하는 Bz 성분 [μT] (I = 1 A).

    Biot-Savart 중점 근사 (세그먼트 단위):
        dBz = (μ₀/4π) × (dlₓ Δy − dly Δx) / |r|³

    단위 정책:
        입력은 모두 mm → 내부에서 1e-3 을 곱해 m 으로 변환
        출력: T × 1e6 = μT
    """
    mu0 = 4e-7 * np.pi
    # mm → m
    Xm = Xm_mm * 1e-3;  Ym = Ym_mm * 1e-3;  Zm = Zm_mm * 1e-3
    xc = xc_mm * 1e-3;  yc = yc_mm * 1e-3
    Bz = np.zeros_like(Xm_mm, dtype=float)
    for i in range(len(xc) - 1):
        dx = xc[i+1] - xc[i];  dy = yc[i+1] - yc[i]
        mx = 0.5 * (xc[i] + xc[i+1]);  my = 0.5 * (yc[i] + yc[i+1])
        rx = Xm - mx;  ry = Ym - my
        r3 = (rx**2 + ry**2 + Zm**2)**1.5 + 1e-30
        Bz += (mu0 / (4 * np.pi)) * (dx * ry - dy * rx) / r3
    return Bz * 1e6    # [μT]


# ─────────────────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────────────────
print("Generating spirals ...")
v_sq = generate_polygon_spiral(4, TURNS, AREA, W, S)
v_hx = generate_polygon_spiral(6, TURNS, AREA, W, S)
v_sq_mesh = discretize(v_sq)
v_hx_mesh = discretize(v_hx)
print(f"  Square  : {len(v_sq)-1} segs → {len(v_sq_mesh)-1} discretized")
print(f"  Hexagon : {len(v_hx)-1} segs → {len(v_hx_mesh)-1} discretized")

print("\nComputing L (Neumann integral) ...")
L_sq = calc_L_neumann(v_sq_mesh, W)
L_hx = calc_L_neumann(v_hx_mesh, W)

print("Computing C (conformal mapping) ...")
C_sq = calc_C_fringe(v_sq, 4, W, S)
C_hx = calc_C_fringe(v_hx, 6, W, S)

def wire_metrics(mesh_mm, L_nH, w_mm=W, t_mm=T, f_MHz=FREQ):
    """DC 저항, 표피효과 보정 저항, Q 인자 계산."""
    lens_m = np.linalg.norm(np.diff(mesh_mm, axis=0), axis=1) * 1e-3
    R_dc   = RHO * lens_m.sum() / (w_mm * t_mm * 1e-6)
    delta  = np.sqrt(2 * RHO / (2*np.pi*f_MHz*1e6 * 4e-7*np.pi))  # 표피 깊이 [m]
    ratio  = min(w_mm, t_mm) * 1e-3 / (2 * delta)
    R_eff  = R_dc * max(1.0, np.sqrt(1 + ratio**2))
    Q      = 2*np.pi*f_MHz*1e6 * L_nH*1e-9 / R_eff
    return R_dc, R_eff, Q

R_sq, Re_sq, Q_sq = wire_metrics(v_sq_mesh, L_sq)
R_hx, Re_hx, Q_hx = wire_metrics(v_hx_mesh, L_hx)

print("\n" + "=" * 56)
print(f"  {'':28} {'Square':>12} {'Hexagon':>12}")
print("=" * 56)
print(f"  {'Area (mm²)':28} {AREA:>12.0f} {AREA:>12.0f}")
print(f"  {'L  (nH, Neumann)':28} {L_sq:>12.1f} {L_hx:>12.1f}")
print(f"  {'C  (pF, conformal)':28} {C_sq:>12.2f} {C_hx:>12.2f}")
print(f"  {'R_dc  (Ohm)':28} {R_sq:>12.2f} {R_hx:>12.2f}")
print(f"  {'R_eff (Ohm, 5MHz skin)':28} {Re_sq:>12.2f} {Re_hx:>12.2f}")
print(f"  {'Q  (5MHz)':28} {Q_sq:>12.1f} {Q_hx:>12.1f}")
print("=" * 56)
print(f"  L(sq)/L(hx) - 1 = {(L_sq/L_hx-1)*100:+.1f}%     "
      f"C(sq)/C(hx) - 1 = {(C_sq/C_hx-1)*100:+.1f}%")

# ─────────────────────────────────────────────────────────────────────
# Bz 필드 계산 (원본 좌표 — 빠름)
# ─────────────────────────────────────────────────────────────────────
print("\nBiot-Savart Bz field ...")
NG   = 50
XLIM = 10.5
xv   = np.linspace(-XLIM, XLIM, NG)
zv   = np.linspace(0.3, 14.0, 42)

Xm2, Ym2 = np.meshgrid(xv, xv)                        # xy 평면 @ z=2mm
Xcs, Zcs = np.meshgrid(xv, zv)                         # xz 단면
Ycs       = np.zeros_like(Xcs)

Bz_sq_2  = bz_field(Xm2, Ym2, 2.0,  v_sq[:,0], v_sq[:,1])
Bz_hx_2  = bz_field(Xm2, Ym2, 2.0,  v_hx[:,0], v_hx[:,1])
Bz_sq_cs = bz_field(Xcs, Ycs, Zcs,  v_sq[:,0], v_sq[:,1])
Bz_hx_cs = bz_field(Xcs, Ycs, Zcs,  v_hx[:,0], v_hx[:,1])

# 중심축 감쇠 (x=0, y=0)
Bz_sq_ax = np.array([bz_field(np.array([[0.]]), np.array([[0.]]), z,
                                v_sq[:,0], v_sq[:,1])[0,0] for z in zv])
Bz_hx_ax = np.array([bz_field(np.array([[0.]]), np.array([[0.]]), z,
                                v_hx[:,0], v_hx[:,1])[0,0] for z in zv])

# ─────────────────────────────────────────────────────────────────────
# Figure 1: 형상 + L/C/Q 비교
# ─────────────────────────────────────────────────────────────────────
fig1, axs1 = plt.subplots(1, 3, figsize=(14, 5))
fig1.suptitle(
    f'Square vs Hexagonal Spiral  (Area={AREA}mm², turns={TURNS}, '
    f'w={W}mm, s={S}mm, EGaIn)',
    fontsize=11, fontweight='bold')

for ax, v, label, color in zip(
        axs1[:2],
        [v_sq, v_hx],
        ['Square (4-gon)', 'Hexagon (6-gon)'],
        ['tomato', 'steelblue']):
    ax.plot(v[:,0], v[:,1], '.-', color=color, ms=3, lw=1.2)
    ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
    ax.set_title(label, fontsize=10)
    ax.set_xlabel('x (mm)'); ax.set_ylabel('y (mm)')

ax = axs1[2]
names  = ['Square', 'Hexagon']
colors = ['tomato', 'steelblue']
vals   = {'L (nH)': [L_sq, L_hx], 'C (pF)': [C_sq, C_hx], 'Q': [Q_sq, Q_hx]}
x      = np.arange(len(names))
width  = 0.25
for ki, (k, v_list) in enumerate(vals.items()):
    scale = 1.0
    bars  = ax.bar(x + (ki - 1)*width, [val/max(v_list)*100 for val in v_list],
                   width, label=k, color=[colors[j] for j in range(len(names))],
                   alpha=0.6 + ki*0.1, edgecolor='k', lw=0.6)
ax.set_xticks(x); ax.set_xticklabels(names)
ax.set_ylabel('Relative value (%, max=100)')
ax.set_title('Normalised L / C / Q', fontsize=10)
ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

info = (f'Square : L={L_sq:.0f}nH  C={C_sq:.1f}pF  Q={Q_sq:.1f}\n'
        f'Hexagon: L={L_hx:.0f}nH  C={C_hx:.1f}pF  Q={Q_hx:.1f}')
ax.text(0.02, 0.02, info, transform=ax.transAxes,
        fontsize=8, va='bottom', family='monospace',
        bbox=dict(boxstyle='round', fc='lightyellow', alpha=0.8))

plt.tight_layout()
plt.savefig('spiral_LC_compare.png', dpi=150, bbox_inches='tight')
plt.close()

# ─────────────────────────────────────────────────────────────────────
# Figure 2: 3D Bz Fringing Field (3×2 레이아웃)
# ─────────────────────────────────────────────────────────────────────
vmax_2  = np.percentile(np.abs(np.concatenate(
               [Bz_sq_2.ravel(), Bz_hx_2.ravel()])), 97)
vmax_cs = np.percentile(np.abs(np.concatenate(
               [Bz_sq_cs.ravel(), Bz_hx_cs.ravel()])), 97)
RELIEF  = 2.0 / (vmax_2 + 1e-10)    # 1μT → 2mm 부양 (동일 스케일)
norm2   = matplotlib.colors.Normalize(-vmax_2, vmax_2)
cmap    = plt.cm.RdBu_r

fig2 = plt.figure(figsize=(14, 13))
fig2.suptitle(
    'Magnetic Fringing Field — 3D Relief Surface, xz Cross-section, Axis Decay\n'
    f'(EGaIn coil, {FREQ}MHz, I=1A,  same colour/relief scale for both)',
    fontsize=11, fontweight='bold')

coils = [
    (v_sq, Bz_sq_2, Bz_sq_cs, Bz_sq_ax, 'Square Spiral',  'tomato'),
    (v_hx, Bz_hx_2, Bz_hx_cs, Bz_hx_ax, 'Hexagon Spiral', 'steelblue'),
]

for col, (vc, Bz2, Bzcs, Bz_ax, label, color) in enumerate(coils):

    # ── Row 0: 3D relief surface ──────────────────────────────────
    ax3d = fig2.add_subplot(3, 2, col + 1, projection='3d')
    # 코일 와이어 (z=0 평면)
    ax3d.plot(vc[:,0], vc[:,1], np.zeros(len(vc)),
              '-', color=color, lw=0.9, alpha=0.7)
    # Bz 부양 서피스 (높이 ∝ Bz, 색 ∝ Bz)
    Z_surf = 2.0 + Bz2 * RELIEF
    ax3d.plot_surface(Xm2, Ym2, Z_surf,
                      facecolors=cmap(norm2(Bz2)),
                      linewidth=0, antialiased=True, alpha=0.88)
    # 기준 평면 (z=2mm, 반투명)
    ax3d.plot_surface(Xm2, Ym2, np.full_like(Xm2, 2.0),
                      color='lightgray', alpha=0.12, linewidth=0)
    peak_uT = float(np.percentile(np.abs(Bz2), 99))
    ax3d.set_title(f'{label}\nBz at z=2mm  peak = {peak_uT:.3f} uT',
                   fontsize=9)
    ax3d.set_xlabel('x (mm)', fontsize=7, labelpad=1)
    ax3d.set_ylabel('y (mm)', fontsize=7, labelpad=1)
    ax3d.set_zlabel('z (mm)', fontsize=7, labelpad=1)
    ax3d.set_zlim(-0.5, 5.0)
    ax3d.tick_params(labelsize=6)
    ax3d.view_init(elev=28, azim=-55)

    # ── Row 1: xz 단면 (fringe 프로파일) ──────────────────────────
    ax2d = fig2.add_subplot(3, 2, col + 3)
    im = ax2d.pcolormesh(Xcs, Zcs, Bzcs,
                         cmap='RdBu_r', vmin=-vmax_cs, vmax=vmax_cs,
                         shading='auto')
    ax2d.axhline(2.0, color='gold', lw=1.5, ls='--', label='z=2mm (sensing)')
    ax2d.set_xlabel('x (mm)', fontsize=8)
    ax2d.set_ylabel('Height z (mm)', fontsize=8)
    ax2d.set_title(f'{label} — Fringe profile  Bz(x, y=0, z)', fontsize=9)
    ax2d.legend(fontsize=7, loc='upper right')
    ax2d.tick_params(labelsize=7)
    fig2.colorbar(im, ax=ax2d, label='Bz (uT)', fraction=0.046, pad=0.04)

    # ── Row 2: 중심축 감쇠 + 1/z³ 참조선 ─────────────────────────
    ax_ax = fig2.add_subplot(3, 2, col + 5)
    ax_ax.plot(zv, np.abs(Bz_ax), color=color, lw=2.5, label='|Bz(0,0,z)|')
    ax_ax.axvline(2.0, color='red', ls='--', lw=1.5, label='z=2mm')

    # 1/z³ 감쇠 참조 (z=1mm 기준)
    iz1 = np.argmin(np.abs(zv - 1.0))
    B1  = abs(Bz_ax[iz1]) if abs(Bz_ax[iz1]) > 0 else 1e-6
    ax_ax.plot(zv, B1 * (1.0 / zv)**3, 'k--', lw=1, alpha=0.45, label='1/z³ ref')

    # 반값 높이
    peak = np.abs(Bz_ax).max()
    half_idx = np.where(np.abs(Bz_ax) < peak / 2)[0]
    if len(half_idx):
        z_half = zv[half_idx[0]]
        ax_ax.axvline(z_half, color='orange', ls=':', lw=1.5,
                      label=f'z_half = {z_half:.1f} mm')

    ax_ax.set_xlabel('Height z (mm)', fontsize=8)
    ax_ax.set_ylabel('|Bz| at (0,0,z)  [uT]', fontsize=8)
    ax_ax.set_title(f'{label} — Field decay above center', fontsize=9)
    ax_ax.legend(fontsize=7)
    ax_ax.grid(True, alpha=0.3)
    ax_ax.tick_params(labelsize=7)

# 3D 서피스용 공유 컬러바
sm = plt.cm.ScalarMappable(cmap='RdBu_r', norm=norm2)
sm.set_array([])
fig2.colorbar(sm,
              ax=[fig2.axes[0], fig2.axes[1]],
              label='Bz at z=2mm (uT)',
              shrink=0.7, pad=0.06, location='right')

plt.tight_layout()
plt.savefig('fringing_3d_field.png', dpi=150, bbox_inches='tight')
plt.close()

print("\n[Saved] spiral_LC_compare.png")
print("[Saved] fringing_3d_field.png")
print("Done.")
