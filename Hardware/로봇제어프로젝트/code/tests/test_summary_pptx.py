from pptx import Presentation


def _texts(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def test_evidence_numbers_come_from_result_files():
    from build_summary_pptx import evidence
    E = evidence()
    assert E["s9"]["도체 r15 z-70 (공칭)"] < 0 and E["s9"]["유전체 r8 z-60"] < 0      # 힘 직접 추종 → 유지 RMSE 감소
    assert 0 < E["s6_fb"]["강성 +30 %"] < 100 and E["s6_fb"]["공칭"] < 0             # 공칭에선 개루프가 낫다 (그대로 보고)
    assert E["s10"]["reflex"] < E["s10"]["up20"] < E["s10"]["drop"]


def test_every_slide_leads_with_a_claim(tmp_path):
    from build_summary_pptx import build
    prs = Presentation(build(tmp_path / "s.pptx"))
    assert len(prs.slides) >= 8
    first = [next(sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()) for s in list(prs.slides)[2:-1]]
    assert all(t.startswith("결론") for t in first), first
    assert "시뮬레이션" in _texts(prs.slides[1])
