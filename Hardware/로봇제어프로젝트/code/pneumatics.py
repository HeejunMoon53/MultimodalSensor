"""공압 경로: ITV1030 전공 레귤레이터 모델 + 튜브·방 용량 모델.

단위: 압력 kPa(게이지), 체적 mm³, 시간 s.
ITV 비이상성(스펙 2.3): 순수 지연 θ_v, 데드밴드 p_db(처음 열릴 때 +quant 튐),
감도 계단 quant(정격 0.5 MPa × 0.2 % F.S. = 1 kPa), 1차 지연 τ_v, 변화율 제한, 포화, 모니터 잡음.
"""
from collections import deque

import numpy as np

P_ATM = 101.3


class Itv:
    def __init__(self, tau_v=0.05, theta_v=0.01, p_db=0.3, quant=1.0, p_max=30.0, rate_max=200.0,
                 mon_sigma=0.05, seed=0, ideal=False):
        self.tau_v, self.theta_v, self.p_db, self.quant = tau_v, theta_v, p_db, quant
        self.p_max, self.rate_max, self.mon_sigma, self.ideal = p_max, rate_max, mon_sigma, ideal
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self):
        self.p_lag = 0.0
        self.kick = 0.0
        self.opened = False
        self.buf = None

    def step(self, u_kpa, dt):
        u = 0.0 if not np.isfinite(u_kpa) else float(np.clip(u_kpa, 0.0, self.p_max))
        if self.ideal:
            self.p_lag += (u - self.p_lag) * (1.0 - np.exp(-dt / self.tau_v))
            return self.p_lag
        if self.buf is None:
            self.buf = deque([0.0] * max(1, int(round(self.theta_v / dt))))
        self.buf.append(u)
        u = self.buf.popleft()
        if u < self.p_db:
            target, self.opened = 0.0, False
        else:
            target = round(u / self.quant) * self.quant
            if not self.opened:
                self.opened, self.kick = True, self.quant  # 급기 밸브가 처음 열릴 때 튐
        dp = (target - self.p_lag) * (1.0 - np.exp(-dt / self.tau_v))
        self.p_lag += float(np.clip(dp, -self.rate_max * dt, self.rate_max * dt))
        self.kick *= np.exp(-dt / self.tau_v)
        return self.output()

    def output(self):
        return float(np.clip(self.p_lag + (0.0 if self.ideal else self.kick), 0.0, self.p_max))

    def monitor(self):
        if self.ideal:
            return self.output()
        return self.output() + self.mon_sigma * float(self.rng.normal())


class Line:
    """튜브 저항 R_t와 방 용량 C로 이루어진 1차 공압 RC.

    C(p_c)·ṗ_c = (p − p_c)/R_t,  C = dV/dp + V/(κ·(p_c + p_atm))
    R_t 단위: kPa·s/mm³ (유량 [mm³/s] = Δp / R_t). 후진 오일러로 적분한다.
    """

    def __init__(self, R_t=2.0e-4, kappa=1.0):
        self.R_t, self.kappa = R_t, kappa
        self.reset()

    def reset(self):
        self.p_c = 0.0

    def step(self, p, V_mm3, dVdp, dt):
        C = max(dVdp, 0.0) + V_mm3 / (self.kappa * (self.p_c + P_ATM))
        tau = self.R_t * max(C, 1e-9)
        self.p_c += dt / (tau + dt) * (p - self.p_c)
        return self.p_c
