"""캐스케이드 제어기 (F10 제안): 인장 내부 루프 + 근접·힘 외부 루프.

굽힘 인장 b = ε₀ − ε̂ (센서가 손가락 안쪽면에 선인장 ε₀로 붙어 있어 닫을수록 ε̂가 줄어듦).
외부 루프는 모두 b_ref를 출력 → 접근→접촉 전환이 무충격.
  근접 (접촉 전):  ḃ_ref = v(d̂ᵢ)·(d̂ᵢ + s)/(maxⱼ d̂ⱼ + s)  — 가까운 손가락을 늦춰 동시 도착
  힘   (접촉 후):  B_b·ḃ_ref = F_t − F̂                  — 인장 공간 admittance
  내부:            u = u_ff(b_ref) + K_p·e_b + K_i∫e_b,  e_b = b_ref − b̂
                   접촉 중에는 적분 동결 (admittance가 이미 적분기 → 이중 적분이면 힘 오버슈트)
  자유 운동 b_ref ∈ [b̂ − e_max, b̂ + e_max]: 손가락이 막혀도 기준이 앞서 달아나지 않음 (와인드업 방지).
물체 추정: 접촉 후 강성 k̂ = ΔF̂/Δb̂ < k_soft → F_t 축소. 미끄러짐: HOLD 중 F̂가 목표 아래로 지속 하락 → F_t 증가.
"""
from dataclasses import dataclass, field

import numpy as np

from sim_gripper.control.controller import MATERIAL_TABLE, CtrlParams

FF_U = tuple(np.linspace(0.0, 1.0, 11))
# 자유 굽힘 정상상태 b(u) [%]: 물체를 멀리 두고 u 고정 2 s (판형 95A, h = 3 mm)
FF_B = {"tendon": (0.0, 1.43, 2.85, 4.38, 5.8, 6.34, 7.59, 8.67, 9.57, 10.52, 11.12),
        "pneumatic": (0.0, 1.84, 3.56, 5.3, 6.73, 7.55, 8.53, 8.42, 9.44, 11.48, 10.24)}


@dataclass
class CascadeParams:
    base: CtrlParams = field(default_factory=CtrlParams)
    eps0: float = 15.0
    ff_b: tuple = FF_B["tendon"]
    v_far_b: float = 5.5        # [%/s] ≈ 기존 v_far 0.5/s × 11 %/u
    v_near_b: float = 1.1
    sync_floor: float = 0.2
    sync_soft_mm: float = 2.0   # (d̂ᵢ + s)/(max d̂ + s): 접촉 직전 노이즈 크기 d̂에서 비율이 흔들리지 않게
    B_b: float = 0.7            # [N·s/%] ≈ 기존 B_a 8 / 11 %/u
    e_max: float = 1.5          # 자유 운동: 기준이 손가락보다 앞서는 한계 (와인드업 방지)
    e_max_contact: float = 8.0  # 접촉: 막힌 손가락도 힘을 낼 만큼 넓게
    Kp: float = 0.03
    Ki: float = 0.6
    tau_b: float = 0.02
    k_soft: float = 0.0         # [N/%], 0 = 비활성: 판형 손가락은 손가락 자체 컴플라이언스가 지배
                                # (참값 기준 금속 1.0 · 계란 0.9 · 스펀지 0.8 N/%) → 물체 구분 불가
    soft_scale: float = 0.6
    slip_frac: float = 0.75     # HOLD 중 F̂_lp < 0.75·F_t가 slip_hold_s 지속 → 미끄러짐
    slip_hold_s: float = 0.02   # (1 kHz F̂ 미분은 노이즈 ~16 N/s라 미분 임계는 오검출)
    slip_step: float = 0.5
    slip_refractory: float = 0.2
    back_off: float = 1.0

    @classmethod
    def for_actuator(cls, actuator, base=None, **kw):
        return cls(base=base or CtrlParams(), ff_b=FF_B.get(actuator, FF_B["tendon"]), **kw)


class CascadeController:
    """그리퍼 단위 (근접 동기화에 세 손가락 d̂가 모두 필요). step → 손가락별 u."""

    def __init__(self, p, n=3):
        self.p, self.n = p, n
        self._ff_b = np.maximum.accumulate(np.asarray(p.ff_b, float))
        self.reset()

    def reset(self):
        n, bp = self.n, self.p.base
        self.u = np.full(n, bp.u_open)
        self.b_ref, self.I = np.zeros(n), np.zeros(n)
        self.F_t = np.full(n, MATERIAL_TABLE["dielectric"][0])
        self.safety_trip = [False] * n
        self._b_lp = [None] * n
        self._F_lp = [None] * n
        self._prev_contact = [None] * n
        self._onset = [None] * n          # (F₀, b₀) 접촉 시작
        self._k_done = [False] * n
        self._t_slip = np.full(n, -np.inf)
        self._t_low = np.zeros(n)
        self._t = 0.0

    def u_ff(self, b):
        return float(np.interp(b, self._ff_b, FF_U))

    def _v(self, d):
        bp = self.p.base
        s = np.clip((d - bp.d1_mm) / (bp.d0_mm - bp.d1_mm), 0.0, 1.0)
        return self.p.v_near_b + (self.p.v_far_b - self.p.v_near_b) * s

    def step(self, outs, phase, dt):
        p, bp = self.p, self.p.base
        self._t += dt
        free = [m.value for m, _ in outs if not m.contact]
        d_max = max(free) if free else 0.0
        for i, (m, mat) in enumerate(outs):
            F_tm, F_max = MATERIAL_TABLE.get(mat, MATERIAL_TABLE["dielectric"])
            contact = int(m.contact)
            b_hat = p.eps0 - m.strain_pct
            self._b_lp[i] = b_hat if self._b_lp[i] is None else self._b_lp[i] + dt / p.tau_b * (b_hat - self._b_lp[i])
            b = self._b_lp[i]
            if contact != self._prev_contact[i]:
                self._F_lp[i] = None
                self._onset[i], self._k_done[i] = None, False
                self.F_t[i] = F_tm
            self._prev_contact[i] = contact
            F_hat = m.value if contact else 0.0
            if self._F_lp[i] is None:
                F_lp, F_dot = F_hat, 0.0
            else:
                F_lp = self._F_lp[i] + dt / bp.tau_F * (F_hat - self._F_lp[i])
                F_dot = (F_lp - self._F_lp[i]) / dt
            self._F_lp[i] = F_lp if contact else None

            if not contact:
                self.F_t[i] = F_tm
            else:
                if self._onset[i] is None:
                    self._onset[i] = (F_lp, b)
                F0, b0 = self._onset[i]
                if not self._k_done[i] and F_lp - F0 > 1.0:
                    if (F_lp - F0) / max(b - b0, 0.05) < p.k_soft:
                        self.F_t[i] = F_tm * p.soft_scale
                    self._k_done[i] = True
                low = phase == "HOLD" and F_lp < p.slip_frac * self.F_t[i]
                self._t_low[i] = self._t_low[i] + dt if low else 0.0
                if self._t_low[i] >= p.slip_hold_s and self._t - self._t_slip[i] > p.slip_refractory:
                    self.F_t[i] = min(self.F_t[i] + p.slip_step, 0.8 * F_max)
                    self._t_slip[i] = self._t

            eps_ok = bp.eps_range[0] <= m.strain_pct <= bp.eps_range[1]
            if bp.safety and (not eps_ok or (contact and (F_lp > F_max or F_dot > bp.Fdot_max))):
                self.safety_trip[i] = True
            elif self.safety_trip[i] and F_lp < 0.5 * F_max:
                self.safety_trip[i] = False

            du = bp.u_rate_max * dt
            if self.safety_trip[i]:
                self.b_ref[i] = max(0.0, min(self.b_ref[i], b - p.back_off))
                self.u[i] = float(np.clip(self.u[i] - 2 * du, 0.0, bp.u_max))
                self._bumpless(i, b)
                continue
            if phase in ("OPEN", "RELEASE"):
                self.b_ref[i] = 0.0
                self.u[i] = float(np.clip(np.clip(bp.u_open, self.u[i] - du, self.u[i] + du), 0.0, bp.u_max))
                self._bumpless(i, b)
                continue
            if not contact:
                if phase == "APPROACH":
                    sync = max((max(m.value, 0.0) + p.sync_soft_mm) / (max(d_max, 0.0) + p.sync_soft_mm),
                               p.sync_floor)
                    self.b_ref[i] += self._v(m.value) * sync * dt
            else:
                e = self.F_t[i] - F_hat
                if abs(e) > bp.F_dead:
                    self.b_ref[i] += e * dt / p.B_b
            e_max = p.e_max_contact if contact else p.e_max
            self.b_ref[i] = float(np.clip(self.b_ref[i], max(b - e_max, 0.0), b + e_max))
            e_b = self.b_ref[i] - b
            I_new = self.I[i] + (0.0 if contact else p.Ki * e_b * dt)   # 접촉 중 적분은 힘 루프만
            u_ref = self.u_ff(self.b_ref[i]) + p.Kp * e_b + I_new
            if 0.0 <= u_ref <= bp.u_max:
                self.I[i] = I_new                       # 포화 시 적분 정지 (anti-windup)
            self.u[i] = float(np.clip(np.clip(u_ref, self.u[i] - du, self.u[i] + du), 0.0, bp.u_max))
        return [float(x) for x in self.u]

    def _bumpless(self, i, b):
        """PI 밖 경로 후 복귀 시 u가 튀지 않게 적분기를 현재 u에 맞춤."""
        self.I[i] = self.u[i] - self.u_ff(self.b_ref[i]) - self.p.Kp * (self.b_ref[i] - b)
