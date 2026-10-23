"""제어기 (M5): 게이트 기반 상태 머신 + pre-shape 위치제어 + admittance 힘제어 + 안전 계층.

Pre-shape:  u_ref = u_open + (u_pre − u_open)·sat((d₀ − d̂)/(d₀ − d₁))
Admittance: u[k+1] = u[k] + (Tₛ/B_a)(F_t − F̂[k]),  |F_t − F̂| ≤ δF면 0
Safety:     F̂ > F_max ∨ dF̂/dt > Ḟ_max ∨ ε̂ ∉ [0,30] → 개방 방향 램프(2·u̇_max)
모든 경로에서 |Δu| ≤ u̇_max·Tₛ.
"""
from dataclasses import dataclass

import numpy as np

MATERIAL_TABLE = {"conductor": (4.0, 8.0), "dielectric": (1.5, 3.0)}   # (F_t, F_max) [N]


@dataclass
class CtrlParams:
    u_open: float = 0.0
    u_pre: float = 0.35
    d0_mm: float = 20.0
    d1_mm: float = 3.0
    u_rate_max: float = 0.8
    B_a: float = 2.0
    F_dead: float = 0.1
    Fdot_max: float = 50.0
    eps_range: tuple = (0.0, 30.0)
    grasp_timeout_s: float = 3.0


class FingerController:
    def __init__(self, p):
        self.p = p
        self.reset()

    def reset(self):
        self.u, self.safety_trip = self.p.u_open, False
        self._prev_contact, self._F_prev = None, None

    def _toward(self, u_ref, dt):
        du = self.p.u_rate_max * dt
        return float(np.clip(u_ref, self.u - du, self.u + du))

    def step(self, m, material, phase, dt):
        p = self.p
        F_t, F_max = MATERIAL_TABLE.get(material, MATERIAL_TABLE["dielectric"])
        contact = int(m.contact)
        if contact != self._prev_contact:          # 게이트 전이 → admittance 내부 상태 리셋
            self._F_prev = None
        self._prev_contact = contact
        F_hat = m.value if contact else 0.0
        F_dot = 0.0 if self._F_prev is None else (F_hat - self._F_prev) / dt
        self._F_prev = F_hat if contact else None

        eps_ok = p.eps_range[0] <= m.strain_pct <= p.eps_range[1]
        if not eps_ok or (contact and (F_hat > F_max or F_dot > p.Fdot_max)):
            self.safety_trip = True
        elif self.safety_trip and F_hat < 0.5 * F_max:
            self.safety_trip = False

        if self.safety_trip:
            u = self.u - 2 * p.u_rate_max * dt
        elif phase in ("OPEN", "RELEASE"):
            u = self._toward(p.u_open, dt)
        elif phase == "APPROACH" and not contact:
            s = np.clip((p.d0_mm - m.value) / (p.d0_mm - p.d1_mm), 0.0, 1.0)
            u = self._toward(p.u_open + (p.u_pre - p.u_open) * s, dt)
        else:                                      # APPROACH+접촉, GRASP, HOLD
            e = F_t - F_hat
            u = self._toward(self.u + (dt / p.B_a) * e if abs(e) > p.F_dead else self.u, dt)
        self.u = float(np.clip(u, 0.0, 1.0))
        return self.u


class GraspSupervisor:
    def __init__(self, p):
        self.p = p
        self.phase, self.failed, self._t_app = "OPEN", False, None

    def update(self, t, contacts, cmd):
        if cmd == "release":
            self.phase = "RELEASE"
        elif self.phase == "OPEN" and cmd == "approach":
            self.phase, self._t_app = "APPROACH", t
        elif self.phase == "APPROACH":
            if all(contacts):
                self.phase = "GRASP"
            elif t - self._t_app > self.p.grasp_timeout_s:
                self.phase, self.failed = "RELEASE", True
        elif self.phase == "GRASP" and cmd == "lift":
            self.phase = "HOLD"
        return self.phase
