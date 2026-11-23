"""상위 루프 상태 머신 (스펙 4절, 4.1, 4.2, 11.8): 근접 스케줄 pre-shape, 속도 제한, 어드미턴스, 재질표, 안전.

출력은 손가락 하나의 기준이다. mode = "eps" 이면 ε_ref [%] (자유 모드 LQG), mode = "force" 이면 F_ref [N]
(접촉 모드 힘 추종, 스펙 12절). grasp_mode = "admittance" 는 기존 방식(F 오차 → ε_ref 적분)으로 비교용이다.
"""
import numpy as np

import paths  # noqa: F401
from design_stoch import RangeKF

# F 항목 = F_block 배수, Ba·v = 기준값 배수 (모두 가정값, 노란 칸)
MATERIAL = {
    "conductor": dict(Ft=0.5, Fmax=0.8, Ba=1.0, v=1.0),
    "dielectric": dict(Ft=0.35, Fmax=0.6, Ba=1.5, v=0.7),
    "human": dict(Ft=0.15, Fmax=0.3, Ba=3.0, v=0.4),
}
N_CONFIRM = 3  # 게이트 접촉이 연속 3 샘플일 때만 전이 (잡음 방지)


class Supervisor:
    def __init__(self, F_block, Ba0, v0, eps_open, eps_pre, eps_max, d_far=24.0, d_near=5.0,
                 Ts=0.01, t_min=0.2, dFdt_max_human=None, dF_dead=0.02, grasp_mode="admittance", t_ramp=0.5):
        self.FB, self.Ba0, self.v0 = F_block, Ba0, v0
        self.eps_open, self.eps_pre, self.eps_max = eps_open, eps_pre, eps_max
        self.d_far, self.d_near, self.Ts, self.t_min = d_far, d_near, Ts, t_min
        self.dFdt_h = dFdt_max_human if dFdt_max_human is not None else 0.5 * F_block
        self.dF_dead = dF_dead * F_block
        self.grasp_mode, self.t_ramp = grasp_mode, t_ramp
        self.reset()

    def reset(self):
        self.state, self.eps_ref, self.eps_c = "OPEN", self.eps_open, None
        self.n_on = self.n_off = 0
        self.F_prev = 0.0
        self.rkf = RangeKF(self.Ts, 200.0, 0.5)
        self.d_dot = 0.0
        self.mode, self.F_ref = "eps", 0.0

    def g(self, d):
        """근접 스케줄: 가까울수록 미리 굽힌다 (sat 선형)."""
        s = np.clip((self.d_far - d) / (self.d_far - self.d_near), 0.0, 1.0)
        return self.eps_open + (self.eps_pre - self.eps_open) * s

    def _move(self, target, rate):
        step = float(np.clip(target - self.eps_ref, -rate * self.Ts, rate * self.Ts))
        self.eps_ref += step

    def step(self, obs, material, cmd="grasp"):
        """cmd: "approach" = pre-shape 만, "grasp" = 닫기 허용(근접 없어도 천천히), "release"."""
        m = MATERIAL[material]
        v = self.v0 * m["v"]
        d, F, c = float(obs["d_hat"]), float(obs["F_hat"]), int(obs["contact"])
        eps_meas = float(obs.get("eps_hat", self.eps_ref))
        if not c:
            d, self.d_dot = self.rkf.step(d)
        self.n_on, self.n_off = (self.n_on + 1, 0) if c else (0, self.n_off + 1)
        Ft, Fmax = m["Ft"] * self.FB, m["Fmax"] * self.FB
        dFdt = (F - self.F_prev) / self.Ts
        self.F_prev = F

        if cmd == "release" and self.state not in ("OPEN", "RELEASE"):
            self.state = "RELEASE"
        if self.state in ("GRASP", "CONTACT") and (F > Fmax or self.eps_ref > self.eps_max or obs.get("reflex", 0)):  # reflex = 하위 배기 알림
            self.state = "SAFETY"
        if self.mode == "force" and self.state != "GRASP":  # 힘 모드를 떠나면 ε 기준을 현재 측정에서 이어 받는다
            self.mode, self.eps_ref = "eps", min(eps_meas, self.eps_max)

        if self.state == "OPEN":
            self._move(self.eps_open, v)
            if cmd == "grasp" or (cmd == "approach" and d < self.d_far):
                self.state = "APPROACH"
        elif self.state == "APPROACH":
            if d <= self.d_near or cmd == "grasp":
                self._move(self.eps_max, 0.3 * v)  # 근접 끝 또는 파지 명령: 천천히 닫아 접촉을 만든다
            else:
                t_c = d / -self.d_dot if self.d_dot < -1e-3 else np.inf
                rate = abs(self.g(d) - self.eps_ref) / max(t_c, self.t_min)
                self._move(self.g(d), min(v, rate) if np.isfinite(t_c) else v)
            if self.n_on >= N_CONFIRM:
                self.state, self.eps_c = "GRASP", self.eps_ref
                if self.grasp_mode == "force":
                    self.mode, self.F_ref = "force", max(F, 0.0)
        elif self.state == "GRASP" and self.mode == "force":
            rate = (self.dFdt_h if material == "human" else Ft / self.t_ramp) * self.Ts
            self.F_ref = float(self.F_ref + np.clip(Ft - self.F_ref, -rate, rate))
            if self.n_off >= N_CONFIRM:
                self.state, self.mode, self.eps_ref = "APPROACH", "eps", min(eps_meas, self.eps_max)
        elif self.state == "GRASP":
            e = Ft - F
            if abs(e) <= self.dF_dead:
                e = 0.0
            de = self.Ts / (self.Ba0 * m["Ba"]) * e
            if material == "human" and dFdt > self.dFdt_h:
                de = min(de, 0.0)  # 힘 증가율 상한
            self._move(self.eps_ref + de, v)
            if self.n_off >= N_CONFIRM:
                self.state = "APPROACH"
        elif self.state == "SAFETY":
            self._move(-np.inf, v)
            if F <= Ft and self.eps_ref <= self.eps_max and not obs.get("reflex", 0):
                self.state = "GRASP"
                if self.grasp_mode == "force":  # 힘 모드로 복귀 (현재 힘에서 다시 경사)
                    self.mode, self.F_ref = "force", max(min(F, Ft), 0.0)
        elif self.state == "RELEASE":
            self._move(self.eps_open, 0.5 * self.v0)
            if abs(self.eps_ref - self.eps_open) < 1e-9:
                self.state = "OPEN"
        self.eps_ref = float(np.clip(self.eps_ref, min(self.eps_open, 0.0), self.eps_max))
        return self.eps_ref
