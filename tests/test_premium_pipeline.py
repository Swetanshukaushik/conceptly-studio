import json
import os

import pytest

from src.engines.render.tier_free.studio3d_engine import Studio3DEngine
from src.models.schemas import ActScript, ReelGenerationTier, ReelScript
from src.services.media.cache import ImageCache
from src.services.media.ledger import SpendLedger
from src.services.media.providers import FakeImageProvider, MediaGateway, ProviderError
from src.services.premium import composer, director, facts, planner, stills, style
from src.services.premium.planner import Pin, Shot, ShotPlan

NARR = [
    "Why did one handful of salt shake an empire in 1930?",
    "Gandhi walked for twenty four days toward the sea at Dandi with thousands following him.",
    "At the shore he lifted a pinch of salt and broke the law on salt.",
    "Within weeks, thousands more were arrested but the movement kept growing.",
    "That small act of defiance changed how the world saw the struggle for freedom.",
]


def _script():
    acts = [ActScript(act_number=i + 1, title=f"Act {i + 1}", start_sec=i * 8, end_sec=i * 8 + 8, visual_direction="", spoken_text=t + " " + t.split(".")[0] + " today.") for i, t in enumerate(NARR)]
    return ReelScript(title="t", topic_title="Salt March", hook="h", key_takeaway="k", summary_notes=[], total_word_count=100, acts=acts)


ROUTE = {"pack": "history_civics", "label": "History and Civics", "method": "rule", "status": "planned", "persona": None, "kits": [], "verification": []}


def _planner(topic, subject, beats, pack, tier, provider):
    shots = [Shot(beat=b["beat"], prompt=f"A crowd of villagers walking on a coastal road at dawn, view {b['beat']}", named_people=["Gandhi"],
                  motion=["push_in", "pan_left", "pull_out", "drift_up", "pan_right"][i % 5], title="Dandi, 1930" if i == 1 else None,
                  pop_word="salt" if i == 2 else None) for i, b in enumerate(beats)]
    shots[1].real_photo_query = "Salt March Dandi 1930"
    return {"shots": shots, "notes": [], "style_note": "warm painterly"}


def _gw(cap=1.5, **kw):
    return MediaGateway(SpendLedger(cap), FakeImageProvider(**kw))


def _run(tmp_path, gateway, **kw):
    assets = str(tmp_path / "job" / "assets")
    args = dict(script=_script(), subject="History", class_level=10, exam_type="SCHOOL", assets_dir=assets, tier=ReelGenerationTier.PREMIUM, provider="AUTO",
                route=ROUTE, gateway=gateway, planner_fn=_planner, judge=lambda p, s, n: {"score": 8, "issues": []},
                resolver=lambda q, d, n: {"src": None, "problems": ["none"]}, fact_fn=lambda *a, **k: {"status": "verified", "claims": [], "sources": []},
                judge_sheet=lambda p: {"score": 8, "issues": []}, cache=ImageCache(str(tmp_path / "cache")))
    args.update(kw)
    return director.direct_premium_storyboard(**args), assets


def test_sanitizer_removes_names_and_text_requests():
    out = style.sanitize_prompt("Gandhi holds a sign reading FREEDOM near Mohandas Gandhi", ["Mohandas Gandhi"])
    assert "Gandhi" not in out["prompt"] and "sign reading" not in out["prompt"] and out["notes"]


def test_plan_cleanup_drops_pop_words_not_in_narration():
    beats = [{"beat": 1, "text": "Salt shook an empire.", "seconds": 5}]
    plan = ShotPlan(shots=[Shot(beat=1, prompt="a beach", pop_word="Revolution")])
    assert planner.clean_plan(plan, beats, "history_civics")["shots"][0].pop_word is None


def test_pipeline_generates_composes_and_stays_in_budget(tmp_path):
    res, assets = _run(tmp_path, _gw())
    sb, rec = res["storyboard"], res["premium"]
    assert len(sb.scenes) == len(rec["per_beat"]) and rec["images"]["generated"] == rec["shots"]
    assert rec["cost"]["spent_usd"] <= rec["cost"]["cap_usd"]
    assert rec["cost"]["calls"] == rec["images"]["generated"]
    assert all(os.path.exists(os.path.join(assets, o["src"])) for s in sb.scenes for o in s.scene3d["objects"] if o.get("src"))


def test_scenes_pass_the_real_renderer_lint(tmp_path):
    res, assets = _run(tmp_path, _gw())
    spec = Studio3DEngine.build_spec(res["storyboard"], look=res["storyboard"].style_bible)
    problems = Studio3DEngine.lint(spec, assets_dir=assets)
    hard = [p for p in problems if not Scene3DDirectorSoft(p)]
    assert not hard, hard


def Scene3DDirectorSoft(msg):
    from src.agents.scene3d_director import Scene3DDirector
    return Scene3DDirector._is_soft(msg)


def test_spend_cap_forces_fallback_not_a_crash(tmp_path):
    res, _ = _run(tmp_path, _gw(cap=0.1, price=0.05))
    rec = res["premium"]
    assert rec["cost"]["spent_usd"] <= 0.1 and rec["images"]["generated"] == 2
    assert rec["images"]["none"] + rec["images"]["archive_fallback"] >= 2
    assert any("spend cap" in (v.get("note") or "") for v in rec["per_beat"].values())


def test_provider_credit_error_stops_further_calls(tmp_path):
    class Dead(FakeImageProvider):
        def generate(self, req):
            self.calls.append(req)
            raise ProviderError("credits depleted", status=402)
    gw = MediaGateway(SpendLedger(1.5), Dead())
    res, _ = _run(tmp_path, gw)
    assert len(gw.image_provider.calls) == 1 and res["premium"]["cost"]["spent_usd"] == 0
    assert res["premium"]["images"]["generated"] == 0 and res["storyboard"].qa


def test_low_judge_score_regenerates_once_and_fallback_is_used(tmp_path):
    calls = []
    def judge(p, s, n):
        calls.append(p); return {"score": 3, "issues": ["extra fingers"]}
    gw = _gw()
    res, _ = _run(tmp_path, gw, judge=judge, resolver=lambda q, d, n: {"src": "arch.jpg", "aspect": 1.5, "title": "photo"})
    n = res["premium"]["shots"] - 1   # one shot is a real subject and never generated
    assert len(calls) == min(2 * n, style.cfg()["max_images_per_reel"]) and res["premium"]["images"]["archive_fallback"] == n and res["premium"]["images"]["archive"] == 1
    assert "extra fingers" in json.dumps(gw.image_provider.calls[1].prompt)


def test_real_person_shot_uses_archive_photo_not_generation(tmp_path):
    gw = _gw()
    res, _ = _run(tmp_path, gw, resolver=lambda q, d, n: {"src": "arch.jpg", "aspect": 1.5, "title": "Dandi"})
    assert res["premium"]["per_beat"]["2"]["source"] == "archive"
    assert all("Gandhi" not in c.prompt for c in gw.image_provider.calls)


def test_camera_expressions_cover_motion_types():
    for m in style.cfg()["motions"]:
        cam = composer.camera_for(m)
        assert len(cam["position"]) == 3 and cam["fov"] == 40


def test_pins_become_tagged_glows():
    shot = Shot(beat=1, prompt="heart", pins=[Pin(text="Aorta", x=0.6, y=0.2)], shot_type="diagram")
    sc = composer.compose_scene(shot, {"src": "x.png", "aspect": 0.5625}, {"beat": 1, "seconds": 6})
    assert any(o["id"] == "pin1" for o in sc["objects"]) and any(o["kind"] == "tag" and o["target"] == "pin1" for o in sc["overlays"])


def test_fact_check_statuses():
    fetch = lambda p: ({"query": {"search": [{"title": "Salt March"}]}} if p.get("list") == "search" else {"query": {"pages": {"1": {"title": "Salt March", "extract": "The march began on 12 March 1930."}}}})
    class V:  # stands in for the model reply
        def __init__(self, claims): self.claims = claims
    ok = facts.verify_narration("n", "Salt March", fetch=fetch, ask=lambda p: V([{"claim": "began 1930", "verdict": "supported"}]))
    bad = facts.verify_narration("n", "Salt March", fetch=fetch, ask=lambda p: V([{"claim": "began 1932", "verdict": "contradicted"}]))
    none = facts.verify_narration("n", "x", fetch=lambda p: {"query": {"search": []}})
    assert ok["status"] == "verified" and bad["status"] == "flagged" and none["status"] == "skipped"


def _premium_script(res):
    sb = res["storyboard"].model_dump()
    return {"storyboard": sb, "premium": res["premium"], "acts": [], "math_verification": {"status": "no_numbers"}}


def test_quality_gate_premium_checks_pass_and_block(tmp_path):
    from src.services import quality_gate
    res, _ = _run(tmp_path, _gw())
    good = quality_gate.evaluate(_premium_script(res))
    ids = {c["id"]: c for c in good["checks"]}
    assert {"images_generated", "image_quality", "consistency", "facts", "cost"} <= set(ids) and "variety" not in ids
    assert all(ids[i]["ok"] for i in ("images_generated", "image_quality", "consistency", "facts", "cost"))
    bad = _premium_script(res)
    bad["premium"] = {**bad["premium"], "facts": {"status": "flagged", "claims": [{"claim": "began 1932", "verdict": "contradicted", "note": "source says 1930"}]},
                      "cost": {"spent_usd": 2.0, "cap_usd": 1.5}}
    out = quality_gate.evaluate(bad)
    failed = {c["id"] for c in out["checks"] if not c["ok"] and c["blocking"]}
    assert {"facts", "cost"} <= failed and not out["passed"]


def test_quality_gate_blocks_when_nothing_was_generated(tmp_path):
    from src.services import quality_gate
    class Dead(FakeImageProvider):
        def generate(self, req):
            raise ProviderError("credits depleted", status=402)
    res, _ = _run(tmp_path, MediaGateway(SpendLedger(1.5), Dead()))
    out = quality_gate.evaluate(_premium_script(res))
    assert "images_generated" in {c["id"] for c in out["checks"] if not c["ok"] and c["blocking"]}


def test_gemini_tts_writes_audio_charges_ledger_and_falls_back(tmp_path):
    import base64, wave
    from src.engines.tts.tts_engine import GeminiTTSEngine
    pcm = b"\x00\x01" * 24000 * 3   # 3 seconds at 24 kHz
    ok = lambda url, body: (200, {"candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(pcm).decode()}}]}}]})
    led = SpendLedger(1.0)
    words = GeminiTTSEngine(ledger=led, transport=ok).synthesize("Salt shook an empire in nineteen thirty.", str(tmp_path / "a.wav"))
    with wave.open(str(tmp_path / "a.wav")) as w:
        assert w.getnframes() == 72000
    assert [x.word for x in words][0] == "Salt" and words[-1].end_sec <= 3.0 + 1e-6
    assert led.spent == pytest.approx(0.00225 * 3 / 10) and led.to_dict()["by_kind"] == {"tts": pytest.approx(0.000675)}
    seen = {}
    class FakeEdge:
        def synthesize(self, text, path, voice=None, **kw):
            seen["edge"] = True; return []
    import src.engines.tts.tts_engine as te
    orig = te.EdgeTTSEngine; te.EdgeTTSEngine = FakeEdge
    try:
        failing = lambda url, body: (402, {"error": {"message": "credits depleted"}})
        led2 = SpendLedger(1.0)
        GeminiTTSEngine(ledger=led2, transport=failing).synthesize("Hello there.", str(tmp_path / "b.wav"))
    finally:
        te.EdgeTTSEngine = orig
    assert seen.get("edge") and led2.spent == 0 and led2.reserved == 0


def test_premium_tier_is_available_and_routes_only_supported_packs():
    from src.services.tiers import require_available
    from src.services.config_loader import load_json
    t = require_available("premium")
    assert t["renderer"] == "studio3d" and t["scene_mode"] == "generated_stills"
    sup = load_json("premium.json")["supported_packs"]
    assert "history_civics" in sup and "biology" in sup and "maths" not in sup and "physics" not in sup and "chemistry" not in sup


def _shots(n, **over):
    return [Shot(beat=i + 1, prompt=f"scene {i}", motion="push_in", **over) for i in range(n)]


def test_sharing_is_capped_and_uses_a_different_camera_move():
    shots = _shots(10)
    notes = planner.enforce_sharing(shots)
    unique = sum(1 for s in shots if not s.reuse_previous)
    assert unique <= 6 and notes
    for i, s in enumerate(shots):
        if s.reuse_previous:
            assert s.motion != shots[i - 1].motion


def test_pinned_and_real_subject_shots_never_share():
    shots = _shots(6)
    shots[1].pins = [Pin(text="Aorta")]; shots[1].reuse_previous = True
    shots[3].real_photo_query = "Dandi"; shots[3].reuse_previous = True
    shots[4].reuse_previous = True   # previous is a real subject
    planner.enforce_sharing(shots)
    assert not shots[1].reuse_previous and not shots[3].reuse_previous and not shots[4].reuse_previous


def test_shared_beats_cost_nothing_and_are_not_counted_as_images(tmp_path):
    def shared_planner(topic, subject, beats, pack, tier, provider):
        shots = [Shot(beat=b["beat"], prompt=f"a coastal road at dawn {b['beat']}", motion="push_in" if i % 2 == 0 else "pull_out", reuse_previous=bool(i % 2)) for i, b in enumerate(beats)]
        return {"shots": shots, "notes": [], "style_note": ""}
    gw = _gw()
    res, _ = _run(tmp_path, gw, planner_fn=shared_planner)
    rec = res["premium"]; n = rec["shots"]
    assert rec["images"]["generated"] == (n + 1) // 2 and rec["images"]["shared"] == n // 2
    assert len(gw.image_provider.calls) == (n + 1) // 2
    scenes = res["storyboard"].scenes
    assert scenes[0].scene3d["objects"][0]["src"] == scenes[1].scene3d["objects"][0]["src"]
    assert scenes[0].scene3d["camera"] != scenes[1].scene3d["camera"]


def test_hero_model_only_on_the_first_generated_shot(tmp_path):
    gw = _gw()
    _run(tmp_path, gw)
    models = [c.model for c in gw.image_provider.calls]
    assert models[0] == "gemini-3.1-flash-image" and all(m == "gemini-3.1-flash-lite-image" for m in models[1:])


def test_cache_makes_the_second_run_free(tmp_path):
    gw1 = _gw(); r1, _ = _run(tmp_path, gw1)
    spent1 = r1["premium"]["cost"]["spent_usd"]
    gw2 = _gw(); r2, _ = _run(tmp_path, gw2, assets_dir=str(tmp_path / "other_job" / "assets"))   # a new job, so only the shared cache can help
    assert spent1 > 0 and r2["premium"]["cost"]["spent_usd"] == 0 and len(gw2.image_provider.calls) == 0
    assert r2["premium"]["cost"]["cache_hits"] == r2["premium"]["images"]["generated"] > 0


def test_a_rejected_image_is_not_cached(tmp_path):
    gw1 = _gw(); _run(tmp_path, gw1, judge=lambda p, s, n: {"score": 2, "issues": ["bad"]}, resolver=lambda q, d, n: {"src": "a.jpg", "aspect": 1.5})
    gw2 = _gw(); _run(tmp_path, gw2)
    assert len(gw2.image_provider.calls) > 0


def test_landscape_photo_gets_a_blurred_backdrop_and_titles_do_not_collide(tmp_path):
    from PIL import Image
    assets = tmp_path / "assets"; assets.mkdir()
    Image.new("RGB", (1200, 800), (200, 180, 160)).save(assets / "photo.jpg")
    name = composer.make_backdrop(str(assets), "photo.jpg")
    assert name and (assets / name).exists() and Image.open(assets / name).size == (360, 640)
    shot = Shot(beat=1, prompt="x", title="Dandi, 1930", pop_word="salt")
    sc = composer.compose_scene(shot, {"src": "photo.jpg", "aspect": 1.5}, {"beat": 1, "seconds": 6}, backdrop=name)
    assert sc["objects"][0]["id"] == "backdrop" and sc["objects"][1]["id"] == "still"
    anchors = {o["kind"]: o["anchor"] for o in sc["overlays"]}
    assert anchors["title"] == "top" and anchors["pop"] == "center"


def test_fact_sources_search_the_topic_title_first():
    queries = []
    def fetch(p):
        if p.get("list") == "search":
            queries.append(p["srsearch"]); return {"query": {"search": [{"title": "Salt March"}] if p["srsearch"] == "The Salt March" else []}}
        return {"query": {"pages": {"1": {"title": "Salt March", "extract": "Began 12 March 1930."}}}}
    out = facts.retrieve_sources("The Salt March", "History", fetch)
    assert queries[0] == "The Salt March" and out[0]["title"] == "Salt March"


def test_exact_titled_article_is_used_before_search_hits():
    def fetch(p):
        if p.get("list") == "search":
            return {"query": {"search": [{"title": "Padandi Munduku"}]}}
        if "extracts" not in p.get("prop", ""):
            return {"query": {"pages": {"7": {"title": "Salt March"}, "-1": {"title": "The Salt March", "missing": ""}}}}
        pages = {"Padandi Munduku": {"title": "Padandi Munduku", "extract": "A film."}, "Salt March": {"title": "Salt March", "extract": "Began 12 March 1930."}}
        return {"query": {"pages": {"1": pages[p["titles"]]}}}   # one full-text extract per request, as the real API does
    out = facts.retrieve_sources("The Salt March", "History", fetch)
    assert [o["title"] for o in out] == ["Salt March", "Padandi Munduku"]


def test_gate_warns_when_facts_are_not_backed_by_sources(tmp_path):
    from src.services import quality_gate
    res, _ = _run(tmp_path, _gw())
    s = _premium_script(res)
    s["premium"]["facts"] = {"status": "unverified", "claims": [{"claim": "a", "verdict": "unverified"}], "supported": 0, "sources": [{"title": "Padandi Munduku"}]}
    out = quality_gate.evaluate(s)
    c = {x["id"]: x for x in out["checks"]}
    assert not c["facts_coverage"]["ok"] and not c["facts_coverage"]["blocking"] and c["facts"]["ok"]


def test_premium_beats_use_the_measured_voice_pace_and_writer_range():
    script = _script()
    default = Scene3DDirectorBeats(script, None); slow = Scene3DDirectorBeats(script, 2.0)
    assert sum(b["seconds"] for b in slow) > sum(b["seconds"] for b in default)
    from src.services.config_loader import load_json
    p = load_json("pacing.json")["tiers"]["premium"]
    assert p["min_wps"] < p["words_per_second"] <= p["max_wps"]


def Scene3DDirectorBeats(script, wps):
    from src.agents.scene3d_director import Scene3DDirector
    return Scene3DDirector.split_beats(script, wps=wps)
