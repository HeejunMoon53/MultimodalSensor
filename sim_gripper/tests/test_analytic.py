import numpy as np
import pytest

from sim_gripper.perception.analytic import error_map, fit_empirical, invert
from sim_gripper.sensor.forward import SensorForward


@pytest.fixture(scope="module")
def fit():
    return fit_empirical(SensorForward())


def test_fit_quality(fit):
    assert fit["r2_L"] > 0.9 and fit["r2_R"] > 0.99


def test_inverts_midrange(fit):
    f = SensorForward()
    dL, dR = f.signals(12.0, 6.0, 0.0, "conductor")
    eps, d, ok = invert(fit, dL, dR)
    assert ok and abs(eps - 12.0) < 1.0 and abs(d - 6.0) < 1.5


def test_error_map_has_failure_region(fit):
    m = error_map(fit, SensorForward(), n_noise=3, seed=0)
    bad = (m["fail_rate"] > 0.5) | (m["d_err"] > 5.0)
    assert bad.mean() > 0.05                       # 해석적 역산은 일부 영역에서 실패/발산
    assert np.all(np.isfinite(m["moe_d_err"]))     # MoE는 유한·유계 출력
