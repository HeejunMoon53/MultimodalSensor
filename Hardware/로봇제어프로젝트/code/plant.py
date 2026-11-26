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
# 물체 컴플라이언스 k_obj [N/mm] (가정값, 노란 칸): None = 강체. 무른 물체는 스프링 패드 2개(손가락별)로 만든다
OBJ_K = {"conductor": None, "dielectric": 2.0, "human": 0.7}
PAD_TRAVEL_MM = 12.0


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
    obj_k_N_mm: object = "material"       # 물체 강성 [N/mm]: "material" = OBJ_K[재질], None = 강체
    photo: Optional[str] = None           # 사진형 렌더 소품 (photo_scene.deco: "hammer" | "wrist"), 물리 불변


@dataclass
class Obs:
    p_mon: np.ndarray
    eps_hat: np.ndarray
    val_hat: np.ndarray
    contact: np.ndarray
    gate_p: np.ndarray
    teng: np.ndarray = None      # TENG 전압 (마지막 1 kHz 샘플)
    gate: np.ndarray = None      # MoE 게이트만의 접촉 판정
    LR: np.ndarray = None        # TDM 원신호 [ΔL, ΔR] (손가락별, 마지막 1 kHz 샘플)


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
        self.reflex = None  # 손가락별 layers.Reflex (하위 반사 안전, 1 kHz). None = 기존 경로 (10 ms 끝에 센서 일괄)
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
        shp = lambda rr, extra="": ((f'<geom type="cylinder" size="{rr} 0.04" euler="1.5708 0 0"' if s.obj_kind == "cylinder"
                                     else f'<geom type="sphere" size="{rr}"') + extra)
        col = f' solref="{SOLREF[s.material]} 1" condim="3" contype="2" conaffinity="1"/>'
        k = OBJ_K[s.material] if s.obj_k_N_mm == "material" else s.obj_k_N_mm
        self.obj_k = k
        if k is None:
            geom = shp(r, ' rgba="0.6 0.65 0.75 1"' + col)
        else:  # 무른 물체: 손가락 쪽 반쪽 패드(슬라이드 + 스프링) 2개. 패드끼리는 충돌 안 함 (contype 2 & conaffinity 1)
            tr = min(PAD_TRAVEL_MM * 1e-3, 0.8 * r); dl = tr / 2 + 0.001  # 2δ > 이동량: 손가락 A 가 패드 B 에 닿지 않게
            kk, mp = k * 1e3, 0.05
            cc = 2 * np.sqrt(kk * mp)
            pad = lambda nm, sx, rng: (f'<body name="{nm}" pos="{sx * dl} 0 0"><joint name="{nm}_j" type="slide" axis="1 0 0" '
                                       f'stiffness="{kk}" damping="{cc}" limited="true" range="{rng}"/>'
                                       + shp(r - dl, f' mass="{mp}" rgba="0.85 0.62 0.55 1"' + col) + '</body>')
            geom = (shp(r * 0.5, ' rgba="0.5 0.5 0.55 1" contype="0" conaffinity="0"/>')
                    + pad("padA", -1, f"0 {tr}") + pad("padB", 1, f"{-tr} 0"))
        x0 = np.array(s.obj_start_mm) * 1e-3
        d_asset, d_vis, d_world, d_obj = ("",) * 4
        if s.photo:
            from photo_scene import deco
            d_asset, d_vis, d_world, d_obj = deco(s.photo)
            geom = geom + d_obj
        xml = (f'<mujoco><compiler angle="radian"/>'
               f'<option timestep="{self.dt}" gravity="0 0 -9.81" solver="Newton" integrator="discrete"/>'
               f'{d_asset}<visual><global offwidth="1280" offheight="960"/>{d_vis}</visual>'
               f'<worldbody>{d_world}<light pos="0 -0.4 0.3" dir="0 1 -0.6"/><light pos="0.3 0 0.3" dir="-1 0 -1"/>'
               f'<camera name="front" pos="0 -0.38 -0.07" xyaxes="1 0 0 0 0 1"/>'
               f'<body name="hub" pos="0 0 0.008"><geom type="box" size="0.06 0.03 0.008" rgba="0.3 0.3 0.32 1" contype="0" conaffinity="0"/></body>'
               f'<body name="obj" mocap="true" pos="{x0[0]} {x0[1]} {x0[2]}">{geom}</body>'
               + "".join(parts) + "</worldbody></mujoco>")
        self.m = mujoco.MjModel.from_xml_string(xml)
        self.d = mujoco.MjData(self.m)
        for i, f in enumerate(self.fingers):
            f.attach(self.m, self.d, f"finger{i}")
        ob = {mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, n) for n in ("obj", "padA", "padB")} - {-1}
        self.obj_geoms = {g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] in ob}
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
            if (c.geom[0] in self.obj_geoms or c.geom[1] in self.obj_geoms) and mine:
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
        n = self.scn.fingers
        p = np.zeros(n)
        rx = self.reflex if self.nonideal else None
        sensed = [None] * n
        for _ in range(self.n_sub):
            if self.scn.obj_path is not None:
                self.d.mocap_pos[0] = np.array(self.scn.obj_path(self.t)) * 1e-3
            for i, f in enumerate(self.fingers):
                p[i] = self.itv[i].step(0.0 if rx is not None and rx[i].tripped else u[i], self.dt)  # 반사: ITV 배기
                V = f.chamber_volume(self.d)
                pc = self.line[i].step(p[i], V, self._dVdp(self.line[i].p_c), self.dt)
                f.apply_pressure(self.d, pc)
                if self.scn.tip_load_N:
                    self.d.xfrc_applied[f.tip_body, :3] = np.array([0, 0, -self.scn.tip_load_N])
                elif hasattr(f, "contact_geoms"):
                    self.d.xfrc_applied[f.tip_body, :3] = 0.0
            mujoco.mj_step(self.m, self.d)
            self.t += self.dt
            if rx is not None:  # 하위 제어기: 물리 스텝마다 TDM 샘플을 받아 반사 판정
                eps, F, dist = self._measure()
                sensed = [self._sense(i, eps[i], dist[i], F[i], int(round(self.dt / 1e-3)), rx[i]) for i in range(n)]
        self._check()
        return self._observe(sensed if rx is not None else None)

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

    def _measure(self):
        n = self.scn.fingers
        return (np.array([f.sensor_strain(self.d) for f in self.fingers]),
                np.array([self._contact_force(i) for i in range(n)]), np.array([self._distance(i) for i in range(n)]))

    def _sense(self, i, eps, dist, F, n_samp, rx=None):
        """TDM 1 kHz 샘플 n_samp 개 → MoE·TENG. rx 가 있으면 샘플마다 반사 판정 (F̂ 1 kHz)."""
        mat = "conductor" if self.scn.material == "human" else self.scn.material  # shortcut: 인체 K_MAT 미정, B단계 R1에서 교체
        d_eff = 0.0 if F > 1e-3 else dist  # 접촉 중이면 접촉점 간격 0 (센서 중심 거리 아님)
        dL, dR = self.fwd.signals(eps + self.prestrain, d_eff, F, mat)
        for _ in range(n_samp):
            sL, sR = self.tdm[i].sample(dL, dR)
            V = self.teng_m[i].step(F, 1e-3)
            lat = self.latch[i].update(V)
            o = self.moe[i].step(sL, sR, dt_s=1e-3)
            if rx is not None:
                F1 = (o.value if o.contact else self.diel.estimate(sL, sR)[1]) if (o.contact or (self.use_teng and lat)) else 0.0
                rx.step(F1 / self.fcal, self.t)
        return o, V, lat, sL, sR

    def _observe(self, sensed=None):
        n = self.scn.fingers
        eps, F, dist = self._measure()
        self._truth = Truth(p=np.array([it.output() for it in self.itv]), p_c=np.array([ln.p_c for ln in self.line]),
                            eps=eps, eps_dot=(eps - self._eps_prev) / TS, d_mm=dist, F_N=F,
                            tip_deg=np.array([f.tip_angle(self.d) for f in self.fingers]))
        self._eps_prev = eps
        p_mon = np.array([it.monitor() for it in self.itv])
        if not self.nonideal:
            contact = (F > 1e-3).astype(int)
            return Obs(p_mon, eps.copy(), np.where(contact, F, dist), contact, contact.astype(float))
        eh, vh, ch, gp, tv, gt = (np.zeros(n) for _ in range(6))
        lr = np.zeros((n, 2))
        for i in range(n):
            o, V, lat, sL, sR = sensed[i] if sensed is not None else self._sense(i, eps[i], dist[i], F[i], int(round(TS / 1e-3)))
            eh[i], vh[i], gt[i], gp[i], tv[i] = o.strain_pct - self.prestrain, o.value, o.contact, o.gate_proba, V
            lr[i] = sL, sR
            ch[i] = gt[i] or (self.use_teng and lat)
            if ch[i] and not gt[i]:               # TENG 만 접촉: 유전체 추정기 (ΔL → ε, ΔR 잔차 → F)
                eh[i], vh[i] = self.diel.estimate(sL, sR)
                eh[i] -= self.prestrain
            eh[i] = (eh[i] - self.cal["b"]) / self.cal["a"]
            if ch[i]:
                vh[i] = vh[i] / self.fcal  # 힘 장착 보정 F = F̂/c (S8, B단계 R6)
        return Obs(p_mon, eh, vh, ch.astype(int), gp, tv, gt.astype(int), lr)

    def frames(self, cam="front", w=640, h=480):
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.m, h, w)
        self._renderer.update_scene(self.d, camera=cam)
        return self._renderer.render()
