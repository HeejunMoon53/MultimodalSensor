import numpy as np

from layers import Reflex, UpperLink
from plant import Plant, Scenario


def test_reflex_trips_after_n_on_and_clears_after_n_off():
    r = Reflex(F_max=1.0, F_clr=0.5, n_on=3, n_off=4)
    assert [r.step(1.5) for _ in range(3)] == [False, False, True]
    assert r.step(2.0) and r.step(0.4) and r.step(0.4) and r.step(0.4)
    assert r.step(0.4) is False          # 4 샘플 연속 F_clr 아래 → 해제
    assert r.n_trips == 1


def test_reflex_ignores_single_spike():
    r = Reflex(F_max=1.0, F_clr=0.5, n_on=3)
    assert not any(r.step(F) for F in (2.0, 0.0, 2.0, 2.0, 0.0))


def _close(reflex, steps=150):
    pl = Plant(Scenario(fingers=1, obj_start_mm=(0, 0, -70)), seed=4)
    if reflex is not None:
        pl.reflex = [reflex]
    rec = []
    for _ in range(steps):
        pl.step(np.array([30.0]))
        rec.append((pl.truth().p[0], pl.truth().eps[0]))
    return pl, np.array(rec)


def test_plant_reflex_vents_itv_when_force_exceeds():
    pl, rec = _close(Reflex(F_max=0.3, F_clr=0.1))
    assert pl.reflex[0].n_trips >= 1 and pl.reflex[0].t_trip[0] < 1.5
    assert rec[-1, 0] < 10.0             # 지령 30 kPa 인데 배기


def test_plant_reflex_without_trip_keeps_mechanics():
    _, a = _close(None, 60)
    _, b = _close(Reflex(F_max=np.inf, F_clr=0.0), 60)
    assert np.allclose(a, b)             # 센서 샘플 시점만 다르고 역학은 같다


class _Rec:
    def __init__(self):
        self.calls = []

    def step(self, obs, mat, cmd):
        self.calls.append(obs["k"])


def test_upper_link_rate_and_latency():
    sup = _Rec()
    up = UpperLink(sup, n_up=5, n_lat=2)
    for k in range(12):
        up.step(dict(k=k), "human", "grasp")
    assert sup.calls == [0, 3, 8]        # 5 스텝마다, 2 스텝 전 관측
