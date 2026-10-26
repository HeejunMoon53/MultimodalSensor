"""60A TPU 벨로즈 손가락 파라미터 CAD (Meitani & Nisar, IEEE Access 2025, Table 3 기반).

좌표: 루트 안쪽면 = 원점, 손가락은 −Z로 내려가며 +X(그리퍼 중심) 쪽으로 precurve.
곡률 중심 C = (ρ, 0), 안쪽(오목)면 반경 ρ = arc_len / precurve.
반경 방향 층: [ρ, ρ+t_b] 바닥층(strain-limiting, 센서면) · [ρ+t_b, ρ+t_b+ch] 공기 채널 · 벨로즈 8개.
논문에 없는 값(바닥층 3 mm, 벨로즈 높이 14 mm, 채널 4 mm, 센서 홈)은 Fig.3 비율 추정 — 파라미터로 노출.
"""
import math
from dataclasses import dataclass

from build123d import Axis, Box, Cylinder, Polygon, Pos, Rot, extrude

N_ARC = 48


@dataclass
class FingerCAD:
    arc_len: float = 105.0       # l (안쪽면 호 길이) [mm]
    depth: float = 32.0          # h (손가락 폭)
    n_bellows: int = 8
    precurve_deg: float = 41.0
    backbone_t: float = 3.0      # 바닥층 두께 (추정)
    channel_h: float = 4.0       # 공통 공기 채널 높이 (추정)
    bellow_h: float = 14.0       # 바닥층 바깥 기준 벨로즈 높이 (추정)
    bellow_t: float = 6.43       # l_b: 벨로즈 하나의 두께
    wall: float = 2.5
    root_len: float = 8.0        # w_c: 루트 블록 높이
    inlet_d: float = 4.0
    inlet_z: float = 3.0         # 입구 구멍이 베이스(z=0) 아래로 들어가는 깊이
    groove_w: float = 22.0       # 센서 홈 폭 (y)
    groove_d: float = 0.5        # 센서 홈 깊이
    groove_n: int = 3            # 원위 벨로즈 몇 개 구간에 홈

    def rho(self):
        return self.arc_len / math.radians(self.precurve_deg)

    def theta(self):
        return math.radians(self.precurve_deg)


def _sector(p, r0, r1, a0, a1):
    """곡률 중심 기준 반경 r0..r1, 각 a0..a1(루트=0, 끝단=θ)의 고리 부채꼴 → XY 평면 다각형(Y가 실제 Z)."""
    rho = p.rho()
    arc = [a0 + (a1 - a0) * k / N_ARC for k in range(N_ARC + 1)]
    pt = lambda r, a: (rho - (rho + r) * math.cos(a), -(rho + r) * math.sin(a))
    pts = [pt(r1, a) for a in arc] + [pt(r0, a) for a in reversed(arc)]
    return Polygon(*pts, align=None)


def _solidify(face, depth):
    """XY 프로파일을 Z로 대칭 압출 후 X축 +90° 회전 → 프로파일 Y가 실제 Z, 압출 방향이 Y."""
    return Rot(90, 0, 0) * extrude(face, amount=depth / 2, both=True)


def make_finger(p=FingerCAD(), hollow=True):
    th, tb, w = p.theta(), p.backbone_t, p.wall
    band_out = tb + p.channel_h + w
    pitch = th / p.n_bellows
    r_mid = p.rho() + tb + p.bellow_h / 2
    half_t = (p.bellow_t / 2) / r_mid
    body = _solidify(_sector(p, 0.0, band_out, 0, th), p.depth)   # 바닥층+채널+덮개 (r: 안쪽면 기준 오프셋)
    for i in range(p.n_bellows):
        c = (i + 0.5) * pitch
        body += _solidify(_sector(p, band_out - 0.5, tb + p.bellow_h, c - half_t, c + half_t), p.depth)
    body += Pos(-band_out / 2, 0, p.root_len / 2) * Box(band_out, p.depth, p.root_len)   # 루트 블록 (바깥=−X)
    if not hollow:
        return body
    inner_depth = p.depth - 2 * w
    a_end = th - w / (p.rho() + tb)
    cavity = _solidify(_sector(p, tb, tb + p.channel_h, 0.0, a_end), inner_depth)
    cavity_half = max(half_t - w / r_mid, 0.4 / r_mid)
    for i in range(p.n_bellows):
        c = (i + 0.5) * pitch
        cavity += _solidify(_sector(p, tb + 0.5, tb + p.bellow_h - w, c - cavity_half, c + cavity_half), inner_depth)
    inlet = Pos(-(tb + p.channel_h / 2), 0, (p.root_len - p.inlet_z) / 2) * Cylinder(
        p.inlet_d / 2, p.root_len + p.inlet_z)
    body -= cavity + inlet
    g0 = th * (1 - p.groove_n / p.n_bellows)
    groove = _solidify(_sector(p, -1.0, p.groove_d, g0, th - 0.02), p.groove_w)
    return body - groove
