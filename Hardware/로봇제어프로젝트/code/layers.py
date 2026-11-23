"""상·하위 제어기 계층 (스펙 13절).

하위 (STM32G473 + TDM 보드): TDM 1 kHz → MoE → Reflex(반사 안전), 내부 루프 100 Hz (LQG / F-LQG).
상위 (PC): 감독기 상태 머신 · 재질 · 기준 생성. 주기 n_up·T_s, 통신 지연 n_lat·T_s (가정값).
"""
from collections import deque


class Reflex:
    """하위 반사 안전 (1 kHz 샘플마다): F̂ > F_max 가 n_on 샘플 연속 → 배기(u = 0) 래치,
    F̂ < F_clr 가 n_off 샘플 연속 → 해제. 상위 감독기를 기다리지 않는다."""

    def __init__(self, F_max, F_clr, n_on=3, n_off=20):
        self.F_max, self.F_clr, self.n_on, self.n_off = F_max, F_clr, n_on, n_off
        self.tripped, self._on, self._off = False, 0, 0
        self.n_trips, self.t_trip = 0, []

    def step(self, F_hat, t=None):
        if not self.tripped:
            self._on = self._on + 1 if F_hat > self.F_max else 0
            if self._on >= self.n_on:
                self.tripped, self._off = True, 0
                self.n_trips += 1
                self.t_trip.append(t)
        else:
            self._off = self._off + 1 if F_hat < self.F_clr else 0
            if self._off >= self.n_off:
                self.tripped, self._on = False, 0
        return self.tripped


class UpperLink:
    """상위 감독기를 n_up 스텝마다, n_lat 스텝 전 관측으로 돌린다 (사이에는 기준 유지)."""

    def __init__(self, sup, n_up=5, n_lat=2):
        self.sup, self.n_up, self.k = sup, n_up, 0
        self.buf = deque(maxlen=n_lat + 1)

    def step(self, obs, material, cmd):
        self.buf.append(obs)
        if self.k % self.n_up == 0:
            self.sup.step(self.buf[0], material, cmd)
        self.k += 1
