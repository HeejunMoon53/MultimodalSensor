"""A단계 플랜트 (스펙 2절): MuJoCo flex PneuNet 2지 + ITV·튜브 + 센서 체인(순방향 → TDM 잡음 → v4 MoE).

과제 1절의 '실제 플랜트'로 간주한다. 설계 코드는 이 파일의 내부 파라미터를 보지 않고 식별 모델만 쓴다.
손가락은 아래(−z)로 매달리고, 바닥층(센서 면)이 서로 마주 본다(손가락 A: x<0, B: x>0).
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

import mujoco
import numpy as np

import paths  # noqa: F401
from finger_flex import FlexFinger
from finger_prbm import PrbmFinger
from paths import load_params
from pneumatics import Itv, Line

TS = 0.01
R_IN = 25.0  # 그리퍼 중심 ~ 바닥층 안쪽면 [mm] (PP.r_in)
_NOISE = None
# 재질별 물체 접촉 강성 (MuJoCo solref 시정수 [s]): 도체 = 단단한 금속, 유전체 = 플라스틱, 인체 = 피부
SOLREF = {"conductor": 0.002, "dielectric": 0.004, "human": 0.02}


class PlantDiverged(RuntimeError):
    pass


@dataclass
class Scenario:
    material: str = "conductor"
    obj_kind: str = "cylinder"            # cylinder(축 = y) | sphere
    obj_radius_mm: float = 15.0
    obj_start_mm: tuple = (0.0, 0.0, -400.0)
    obj_path: Optional[Callable[[float], tuple]] = None   # t[s] → (x, y, z) [mm]
    tip_load_N: float = 0.0
    young_scale: float = 1.0
    tau_v_scale: float = 1.0
    R_t_scale: float = 1.0
    fingers: int = 2


@dataclass
class Obs:
    p_mon: np.ndarray
    eps_hat: np.ndarray
    val_hat: np.ndarray
    contact: np.ndarray
    gate_p: np.ndarray
    teng: np.ndarray = None      # TENG 전압 (마지막 1 kHz 샘플)
    gate: np.ndarray = None      # MoE 게이트만의 접촉 판정


@dataclass
class Truth:
    p: np.ndarray
    p_c: np.ndarray
    eps: np.ndarray
    eps_dot: np.ndarray
    d_mm: np.ndarray
    F_N: np.ndarray
    tip_deg: np.ndarray
    extra: dict = field(default_factory=dict)


def _quat(R):
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(R, float).ravel())
    return q


def _sensor_noise():
    global _NOISE
    if _NOISE is None:
        from sim_gripper.sensor.tdm import noise_from_data
        _NOISE = noise_from_data()
    return _NOISE


class Plant:
    def __init__(self, scn: Scenario, seed=0, nonideal=True, params=None, teng=True):
        """teng=True: 접촉 = MoE 게이트 ∨ TENG 래치, 유전체 접촉 중 ε̂·F̂ 는 ΔR 잔차 추정기 (sim_gripper M3)."""
        self.scn, self.seed, self.nonideal, self.use_teng = scn, seed, nonideal, teng
        P = (params or load_params()).get("plant", {})
        self.dt = float(P.get("dt_sim", 2e-3))
        self.n_sub = int(round(TS / self.dt))
        self.prestrain = float(P.get("eps_prestrain", 0.0))
        E = float(P.get("young_pa", 4.0e4)) * scn.young_scale
        self.cal = (params or load_params()).get("sensor_cal", {"a": 1.0, "b": 0.0})  # 장착 보정 ε = (ε̂ − b)/a (B단계 R1)
        self.fcal = float((params or load_params()).get("force_cal", {}).get("c", 1.0))
        if P.get("model", "prbm") == "flex":
            self.fingers = [FlexFinger(young_pa=E, sensor_z_mm=float(P.get("sensor_z_mm", 2.0)))
                            for _ in range(scn.fingers)]
        else:
            self.fingers = [PrbmFinger(stiff_scale=scn.young_scale) for _ in range(scn.fingers)]
        from finger_prbm import V_TABLE
        self._Vp = np.array(P.get("V_of_p", V_TABLE)) if P.get("model") == "flex" else V_TABLE
        self._build()
        self.itv = [Itv(tau_v=0.05 * scn.tau_v_scale, seed=seed + i, ideal=not nonideal) for i in range(scn.fingers)]
        self.line = [Line(R_t=2.0e-4 * scn.R_t_scale) for _ in range(scn.fingers)]
        self.t = 0.0
        self._eps_prev = np.zeros(scn.fingers)
        self._tip_prev = None
        self._renderer = None
        self._sensors()

    # ---------------- 모델 ----------------
    def _build(self):
        s = self.scn
        frames = [(np.array([[0, 0, -1], [0, -1, 0], [-1, 0, 0]]).T, (-R_IN, 15.0)),
                  (np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]]).T, (R_IN, -15.0))][: s.fingers]
        parts = []
        for i, (f, (R, (x, y))) in enumerate(zip(self.fingers, frames)):
            parts.append(f.mjcf(f"finger{i}", pos=(x * 1e-3, y * 1e-3, 0.0), quat=tuple(_quat(R))))
        r = s.obj_radius_mm * 1e-3
        geom = (f'<geom type="cylinder" size="{r} 0.04" euler="1.5708 0 0"' if s.obj_kind == "cylinder"
                else f'<geom type="sphere" size="{r}"')
        geom += f' rgba="0.6 0.65 0.75 1" solref="{SOLREF[s.material]} 1" condim="3" contype="2" conaffinity="1"/>'
        x0 = np.array(s.obj_start_mm) * 1e-3
        xml = (f'<mujoco><compiler angle="radian"/>'
               f'<option timestep="{self.dt}" gravity="0 0 -9.81" solver="Newton" integrator="discrete"/>'
               f'<visual><global offwidth="960" offheight="720"/></visual>'
               f'<worldbody><light pos="0 -0.4 0.3" dir="0 1 -0.6"/><light pos="0.3 0 0.3" dir="-1 0 -1"/>'
               f'<camera name="front" pos="0 -0.38 -0.07" xyaxes="1 0 0 0 0 1"/>'
               f'<body name="hub" pos="0 0 0.008"><geom type="box" size="0.06 0.03 0.008" rgba="0.3 0.3 0.32 1" contype="0" conaffinity="0"/></body>'
               f'<body name="obj" mocap="true" pos="{x0[0]} {x0[1]} {x0[2]}">{geom}</body>'
               + "".join(parts) + "</worldbody></mujoco>")
        self.m = mujoco.MjModel.from_xml_string(xml)
        self.d = mujoco.MjData(self.m)
        for i, f in enumerate(self.fingers):
            f.attach(self.m, self.d, f"finger{i}")
        self.obj_geom = self.m.body_geomadr[mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, "obj")]
        mujoco.mj_forward(self.m, self.d)

    def _sensors(self):
        n = self.scn.fingers
        if self.nonideal:
            from sim_gripper.perception.moe import MoE
            from sim_gripper.sensor.forward import SensorForward
            from sim_gripper.sensor.tdm import TdmSampler
            sL, sR = _sensor_noise()
            self.fwd = SensorForward()
            self.tdm = [TdmSampler(sL, sR, seed=self.seed * 10 + i) for i in range(n)]
            self.moe = [MoE() for _ in range(n)]
            from sim_gripper.perception.contact import DielectricEstimator, TengContact
            from sim_gripper.sensor.forward import TengModel
            self.teng_m = [TengModel() for _ in range(n)]
            self.latch = [TengContact() for _ in range(n)]
            self.diel = DielectricEstimator(self.fwd)

    # ---------------- 측정 ----------------
    def _dVdp(self, p):
        V = self._Vp
        return float(np.interp(p, V[1:, 0] * 0.5 + V[:-1, 0] * 0.5, np.diff(V[:, 1]) / np.diff(V[:, 0])))

    def _contact_force(self, i):
        f = self.fingers[i]
        F, f6 = 0.0, np.zeros(6)
        for k in range(self.d.ncon):
            c = self.d.contact[k]
            mine = (c.geom[0] in f.contact_geoms or c.geom[1] in f.contact_geoms) if hasattr(f, "contact_geoms")                 else f.fid in (c.flex[0], c.flex[1])
            if self.obj_geom in (c.geom[0], c.geom[1]) and mine:
                mujoco.mj_contactForce(self.m, self.d, k, f6)
                F += abs(f6[0])
        return F

    def _distance(self, i):
        p = self.fingers[i].sensor_point(self.d)
        c = self.d.mocap_pos[0]
        r = self.scn.obj_radius_mm * 1e-3
        v = p - c
        if self.scn.obj_kind == "cylinder":
            v[1] = 0.0
        return max(0.0, (np.linalg.norm(v) - r) * 1e3)

    # ---------------- 진행 ----------------
    def step(self, u):
        u = np.broadcast_to(np.asarray(u, float), (self.scn.fingers,))
        p = np.zeros(self.scn.fingers)
        for _ in range(self.n_sub):
            if self.scn.obj_path is not None:
                self.d.mocap_pos[0] = np.array(self.scn.obj_path(self.t)) * 1e-3
            for i, f in enumerate(self.fingers):
                p[i] = self.itv[i].step(u[i], self.dt)
                V = f.chamber_volume(self.d)
                pc = self.line[i].step(p[i], V, self._dVdp(self.line[i].p_c), self.dt)
                f.apply_pressure(self.d, pc)
                if self.scn.tip_load_N:
                    self.d.xfrc_applied[f.tip_body, :3] = np.array([0, 0, -self.scn.tip_load_N])
                elif hasattr(f, "contact_geoms"):
                    self.d.xfrc_applied[f.tip_body, :3] = 0.0
            mujoco.mj_step(self.m, self.d)
            self.t += self.dt
        self._check()
        return self._observe()

    def _check(self):
        tips = np.array([f.tip_point(self.d) for f in self.fingers])
        W = mujoco.mjtWarning
        nwarn = sum(int(self.d.warning[w].number) for w in (W.mjWARN_BADQACC, W.mjWARN_BADQVEL, W.mjWARN_BADQPOS))
        bad = not np.isfinite(tips).all() or nwarn > 0  # MuJoCo 는 발산 시 상태를 조용히 리셋하므로 경고 수로 잡는다
        if self._tip_prev is not None and not bad:
            bad = np.max(np.linalg.norm(tips - self._tip_prev, axis=1)) > 0.2
        self._tip_prev = tips
        if bad:
            raise PlantDiverged(f"flex 발산 t={self.t:.3f}s")

    def truth(self):
        return self._truth

    def _observe(self):
        n = self.scn.fingers
        eps = np.array([f.sensor_strain(self.d) for f in self.fingers])
        F = np.array([self._contact_force(i) for i in range(n)])
        dist = np.array([self._distance(i) for i in range(n)])
        self._truth = Truth(p=np.array([it.output() for it in self.itv]), p_c=np.array([ln.p_c for ln in self.line]),
                            eps=eps, eps_dot=(eps - self._eps_prev) / TS, d_mm=dist, F_N=F,
                            tip_deg=np.array([f.tip_angle(self.d) for f in self.fingers]))
        self._eps_prev = eps
        p_mon = np.array([it.monitor() for it in self.itv])
        if not self.nonideal:
            contact = (F > 1e-3).astype(int)
            return Obs(p_mon, eps.copy(), np.where(contact, F, dist), contact, contact.astype(float))
        eh, vh, ch, gp, tv, gt = (np.zeros(n) for _ in range(6))
        mat = "conductor" if self.scn.material == "human" else self.scn.material  # shortcut: 인체 K_MAT 미정, B단계 R1에서 교체
        for i in range(n):
            d_eff = 0.0 if F[i] > 1e-3 else dist[i]  # 접촉 중이면 접촉점 간격 0 (센서 중심 거리 아님)
            dL, dR = self.fwd.signals(eps[i] + self.prestrain, d_eff, F[i], mat)
            lat = 0
            for _ in range(int(round(TS / 1e-3))):
                sL, sR = self.tdm[i].sample(dL, dR)
                V = self.teng_m[i].step(F[i], 1e-3)
                lat = self.latch[i].update(V)
                o = self.moe[i].step(sL, sR, dt_s=1e-3)
            eh[i], vh[i], gt[i], gp[i], tv[i] = o.strain_pct - self.prestrain, o.value, o.contact, o.gate_proba, V
            ch[i] = gt[i] or (self.use_teng and lat)
            if ch[i] and not gt[i]:               # TENG 만 접촉: 유전체 추정기 (ΔL → ε, ΔR 잔차 → F)
                eh[i], vh[i] = self.diel.estimate(sL, sR)
                eh[i] -= self.prestrain
            eh[i] = (eh[i] - self.cal["b"]) / self.cal["a"]
            if ch[i]:
                vh[i] = vh[i] / self.fcal  # 힘 장착 보정 F = F̂/c (S8, B단계 R6)
        return Obs(p_mon, eh, vh, ch.astype(int), gp, tv, gt.astype(int))

    def frames(self, cam="front", w=640, h=480):
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.m, h, w)
        self._renderer.update_scene(self.d, camera=cam)
        return self._renderer.render()
