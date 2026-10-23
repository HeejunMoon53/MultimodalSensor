"""MuJoCo 3지 PRBM 소프트 그리퍼 + 물체 (M0).

손가락 = 세그먼트 4개 + hinge 4개, 관절 강성 k = E·w·t³/12 / (L/n).
센서 pad는 세그먼트 1·2 안쪽면 (센서 구간 40 mm). 물체는 받침대 위, 중심 높이를 pad 구간 중앙에 맞춤.
"""
from dataclasses import dataclass

import mujoco
import numpy as np

BASE_R = 0.05        # 손가락 장착 반경 [m]
BASE_Z = 0.12        # 그리퍼 베이스 높이 [m]
PAD_T = 0.0005       # pad 반두께 [m]
DIST_CUTOFF = 0.03   # mj_geomDistance 탐색 한계 [m]


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
    xml = f'<body name="f{i}" pos="{x:.5f} {y:.5f} 0" euler="0 0 {phi + 180}">'
    for j in range(fp.n_joints):
        pos = "0 0 0" if j == 0 else f"0 0 {-ell}"
        xml += (f'<body name="f{i}_s{j}" pos="{pos}">'
                f'<joint name="q{i}_{j}" type="hinge" axis="0 -1 0" stiffness="{k:.5f}" damping="{c:.6f}" '
                f'armature="1e-6" limited="true" range="-0.5 1.6"/>'
                f'<geom type="box" size="{ht} {hw} {ell / 2}" pos="0 0 {-ell / 2}" mass="{fp.seg_mass():.6f}" '
                f'rgba="0.9 0.9 0.85 1"/>')
        if j in (1, 2):
            xml += (f'<geom name="pad_{i}_{j}" type="box" size="{PAD_T} {hw * 0.9} {ell / 2 * 0.95}" '
                    f'pos="{ht + PAD_T} 0 {-ell / 2}" mass="0.0001" friction="1.2" rgba="0.75 0.75 0.8 1"/>')
    return xml + "</body>" * (fp.n_joints + 1)


def build_mjcf(fp, obj):
    pad_mid = BASE_Z - 2 * fp.seg_m()             # pad 구간(세그먼트 1·2) 중앙 높이
    hh = obj.half_height()
    ped_h = max(pad_mid - hh, 0.002)
    oz = ped_h + hh
    size = " ".join(f"{s}" for s in obj.size)
    soft = ' solref="0.02 1"' if obj.soft else ""
    color = "0.7 0.72 0.75 1" if obj.material == "conductor" else "0.95 0.85 0.7 1"
    fingers = "".join(_finger_xml(i, fp) for i in range(3))
    return f"""
<mujoco model="soft_gripper">
  <option timestep="0.00025" integrator="implicitfast"/>
  <visual><global offwidth="1280" offheight="960"/></visual>
  <worldbody>
    <light pos="0 0 0.6" dir="0 0 -1"/>
    <geom name="table" type="plane" size="0.3 0.3 0.01" rgba="0.35 0.38 0.42 1"/>
    <geom name="pedestal" type="cylinder" size="0.012 {ped_h / 2}" pos="0 0 {ped_h / 2}" rgba="0.3 0.3 0.3 1"/>
    <body name="obj" pos="0 0 {oz}">
      <freejoint/>
      <geom name="obj" type="{obj.shape}" size="{size}" mass="{obj.mass_kg}" friction="1.0"{soft} rgba="{color}"/>
    </body>
    <body name="base" pos="0 0 {BASE_Z}" gravcomp="1">
      <joint name="lift" type="slide" axis="0 0 1" damping="60" range="-0.05 0.15" limited="true"/>
      <geom type="cylinder" size="{BASE_R + 0.01} 0.008" pos="0 0 0.008" mass="0.5" rgba="0.2 0.25 0.3 1"/>
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
        self.pads = np.array([[m.geom(f"pad_{i}_{j}").id for j in (1, 2)] for i in range(3)])
        self.obj_geom, self.obj_body = m.geom("obj").id, m.body("obj").id
        self.pad_finger = {int(g): i for i in range(3) for g in self.pads[i]}
        self.object_broken = False
        self._renderer = None
        mujoco.mj_forward(m, self.data)

    def step(self, tau, lift_target_m):
        self.data.qfrc_applied[self.dof.ravel()] = np.asarray(tau, float).ravel()
        self.data.ctrl[0] = lift_target_m
        mujoco.mj_step(self.model, self.data)
        if self.obj.fragile_F_N is not None and not self.object_broken:
            self.object_broken = bool(self.pad_force_N().sum() > self.obj.fragile_F_N)

    def joint_angles(self):
        return self.data.qpos[self.qadr].copy()

    def kappa_bar_per_mm(self):
        q = self.joint_angles()
        return (q[:, 1] + q[:, 2]) / 40.0

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
