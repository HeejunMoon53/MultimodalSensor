"""접촉 융합 + 유전체 접촉 추정 (M3 보강).

v4 게이트는 도체 압자 데이터로만 학습 → 유전체 접촉, 저하중(<4 N) 도체 접촉을 놓침.
- TengContact: V > v_on → 접촉 래치, 누적 전하 하락 → 해제 (TENG = 접촉 모달리티). contact = gate ∨ 래치.
- DielectricEstimator: 유전체 접촉 시 L은 거의 변형률만 반영 → ΔL에서 ε̂, ΔR 잔차에서 F̂ (보정 곡면 역산, 고정점 반복).
"""
import numpy as np

from sim_gripper.sensor.forward import K_MAT


class TengContact:
    """해제: 누적 전하 q = ∫V dt < off_frac·q_peak (분리 펄스 크기 임계는 쓰지 않음).
    τV̇ + V = gḞ → q ≈ g·F: 파지 중 출렁임엔 유지, 가벼운 접촉 후 튕김(작은 분리 펄스)도 해제."""

    def __init__(self, v_on=0.3, off_frac=0.3, dt=0.001):
        self.v_on, self.off_frac, self.dt = v_on, off_frac, dt
        self.reset()

    def reset(self):
        self.state, self.q, self.q_peak = 0, 0.0, 0.0

    def update(self, V):
        if self.state:
            self.q += V * self.dt
            self.q_peak = max(self.q_peak, self.q)
        if V > self.v_on and not self.state:
            self.state, self.q, self.q_peak = 1, V * self.dt, V * self.dt
        elif self.state and self.q < self.off_frac * self.q_peak:
            self.reset()
        return self.state


class DielectricEstimator:
    def __init__(self, fwd, n_iter=5):
        self.fwd, self.n_iter = fwd, n_iter
        self._F = fwd.F

    def estimate(self, dL, dR):
        f, eps, F = self.fwd, 15.0, 0.0
        for _ in range(self.n_iter):
            # ΔL = ΔL_ε(ε) + k_mat·ΔL_prox(ε,0) + ΔL_F(ε,F)  →  ε
            extra = K_MAT["dielectric"] * float(f._prox([[eps, 0.0]])[0]) + (float(f._LF([[eps, F]])[0]) if F > 0 else 0.0)
            eps = float(np.interp(dL - extra, f._dL_eps, f.eps))
            # ΔR − ΔR_ε(ε) = ΔR_F(ε,F)  →  F (F 방향 단조화 후 역보간)
            r = dR - float(np.interp(eps, f.eps, f._dR_eps))
            curve = np.maximum.accumulate(f._RF(np.c_[np.full(len(self._F), eps), self._F]))
            F = float(np.interp(r, curve, self._F))
        return eps, F
