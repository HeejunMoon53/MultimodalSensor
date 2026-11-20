import mujoco


def settle(f, m, d, p_kpa, seconds):
    for _ in range(int(seconds / m.opt.timestep)):
        f.apply_pressure(d, p_kpa)
        mujoco.mj_step(m, d)
