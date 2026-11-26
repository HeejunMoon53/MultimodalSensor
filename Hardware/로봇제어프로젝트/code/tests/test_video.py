import numpy as np

from run_compare import approach_path


def test_handover_path_sags_only_after_hand_lets_go():
    from run_video import handover_path
    base, f = approach_path("conductor"), handover_path(t_hand=6.5, sag=3.0, t_sag=0.3)
    assert f(6.4) == base(6.4)
    assert np.isclose(f(7.5)[2], base(7.5)[2] - 3.0)


def test_phase_label_follows_upper_state_and_events():
    from run_video import phase_label
    assert phase_label("OPEN", False, False, False) == "대기"
    assert "근접" in phase_label("APPROACH", False, False, False)
    assert "힘 추종" in phase_label("GRASP", False, False, False)
    assert "하중" in phase_label("GRASP", False, True, False)
    assert "반사" in phase_label("GRASP", True, False, False)
    assert "반사" in phase_label("SAFETY", False, False, False)


def test_short_run_writes_log_and_dashboard_frame(tmp_path):
    from run_video import run
    log, frame = run("B", seconds=0.4, out_dir=tmp_path, fps=10, w=320, h=240)
    assert len(log["t"]) == 40 and {"F_hat", "d_hat", "u", "state", "teng"} <= set(log)
    assert frame.ndim == 3 and frame.shape[0] == 240 and frame.shape[1] > 320
    assert (tmp_path / "V_B.mp4").exists() and (tmp_path / "V_B.csv").exists()
