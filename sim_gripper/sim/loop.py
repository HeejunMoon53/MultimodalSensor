"""폐루프 실행기: MuJoCo(0.25 ms) ↔ 센서·MoE·제어(1 ms).

물리 → (ε, d, F) → 순방향 모델 → TDM 노이즈 → Gate-MoE → 재질 판별 → 제어기 → 액추에이터 → 물리
"""
from collections import deque
from dataclasses import replace

import numpy as np
import pandas as pd

from sim_gripper.actuators import make_actuator
from sim_gripper.control.cascade import CascadeController, CascadeParams
from sim_gripper.control.controller import CtrlParams, FingerController, GraspSupervisor
from sim_gripper.model.gripper import BellowsParams, FingerParams, GripperSim
from sim_gripper.perception.contact import DielectricEstimator, TengContact
from sim_gripper.perception.material import MaterialClassifier
from sim_gripper.perception.moe import MoE, MoeOut
from sim_gripper.sensor.forward import SensorForward, TengModel
from sim_gripper.sensor.tdm import TdmSampler

DT = 0.001
SIGMA_L, SIGMA_R = 0.116, 0.382   # noise_from_data() 결과 (세션 214746)
LIFT_H, LIFT_V = 0.04, 0.04       # 리프트 높이 [m], 속도 [m/s]
CONTACT_F = 0.05                  # 참값 접촉 판정 [N]
VIDEO_DT = 0.033
FINGERS = {"flat": FingerParams, "bellows60a": BellowsParams}
DEFAULT_ACT = {"flat": "tendon", "bellows60a": "pneumatic60a"}


def run(scenario, actuator=None, sensor_mode="pipeline", shift=None, moe_models=None,
        record_video=False, seed=0, ctrl=None, fp=None, on_step=None, finger="flat", latency_ms=0,
        ablate=(), ctrl_mode="baseline", cascade=None):
    """on_step(sim, row): 매 1 ms 호출 (실시간 뷰어용).
    latency_ms: 센서 처리 결과 → 제어기 전달 지연 (PC 경유 시스템 모사, 물리·액추에이터는 그대로).
    ablate: 모달리티 제거 — "proximity"(d̂=30 mm 고정), "material"(항상 도체), "teng"(접촉 힌트 없음), "safety".
    ctrl_mode: "baseline"(u 직접: 근접 스케줄 + admittance) | "cascade"(인장 내부 루프 + 근접·힘 외부 루프)."""
    fp = fp or FINGERS[finger]()
    # 벨로즈는 과굽힘으로 물체를 밀어내지 않고 힘 여유가 작아(200 kPa 끝단 ~6 N) u 상한 없음
    ctrl = ctrl or (CtrlParams(u_max=1.0) if finger == "bellows60a" else CtrlParams())
    actuator = actuator or DEFAULT_ACT[finger]
    if "safety" in ablate:
        ctrl = replace(ctrl, safety=False)
    delay = deque(maxlen=int(round(latency_ms)) + 1)
    sim = GripperSim(fp, scenario.obj)
    n_sub = round(DT / sim.model.opt.timestep)
    fwd = SensorForward(h_mm=fp.h_sensor_mm)
    moes = [MoE(models=moe_models) if moe_models else MoE() for _ in range(3)]
    tdms = [TdmSampler(SIGMA_L, SIGMA_R, seed + i) for i in range(3)]
    tengs = [TengModel() for _ in range(3)]
    clfs = [MaterialClassifier(fwd) for _ in range(3)]
    tcs = [TengContact() for _ in range(3)]
    diel = DielectricEstimator(fwd)
    ctrls = [FingerController(ctrl) for _ in range(3)]
    casc = CascadeController(cascade or CascadeParams.for_actuator(actuator, base=ctrl)) if ctrl_mode == "cascade" else None
    acts = [make_actuator(actuator) for _ in range(3)]
    sup = GraspSupervisor(ctrl)
    rng = np.random.default_rng(seed + 100)
    events = sorted(scenario.events)
    mat_true = scenario.obj.material

    rows, frames, lift, next_frame = [], ([] if record_video else None), sim.lift0, 0.0
    for k in range(int(round(scenario.t_end / DT))):
        t = k * DT
        cmd = None
        while events and events[0][0] <= t + 1e-9:
            cmd = events.pop(0)[1]
        kap, d_true, F_true = sim.kappa_bar_per_mm(), sim.pad_distance_mm(), sim.pad_force_N()

        outs, row = [], {"t": t}
        for i in range(3):
            eps = fwd.strain_from_curvature(kap[i])
            dL, dR = tdms[i].sample(*fwd.signals(eps, d_true[i], F_true[i], mat_true, shift, kap[i]))
            V = tengs[i].step(F_true[i], DT)
            touching = F_true[i] > CONTACT_F
            if sensor_mode == "ideal":
                val = F_true[i] if touching else d_true[i]
                m = MoeOut(eps + SIGMA_R * rng.normal(), val + SIGMA_L * rng.normal(), int(touching), float(touching))
                mat = mat_true
            else:
                hint = tcs[i].update(V)
                m = moes[i].step(dL, dR, DT, contact_hint=0 if "teng" in ablate else hint)
                mat = clfs[i].update(dL, fwd.eps_from_dR(dR), m.contact)   # 비접촉 ε: ΔR 역산
                if m.contact and mat != "conductor":       # 유전체/미정: Expert B 분포 밖 → 해석적 역산
                    m = MoeOut(*diel.estimate(dL, dR), 1, m.gate_proba)
            if "material" in ablate:
                mat = "conductor"
            if "proximity" in ablate and not m.contact:
                m = MoeOut(m.strain_pct, 30.0, 0, m.gate_proba)
            outs.append((m, mat))
            row.update({f"eps_true_{i}": eps, f"d_true_{i}": d_true[i], f"F_true_{i}": F_true[i],
                        f"dL_{i}": dL, f"dR_{i}": dR, f"V_{i}": V, f"eps_hat_{i}": m.strain_pct,
                        f"value_{i}": m.value, f"contact_{i}": m.contact, f"gate_proba_{i}": m.gate_proba,
                        f"material_{i}": mat})

        delay.append(outs)
        seen = delay[0]                                  # latency_ms 전의 센서 결과
        phase = sup.update(t, [o[0].contact for o in seen], cmd)
        if casc is None:
            u = [ctrls[i].step(seen[i][0], seen[i][1], phase, DT) for i in range(3)]
            trips = [ctrls[i].safety_trip for i in range(3)]
        else:
            u, trips = casc.step(seen, phase, DT), casc.safety_trip
            for i in range(3):
                row[f"b_ref_{i}"], row[f"F_t_{i}"] = casc.b_ref[i], casc.F_t[i]
        for i in range(3):
            row[f"u_{i}"], row[f"safety_{i}"] = u[i], int(trips[i])

        if phase == "HOLD":
            lift = min(sim.lift0 + LIFT_H, lift + LIFT_V * DT)
        dist = scenario.disturbance
        sim.apply_object_force(np.array(dist[2]) if dist and dist[0] <= t < dist[1] else np.zeros(3))

        for _ in range(n_sub):
            q = sim.joint_angles()
            tau = np.stack([acts[i].step(u[i], q[i], sim.model.opt.timestep) for i in range(3)])
            sim.step(tau, lift)

        ox, oy = sim.object_xy_m()
        row.update(phase=phase, obj_z=sim.object_height_m(), obj_x=ox, obj_y=oy, broken=sim.object_broken,
                   failed=sup.failed, mat_true=mat_true)
        rows.append(row)
        if on_step is not None:
            on_step(sim, row)
        if record_video and t >= next_frame:
            f = sim.render_frame()
            if f is not None:
                frames.append(f)
            next_frame += VIDEO_DT
    return pd.DataFrame(rows), frames
