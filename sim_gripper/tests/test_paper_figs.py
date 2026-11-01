import pytest

from sim_gripper.paper.diagrams import fig1_architecture, fig2_timing_budget, fig3_state_machine


@pytest.mark.parametrize("fn", [fig1_architecture, fig2_timing_budget, fig3_state_machine])
def test_diagram_writes_png_and_svg(fn, tmp_path):
    paths = fn(tmp_path)
    assert {p.suffix for p in paths} == {".png", ".svg"}
    assert all(p.exists() and p.stat().st_size > 5000 for p in paths)


def test_run_cache_key_distinguishes_approach_speed():
    from sim_gripper.control.controller import CtrlParams
    from sim_gripper.paper.figures import _key
    assert _key("E1_metal", ctrl=CtrlParams()) != _key("E1_metal", ctrl=CtrlParams(v_far=0.1))
    assert _key("E1_metal") == _key("E1_metal")


def test_guide_has_all_figures(tmp_path):
    from docx import Document

    from sim_gripper.paper.guide import FIGS, build_guide
    doc = Document(str(build_guide(tmp_path)))
    heads = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert all(title in heads for _, title in FIGS) and len(FIGS) == 9
