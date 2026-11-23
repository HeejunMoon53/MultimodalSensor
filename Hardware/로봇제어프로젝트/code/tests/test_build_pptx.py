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


def test_deck_has_26_slides_and_editable_diagram(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    assert len(prs.slides) == 26
    assert sum(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE for sh in prs.slides[5].shapes) >= 8


def test_variable_definition_slide_lists_modes(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    txt = " ".join(c.text for c in _cells(prs, 4))
    assert "ε_f" in txt and "접촉" in txt and "F_ref" in txt


def test_gain_table_from_params(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    assert any("1.234" in c.text for c in _cells(prs, 23))


def test_missing_value_cell_is_yellow(tmp_path):
    p = copy.deepcopy(FAKE)
    del p["det"]["lqr"]["K"]
    prs = Presentation(build(tmp_path / "d.pptx", params=p))
    cell = next(c for c in _cells(prs, 23) if c.text.strip() == "?")
    assert str(cell.fill.fore_color.rgb) == YELLOW
