"""공압 구동 (M6b): 변화율 제한 1차 압력 + 굽힘에 따라 효율 감소.

Ṗ = sat((u·P_max − P)/τ_p, ±Pdot_max)
τⱼ = max(0, α·P·(1 − β·qⱼ))
"""
import numpy as np


class PneumaticActuator:
    def __init__(self, P_max=60e3, tau_p=0.15, Pdot_max=400e3, alpha=1.0e-5, beta=0.3):
        self.P_max, self.tau_p, self.Pdot_max = P_max, tau_p, Pdot_max
        self.alpha, self.beta = alpha, beta
        self.reset()

    def reset(self):
        self.P = 0.0

    def torque(self, q):
        return np.maximum(0.0, self.alpha * self.P * (1 - self.beta * np.asarray(q, float)))

    def step(self, u, q, dt):
        Pdot = np.clip((u * self.P_max - self.P) / self.tau_p, -self.Pdot_max, self.Pdot_max)
        self.P += Pdot * dt
        return self.torque(q)
