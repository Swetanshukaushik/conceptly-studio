"""A failure redoes only the failed piece: one image retries alone, a rerun keeps finished stills and the plan, one beat can be redone."""
import pytest

from src.services.premium import director, stills
from tests.test_premium_pipeline import _gw, _planner, _run


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(stills.time, "sleep", lambda s: None)


def test_transient_error_retries_only_that_image(tmp_path):
    gw = _gw(fail_on=[2])   # the second provider call times out once
    (res, assets) = _run(tmp_path, gw, cache=None)
    rec = res["premium"]
    calls = len(gw.image_provider.calls)
    assert rec["images"]["generated"] == rec["shots"] and calls == rec["shots"] + 1   # one extra call, for the one failed image
    assert not any(v.get("note", "").startswith("provider error") for v in rec["per_beat"].values())


def test_rerun_after_failure_keeps_finished_work(tmp_path):
    plans = []

    def planner(*a):
        plans.append(1)
        return _planner(*a)

    first_gw = _gw(fail_on=[3, 4, 5, 6])   # beat 3 fails for good (retries exhausted)
    (res1, assets) = _run(tmp_path, first_gw, cache=None, planner_fn=planner, resolver=lambda q, d, n: {"src": None, "problems": ["none"]})
    done = {k for k, v in res1["premium"]["per_beat"].items() if v["source"] == "generated"}
    assert len(done) < res1["premium"]["shots"]
    second_gw = _gw()
    (res2, _) = _run(tmp_path, second_gw, cache=None, planner_fn=planner)
    rec = res2["premium"]
    assert len(plans) == 1                                    # the shot plan was not asked for again
    assert len(second_gw.image_provider.calls) == rec["shots"] - len(done) - sum(1 for v in res1["premium"]["per_beat"].values() if v["source"] in ("archive",))
    assert all(rec["per_beat"][k]["note"] == "kept from an earlier run" for k in done)


def test_redo_one_beat_changes_only_that_beat(tmp_path):
    gw = _gw()
    (res, assets) = _run(tmp_path, gw, cache=None)
    sb = {"topic_title": "Salt March", "route": {"pack": "history_civics"}, "scenes": [s.dict() for s in res["storyboard"].scenes]}
    before = {s["scene_number"]: s["scene3d"] for s in sb["scenes"]}
    gw2 = _gw()
    changed = director.regenerate_beat_still(sb, res["premium"], 3, assets, new_prompt="A quiet shoreline at dawn, a hand lifting salt", gateway=gw2,
                                             judge=lambda p, s, n: {"score": 8, "issues": []})
    assert changed == [3] and len(gw2.image_provider.calls) == 1
    after = {s["scene_number"]: s["scene3d"] for s in sb["scenes"]}
    assert after[3] != before[3] and all(after[n] == before[n] for n in before if n != 3)
