import numpy as np

from sim_gripper.sensor.tdm import TdmSampler, noise_from_data


def test_noise_reproducible():
    a, b = TdmSampler(0.1, 0.05, seed=3), TdmSampler(0.1, 0.05, seed=3)
    assert [a.sample(1.0, 2.0) for _ in range(20)] == [b.sample(1.0, 2.0) for _ in range(20)]


def test_noise_level():
    s = TdmSampler(0.2, 0.05, seed=0)
    x = np.array([s.sample(0.0, 0.0) for _ in range(10000)])
    assert abs(x[:, 0].std() / 0.2 - 1) < 0.05 and abs(x[:, 1].std() / 0.05 - 1) < 0.05


def test_noise_from_data_positive():
    sL, sR = noise_from_data()
    assert 0 < sL < 1 and 0 < sR < 1
