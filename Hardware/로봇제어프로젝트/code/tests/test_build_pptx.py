import copy

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from build_pptx import YELLOW, build

FAKE = {"det": {"lqr": {"K": [[1.2345, 0.5, 0.01]], "KI": -0.2, "Q": [1, 1, 1, 1], "R": 1.0, "gm_db": 10.0, "pm_deg": 60.0,
                        "poles": [[0.9, 0.0]]},
                "pp": {"K": [[1.0, 2.0, 3.0]], "KI": -0.1, "poles": [[0.9, 0.0]]},
                "obs": {"L": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]], "poles": [0.5, 0.4, 0.3]}, "v0": 20.0}}


def _cells(prs, idx):
    for sh in prs.slides[idx].shapes:
        if sh.has_table:
            for row in sh.table.rows:
                for c in row.cells:
                    yield c


def _title(slide):
    return next(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip())


def test_deck_has_30_slides_and_editable_diagrams(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    assert len(prs.slides) == 30
    for i in (5, 6):  # 5 = 상·하위 계층 개요, 6 = 내부 루프 상세
        assert sum(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE for sh in prs.slides[i].shapes) >= 8
    assert "상위" in _title(prs.slides[5]) and "하위" in _title(prs.slides[5])


def test_scenario_slides_follow_s7(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    titles = [_title(s) for s in prs.slides]
    i = next(k for k, t in enumerate(titles) if "S7" in t)
    assert "시나리오 1" in titles[i + 1] and "시나리오 2" in titles[i + 2] and "S10" in titles[i + 3]


def test_variable_definition_slide_lists_modes(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    txt = " ".join(c.text for c in _cells(prs, 4))
    assert "ε_f" in txt and "접촉" in txt and "F_ref" in txt


def test_gain_table_from_params(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    assert any("1.234" in c.text for c in _cells(prs, 27))


def test_missing_value_cell_is_yellow(tmp_path):
    p = copy.deepcopy(FAKE)
    del p["det"]["lqr"]["K"]
    prs = Presentation(build(tmp_path / "d.pptx", params=p))
    cell = next(c for c in _cells(prs, 27) if c.text.strip() == "?")
    assert str(cell.fill.fore_color.rgb) == YELLOW
