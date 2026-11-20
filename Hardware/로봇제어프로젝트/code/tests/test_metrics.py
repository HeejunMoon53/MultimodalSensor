import numpy as np
import pytest

from metrics import effort, rmse, step_metrics


def test_step_metrics_on_known_response():
    t = np.arange(0, 3, 0.01)
    y = 1 - np.exp(-t / 0.1)
    m = step_metrics(t, y, np.ones_like(t))
    assert m["rise_s"] == pytest.approx(0.2197, abs=0.02)
    assert m["overshoot_pct"] == pytest.approx(0.0, abs=1e-9)
    assert m["settle_s"] == pytest.approx(0.391, abs=0.02)
    assert effort(np.array([1.0, 2.0, 2.0]))["sum_du"] == pytest.approx(1.0)
    assert rmse([1, 2], [1, 4]) == pytest.approx(np.sqrt(2))
