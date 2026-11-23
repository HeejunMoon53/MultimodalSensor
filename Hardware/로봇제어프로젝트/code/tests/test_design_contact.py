import numpy as np

from design_contact import ContactLqg, Rls, contact_lqr, contact_obsv, make_schedule
from design_det import load_model
from paths import load_params

P = load_params()
Ad, Bd, C, Ts, x0, u0, phys = load_model(P)


def test_rls_recovers_line():
    rng = np.random.default_rng(0)
    r = Rls(theta0=[1.0, 0.0], lam=0.995)
    for _ in range(2000):
        x = rng.uniform(5, 15)
        r.update([x, 1.0], 0.4 * x - 2.0 + 0.01 * rng.standard_normal())
    assert np.allclose(r.theta, [0.4, -2.0], rtol=0.03, atol=0.05)


def test_contact_lqr_stable_over_grid():
    for k in (0.2, 0.35, 0.5, 0.8):
        K, KI, Aa, Ba = contact_lqr(Ad, Bd, k)
        Kf = np.c_[K, [[KI]]]
        assert np.max(np.abs(np.linalg.eigvals(Aa - Ba @ Kf))) < 1.0, k


def test_schedule_matches_direct_design():
    sch = make_schedule(Ad, Bd, [0.2, 0.4, 0.8])
    K, KI = sch(0.4)
    Kd, KId, _, _ = contact_lqr(Ad, Bd, 0.4)
    assert np.allclose(K, Kd) and np.isclose(KI, KId)
    K3, KI3 = sch(0.3)  # 사이값: 이웃 설계 사이
    assert min(KI, sch(0.2)[1]) - 1e-12 <= KI3 <= max(KI, sch(0.2)[1]) + 1e-12


def test_eps_only_observability_collapses_for_blocked_finger():
    s_eps = contact_obsv(Ad, k_eq=0.4, g=0.01)["eps"]
    s_F = contact_obsv(Ad, k_eq=0.4, g=0.01)["F"]
    assert s_eps < 1e-3 * s_F


def _synthetic_run(k_true, use_rls, eps_c=5.0, F_ref=2.0, n=1500):  # ε_c 5 %: F=2 N 이 30 kPa 안에서 가능
    """식별 모델을 플랜트로: x⁺ = A x + B u (편차), F = k_true (ε_f − ε_c)."""
    sch = make_schedule(Ad, Bd, [0.2, 0.35, 0.5, 0.8])
    V = np.array(P["noise"]["var"])
    c = ContactLqg(Ad, Bd, x0, u0, phys, sch, k_nom=0.5, V_p=V[0], V_F=0.01, W=np.array(P["stoch"]["W"]), use_rls=use_rls)
    ef_c = eps_c
    p_c = x0[0] + (ef_c - x0[1]) / phys["K_f"]       # 정지 상태에서 접촉 시작
    x = np.array([p_c - x0[0], ef_c - x0[1]])
    u_prev = u0 + (p_c - x0[0]) / phys["K_p"]
    c.enter(np.array([p_c, ef_c]), u_prev)
    Fs, us = [], []
    for k in range(n):
        p, ef = x + x0
        F = max(0.0, k_true * (ef - eps_c))
        u = c.u(p, F, F_ref)
        us.append(u); Fs.append(F)
        x = Ad @ x + Bd[:, 0] * (u - u0)
    return np.array(Fs), np.array(us), c, u_prev


def test_rls_does_not_run_away_on_noisy_unexcited_force():
    """진입 직후 ε_f 가 거의 안 움직이고 F̂ 가 잡음뿐이면 k̂ 은 공칭 근처·격자 안에 머문다."""
    sch = make_schedule(Ad, Bd, [0.25, 0.5, 0.75])
    rng = np.random.default_rng(1)
    c = ContactLqg(Ad, Bd, x0, u0, phys, sch, k_nom=0.5, V_p=0.003, V_F=0.06, W=np.array(P["stoch"]["W"]), use_rls=True)
    c.enter(x0 + np.array([2.0, 1.0]), u0 + 2.0)
    for k in range(150):  # 접촉 직후 1.5 s: ε_f 는 오르는데 F̂ 는 (TENG 추정기 등) 잘못된 평평한 값
        c.efm = 1.0 + 0.03 * k
        c.u(x0[0] + 2.0, 2.4 + 0.25 * rng.standard_normal(), F_ref=1.0)
    assert 0.25 <= c.k_eq <= 0.75
    assert abs(-c.c / c.k_eq - (x0[1] + 1.0)) <= 4.0 + 1e-9   # ε̂_c 도 진입값 ± 4 % 안


def test_contact_lqg_bumpless_entry():
    _, us, _, u_prev = _synthetic_run(0.5, False)
    assert abs(us[0] - u_prev) < 0.5


def test_contact_lqg_tracks_force_despite_keq_error():
    for rls in (False, True):
        F, _, c, _ = _synthetic_run(0.3, rls)
        assert abs(F[-200:].mean() - 2.0) < 0.05, rls
    assert abs(c.k_eq - 0.3) < 0.1   # 공칭 0.5 → 참 0.3 쪽으로 이동. 일정 F_ref 에선 과도 구간만 정보라 완전 수렴은 안 함 (여기 부족)
