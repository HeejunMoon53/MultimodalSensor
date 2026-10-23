"""텐던 구동 (M6a): 모터 서보 1차 지연 + 텐던 장력 (늘어진 상태면 0).

θ̇ₘ = sat((u·θ_max − θₘ)/τₘ, ±ω_max)
T = k_t·max(0, r_p·θₘ − Σ r_j·qⱼ),  τⱼ = r_j·T
"""
import numpy as np


class TendonActuator:
    def __init__(self, r_j=0.006, r_p=0.01, k_t=2000.0, theta_max=3.0, tau_m=0.02, omega_max=10.0):
        self.r_j, self.r_p, self.k_t = r_j, r_p, k_t
        self.theta_max, self.tau_m, self.omega_max = theta_max, tau_m, omega_max
        self.reset()

    def reset(self):
        self.theta_m = 0.0

    def torque(self, q):
        T = self.k_t * max(0.0, self.r_p * self.theta_m - self.r_j * float(np.sum(q)))
        return np.full(len(q), self.r_j * T)

    def step(self, u, q, dt):
        w = np.clip((u * self.theta_max - self.theta_m) / self.tau_m, -self.omega_max, self.omega_max)
        self.theta_m += w * dt
        return self.torque(q)
