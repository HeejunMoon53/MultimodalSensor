"""MuJoCo 3지 PRBM 소프트 그리퍼 + 물체 (M0).

손가락 두 종류:
- FingerParams (판형 TPU 95A 가정): 세그먼트 4개 + hinge 4개, k = E·w·t³/12 / (L/n), 센서 pad 원위 세그먼트 2·3.
- BellowsParams (60A 벨로즈, Meitani & Nisar 2025): 벨로즈당 hinge 1개(8개), precurve 41° = springref,
  k는 Fig.9·Fig.7 보정값, 센서 pad 원위 벨로즈 5·6·7 안쪽(바닥층)면.
물체는 테이블 위, 손끝은 테이블 위 약 10 mm.

visual=True (기본): 충돌 형상은 group 3(숨김)으로 두고, 보이는 형상(group 1, 충돌·질량 0)을 따로 얹음.
벨로즈는 CAD를 벨로즈 단위로 자른 메시(cad/visual.py → assets/), 판형은 둥근 마디·텐던 선.
물리(질량·관성·접촉·궤적)는 visual=False와 같음 (test_visual.py).
"""
from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np

ASSETS = Path(__file__).resolve().parent / "assets"
VIS = 'contype="0" conaffinity="0" group="1" mass="0"'
OBJ_MAT = {"metal": "alu", "hand": "skin", "egg": "eggshell", "sponge": "sponge", "spool": "wood"}

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

    def finger_xml(self, i, visual=False):
        return _finger_xml(i, self, visual)


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

    def finger_xml(self, i, visual=False):
        phi = 120 * i
        ang = np.deg2rad(phi)
        x, y = self.base_R * np.cos(ang), self.base_R * np.sin(ang)
        ell, hd = self.seg_m(), self.depth_mm / 2000
        bb, bh, bt = self.backbone_mm / 1000, self.bellow_h_mm / 1000, self.bellow_t_mm / 1000
        m = self.mass_g / 1000 / self.n_joints
        k, c, ref = self.k_joint, self.joint_damping(), self.springref()
        hide, pad = (' group="3"', ' material="coil"') if visual else ("", ' rgba="0.75 0.75 0.8 1"')
        xml = f'<body name="f{i}" pos="{x:.5f} {y:.5f} 0" euler="0 0 {np.radians(phi + 180):.6f}">'
        if visual:
            xml += f'<geom type="mesh" mesh="broot" material="tpu60" {VIS}/>'
        for j in range(self.n_joints):
            sensor = j in self.sensor_segs
            pos = "0 0 0" if j == 0 else f"0 0 {-ell}"
            xml += (f'<body name="f{i}_s{j}" pos="{pos}">'
                    f'<joint name="q{i}_{j}" type="hinge" axis="0 -1 0" stiffness="{k:.6f}" springref="{ref:.6f}" '
                    f'damping="{c:.6f}" armature="1e-6" limited="true" range="-0.3 0.8"/>'
                    f'<geom type="box" size="{bb / 2} {hd} {ell / 2}" pos="{-bb / 2} 0 {-ell / 2}" mass="{m * 0.6:.6f}" '
                    f'{"contype=\"0\" conaffinity=\"0\" " if sensor else ""}rgba="0.85 0.82 0.76 1"{hide}/>'
                    f'<geom type="box" size="{bh / 2} {hd} {bt / 2}" pos="{-bb - bh / 2} 0 {-ell / 2}" '
                    f'mass="{m * 0.4:.6f}" rgba="0.78 0.74 0.68 1"{hide}/>')
            if visual:
                xml += f'<geom type="mesh" mesh="bseg{j}" material="tpu60" {VIS}/>'
            if sensor:
                xml += (f'<geom name="pad_{i}_{j}" type="box" size="{PAD_T} {self.pad_halfwidth_mm / 1000} '
                        f'{ell / 2 * 0.95}" pos="{PAD_T} 0 {-ell / 2}" mass="0.0001" friction="1.2"{pad}/>')
        return xml + "</body>" * (self.n_joints + 1)

    def base_visual_xml(self):
        return f'<geom type="mesh" mesh="base60" material="pla" {VIS}/>'


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
    xy: tuple = (0.0, 0.0)  # 그리퍼 중심 대비 물체 위치 [m] (정렬 실험용)

    def half_height(self):
        r = self.size[0]
        return {"sphere": r, "cylinder": self.size[-1], "capsule": self.size[-1] + r}[self.shape]


def _finger_xml(i, fp, visual=False):
    phi = 120 * i
    ang = np.deg2rad(phi)
    x, y = BASE_R * np.cos(ang), BASE_R * np.sin(ang)
    ell, hw, ht = fp.seg_m(), fp.w_mm / 2000, fp.t_mm / 2000
    k, c = fp.joint_stiffness(), fp.joint_damping()
    hide, pad = (' group="3"', ' material="coil"') if visual else ("", ' rgba="0.75 0.75 0.8 1"')
    ts = (ht * 0.4, hw + 0.0006)                    # 텐던 경로: 옆면, 안쪽(+X)으로 치우침
    xml = f'<body name="f{i}" pos="{x:.5f} {y:.5f} 0" euler="0 0 {np.radians(phi + 180):.6f}">'
    if visual:
        xml += (f'<geom type="box" size="{ht + 0.002} {hw + 0.002} 0.006" pos="0 0 0.006" material="pla" {VIS}/>'
                f'<site name="t{i}_a" pos="{ts[0]} {ts[1]} 0.010" size="0.0008" group="4"/>')
    for j in range(fp.n_joints):
        pos = "0 0 0" if j == 0 else f"0 0 {-ell}"
        xml += (f'<body name="f{i}_s{j}" pos="{pos}">'
                f'<joint name="q{i}_{j}" type="hinge" axis="0 -1 0" stiffness="{k:.5f}" damping="{c:.6f}" '
                f'armature="1e-6" limited="true" range="-0.5 1.6"/>'
                f'<geom type="box" size="{ht} {hw} {ell / 2}" pos="0 0 {-ell / 2}" mass="{fp.seg_mass():.6f}" '
                f'{"contype=\"0\" conaffinity=\"0\" " if j in SENSOR_SEGS else ""}rgba="0.9 0.9 0.85 1"{hide}/>')
        if visual:                                   # 둥근 마디(관절 틈 메움) + 몸통 + 텐던 가이드
            r = ht * 0.98
            xml += (f'<geom type="box" size="{ht * 0.98} {hw} {ell / 2 - r / 2}" pos="0 0 {-ell / 2}" '
                    f'material="tpu95" {VIS}/>'
                    f'<geom type="capsule" fromto="0 {-hw + r} 0 0 {hw - r} 0" size="{r}" material="tpu95" {VIS}/>'
                    f'<geom type="box" size="{r} {r} {r}" pos="0 {-hw + r} 0" material="tpu95" {VIS}/>'
                    f'<geom type="box" size="{r} {r} {r}" pos="0 {hw - r} 0" material="tpu95" {VIS}/>'
                    f'<geom type="box" size="0.0012 0.0009 0.0015" pos="{ts[0]} {hw + 0.0002} {-ell * 0.5}" '
                    f'material="pla" {VIS}/>'
                    f'<site name="t{i}_{j}" pos="{ts[0]} {ts[1]} {-ell * 0.5}" size="0.0008" group="4"/>')
            if j == fp.n_joints - 1:
                xml += f'<geom type="capsule" fromto="0 {-hw + r} {-ell} 0 {hw - r} {-ell}" size="{r}" material="tpu95" {VIS}/>'
        if j in SENSOR_SEGS:
            xml += (f'<geom name="pad_{i}_{j}" type="box" size="{PAD_T} {hw * 0.9} {ell / 2 * 0.95}" '
                    f'pos="{ht + PAD_T} 0 {-ell / 2}" mass="0.0001" friction="1.2"{pad}/>')
    return xml + "</body>" * (fp.n_joints + 1)


def _tendon_xml(fp):
    if not isinstance(fp, FingerParams):
        return ""
    paths = "".join(f'<spatial name="tendon{i}" width="0.0005" material="tendon">'
                    + "".join(f'<site site="t{i}_{s}"/>' for s in ["a", *range(fp.n_joints)]) + "</spatial>"
                    for i in range(3))
    return f"<tendon>{paths}</tendon>"


SCENE_ASSETS = f"""
  <compiler angle="radian" meshdir="{ASSETS.as_posix()}"/>
  <visual>
    <global offwidth="1280" offheight="960"/>
    <quality shadowsize="4096" offsamples="8"/>
    <headlight ambient="0.22 0.22 0.24" diffuse="0.32 0.32 0.32" specular="0.08 0.08 0.08"/>
    <map znear="0.005" zfar="5"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.93 0.94 0.96" rgb2="0.55 0.6 0.68" width="512" height="3072"/>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.66 0.68 0.71" rgb2="0.61 0.63 0.66"
             mark="edge" markrgb="0.54 0.56 0.6" width="512" height="512"/>
    <material name="floor" texture="grid" texrepeat="16 16" texuniform="true"/>
    <material name="tpu60" rgba="0.94 0.94 0.92 1" specular="0.25" shininess="0.35"/>
    <material name="tpu95" rgba="0.95 0.95 0.93 1" specular="0.3" shininess="0.4"/>
    <material name="pla" rgba="0.18 0.2 0.24 1" specular="0.3" shininess="0.3"/>
    <material name="coil" rgba="0.80 0.52 0.25 1" specular="0.9" shininess="0.8"/>
    <material name="tendon" rgba="0.12 0.3 0.75 1"/>
    <material name="mount" rgba="0.55 0.57 0.6 1" specular="0.6" shininess="0.6"/>
    <material name="alu" rgba="0.74 0.76 0.8 1" specular="1" shininess="0.9" reflectance="0.25"/>
    <material name="eggshell" rgba="0.9 0.8 0.66 1" specular="0.05" shininess="0.1"/>
    <material name="skin" rgba="0.92 0.72 0.6 1" specular="0.15" shininess="0.2"/>
    <material name="sponge" rgba="0.98 0.82 0.25 1" specular="0.02"/>
    <material name="wood" rgba="0.72 0.53 0.33 1" specular="0.1"/>
    <material name="dielectric" rgba="0.95 0.85 0.7 1"/>
    {"".join(f'<mesh name="bseg{j}" file="bellows_seg{j}.stl" scale="0.001 0.001 0.001"/>' for j in range(8))}
    <mesh name="broot" file="bellows_root.stl" scale="0.001 0.001 0.001"/>
    <mesh name="base60" file="base_60A.stl" scale="0.001 0.001 0.001"/>
  </asset>"""


def _object_xml(obj, visual):
    size = " ".join(f"{s}" for s in obj.size)
    soft = ' solref="0.02 1"' if obj.soft else ""
    color = "0.7 0.72 0.75 1" if obj.material == "conductor" else "0.95 0.85 0.7 1"
    if not visual:
        return f'<geom name="obj" type="{obj.shape}" size="{size}" mass="{obj.mass_kg}" friction="1.0"{soft} rgba="{color}"/>'
    mat = OBJ_MAT.get(obj.name, "alu" if obj.material == "conductor" else "dielectric")
    if obj.name != "egg":
        return f'<geom name="obj" type="{obj.shape}" size="{size}" mass="{obj.mass_kg}" friction="1.0"{soft} material="{mat}"/>'
    r = obj.size[0]                                  # 충돌은 구 그대로, 보이는 형상은 바닥을 맞춘 타원체 (적도 오차 < 0.4 mm)
    return (f'<geom name="obj" type="sphere" size="{size}" mass="{obj.mass_kg}" friction="1.0"{soft} group="3"/>'
            f'<geom type="ellipsoid" size="{r} {r} {r * 1.23}" pos="0 0 {r * 0.23}" material="{mat}" {VIS}/>')


def build_mjcf(fp, obj, visual=True):
    oz = obj.half_height()
    fingers = "".join(fp.finger_xml(i, visual) for i in range(3))
    base_r = fp.base_R + fp.base_margin
    if visual:
        head = SCENE_ASSETS
        light = ('<light pos="0.35 -0.45 0.75" dir="-0.35 0.45 -0.75" diffuse="0.55 0.55 0.53" castshadow="true"/>'
                 '<light pos="-0.4 0.3 0.5" dir="0.4 -0.3 -0.5" diffuse="0.25 0.27 0.3" castshadow="false"/>')
        table = '<geom name="table" type="plane" size="0.3 0.3 0.01" material="floor"/>'
        mesh_base = isinstance(fp, BellowsParams)
        base = (f'<geom type="cylinder" size="{base_r} 0.008" pos="0 0 0.008" mass="0.5"'
                + (' group="3"/>' + fp.base_visual_xml() if mesh_base else ' material="pla"/>')
                + f'<geom type="cylinder" size="0.03 0.005" pos="0 0 {0.021 if not mesh_base else 0.017}" material="mount" {VIS}/>'
                + f'<geom type="cylinder" fromto="0 0 0.02 0 0 0.3" size="0.014" material="mount" {VIS}/>')
    else:
        head = '\n  <compiler angle="radian"/>\n  <visual><global offwidth="1280" offheight="960"/></visual>'
        light = '<light pos="0 0 0.6" dir="0 0 -1"/>'
        table = '<geom name="table" type="plane" size="0.3 0.3 0.01" rgba="0.35 0.38 0.42 1"/>'
        base = f'<geom type="cylinder" size="{base_r} 0.008" pos="0 0 0.008" mass="0.5" rgba="0.2 0.25 0.3 1"/>'
    return f"""
<mujoco model="soft_gripper">{head}
  <option timestep="0.00025" integrator="implicitfast" cone="elliptic" impratio="10"/>
  <worldbody>
    {light}
    {table}
    <body name="obj" pos="{obj.xy[0]} {obj.xy[1]} {oz}">
      <freejoint/>
      {_object_xml(obj, visual)}
    </body>
    <body name="base" pos="0 0 {fp.base_z():.5f}" gravcomp="1">
      <joint name="lift" type="slide" axis="0 0 1" damping="60" range="-0.05 0.15" limited="true"/>
      {base}
      {fingers}
    </body>
  </worldbody>
  {_tendon_xml(fp) if visual else ""}
  <actuator><position name="lift" joint="lift" kp="2000"/></actuator>
</mujoco>"""


class GripperSim:
    def __init__(self, fp, obj, visual=True):
        self.fp, self.obj = fp, obj
        self.model = mujoco.MjModel.from_xml_string(build_mjcf(fp, obj, visual))
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
            if b in (0, base, self.obj_body) or m.geom_type[g] != mujoco.mjtGeom.mjGEOM_BOX or m.geom_group[g] == 1:
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

    def object_xy_m(self):
        return self.data.xpos[self.obj_body][:2].copy()

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
