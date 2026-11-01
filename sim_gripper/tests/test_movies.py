import imageio.v2 as imageio
import numpy as np
import pandas as pd

from sim_gripper.paper.movies import approach_time, compose_grid, compose_s1, snapshot_times


def _df(n=10000):
    t = np.arange(n) * 0.001
    phase = np.select([t < 0.5, t < 1.2, t < 4.0, t < 8.0], ["OPEN", "APPROACH", "GRASP", "HOLD"], "RELEASE")
    d = {"t": t, "phase": phase, "obj_z": 0.04 + 0.04 * (phase == "HOLD"), "broken": False, "failed": False,
         "mat_true": "dielectric"}
    for i, tc in enumerate((1.0, 1.1, 1.2)):
        touch = (t >= tc) & (phase != "RELEASE")
        d.update({f"F_true_{i}": np.where(touch, 1.5, 0.0), f"d_true_{i}": np.where(touch, 0.0, 20.0),
                  f"value_{i}": np.where(touch, 1.4, 19.0), f"contact_{i}": touch.astype(int),
                  f"dL_{i}": np.sin(t), f"dR_{i}": np.cos(t), f"V_{i}": 0.1 * np.sin(5 * t),
                  f"eps_true_{i}": 12.0 + 0 * t, f"eps_hat_{i}": 12.1 + 0 * t, f"u_{i}": 0.1 + 0 * t,
                  f"material_{i}": np.where(touch, "dielectric", "unknown")})
    return pd.DataFrame(d)


def test_approach_time_until_all_fingers_touch():
    assert abs(approach_time(_df()) - 0.7) < 2e-3


def test_snapshot_times_follow_phases():
    df = _df()
    snaps = snapshot_times(df)
    ts = [t for t, _ in snaps]
    assert len(snaps) == 5 and ts == sorted(ts)
    ph = dict(zip(df.t.round(3), df.phase))
    assert [ph[round(t, 3)] for t in ts] == ["APPROACH", "GRASP", "GRASP", "HOLD", "RELEASE"]


def test_compose_writes_video_and_preview(tmp_path):
    df = _df()
    frames = [np.full((48, 64, 3), k * 60, np.uint8) for k in range(4)]
    times = [0.0, 1.0, 2.0, 3.0]
    p = compose_s1(df, frames, times, tmp_path / "s1.mp4", "test")
    assert len(imageio.mimread(str(p), memtest=False)) == 4
    assert (tmp_path / "s1.gif").exists()
    g = compose_grid([("full", df, frames), ("− TENG", df, frames)], times, tmp_path / "s2.mp4")
    assert len(imageio.mimread(str(g), memtest=False)) == 4
