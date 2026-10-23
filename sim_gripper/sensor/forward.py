"""센서 순방향 모델 (M1): (ε, d, F, 재질) → ΔL, ΔR  /  TENG 모델."""
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from sim_gripper.sensor.build_tables import DEFAULT_TABLES

K_MAT = {"conductor": 1.0, "dielectric": -0.1}


@dataclass
class DomainShift:
    d_eps: float = 0.0
    gamma: float = 0.0
    scale: float = 1.0


class SensorForward:
    def __init__(self, tables_path=DEFAULT_TABLES, eps0=15.0, h_mm=3.0):
        t = np.load(tables_path)
        self.eps, self.d, self.F = t["eps"], t["d"], t["F"]
        self._dL_eps, self._dR_eps = t["dL_eps"], t["dR_eps"]
        kw = dict(bounds_error=False, fill_value=None)
        self._prox = RegularGridInterpolator((self.eps, self.d), t["dL_prox"], **kw)
        self._LF = RegularGridInterpolator((self.eps, self.F), t["dL_F"], **kw)
        self._RF = RegularGridInterpolator((self.eps, self.F), t["dR_F"], **kw)
        self.eps0, self.h_mm = eps0, h_mm

    def strain_from_curvature(self, kappa_bar_per_mm, eps0=None, h_mm=None):
        eps0 = self.eps0 if eps0 is None else eps0
        h = self.h_mm if h_mm is None else h_mm
        return float(np.clip(eps0 - 100.0 * h * kappa_bar_per_mm, 0.0, 30.0))

    def dL_eps(self, eps):
        return float(np.interp(np.clip(eps, 0, 30), self.eps, self._dL_eps))

    def signals(self, eps, d_mm, F_N, material, shift=None, kappa_bar_per_mm=0.0):
        if shift is not None:
            eps = eps + shift.d_eps
        e = float(np.clip(eps, 0.0, 30.0))
        dL = self.dL_eps(e)
        dR = float(np.interp(e, self.eps, self._dR_eps))
        if d_mm < 24.0:
            dL += K_MAT[material] * float(self._prox([[e, float(np.clip(d_mm, 0, 24))]])[0])
        f = float(np.clip(F_N, 0.0, 12.0))
        if f > 0:
            dL += float(self._LF([[e, f]])[0])
            dR += float(self._RF([[e, f]])[0])
        if shift is not None:
            dL = shift.scale * dL + shift.gamma * 100.0 * self.h_mm * kappa_bar_per_mm
            dR = shift.scale * dR
        return dL, dR


class TengModel:
    """τ·V̇ + V = g·Ḟ (후진 오일러): 접촉 시 +, 분리 시 − 피크."""

    def __init__(self, tau_s=0.05, gain=1.0):
        self.tau, self.g = tau_s, gain
        self.reset()

    def reset(self):
        self.v, self.f_prev = 0.0, None

    def step(self, F_N, dt_s):
        if self.f_prev is None:
            self.f_prev = F_N
        self.v = (self.tau * self.v + self.g * (F_N - self.f_prev)) / (self.tau + dt_s)
        self.f_prev = F_N
        return self.v
