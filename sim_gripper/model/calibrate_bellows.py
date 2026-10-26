"""60A 벨로즈 손가락 보정: 논문 Fig.9(자유 굽힘)·Fig.7(끝단 차단력)에 k_joint, alpha를 맞춘다.

python -m sim_gripper.model.calibrate_bellows
- 자유 굽힘: 손가락 1개, 루트 고정, 중력 포함, 각 관절에 τ = α·(P − P₀) → Δθ = Σ(q − springref).
- 차단력: 정지 상태 끝단 바로 아래 판(저울) → 압력 인가 후 판 법선력.
Δθ ≈ n·α·(P − P₀)/k 이므로 α/k는 Fig.9 기울기로 정해지고, α 크기는 차단력으로 정해진다.
"""
import numpy as np
import mujoco

from sim_gripper.actuators import PNEUMATIC_60A
from sim_gripper.model.gripper import BellowsParams

FIG9_SLOPE_DEG_PER_KPA = 0.456     # (63 − (−10)) / (200 − 40)
P0_KPA = 62.0                      # Fig.9 영점
FIG7_FORCE_N = {100e3: 4.48, 200e3: 6.28, 300e3: 10.77}
DT = 0.00025


def _model(bp, pin=None):
    """pin: 끝단 세그먼트 로컬 좌표의 고정점 — 주면 그 점을 현재 월드 위치에 connect 구속(차단력 측정)."""
    finger = bp.finger_xml(0).replace(f'pos="{bp.base_R:.5f} 0.00000 0"', 'pos="0 0 0"')
    eq = ""
    if pin is not None:
        eq = (f'<equality><connect name="pin" body1="f0_s{bp.n_joints - 1}" '
              f'anchor="{pin[0]:.6f} {pin[1]:.6f} {pin[2]:.6f}"/></equality>')
    xml = f"""<mujoco><compiler angle="radian"/><option timestep="{DT}" integrator="implicitfast"/>
      <worldbody><body name="root" pos="0 0 0.2">{finger}</body></worldbody>{eq}</mujoco>"""
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    d.qpos[:] = m.qpos_spring
    return m, d


def _settle(m, d, tau, seconds=2.0):
    for _ in range(int(seconds / DT)):
        d.qfrc_applied[:] = tau
        mujoco.mj_step(m, d)


def _torque(P, alpha):
    return alpha * max(0.0, P - P0_KPA * 1e3)


def free_bending_deg(P, bp=None, alpha=None):
    bp, alpha = bp or BellowsParams(), alpha or PNEUMATIC_60A["alpha"]
    m, d = _model(bp)
    _settle(m, d, 0.0, 1.0)
    rest = d.qpos.sum()
    _settle(m, d, _torque(P, alpha))
    return float(np.degrees(d.qpos.sum() - rest))


def blocked_force_N(P, bp=None, alpha=None):
    """끝단 차단력: 정지 자세에서 끝단 pad 중심을 공간에 고정(connect)하고 압력 인가 →
    구속 반력의 굽힘 방향(끝단 안쪽면 법선) 성분. 논문 Fig.7(저울 위 끝단)에 대응."""
    bp, alpha = bp or BellowsParams(), alpha or PNEUMATIC_60A["alpha"]
    anchor = np.array([0.001, 0.0, -bp.seg_m() / 2])            # 끝단 세그먼트 pad 바깥면 중심 (로컬)
    m, d = _model(bp, pin=anchor)
    _settle(m, d, 0.0, 1.0)
    tip = m.body(f"f0_s{bp.n_joints - 1}").id
    normal = d.xmat[tip].reshape(3, 3)[:, 0].copy()             # 안쪽면 법선(로컬 +x) = 굽힘 방향
    _settle(m, d, _torque(P, alpha), 2.0)
    rows = np.flatnonzero(d.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY)
    f_world = d.efc_force[rows][:3]                              # connect: 월드 좌표 3성분 (손가락이 받는 힘)
    return float(abs(f_world @ normal))


def calibrate():
    """α를 200 kPa 차단력 6.28 N에 맞추고 k = n·α·ΔP/Δθ(Fig.9)로 정한다(비율 고정 후 할선법)."""
    ratio = np.radians(FIG9_SLOPE_DEG_PER_KPA) / 1e3 / BellowsParams().n_joints   # α/k [rad/Pa]
    alphas, forces = [], []
    a = 2e-6
    for _ in range(6):
        bp = BellowsParams(k_joint=a / ratio)
        F = blocked_force_N(200e3, bp, a)
        alphas.append(a), forces.append(F)
        if abs(F - 6.28) < 0.05:
            break
        a = a * 6.28 / max(F, 1e-3) if len(alphas) < 2 else \
            alphas[-1] + (6.28 - forces[-1]) * (alphas[-1] - alphas[-2]) / (forces[-1] - forces[-2] + 1e-12)
    bp = BellowsParams(k_joint=alphas[-1] / ratio)
    rows = [(P / 1e3, free_bending_deg(P, bp, alphas[-1]), FIG9_SLOPE_DEG_PER_KPA * (P / 1e3 - P0_KPA))
            for P in (100e3, 150e3, 200e3)]
    frows = [(P / 1e3, blocked_force_N(P, bp, alphas[-1]), F) for P, F in FIG7_FORCE_N.items()]
    return {"alpha": alphas[-1], "k_joint": bp.k_joint, "bending": rows, "force": frows}


if __name__ == "__main__":
    r = calibrate()
    print(f"alpha = {r['alpha']:.4e} N·m/Pa, k_joint = {r['k_joint']:.4f} N·m/rad")
    for P, sim, paper in r["bending"]:
        print(f"  {P:.0f} kPa  굽힘 sim {sim:6.1f}°  Fig.9 {paper:6.1f}°")
    for P, sim, paper in r["force"]:
        print(f"  {P:.0f} kPa  차단력 sim {sim:5.2f} N  Fig.7 {paper:5.2f} N")
