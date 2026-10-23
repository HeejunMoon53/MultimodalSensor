"""전기적 성질 판별 (M4): 순수 변형률 성분을 뺀 ΔL 잔차의 부호.

r = ΔL − ΔL_ε(ε̂). r < −θ가 persist_steps 연속 → 도체, r > +θ 연속 → 유전체.
첫 접촉 순간의 판단을 래치. (θ=0.5 %, persist=50 ms)
"""


class MaterialClassifier:
    def __init__(self, fwd, theta=0.5, persist_steps=50):
        self.fwd, self.theta, self.persist = fwd, theta, persist_steps
        self.reset()

    def reset(self):
        self.label, self.latched = "unknown", False
        self._run_sign, self._run = 0, 0

    def update(self, dL_meas, eps_hat, contact):
        if self.latched:
            return self.label
        r = dL_meas - self.fwd.dL_eps(eps_hat)
        sign = -1 if r < -self.theta else (1 if r > self.theta else 0)
        self._run = self._run + 1 if (sign and sign == self._run_sign) else (1 if sign else 0)
        self._run_sign = sign
        if sign and self._run >= self.persist:
            self.label = "conductor" if sign < 0 else "dielectric"
        if contact:
            self.latched = True
        return self.label
