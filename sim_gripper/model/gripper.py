"""MuJoCo 3지 PRBM 소프트 그리퍼 + 물체 (M0).

손가락 두 종류:
- FingerParams (판형 TPU 95A 가정): 세그먼트 4개 + hinge 4개, k = E·w·t³/12 / (L/n), 센서 pad 원위 세그먼트 2·3.
- BellowsParams (60A 벨로즈, Meitani & Nisar 2025): 벨로즈당 hinge 1개(8개), precurve 41° = springref,
  k는 Fig.9·Fig.7 보정값, 센서 pad 원위 벨로즈 5·6·7 안쪽(바닥층)면.
물체는 테이블 위, 손끝은 테이블 위 약 10 mm.
"""
from dataclasses import dataclass

import mujoco
import numpy as np

BASE_R = 0.05        # 판형: 손가락 장착 반경 [m]
BASE_Z = 0.09        # 판형: 그리퍼 베이스 높이 [m] (손끝 z=10 mm)
PAD_T = 0.0005       # pad 반두께 [m]
DIST_CUTOFF = 0.03   # mj_geomDistance 탐색 한계 [m]
SENSOR_SEGS = (2, 3)  # 판형: 센서(pad)가 붙은 세그먼트


@dataclass
class FingerParams:
    L_mm: float = 80.0
    w_mm: float = 20.0
    t_mm: float = 6.0
    E_Pa: float = 26e6
    n_joints: int = 4
    zeta: float = 0.3

    def seg_m(self):
        return self.L_mm / 1000 / self.n_joints

    def joint_stiffness(self):
        w, t = self.w_mm / 1000, self.t_mm / 1000
        return self.E_Pa * w * t**3 / 12 / self.seg_m()

    def seg_mass(self, rho=1200.0):
        return rho * self.seg_m() * self.w_mm / 1000 * self.t_mm / 1000

    def joint_damping(self):
        L = self.L_mm / 1000
        inertia = self.seg_mass() * self.n_joints * L**2 / 3   # 손가락 전체를 근위 관절 기준 막대로 근사
        return 2 * self.zeta * np.sqrt(self.joint_stiffness() * inertia)

    base_R, sensor_segs, h_sensor_mm, base_margin, auto_height = BASE_R, SENSOR_SEGS, 3.0, 0.01, False

    def base_z(self):
        return BASE_Z

    def springref(self):
        return 0.0

    def finger_xml(self, i):
        return _finger_xml(i, self)


@dataclass
class BellowsParams:
    arc_len_mm: float = 105.0       # l
    depth_mm: float = 32.0          # h
    n_joints: int = 8               # 벨로즈 수
    precurve_deg: float = 41.0
    backbone_mm: float = 9.5        # 바닥층 3 + 채널 4 + 덮개 2.5 (CAD와 동일)
    bellow_h_mm: float = 7.5        # 덮개 바깥 벨로즈 돌출 (CAD: 3+14−9.5)
    bellow_t_mm: float = 6.43       # l_b
    mass_g: float = 40.0            # CAD 부피 33.7 cm³ × 1.2 g/cm³
    k_joint: float = 0.0            # 보정값으로 채움 (아래 CALIBRATED)
    zeta: float = 0.3
    base_R: float = 0.076           # 논문(끝단 반경 ≈ 30 mm)보다 10 mm 넓힘 → 지름 50 mm 물체에 근접 구간 ~20 mm
    sensor_segs: tuple = (5, 6, 7)
    h_sensor_mm: float = 0.5        # 센서면 ≈ 중립축(바닥층) → 굽힘 인장 작음
    pad_halfwidth_mm: float = 11.0  # 센서 홈 폭 22 mm
    base_margin: float = 0.012
    auto_height: bool = True        # 팔이 그리퍼를 내려 센서 pad 중심 = 물체 중심 높이 (손끝 ≥ 5 mm)

    def __post_init__(self):
        if not self.k_joint:
            self.k_joint = CALIBRATED["k_joint"]

    def seg_m(self):
        return self.arc_len_mm / 1000 / self.n_joints

    def springref(self):
        return np.radians(self.precurve_deg) / self.n_joints

    def base_z(self):
        rho = self.arc_len_mm / 1000 / np.radians(self.precurve_deg)
        return 0.025 + rho * np.sin(np.radians(self.precurve_deg)) + 0.008   # 손끝 ≈ 테이블 위 25 mm (계란 적도 위)

    def joint_damping(self):
        inertia = self.mass_g / 1000 * (self.arc_len_mm / 1000) ** 2 / 3
        return 2 * self.zeta * np.sqrt(self.k_joint * inertia)

    def finger_xml(self, i):
        phi = 120 * i
        ang = np.deg2rad(phi)
        x, y = self.base_R * np.cos(ang), self.base_R * np.sin(ang)
        ell, hd = self.seg_m(), self.depth_mm / 2000
        bb, bh, bt = self.backbone_mm / 1000, self.bellow_h_mm / 1000, self.bellow_t_mm / 1000
        m = self.mass_g / 1000 / self.n_joints
        k, c, ref = self.k_joint, self.joint_damping(), self.springref()
        xml = f'<body name="f{i}" pos="{x:.5f} {y:.5f} 0" euler="0 0 {np.radians(phi + 180):.6f}">'
        for j in range(self.n_joints):
            sensor = j in self.sensor_segs
            pos = "0 0 0" if j == 0 else f"0 0 {-ell}"
            xml += (f'<body name="f{i}_s{j}" pos="{pos}">'
                    f'<joint name="q{i}_{j}" type="hinge" axis="0 -1 0" stiffness="{k:.6f}" springref="{ref:.6f}" '
                    f'damping="{c:.6f}" armature="1e-6" limited="true" range="-0.3 0.8"/>'
                    f'<geom type="box" size="{bb / 2} {hd} {ell / 2}" pos="{-bb / 2} 0 {-ell / 2}" mass="{m * 0.6:.6f}" '
                    f'{"contype=\"0\" conaffinity=\"0\" " if sensor else ""}rgba="0.85 0.82 0.76 1"/>'
                    f'<geom type="box" size="{bh / 2} {hd} {bt / 2}" pos="{-bb - bh / 2} 0 {-ell / 2}" '
                    f'mass="{m * 0.4:.6f}" rgba="0.78 0.74 0.68 1"/>')
            if sensor:
                xml += (f'<geom name="pad_{i}_{j}" type="box" size="{PAD_T} {self.pad_halfwidth_mm / 1000} '
                        f'{ell / 2 * 0.95}" pos="{PAD_T} 0 {-ell / 2}" mass="0.0001" friction="1.2" '
                        f'rgba="0.75 0.75 0.8 1"/>')
        return xml + "</body>" * (self.n_joints + 1)


CALIBRATED = {"k_joint": 1.9834}   # calibrate_bellows.calibrate(): Fig.9 기울기 + Fig.7 200 kPa 6.28 N


@dataclass
class ObjectSpec:
    name: str
    shape: str          # "cylinder" | "capsule" | "sphere"
    size: tuple         # MJCF size (반경[, 반높이])
    mass_kg: float
    material: str       # "conductor" | "dielectric"
    fragile_F_N: float | None = None
    soft: bool = False

    def half_height(self):
        r = self.size[0]
        return {"sphere": r, "cylinder": self.size[-1], "capsule": self.size[-1] + r}[self.shape]


def _finger_xml(i, fp):
    phi = 120 * i
    ang = np.deg2rad(phi)
    x, y = BASE_R * np.cos(ang), BASE_R * np.sin(ang)
    ell, hw, ht = fp.seg_m(), fp.w_mm / 2000, fp.t_mm / 2000
    k, c = fp.joint_stiffness(), fp.joint_damping()
    xml = f'<body name="f{i}" pos="{x:.5f} {y:.5f} 0" euler="0 0 {np.radians(phi + 180):.6f}">'
    for j in range(fp.n_joints):
        pos = "0 0 0" if j == 0 else f"0 0 {-ell}"
        xml += (f'<body name="f{i}_s{j}" pos="{pos}">'
                f'<joint name="q{i}_{j}" type="hinge" axis="0 -1 0" stiffness="{k:.5f}" damping="{c:.6f}" '
                f'armature="1e-6" limited="true" range="-0.5 1.6"/>'
                f'<geom type="box" size="{ht} {hw} {ell / 2}" pos="0 0 {-ell / 2}" mass="{fp.seg_mass():.6f}" '
                f'{"contype=\"0\" conaffinity=\"0\" " if j in SENSOR_SEGS else ""}rgba="0.9 0.9 0.85 1"/>')
        if j in SENSOR_SEGS:
            xml += (f'<geom name="pad_{i}_{j}" type="box" size="{PAD_T} {hw * 0.9} {ell / 2 * 0.95}" '
                    f'pos="{ht + PAD_T} 0 {-ell / 2}" mass="0.0001" friction="1.2" rgba="0.75 0.75 0.8 1"/>')
    return xml + "</body>" * (fp.n_joints + 1)


def build_mjcf(fp, obj):
    oz = obj.half_height()
    size = " ".join(f"{s}" for s in obj.size)
    soft = ' solref="0.02 1"' if obj.soft else ""
    color = "0.7 0.72 0.75 1" if obj.material == "conductor" else "0.95 0.85 0.7 1"
    fingers = "".join(fp.finger_xml(i) for i in range(3))
    return f"""
<mujoco model="soft_gripper">
  <compiler angle="radian"/>
  <option timestep="0.00025" integrator="implicitfast" cone="elliptic" impratio="10"/>
  <visual><global offwidth="1280" offheight="960"/></visual>
  <worldbody>
    <light pos="0 0 0.6" dir="0 0 -1"/>
    <geom name="table" type="plane" size="0.3 0.3 0.01" rgba="0.35 0.38 0.42 1"/>
    <body name="obj" pos="0 0 {oz}">
      <freejoint/>
      <geom name="obj" type="{obj.shape}" size="{size}" mass="{obj.mass_kg}" friction="1.0"{soft} rgba="{color}"/>
    </body>
    <body name="base" pos="0 0 {fp.base_z():.5f}" gravcomp="1">
      <joint name="lift" type="slide" axis="0 0 1" damping="60" range="-0.05 0.15" limited="true"/>
      <geom type="cylinder" size="{fp.base_R + fp.base_margin} 0.008" pos="0 0 0.008" mass="0.5" rgba="0.2 0.25 0.3 1"/>
      {fingers}
    </body>
  </worldbody>
  <actuator><position name="lift" joint="lift" kp="2000"/></actuator>
</mujoco>"""


class GripperSim:
    def __init__(self, fp, obj):
        self.fp, self.obj = fp, obj
        self.model = mujoco.MjModel.from_xml_string(build_mjcf(fp, obj))
        self.data = mujoco.MjData(self.model)
        m = self.model
        self.dof = np.array([[m.jnt_dofadr[m.joint(f"q{i}_{j}").id] for j in range(fp.n_joints)] for i in range(3)])
        self.qadr = np.array([[m.jnt_qposadr[m.joint(f"q{i}_{j}").id] for j in range(fp.n_joints)] for i in range(3)])
        self.pads = np.array([[m.geom(f"pad_{i}_{j}").id for j in fp.sensor_segs] for i in range(3)])
        self.obj_geom, self.obj_body = m.geom("obj").id, m.body("obj").id
        self.pad_finger = {int(g): i for i in range(3) for g in self.pads[i]}
        self.object_broken = False
        self._renderer = None
        self.data.qpos[self.qadr] = m.qpos_spring[self.qadr]   # 손가락 초기 자세 = 스프링 기준각 (precurve)
        mujoco.mj_forward(m, self.data)
        self.lift0 = 0.0
        if fp.auto_height:                       # 접근 높이 사전 위치 (리프트 관절 오프셋)
            pad_z = float(np.mean([self.data.geom_xpos[g][2] for g in self.pads.ravel()]))
            self.lift0 = max(obj.half_height() - pad_z, 0.005 - self.lowest_finger_z())
            self.data.qpos[m.jnt_qposadr[m.joint("lift").id]] = self.lift0
            mujoco.mj_forward(m, self.data)

    def step(self, tau, lift_target_m):
        self.data.qfrc_applied[self.dof.ravel()] = np.asarray(tau, float).ravel()
        self.data.ctrl[0] = lift_target_m
        mujoco.mj_step(self.model, self.data)
        if self.obj.fragile_F_N is not None and not self.object_broken:
            self.object_broken = bool(self.pad_force_N().max() > self.obj.fragile_F_N)   # 국부 접촉력 기준

    def lowest_finger_z(self):
        """손가락 geom(박스) 꼭짓점 중 최저 높이 [m]."""
        m, d, low = self.model, self.data, np.inf
        base = m.body("base").id
        for g in range(m.ngeom):
            b = m.geom_bodyid[g]
            if b in (0, base, self.obj_body) or m.geom_type[g] != mujoco.mjtGeom.mjGEOM_BOX:
                continue
            R, h = d.geom_xmat[g].reshape(3, 3), m.geom_size[g]
            corners = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * h
            low = min(low, float((d.geom_xpos[g] + corners @ R.T)[:, 2].min()))
        return low

    def joint_angles(self):
        return self.data.qpos[self.qadr].copy()

    def kappa_bar_per_mm(self):
        dq = self.joint_angles() - self.fp.springref()          # 장착(정지) 형상 대비 추가 굽힘
        segs = list(self.fp.sensor_segs)
        return dq[:, segs].sum(axis=1) / (len(segs) * self.fp.seg_m() * 1000)

    def pad_distance_mm(self):
        out = np.empty(3)
        for i in range(3):
            d = min(mujoco.mj_geomDistance(self.model, self.data, int(g), self.obj_geom, DIST_CUTOFF, None)
                    for g in self.pads[i])
            out[i] = max(d, 0.0) * 1000
        return out

    def pad_force_N(self):
        out, f6 = np.zeros(3), np.zeros(6)
        for k in range(self.data.ncon):
            c = self.data.contact[k]
            g1, g2 = int(c.geom1), int(c.geom2)
            pad = g1 if g2 == self.obj_geom else (g2 if g1 == self.obj_geom else None)
            if pad in self.pad_finger:
                mujoco.mj_contactForce(self.model, self.data, k, f6)
                out[self.pad_finger[pad]] += abs(f6[0])
        return out

    def object_height_m(self):
        return float(self.data.xpos[self.obj_body][2])

    def apply_object_force(self, f_xyz):
        self.data.xfrc_applied[self.obj_body, :3] = f_xyz

    def render_frame(self, width=640, height=480):
        try:
            if self._renderer is None:
                self._renderer = mujoco.Renderer(self.model, height, width)
            self._renderer.update_scene(self.data)
            return self._renderer.render()
        except Exception:
            return None
