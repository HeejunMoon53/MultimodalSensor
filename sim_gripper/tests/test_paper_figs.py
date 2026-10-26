import pytest

from sim_gripper.paper.diagrams import fig1_architecture, fig2_timing_budget, fig3_state_machine


@pytest.mark.parametrize("fn", [fig1_architecture, fig2_timing_budget, fig3_state_machine])
def test_diagram_writes_png_and_svg(fn, tmp_path):
    paths = fn(tmp_path)
    assert {p.suffix for p in paths} == {".png", ".svg"}
    assert all(p.exists() and p.stat().st_size > 5000 for p in paths)
