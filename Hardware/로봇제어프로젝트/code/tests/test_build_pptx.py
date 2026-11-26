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


def test_deck_has_35_slides_and_editable_diagrams(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    assert len(prs.slides) == 35
    for i in (5, 6):  # 5 = 상·하위 계층 개요, 6 = 내부 루프 상세
        assert sum(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE for sh in prs.slides[i].shapes) >= 8
    assert "상위" in _title(prs.slides[5]) and "하위" in _title(prs.slides[5])


def test_scenario_slides_follow_s7(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    titles = [_title(s) for s in prs.slides]
    i = next(k for k, t in enumerate(titles) if "S7" in t)
    assert "그림" in titles[i + 1] and "사진" in titles[i + 2] and "시나리오 1" in titles[i + 3]
    assert "시나리오 2" in titles[i + 4] and "S10" in titles[i + 5]


def test_photo_slide_shows_both_rows(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    titles = [_title(s) for s in prs.slides]
    s = prs.slides[next(k for k, t in enumerate(titles) if "사진" in t)]
    txt = _texts(s)
    for w in ("망치", "손목", "도체", "인체", "접근", "접촉", "시뮬레이션"):
        assert w in txt, w


def test_scenario_storyboard_has_two_rows_of_phases(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    titles = [_title(s) for s in prs.slides]
    s = prs.slides[next(k for k, t in enumerate(titles) if "S7" in t) + 1]
    txt = _texts(s)
    for w in ("도체", "인체", "탐지", "식별", "접근", "접촉", "파지", "상호작용", "APPROACH", "GRASP", "반사"):
        assert w in txt, w
    assert sum(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE for sh in s.shapes) >= 60


def test_variable_definition_slide_lists_modes(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    txt = " ".join(c.text for c in _cells(prs, 4))
    assert "ε_f" in txt and "접촉" in txt and "F_ref" in txt


def test_gain_table_from_params(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    assert any("1.234" in c.text for c in _cells(prs, 32))


def test_missing_value_cell_is_yellow(tmp_path):
    p = copy.deepcopy(FAKE)
    del p["det"]["lqr"]["K"]
    prs = Presentation(build(tmp_path / "d.pptx", params=p))
    cell = next(c for c in _cells(prs, 32) if c.text.strip() == "?")
    assert str(cell.fill.fore_color.rgb) == YELLOW


def _texts(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def test_state_space_diagrams_follow_detail(tmp_path):
    prs = Presentation(build(tmp_path / "d.pptx", params=FAKE))
    for i, key in ((7, "자유"), (8, "접촉")):
        assert "상태공간 블록도" in _title(prs.slides[i]) and key in _title(prs.slides[i])
        assert sum(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE for sh in prs.slides[i].shapes) >= 15
        assert "z⁻¹" in _texts(prs.slides[i])
    assert "1.23" in _texts(prs.slides[7])           # K 는 params 에서 (유효 3자리)
    assert "RLS" in _texts(prs.slides[8]) and "반사" in _texts(prs.slides[8])


def test_transfer_function_slide_follows_state_space(tmp_path):
    P = dict(FAKE, tf={"Gp": "0.22 / (z − 0.775)", "Ce": "1.57·(z − 0.957) / (z − 1)", "gm_db": 27.5, "pm_deg": 88.3})
    prs = Presentation(build(tmp_path / "d.pptx", params=P))
    s = prs.slides[9]
    assert "전달함수" in _title(s)
    tx = _texts(s) + " ".join(c.text for c in _cells(prs, 9))
    assert "G_p" in tx and "C_ε" in tx and "F(z)" in tx
    assert "0.775" in tx and "(z − 1)" in tx and "27.5" in tx   # 값은 params tf 에서
