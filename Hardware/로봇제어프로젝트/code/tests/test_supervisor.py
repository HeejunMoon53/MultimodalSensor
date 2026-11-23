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


def test_force_mode_ramps_F_ref_to_target_and_safety_exits():
    s = Supervisor(F_block=FB, Ba0=0.5, v0=20.0, eps_open=0.0, eps_pre=5.0, eps_max=20.0, grasp_mode="force")
    F = 0.0
    for k in range(400):  # 내부 힘 루프가 완벽: F = F_ref (접촉 후)
        c = int(k > 50)
        s.step(dict(d_hat=3.0, F_hat=F, contact=c, eps_hat=8.0), "conductor", "grasp")
        F = s.F_ref if s.mode == "force" else (0.01 if c else 0.0)
    assert s.state == "GRASP" and s.mode == "force"
    assert abs(s.F_ref - MATERIAL["conductor"]["Ft"] * FB) < 1e-9
    s.step(dict(d_hat=3.0, F_hat=MATERIAL["conductor"]["Fmax"] * FB * 1.1, contact=1, eps_hat=8.0), "conductor", "grasp")
    assert s.state == "SAFETY" and s.mode == "eps" and s.eps_ref <= 8.0
    for _ in range(5):  # 힘이 내려가면 GRASP 로 돌아오고 반드시 힘 모드여야 한다 (어드미턴스로 새지 않게)
        s.step(dict(d_hat=3.0, F_hat=0.5, contact=1, eps_hat=7.0), "conductor", "grasp")
    assert s.state == "GRASP" and s.mode == "force"


def test_no_grasp_on_force_noise():
    s = make()
    for k in range(300):
        s.step(dict(d_hat=3.0, F_hat=0.5 * (k % 2), contact=k % 2), "conductor", "grasp")
        assert s.state != "GRASP"


def test_lower_reflex_flag_sends_grasp_to_safety():
    s = Supervisor(F_block=FB, Ba0=0.5, v0=20.0, eps_open=0.0, eps_pre=5.0, eps_max=20.0, grasp_mode="force")
    for _ in range(5):
        s.step(dict(d_hat=0.0, F_hat=0.1, contact=1), "human", "grasp")
    assert s.state == "GRASP"
    s.step(dict(d_hat=0.0, F_hat=0.1, contact=1, reflex=1), "human", "grasp")  # 힘은 낮아도 하위가 배기했으면
    assert s.state == "SAFETY"
