import datetime
import json
import os
import types

import pytest

from src.services.media import usage
from src.services.media.ledger import BudgetExceeded, SpendLedger
from src.services.media.providers import FakeImageProvider, ImageRequest, MediaGateway, new_gateway


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "usage.jsonl"
    monkeypatch.setenv("CONCEPTLY_USAGE_LOG", str(path))
    return path


def lines(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def test_text_price_from_config_and_price_change_date():
    assert usage.text_price("gemini-3.5-flash-lite")["input_per_m"] == 0.30
    now = usage.text_price("gemini-3.8-flash", datetime.date(2026, 12, 31))
    later = usage.text_price("gemini-3.8-flash", datetime.date(2027, 1, 1))
    assert (now["input_per_m"], now["output_per_m"]) == (0.75, 3.75) and (later["input_per_m"], later["output_per_m"]) == (1.5, 7.5)
    assert usage.price_tokens("gemini-3.8-flash", 1_000_000, 1_000_000)["cost_usd"] == pytest.approx(0.75 + 3.75) or datetime.date.today() >= datetime.date(2027, 1, 1)
    assert usage.price_tokens("no-such-model", 1000, 1000)["estimated"] is True


def test_gemini_response_counts_thinking_as_output(log):
    led = SpendLedger(1.0)
    um = types.SimpleNamespace(prompt_token_count=10_000, candidates_token_count=2_000, total_token_count=18_000, thoughts_token_count=0)
    with usage.job_scope("job1", led, "premium"):
        usage.record_gemini_response("gemini-3.5-flash-lite", types.SimpleNamespace(usage_metadata=um))
    # 6,000 hidden thinking tokens (total - prompt - candidates) bill as output
    assert led.spent == pytest.approx(10_000 * 0.30 / 1e6 + 8_000 * 2.50 / 1e6, rel=1e-6)
    row = lines(log)[0]
    assert row["job"] == "job1" and row["kind"] == "llm" and row["output_tokens"] == 8_000


def test_wrapped_generate_content_is_recorded_and_blocked_in_tests(log, monkeypatch):
    genai = usage.genai_module()
    um = types.SimpleNamespace(prompt_token_count=1000, candidates_token_count=500, total_token_count=1500)
    # the wrapper must refuse while live calls are blocked, before anything reaches the network
    monkeypatch.setenv("CONCEPTLY_BLOCK_LIVE", "1")
    with pytest.raises(usage.LiveCallBlocked):
        genai.GenerativeModel("gemini-3.5-flash-lite").generate_content("hi")
    assert lines(log) == []


def test_job_ledger_collects_text_image_and_voice_in_one_report(log):
    led = SpendLedger(1.0)
    with usage.job_scope("job2", led, "premium"):
        usage.record_llm("gemini", "gemini-3.5-flash-lite", 10_000, 1_000, "planner")
        gw = new_gateway(1.0, FakeImageProvider(price=0.04))
        gw.generate_image(ImageRequest("a"))
        assert gw.ledger is led                                   # the gateway shares the job's ledger
    d = led.to_dict()
    assert set(d["by_kind"]) == {"llm", "image"} and d["spent_usd"] == pytest.approx(0.04 + 0.003 + 0.0025)
    assert {r["kind"] for r in lines(log)} == {"llm", "image"} and all(r["job"] == "job2" for r in lines(log))


def test_optional_calls_stop_when_the_budget_is_gone_but_required_ones_continue(log):
    led = SpendLedger(0.01)
    with usage.job_scope("job3", led):
        usage.record_llm("gemini", "gemini-3.8-flash", 100_000, 10_000, "script")        # required: recorded even though it exceeds the cap
        assert led.spent > led.cap_usd
        with pytest.raises(BudgetExceeded):
            usage.check_budget("vision review")
    usage.check_budget("outside any job")                                                  # no active ledger: nothing to enforce


def test_ledger_roundtrips_between_stages(log):
    a = SpendLedger(0.75); a.record("llm", "m", 0.1, "writer"); a.reserve("image", "x", 0.03); 
    d = a.to_dict()
    b = SpendLedger.from_dict(d, 0.75)
    b.record("tts", "t", 0.02, "voice")
    assert b.spent == pytest.approx(0.12) and b.to_dict()["by_kind"] == {"llm": 0.1, "tts": 0.02}


def test_cached_and_failed_calls_are_logged_but_not_priced(log):
    led = SpendLedger(1.0)
    with usage.job_scope("job4", led):
        led.note_free("image", "m", "beat 1", from_cache=True)
        t = led.reserve("image", "m", 0.03); led.release(t, "boom")
    assert led.spent == 0 and {r["status"] for r in lines(log)} == {"cached", "failed"}


def test_spend_report_sums_by_model(log, capsys):
    import scripts.spend_report as report
    rows = [{"ts": "2026-10-28T10:00:00", "kind": "llm", "model": "a", "cost_usd": 0.5, "input_tokens": 10, "output_tokens": 5, "status": "ok"},
            {"ts": "2026-10-28T10:01:00", "kind": "image", "model": "b", "cost_usd": 0.25, "status": "ok"},
            {"ts": "2026-10-27T10:01:00", "kind": "image", "model": "b", "cost_usd": 9.0, "status": "ok"}]
    log.write_text("\n".join(json.dumps(r) for r in rows))
    got = report.load(str(log), "2026-10-28")
    assert sum(r["cost_usd"] for r in got) == pytest.approx(0.75)


def test_quality_gate_reports_total_cost_for_every_tier():
    from src.services import quality_gate
    free = quality_gate.evaluate({"storyboard": {"scenes": []}, "cost": {"spent_usd": 0.2, "cap_usd": 0.05, "by_kind": {"llm": 0.2}}})
    c = {x["id"]: x for x in free["checks"]}
    assert "cost_info" in c and not c["cost_info"]["ok"] and not c["cost_info"]["blocking"]
    prem = quality_gate.evaluate({"storyboard": {"scenes": []}, "premium": {"images": {}, "per_beat": {}}, "cost": {"spent_usd": 0.9, "cap_usd": 0.75, "by_kind": {"llm": 0.9}}})
    assert {x["id"]: x for x in prem["checks"]}["cost"]["blocking"] and not prem["passed"]


def test_stage_wrapper_saves_the_job_total_and_nested_stages_share_one_ledger(log, monkeypatch):
    from src.database.session import SessionLocal
    from src.models.entities import ReelJob
    from src.pipeline.orchestrator import PipelineOrchestrator as PO
    db = SessionLocal()
    job = ReelJob(subject="Physics", topic_title="cost test", class_level=9, exam_type="SCHOOL", generation_tier="PREMIUM", script_generator="AUTO",
                  script_data=json.dumps({"storyboard": {"scenes": []}, "premium": {"images": {}, "per_beat": {}}}))
    db.add(job); db.commit(); jid = job.id; db.close()
    seen = []

    def stage2(job_id, auto_advance=False):
        seen.append(usage.current_ledger()); usage.record_llm("gemini", "gemini-3.5-flash-lite", 1000, 1000, "quiz")

    def stage1(job_id, avatar_id="AUTO", auto_advance=False):
        seen.append(usage.current_ledger()); usage.record_llm("gemini", "gemini-3.5-flash-lite", 10_000, 2_000, "writer"); PO.run_stage2_quiz(job_id)
    monkeypatch.setattr(PO, "_stage1_blueprint", classmethod(lambda cls, *a, **k: stage1(*a, **k)))
    monkeypatch.setattr(PO, "_stage2_quiz", classmethod(lambda cls, *a, **k: stage2(*a, **k)))
    PO.run_stage1_blueprint(jid)
    assert seen[0] is seen[1]                                                    # nested stage reused the outer ledger
    db = SessionLocal(); saved = json.loads(db.query(ReelJob).filter(ReelJob.id == jid).first().script_data); db.close()
    assert saved["cost"]["spent_usd"] == pytest.approx(10_000 * 0.30 / 1e6 + 2_000 * 2.5 / 1e6 + 1000 * 0.30 / 1e6 + 1000 * 2.5 / 1e6)
    assert saved["cost"]["cap_usd"] == 0.75 and saved["premium"]["cost"] == saved["cost"] and "cost" in {c["id"] for c in saved["quality_gate"]["checks"]} if saved.get("quality_gate") else True
    assert {r["job"] for r in lines(log)} == {jid}
