from sim_gripper.actuators.pneumatic import PneumaticActuator
from sim_gripper.actuators.tendon import TendonActuator

# 60A 벨로즈 (Meitani & Nisar 2025): 0~200 kPa, 데드존 62 kPa (Fig.9 영점), alpha는 Fig.9·Fig.7 보정값
PNEUMATIC_60A = dict(P_max=200e3, tau_p=0.15, Pdot_max=1000e3, alpha=1.0e-5, beta=0.0, P0=62e3)


def make_actuator(kind):
    if kind == "pneumatic60a":
        return PneumaticActuator(**PNEUMATIC_60A)
    return {"tendon": TendonActuator, "pneumatic": PneumaticActuator}[kind]()
