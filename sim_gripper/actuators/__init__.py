from sim_gripper.actuators.pneumatic import PneumaticActuator
from sim_gripper.actuators.tendon import TendonActuator


def make_actuator(kind):
    return {"tendon": TendonActuator, "pneumatic": PneumaticActuator}[kind]()
