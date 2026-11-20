import numpy as np

from supervisor import MATERIAL, Supervisor

FB = 2.0  # F_block [N]


def make(material="conductor"):
    return Supervisor(F_block=FB, Ba0=0.5, v0=20.0, eps_open=0.0, eps_pre=5.0, eps_max=20.0)


def env_run(sup, material, k_env=0.2, eps_c=8.0, steps=3000, k_jump=None):
    """내부 루프가 완벽하다고 보고 ε = ε_ref, F = k_env·max(0, ε − ε_c)."""
    F, Fs, eps = 0.0, [], 0.0
    for k in range(steps):
        kk = k_env * (k_jump if (k_jump and k > steps // 2) else 1.0)
        F = kk * max(0.0, eps - eps_c)
        eps = sup.step(dict(d_hat=3.0, F_hat=F, contact=int(F > 0)), material, "grasp")
        Fs.append(kk * max(0.0, eps - eps_c))
    return np.array(Fs)


def test_approach_rate_limited():
    s = make(); prev = s.step(dict(d_hat=30.0, F_hat=0.0, contact=0), "conductor", "grasp")
    for k in range(200):
        d = 24.0 if k < 20 else 5.0
        e = s.step(dict(d_hat=d, F_hat=0.0, contact=0), "conductor", "grasp")
        assert abs(e - prev) <= 20.0 * MATERIAL["conductor"]["v"] * 0.01 + 1e-9
        prev = e


def test_admittance_converges_first_order_env():
    for mat in MATERIAL:
        F = env_run(make(), mat)
        Ft = MATERIAL[mat]["Ft"] * FB
        assert abs(F[-1] - Ft) <= 0.02 * FB + 1e-6, mat


def test_human_never_exceeds_fmax():
    F = env_run(make(), "human", k_jump=1.5)
    assert F.max() <= MATERIAL["human"]["Fmax"] * FB + 1e-9


def test_no_grasp_on_force_noise():
    s = make()
    for k in range(300):
        s.step(dict(d_hat=3.0, F_hat=0.5 * (k % 2), contact=k % 2), "conductor", "grasp")
        assert s.state != "GRASP"
