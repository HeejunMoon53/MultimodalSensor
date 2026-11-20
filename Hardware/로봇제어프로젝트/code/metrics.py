"""정량 지표 (과제 7절): 과도응답, 추종 오차, 제어 노력, 추정 오차, 개선율."""
import numpy as np


def step_metrics(t, y, r, band=0.02):  # run_compare 는 band=0.1 (센서 오차 > 2 % 띠)
    """단일 계단 응답 지표. r 은 최종 기준값 배열(마지막 값 사용), 출발점은 y[0]."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    y0, yf = y[0], float(np.asarray(r)[-1])
    span = yf - y0
    z = (y - y0) / span if span else np.zeros_like(y)
    i10, i90 = np.argmax(z >= 0.1), np.argmax(z >= 0.9)
    rise = float(t[i90] - t[i10]) if z.max() >= 0.9 else float("nan")
    over = float(max(0.0, (z.max() - 1.0) * 100.0))
    out = np.where(np.abs(z - 1.0) > band)[0]
    settle = float(t[out[-1] + 1] - t[0]) if len(out) and out[-1] + 1 < len(t) else (0.0 if not len(out) else float("nan"))
    return dict(rise_s=rise, overshoot_pct=over, settle_s=settle, ess=float(yf - y[-1]))


def effort(u):
    u = np.asarray(u, float)
    return dict(sum_u2=float(np.sum(u ** 2)), sum_du=float(np.sum(np.abs(np.diff(u)))))


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a, float) - np.asarray(b, float)) ** 2)))


def improvement_pct(base, new):
    """기준선 대비 개선율 [%] (작을수록 좋은 지표). 양수 = 개선."""
    return float(100.0 * (base - new) / base) if base else float("nan")
