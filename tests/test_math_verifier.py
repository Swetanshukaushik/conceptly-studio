from types import SimpleNamespace

import pytest

from src.agents.writer_agent import MathVerificationError, WriterAgent
from src.models.schemas import ReelGenerationTier
from src.services import math_verifier as mv
from src.services.math_verifier import MathClaim


def claim(**kw):
    kw.setdefault("quote", "q")
    return MathClaim(**kw)


# the real error Gemini wrote in the first Parabola reel: focus (2,0), directrix x = -2, so the curve is y^2 = 8x
WRONG = "If our point glides to four comma four... its distance to the focus is four units and its distance to the line is also four."
RIGHT = "If our point glides to two comma four... its distance to the focus is four units and its distance to the line is also four."


def test_evaluator_handles_school_notation_and_refuses_code():
    assert mv.evaluate("4ax", {"a": 2, "x": 2}) == 16
    assert mv.evaluate("(x+1)(x-1)", {"x": 3}) == 8
    assert mv.evaluate("x^2 + 2×x", {"x": 3}) == 15
    assert abs(mv.evaluate("sin(pi/2)") - 1) < 1e-12
    for bad in ("__import__('os').system('x')", "open('f')", "x.__class__", "2**9999", "lambda: 1", "[1,2]"):
        with pytest.raises(mv.ClaimError):
            mv.evaluate(bad, {"x": 1})


def test_spoken_numbers_are_found():
    assert mv.numbers_in("four comma four") == [4, 4]
    assert mv.numbers_in("minus three and 2.5") == [3, 2.5]
    assert mv.numbers_in("twenty five units, one hundred and five") == [25, 105]
    assert mv.numbers_in("three point one four") == [3.14]
    assert mv.numbers_in("no numbers here") == []


def test_true_claims_pass_and_false_claims_are_explained():
    assert mv.check_claim(claim(kind="holds", lhs="y^2", rhs="8x", at={"x": 2, "y": 4})) is None
    wrong = mv.check_claim(claim(kind="holds", lhs="y^2", rhs="8x", at={"x": 4, "y": 4}))
    assert "16" in wrong and "32" in wrong
    assert mv.check_claim(claim(kind="distance", a=[2, 4], b=[2, 0], equals=4)) is None
    assert "4.47" in mv.check_claim(claim(kind="distance", a=[4, 4], b=[2, 0], equals=4))
    assert mv.check_claim(claim(kind="distance_to_line", point=[2, 4], line=[1, 0, 2], equals=4)) is None
    assert mv.check_claim(claim(kind="identity", lhs="(x+1)^2", rhs="x^2+2x+1")) is None
    assert "not equal" in mv.check_claim(claim(kind="identity", lhs="(x+1)^2", rhs="x^2+1"))
    assert mv.check_claim(claim(kind="table", function="x^2", rows=[[-2, 4], [0, 0], [2, 4]])) is None
    assert "not 5" in mv.check_claim(claim(kind="table", function="x^2", rows=[[2, 5]]))
    assert mv.check_claim(claim(kind="root", lhs="x^2-5x+6", rhs="0", roots=[2, 3])) is None
    assert "not a root" in mv.check_claim(claim(kind="root", lhs="x^2-5x+6", rhs="0", roots=[2, 4]))
    assert mv.check_claim(claim(kind="derivative", function="x^3", at={"x": 2}, equals=12)) is None
    assert mv.check_claim(claim(kind="derivative_expr", function="x^3", derivative="3x^2")) is None
    assert "not" in mv.check_claim(claim(kind="derivative_expr", function="x^3", derivative="2x^2"))
    assert mv.check_claim(claim(kind="value", expr="pi", equals=3.14, tol=0.001)) is None
    assert mv.check_claim(claim(kind="value", expr="pi", equals=3.2, tol=0.001)) is not None
    assert mv.check_claim(claim(kind="value", expr="pi", equals=3.2, tol=0.5)) is not None   # a huge tolerance is capped


def test_the_parabola_error_is_blocked_and_the_fix_passes():
    wrong_claims = [claim(kind="holds", quote="our point glides to four comma four", stated=[4, 4], lhs="y^2", rhs="8x", at={"x": 4, "y": 4})]
    problems, _ = mv.verify(wrong_claims, WRONG, require=True)
    assert any("does not hold" in p for p in problems)
    # the claim is "corrected" to (2, 4) but the narration still says four comma four: the quote/stated check catches the mismatch
    cheat = [claim(kind="holds", quote="our point glides to four comma four", stated=[2, 4], lhs="y^2", rhs="8x", at={"x": 2, "y": 4})]
    problems, _ = mv.verify(cheat, WRONG, require=True)
    assert any("does not say 2" in p for p in problems)
    good = [claim(kind="holds", quote="our point glides to two comma four", stated=[2, 4], lhs="y^2", rhs="8x", at={"x": 2, "y": 4}),
            claim(kind="distance", quote="its distance to the focus is four units", stated=[4], a=[2, 4], b=[2, 0], equals=4),
            claim(kind="distance_to_line", quote="its distance to the line is also four", stated=[4], point=[2, 4], line=[1, 0, 2], equals=4)]
    assert mv.verify(good, RIGHT, require=True) == ([], [])


def test_quote_must_be_verbatim_and_numbers_need_claims():
    problems, _ = mv.verify([claim(kind="value", quote="three plus four is seven", stated=[7], expr="3+4", equals=7)], "Add three and four.", require=True)
    assert any("verbatim" in p for p in problems)
    problems, _ = mv.verify([], "The slope at two is four.", require=True)
    assert any("no claims" in p for p in problems)
    assert mv.verify([], "Why does a ball curve through the air?", require=True) == ([], [])


def test_uncovered_numbers_are_a_note_or_a_block_by_setting():
    text = "The slope at two is four. Another sentence has seven apples."
    c = [claim(kind="derivative", quote="The slope at two is four", stated=[2, 4], function="x^2", at={"x": 2}, equals=4)]
    problems, notes = mv.verify(c, text, coverage="note")
    assert problems == [] and "seven apples" in notes[0]
    problems, notes = mv.verify(c, text, coverage="block")
    assert notes == [] and "seven apples" in problems[0]


def test_the_word_one_is_not_a_number_unless_the_sentence_is_mathematical():
    assert not mv.sentence_has_number("No one knows why this happens.")
    assert mv.sentence_has_number("The eccentricity equals one.")
    assert mv.sentence_has_number("It takes 3 steps.")


# ---- writer repair loop
def _out(narration, claims):
    return SimpleNamespace(script=SimpleNamespace(acts=[SimpleNamespace(spoken_text=narration)]), claims=claims, model_dump_json=lambda: "{}")


def _calls(monkeypatch, outputs):
    seen = []

    def fake(system_prompt, user_prompt, response_model, **kw):
        seen.append(user_prompt)
        return outputs[len(seen) - 1]
    monkeypatch.setattr("src.agents.writer_agent.LLMFactory.generate_json", fake)
    return seen


def test_writer_repairs_once_with_the_problems_then_accepts(monkeypatch):
    bad = _out(WRONG, [claim(kind="holds", quote="our point glides to four comma four", stated=[4, 4], lhs="y^2", rhs="8x", at={"x": 4, "y": 4})])
    good = _out(RIGHT, [claim(kind="holds", quote="our point glides to two comma four", stated=[2, 4], lhs="y^2", rhs="8x", at={"x": 2, "y": 4})])
    seen = _calls(monkeypatch, [good])
    out, ver = WriterAgent._verified(bad, "Mathematics", "USER", ReelGenerationTier.FREE, "AUTO", "writer")
    assert out is good and ver["status"] == "verified" and ver["attempts"] == 2
    assert len(seen) == 1 and "does not hold" in seen[0] and "failed the automatic maths check" in seen[0]


def test_writer_blocks_the_reel_when_the_repair_is_still_wrong(monkeypatch):
    bad = _out(WRONG, [claim(kind="holds", quote="our point glides to four comma four", stated=[4, 4], lhs="y^2", rhs="8x", at={"x": 4, "y": 4})])
    _calls(monkeypatch, [bad])
    with pytest.raises(MathVerificationError) as e:
        WriterAgent._verified(bad, "Mathematics", "USER", ReelGenerationTier.FREE, "AUTO", "writer")
    assert "not produced" in str(e.value) and "does not hold" in str(e.value)


def test_subjects_without_claim_rules_are_not_blocked_for_missing_claims(monkeypatch):
    _calls(monkeypatch, [])
    out = _out("The Battle of Plassey was fought in 1757 by Clive.", [])
    out2, ver = WriterAgent._verified(out, "History", "USER", ReelGenerationTier.FREE, "AUTO", "writer")
    assert ver["status"] == "no_numbers" and ver["notes"] == []
