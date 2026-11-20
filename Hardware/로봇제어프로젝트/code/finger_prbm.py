"""PneuNet 손가락 PRBM 대체 모델 (Task 1b, 스펙 2.2 대체안).

S0 판정: flex(자기 접촉 없음)는 300° 대변형에서 young 에 대해 굽힘이 비단조(좌굴)라 플랜트로 쓰지 않는다.
- 관절 9개: 뿌리(x=15) + 방 사이 틈 8곳, 바닥층 높이의 y축 힌지. q > 0 이면 물체 쪽(−z)으로 굽는다.
- 관절 토크 τ = α·p·(1 − β·q) − k·q − c·q̇   (α, k 는 30 kPa → 끝단 300° 로 보정)
- 방 부풂 V(p): self-collision flex(E = 200 kPa) 결과 표 → 공압 용량과 화면의 방 크기에 반영
- 센서 ε = 100·h·Σq_s / L_s  (h: 유효 중립축 거리, S0 flex 센서 깊이 2 mm 결과 ε(30 kPa) ≈ 12 % 로 정함)
"""
import mujoco
import numpy as np

import paths  # noqa: F401
from build_cad import PP

RHO = 1080.0
# self-collision flex (E = 200 kPa) 방 체적 [kPa, mm³] — S0 보조 실험
V_TABLE = np.array([[0, 21060.0], [5, 23625], [10, 26340], [15, 31279], [20, 34396], [25, 37840], [30, 41912]])


class PrbmFinger:
    def __init__(self, young_pa=None, sensor_z_mm=2.0, k=0.3, beta=0.3, damping=0.004, target_deg=300.0,
                 p_ref=30.0, eps_ref=12.0, stiff_scale=1.0, pp=None):
        self.pp = pp or PP()
        pp = self.pp
        self.n = pp.n_ch
        self.k = k * stiff_scale
        self.beta, self.c = beta, damping
        q_ref = np.radians(target_deg) / self.n
        self.alpha = k * q_ref / (p_ref * (1 - beta * q_ref))   # 공칭 강성에서 보정 (stiff_scale 은 섭동)
        x_gap = [pp.root_len + i * (pp.blk + pp.gap) + pp.blk + pp.gap / 2 for i in range(pp.n_ch - 1)]
        self.x_j = np.r_[pp.root_len, x_gap] * 1e-3
        L = pp.root_len + pp.n_ch * pp.blk + (pp.n_ch - 1) * pp.gap + pp.end_add
        x1 = L - pp.sensor_tip_gap
        x0 = x1 - pp.sensor[0]
        self.sensor_j = np.where((self.x_j * 1e3 > x0) & (self.x_j * 1e3 < x1))[0]
        self.L_s = pp.sensor[0]
        self.h = eps_ref * self.L_s / (100.0 * np.radians(target_deg) / self.n * len(self.sensor_j))
        self.sensor_x = (x0 + x1) / 2 * 1e-3
        self.L = L * 1e-3
        self.p = 0.0
        vol = (pp.W * pp.t_base * L + pp.W * pp.H * (pp.root_len + pp.n_ch * pp.blk + pp.end_add)
               - pp.n_ch * (pp.blk - 2 * pp.t_in) * (pp.W - 2 * pp.wall) * (pp.H - pp.top_t)) * 1e-9
        self.mass = RHO * vol

    # ---------- MJCF ----------
    def mjcf(self, name, pos=(0, 0, 0), quat=(1, 0, 0, 0)):
        self.name, self.pos, self.quat = name, np.array(pos, float), np.array(quat, float)
        pp, mm = self.pp, 1e-3
        W, tb, H = pp.W * mm, pp.t_base * mm, pp.H * mm
        m_link = self.mass / (self.n + 1)
        col = 'contype="1" conaffinity="2" condim="3" friction="1.0 0.02 0.001"'
        vis = 'contype="0" conaffinity="0" group="1"'

        def link(i, b0, b1, k0, k1):
            g = (f'<geom name="{name}_base{i}" type="box" pos="{(b0 + b1) / 2} {W / 2} {tb / 2}" '
                 f'size="{(b1 - b0) / 2} {W / 2} {tb / 2}" rgba="0.95 0.75 0.55 1" mass="{m_link * 0.3}" {col}/>')
            c = (k0 + k1) / 2
            g += (f'<geom type="box" pos="{c} {W / 2} {tb + H / 2}" size="{(k1 - k0) / 2} {W / 2} {H / 2}" '
                  f'rgba="0.85 0.55 0.45 0.5" mass="{m_link * 0.7}" {vis}/>')
            if i != "r":
                g += (f'<geom name="{name}_ch{i}" type="ellipsoid" pos="{c} {W / 2} {tb + H / 2}" '
                      f'size="{(k1 - k0) / 2 * 0.7} {W / 2 * 0.85} {H / 2 * 0.85}" rgba="0.9 0.35 0.3 0.9" mass="0" {vis}/>')
            return g

        R, B, G, E = pp.root_len * mm, pp.blk * mm, pp.gap * mm, pp.end_add * mm
        xml = f'<body name="{name}" pos="{" ".join(map(str, pos))}" quat="{" ".join(map(str, quat))}">'
        xml += link("r", 0.0, R, 0.0, R)
        for i in range(self.n):
            px = R if i == 0 else (B + G / 2 if i == 1 else B + G)
            off = 0.0 if i == 0 else G / 2
            last = i == self.n - 1
            k1 = off + B + (E if last else 0.0)
            b1 = k1 if last else off + B + G / 2
            xml += (f'<body name="{name}_l{i}" pos="{px} 0 0"><joint name="{name}_j{i}" type="hinge" axis="0 1 0" '
                    f'pos="0 0 {tb / 2}" damping="{self.c}" stiffness="{self.k}" range="-0.3 1.2"/>')
            xml += link(i, 0.0, b1, off, k1)
            if last:
                xml += f'<site name="{name}_tip" pos="{k1} {W / 2} 0"/>'
        xml += "</body>" * (self.n + 1)
        return xml

    def attach(self, model, data, name=None):
        name = name or self.name
        self.m = model
        self.jids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{name}_j{i}") for i in range(self.n)]
        self.dofs = model.jnt_dofadr[self.jids]
        self.qadr = model.jnt_qposadr[self.jids]
        self.bids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"{name}_l{i}") for i in range(self.n)]
        self.tip_site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f"{name}_tip")
        self.contact_geoms = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{name}_base{i}") for i in [*range(self.n), "r"]}
        self.ch_geoms = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{name}_ch{i}") for i in range(self.n)]
        self.ch_size0 = model.geom_size[self.ch_geoms].copy()
        self.tip_body = self.bids[-1]

    def q(self, data):
        return data.qpos[self.qadr]

    # ---------- 압력·측정 ----------
    def apply_pressure(self, data, p_kpa):
        self.p = max(float(p_kpa), 0.0)
        q = self.q(data)
        data.qfrc_applied[self.dofs] = self.alpha * self.p * (1 - self.beta * np.clip(q, 0, None))
        s = (self.chamber_volume(data) / V_TABLE[0, 1]) ** (1 / 3)   # 방 부풂 표시 (체적비의 세제곱근)
        self.m.geom_size[self.ch_geoms] = self.ch_size0 * s

    def chamber_volume(self, data=None):
        return float(np.interp(self.p, V_TABLE[:, 0], V_TABLE[:, 1]))

    def sensor_strain(self, data):
        return float(100.0 * self.h * np.sum(self.q(data)[self.sensor_j]) / self.L_s)

    def tip_angle(self, data):
        return float(np.degrees(np.sum(self.q(data))))

    def sensor_point(self, data):
        k = self.sensor_j[len(self.sensor_j) // 2]
        return data.xpos[self.bids[k]].copy()

    def tip_point(self, data):
        return data.site_xpos[self.tip_site].copy()

    def finite(self, data):
        return bool(np.isfinite(self.q(data)).all())
