import numpy as np
import pytest

from sim_gripper.perception.material import MaterialClassifier
from sim_gripper.sensor.forward import SensorForward
from sim_gripper.sensor.tdm import TdmSampler


@pytest.fixture(scope="module")
def fwd():
    return SensorForward()


def _approach(fwd, material, eps_err=0.0, seed=0, d_end=2.0):
    clf = MaterialClassifier(fwd)
    s, rng = TdmSampler(0.12, 0.38, seed), np.random.default_rng(seed + 1)
    for d in np.linspace(20, d_end, 2000):
        dL, _ = s.sample(*fwd.signals(15.0, d, 0.0, material))
        out = clf.update(dL, 15.0 + eps_err * rng.normal(), 0)
    return clf, out


def test_conductor_approach(fwd):
    assert _approach(fwd, "conductor")[1] == "conductor"


def test_dielectric_approach(fwd):
    assert _approach(fwd, "dielectric")[1] == "dielectric"


def test_far_is_unknown(fwd):
    assert _approach(fwd, "conductor", d_end=24.0)[1] == "unknown"


def test_latched_after_contact(fwd):
    clf, _ = _approach(fwd, "conductor")
    assert clf.update(-20.0, 15.0, 1) == "conductor"
    for _ in range(100):
        out = clf.update(fwd.dL_eps(15.0) + 3.0, 15.0, 1)
    assert out == "conductor"


def test_strain_error_does_not_flip_material(fwd):
    assert _approach(fwd, "dielectric", eps_err=1.5)[1] != "conductor"


@pytest.mark.parametrize("material", ["conductor", "dielectric"])
def test_material_while_bending_with_eps_from_dR(fwd, material):
    clf, s = MaterialClassifier(fwd), TdmSampler(0.12, 0.38, 3)
    for d, eps in zip(np.linspace(20, 1, 2000), np.linspace(15, 10, 2000)):
        dL, dR = s.sample(*fwd.signals(eps, d, 0.0, material))
        out = clf.update(dL, fwd.eps_from_dR(dR), 0)
    assert out == material
