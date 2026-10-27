import json
import os
import subprocess

import pytest

from src.agents.scene3d_director import Scene3DDirector
from src.engines.render.tier_free.studio3d_engine import Studio3DEngine, STUDIO_DIR
from src.models.schemas import ActScript, ReelScript
from src.models.scene3d import ReelVisualPlan
from src.services import tiers
from src.services.config_loader import CONFIG_DIR, load_json

FIXTURE = os.path.join(STUDIO_DIR, "fixtures", "projectile.json")

pytestmark = pytest.mark.skipif(
    not os.path.isdir(os.path.join(STUDIO_DIR, "node_modules")), reason="studio3d dependencies not installed"
)


def _script():
    acts = [
        ActScript(act_number=1, title="Hook", start_sec=0, end_sec=6, visual_direction="",
                  spoken_text="Why does a thrown ball curve through the air instead of flying straight?"),
        ActScript(act_number=2, title="Intuition", start_sec=6, end_sec=12, visual_direction="",
                  spoken_text="Gravity keeps pulling it down while its sideways speed stays exactly the same."),
    ]
    return ReelScript(title="t", topic_title="Projectile motion", hook="h", key_takeaway="k", summary_notes=[],
                      total_word_count=26, acts=acts)


def test_tier_aliases_resolve_to_three_tiers():
    assert tiers.resolve_tier("DEFAULT") == "free"
    assert tiers.resolve_tier("TIER_5_KURZGESAGT") == "ultra"
    assert tiers.resolve_tier("premium") == "premium"
    with pytest.raises(RuntimeError):
        tiers.require_available("ULTRA")


def test_split_beats_keeps_narration_verbatim():
    beats = Scene3DDirector.split_beats(_script())
    assert [b["beat"] for b in beats] == [1, 2]
    joined = " ".join(b["text"] for b in beats)
    assert joined == " ".join(a.spoken_text for a in _script().acts)


def test_lint_reports_bad_expressions_and_latex():
    spec = json.load(open(FIXTURE))
    spec["scenes"][0]["objects"][3]["position"][0] = "nope(t)*speed"
    spec["scenes"][1]["overlays"][0]["latex"] = "\\frac{a"
    problems = Studio3DEngine.lint(spec)
    assert any("Unknown function" in p for p in problems)
    assert any("LaTeX" in p for p in problems)


def _hard(problems):
    """Layout findings (cropping, card overlap, bright title) are advisory; everything else must be clean."""
    return [p for p in problems if not Scene3DDirector._is_soft(p)]


def test_fixture_lints_clean():
    assert _hard(Studio3DEngine.lint(json.load(open(FIXTURE)))) == []


def test_director_pipeline_with_canned_plan(monkeypatch, tmp_path):
    canned = json.load(open(os.path.join(CONFIG_DIR, "prompts", "scene3d_example.json")))
    monkeypatch.setattr(
        "src.agents.scene3d_director.LLMFactory.generate_json",
        lambda **kw: ReelVisualPlan.model_validate(canned),
    )
    sb = Scene3DDirector.direct_storyboard(_script(), "Physics", 9, "SCHOOL", assets_dir=str(tmp_path / "assets"))
    assert len(sb.scenes) == 2 and all(s.scene3d for s in sb.scenes)

    spec = Studio3DEngine.build_spec(sb, look=sb.style_bible)
    files = Studio3DEngine.render_stills(spec, [s.start_sec + 1.5 for s in sb.scenes], str(tmp_path / "frames"))
    assert len(files) == 2 and all(os.path.getsize(f) > 20_000 for f in files)

    out = str(tmp_path / "reel.mp4")
    spec["duration"] = 2.0
    spec["scenes"] = spec["scenes"][:1]
    spec["scenes"][0]["end"] = 2.0
    Studio3DEngine.render_reel(spec, out)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", out],
        capture_output=True, text=True,
    ).stdout.strip()
    assert probe.strip(",") == "1080,1920"


def test_director_rejects_plan_that_skips_beats(monkeypatch, tmp_path):
    canned = json.load(open(os.path.join(CONFIG_DIR, "prompts", "scene3d_example.json")))
    canned["scenes"] = canned["scenes"][:1]
    monkeypatch.setattr(
        "src.agents.scene3d_director.LLMFactory.generate_json",
        lambda **kw: ReelVisualPlan.model_validate(canned),
    )
    from src.agents.scene3d_director import Scene3DPlanError
    with pytest.raises(Scene3DPlanError):
        Scene3DDirector.direct_storyboard(_script(), "Physics", 9, "SCHOOL", assets_dir=str(tmp_path))


def test_prop_fixture_lints_clean():
    """Every prefab (people, crowd, hall, flag...) expands, evaluates and renders a non-black, non-blown-out frame."""
    path = os.path.join(STUDIO_DIR, "fixtures", "props.json")
    assert _hard(Studio3DEngine.lint(json.load(open(path)))) == []


def test_pulley_fixture_lints_clean_and_layout_window_is_used():
    """Pulley prefabs, rope primitive, header block and the explainer window layout render without problems."""
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "pulley.json")))
    assert spec["layout"] == "explainer_window" and spec["header"]
    assert Studio3DEngine.lint(spec) == []


def test_layout_prompt_reports_window_geometry():
    text = Scene3DDirector._layouts_text()
    assert "explainer_window" in text and "1080x850" in text and "full" in text


def _pulley_spec(distance, card_anchor):
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "pulley.json")))
    sc = spec["scenes"][0]
    sc["camera"] = {"position": [0.2, 2.1, distance], "target": [0.2, 2.1, 0], "fov": 40}
    sc["overlays"] = [{"kind": "formula", "latex": "F = \\frac{W}{2}", "anchor": card_anchor, "at": 0.0}]
    spec["scenes"] = [sc]
    spec["duration"] = sc["end"]
    return spec


def test_layout_qa_flags_cropped_subject():
    problems = Studio3DEngine.lint(_pulley_spec(distance=3.5, card_anchor="top"))
    assert any("cropped by the edge" in p for p in problems)


def test_layout_qa_flags_card_covering_subject():
    problems = Studio3DEngine.lint(_pulley_spec(distance=7.6, card_anchor="center"))
    assert any("card" in p and "covers" in p for p in problems)


def test_layout_qa_passes_when_framed_and_card_is_clear():
    assert Studio3DEngine.lint(_pulley_spec(distance=7.6, card_anchor="top")) == []


def _canned_storyboard(monkeypatch, tmp_path):
    canned = json.load(open(os.path.join(CONFIG_DIR, "prompts", "scene3d_example.json")))
    monkeypatch.setattr("src.agents.scene3d_director.LLMFactory.generate_json",
                        lambda **kw: ReelVisualPlan.model_validate(canned))
    return Scene3DDirector.direct_storyboard(_script(), "Physics", 9, "SCHOOL", assets_dir=str(tmp_path / "assets")), canned


def test_vision_review_uses_one_call_per_stage_and_retries_weak_beats_once(monkeypatch, tmp_path):
    sb, canned = _canned_storyboard(monkeypatch, tmp_path)
    judged = []

    def judge(items, note):
        judged.append([i["beat"] for i in items])
        first = len(judged) == 1
        return {i["beat"]: ({"score": 3, "issues": ["abstract shapes"]} if (first and i["beat"] == 1) else {"score": 9, "issues": []}) for i in items}

    redesigns = []
    replacement = dict(canned["scenes"][1]); replacement["beat"] = 1

    def fake_redesign(cls, topic, jobs, *a, **k):
        redesigns.append([j["beat"]["beat"] for j in jobs])
        return {j["beat"]["beat"]: replacement for j in jobs}

    monkeypatch.setattr(Scene3DDirector, "_redesign_beats", classmethod(fake_redesign))
    notes = Scene3DDirector.vision_review(sb, str(tmp_path / "assets"), str(tmp_path / "frames"), judge=judge)
    assert notes == []
    assert judged == [[1, 2], [1]]      # all frames judged in one call, then only the retried beat in one more
    assert redesigns == [[1]]           # one batched re-design call
    assert sb.scenes[0].scene3d["intent"] == replacement["intent"]
    assert all(os.path.getsize(s.image_path) > 20_000 for s in sb.scenes)


def test_vision_review_gives_up_after_one_retry(monkeypatch, tmp_path):
    sb, canned = _canned_storyboard(monkeypatch, tmp_path)
    replacement = dict(canned["scenes"][1]); replacement["beat"] = 1
    monkeypatch.setattr(Scene3DDirector, "_redesign_beats",
                        classmethod(lambda cls, topic, jobs, *a, **k: {j["beat"]["beat"]: replacement for j in jobs}))
    judge = lambda items, note: {i["beat"]: {"score": 2, "issues": ["wrong subject"]} for i in items}
    notes = Scene3DDirector.vision_review(sb, str(tmp_path / "assets"), str(tmp_path / "frames"), judge=judge)
    assert any("still 2/10 after one retry" in n for n in notes)


def test_vision_review_survives_judge_outage(monkeypatch, tmp_path):
    sb, _ = _canned_storyboard(monkeypatch, tmp_path)

    def judge(items, note):
        raise RuntimeError("429 quota")
    notes = Scene3DDirector.vision_review(sb, str(tmp_path / "assets"), str(tmp_path / "frames"), judge=judge)
    assert notes and "unavailable" in notes[0]
    assert all(os.path.exists(s.image_path) for s in sb.scenes)


def test_one_call_writer_returns_all_three_parts(monkeypatch):
    from src.agents.writer_agent import WriterAgent, WriterOutput
    from src.models.schemas import QuizPayload, QuizQuestion, QuizOption, DomainPedagogyDossier, ReelGenerationTier
    script = _script()
    script.acts += [
        ActScript(act_number=3, title="Core", start_sec=12, end_sec=18, visual_direction="", spoken_text="The effort is half the load."),
        ActScript(act_number=4, title="CTA", start_sec=18, end_sec=24, visual_direction="", spoken_text="Tap the quiz below!"),
    ]
    dossier = DomainPedagogyDossier(
        canonical_topic="t", domain_field="Physics", exam_track="SCHOOL", target_class_level="9", core_misconception="m", root_flaw="r",
        counter_intuitive_hook="h", curiosity_gap="c", must_include_concept="x", concrete_visual_metaphor="v", visual_transformation_beat="b", atomic_takeaway="a")
    quiz = QuizPayload(topicTitle="t", questions=[QuizQuestion(id="q1", text="?", options=[QuizOption(id=i, text=i) for i in "abcd"], correctOptionId="a", explanation="e")])
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return WriterOutput(dossier=dossier, script=script, quiz=quiz)
    monkeypatch.setattr("src.agents.writer_agent.LLMFactory.generate_json", fake)
    d, s, q = WriterAgent.write("Pulleys", "SCHOOL", 9, "Physics", ReelGenerationTier.FREE, topic_id="tid")
    assert seen["response_model"] is WriterOutput and seen["profile"] == "writer"
    assert "PART A" in seen["system_prompt"] and "PART B" in seen["system_prompt"] and "PART C" in seen["system_prompt"]
    assert s.total_word_count == sum(len(a.spoken_text.split()) for a in s.acts) and q.topicId == "tid"


def test_pending_quiz_is_tied_to_the_exact_script():
    from src.pipeline.orchestrator import PipelineOrchestrator
    s = _script()
    f1 = PipelineOrchestrator._script_fingerprint(s)
    s.acts[0].spoken_text += " Edited."
    assert PipelineOrchestrator._script_fingerprint(s) != f1


def test_equilibrium_fixture_lints_clean_and_curves_keep_growing_across_frames(tmp_path):
    """Chemistry prefabs expand and render; a self-drawing curve must lengthen from frame to frame (a stale GPU buffer once froze it)."""
    from PIL import Image
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "equilibrium.json")))
    assert _hard(Studio3DEngine.lint(spec)) == []
    files = Studio3DEngine.render_stills(spec, [1.5, 7.5], str(tmp_path))
    box = (560, 900, 1060, 1300)   # right-hand graph area inside the 3D window
    def ink(path):
        im = Image.open(path).convert("RGB").crop(box)
        return sum(1 for px in im.getdata() if px[0] > 200 and 120 < px[1] < 190 and px[2] < 120)  # orange curve pixels
    assert ink(files[1]) > ink(files[0]) * 2


def test_physics_simulator_matches_textbook_formulas():
    """node --test runs 11 checks: projectile, incline, rolling, pendulum, spring, collisions, Atwood, orbit, magnetic circle."""
    node = Studio3DEngine._node()
    res = subprocess.run([node, "--test", os.path.join(STUDIO_DIR, "tests")], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-500:]


def test_physics_projectile_fixture_uses_the_simulator_and_graph():
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "physics_projectile.json")))
    assert "sim" in spec["scenes"][0] and any(o.get("prefab") == "graph" for o in spec["scenes"][0]["objects"])
    assert _hard(Studio3DEngine.lint(spec)) == []


def test_physics_reel_without_simulator_gets_one_repair(monkeypatch, tmp_path):
    canned = json.load(open(os.path.join(CONFIG_DIR, "prompts", "scene3d_example_narrative.json")))   # no sim, no physics prefab
    with_sim = json.loads(json.dumps(canned))
    with_sim["scenes"][0]["sim"] = {"surfaces": [{"p1": [-1, 0], "p2": [6, 0], "mu": 0.5}], "bodies": [{"id": "ball", "kind": "ball", "pos": [0, 1], "vel": [3, 4]}]}
    with_sim["scenes"][0]["camera"]["fit"] = False   # keep the example camera; this test is about the repair flow
    calls = []

    def fake(**kw):
        calls.append(kw["user_prompt"])
        return ReelVisualPlan.model_validate(canned if len(calls) == 1 else with_sim)
    monkeypatch.setattr("src.agents.scene3d_director.LLMFactory.generate_json", fake)
    sb = Scene3DDirector.direct_storyboard(_script(), "Physics", 11, "SCHOOL", assets_dir=str(tmp_path))
    assert "no scene uses the motion simulator" not in calls[0]
    assert sum("no scene uses the motion simulator" in c for c in calls) == 1   # exactly one whole-plan repair
    assert "sim" in sb.scenes[0].scene3d
    calls.clear()
    Scene3DDirector.direct_storyboard(_script(), "Chemistry", 11, "SCHOOL", assets_dir=str(tmp_path))
    assert not any("no scene uses the motion simulator" in c for c in calls)   # the simulator is only demanded for physics


def test_sim_scene_is_framed_automatically():
    """A scene with a sim block and no camera hints still shows the whole motion (no cropping, floor of the look hidden)."""
    spec = {"version": 1, "look": "obsidian_lab", "layout": "explainer_window", "header": ["Projectile", "Motion"], "duration": 5, "scenes": [{
        "id": "a", "start": 0, "end": 5, "camera": {"position": [0, 0, 5], "target": [0, 0, 0]},
        "sim": {"surfaces": [{"p1": [-1, 0], "p2": [9, 0], "mu": 0.8, "e": 0.2}],
                "bodies": [{"id": "ball", "kind": "ball", "r": 0.25, "pos": [0, 0.3], "vel": [4, 6], "restitution": 0.4}]},
        "objects": []}]}
    problems = Studio3DEngine.lint(spec)
    assert not any("cropped" in p for p in problems), problems


def test_llm_payload_coercion_repairs_list_and_string_slips():
    from src.services.llm_factory import LLMFactory
    from src.models.schemas import DomainPedagogyDossier
    raw = {"canonical_topic": "t", "domain_field": "Physics", "exam_track": "S", "target_class_level": "11", "core_misconception": "m",
           "root_flaw": "r", "counter_intuitive_hook": "h", "curiosity_gap": "c", "must_include_concept": "x",
           "strictly_excluded_topics": "Air resistance; relativity.", "marking_scheme_keywords": "range, time of flight, apex",
           "concrete_visual_metaphor": ["a", "b"], "visual_transformation_beat": "b", "atomic_takeaway": "a"}
    m = DomainPedagogyDossier.model_validate(LLMFactory._coerce_payload(raw, DomainPedagogyDossier))
    assert m.strictly_excluded_topics == ["Air resistance", "relativity."]
    assert m.marking_scheme_keywords == ["range", "time of flight", "apex"] and m.concrete_visual_metaphor == "a; b"


def test_sim_without_surfaces_gets_a_ground_and_stays_in_view():
    spec = {"version": 1, "look": "obsidian_lab", "layout": "explainer_window", "header": ["A", "B"], "duration": 4, "scenes": [{
        "id": "a", "start": 0, "end": 4, "camera": {"position": [0, 0, 5], "target": [0, 0, 0]},
        "sim": {"bodies": [{"id": "ball", "kind": "ball", "r": 0.25, "pos": [0, 3], "vel": [2, 0]}]}, "objects": []}]}
    problems = Studio3DEngine.lint(spec)
    assert not any("black" in p or "travel far" in p for p in problems), problems


def test_a_floor_that_is_too_short_is_extended_automatically():
    spec = {"version": 1, "look": "obsidian_lab", "layout": "explainer_window", "header": ["A", "B"], "duration": 6, "scenes": [{
        "id": "a", "start": 0, "end": 6, "camera": {"position": [0, 0, 5], "target": [0, 0, 0]},
        "sim": {"surfaces": [{"p1": [0, 0], "p2": [3, 0], "mu": 0.2, "e": 0.3}],
                "bodies": [{"id": "ball", "kind": "ball", "r": 0.2, "pos": [1, 2], "vel": [4, 0]}]}, "objects": []}]}
    problems = Studio3DEngine.lint(spec)
    assert not any("black" in p or "travel far" in p for p in problems), problems


def test_springs_and_rods_are_drawn_automatically_and_the_fixture_is_clean(tmp_path):
    from PIL import Image
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "physics_spring.json")))
    assert _hard(Studio3DEngine.lint(spec)) == []
    f = Studio3DEngine.render_stills(spec, [1.0], str(tmp_path))[0]
    im = Image.open(f).convert("RGB").crop((0, 540, 540, 1390))   # left part of the window: wall and the coil
    light = sum(1 for px in im.getdata() if px[0] > 150 and px[1] > 150 and px[2] > 150)
    assert light > 800   # the coil adds many pale pixels to the area between the wall and the block


def test_scene_change_sound_effects_are_off_by_default(monkeypatch, tmp_path):
    import wave
    from src.engines.render.audio_mixer import AudioMixer
    from src.engines.render import sound_fx_engine
    from src.services.config_loader import load_json
    assert load_json("audio.json")["scene_change_sfx"] is False
    speech = str(tmp_path / "speech.wav")
    with wave.open(speech, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\x00\x00" * 2 * 22050)
    called = []
    monkeypatch.setattr(sound_fx_engine.SoundFXEngine, "overlay_storyboard_sfx", classmethod(lambda cls, **kw: called.append(1) or kw["base_samples"]))
    AudioMixer.mix_speech_and_bgm(speech, str(tmp_path / "mixed.wav"), storyboard=object())
    assert called == []


def test_explainer_kit_demo_lints_clean_and_pop_word_must_be_spoken():
    path = os.path.join(STUDIO_DIR, "fixtures", "kit_demo.json")
    spec = json.load(open(path))
    assert _hard(Studio3DEngine.lint(spec)) == []
    spec["scenes"][0]["overlays"].append({"kind": "pop", "word": "elephant"})
    problems = Studio3DEngine.lint(spec)
    assert any("elephant" in p for p in problems)
    from src.agents.scene3d_director import Scene3DDirector
    assert all(Scene3DDirector._is_soft(p) for p in problems if "elephant" in p)   # a decorative word never fails the reel


def test_kit_kinds_are_in_the_vocabulary_the_director_sees():
    from src.agents.scene3d_director import Scene3DDirector
    prompt = Scene3DDirector._system_prompt("biology")
    for word in ('"flow"', '"pop"', '"sticker"', "camera.tour", "style 'pin'"):
        assert word in prompt or word.strip('"') in prompt, word


def test_maths_parabola_fixture_lints_clean_and_uses_the_maths_kit():
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "maths_parabola.json")))
    assert spec["look"] == "maths_navy" and spec["layout"] == "maths" and len(spec["header"]) == 3
    assert Studio3DEngine.lint(spec) == []
    prefabs = {o.get("prefab") for sc in spec["scenes"] for o in sc["objects"]}
    assert {"cartesian", "value_table", "mascot_m"} <= prefabs


def test_maths_table_values_match_the_function():
    # the fixture's table is y = x^2 at x = -2, 0, 2
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "maths_parabola.json")))
    table = next(o for sc in spec["scenes"] for o in sc["objects"] if o.get("prefab") == "value_table")["params"]
    for k in (1, 2, 3):
        assert float(table[f"y{k}"]) == float(table[f"x{k}"]) ** 2


def test_maths_pack_prompt_carries_kit_manual_and_example():
    from src.agents.scene3d_director import Scene3DDirector
    prompt = Scene3DDirector._system_prompt("maths")
    for needle in ("cartesian", "value_table", "mascot_m", "maths_navy", "exactly 3 lines", "follow its style closely"):
        assert needle in prompt, needle
    assert "follow its style closely" not in Scene3DDirector._system_prompt("physics")


def test_parabola_focus_fixture_lints_clean_and_header_fits():
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "maths_focus.json")))
    assert Studio3DEngine.lint(spec) == []
    assert [sc["objects"][0]["params"].get("orient", 0) for sc in spec["scenes"]] == [0, 1]   # upward and sideways


def test_parabola_focus_prefab_computes_everything_from_p():
    # the curve is X^2/(4p) in the along-axis coordinate and every drawn point derives from p, so PF == PM by construction
    prefab = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "props", "parabola_focus.json")))
    text = json.dumps(prefab["objects"])
    assert text.count("-(${p})") >= 5 and text.count("${p}") >= 15
    assert prefab["params"]["w"] / (prefab["params"]["xmax"] - prefab["params"]["xmin"]) == prefab["params"]["h"] / (prefab["params"]["ymax"] - prefab["params"]["ymin"])   # equal axis scales


def test_parabola_focus_supports_both_orientations_with_the_focus_derived_from_p():
    prefab = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "props", "parabola_focus.json")))
    assert prefab["params"]["orient"] == 0 and "orient" in prefab["params_doc"]
    cart = next(o for o in prefab["objects"] if o.get("prefab") == "cartesian")["params"]
    assert "X^2/(4*${p})" in cart["x1"] and "X^2/(4*${p})" in cart["y1"]   # one formula, axes swapped by orient


def test_narrator_follows_the_routed_pack_persona():
    from src.services.concept_router import route
    physics = Studio3DEngine.narrator_spec(route("Physics", "x", use_llm=False))
    chem = Studio3DEngine.narrator_spec(route("Chemistry", "x", use_llm=False))
    assert physics["name"] == "einstein_photo" and physics["kind"] == "photo" and physics["photo"]["voice"]["id"]
    assert chem["name"] == "rutherford_like" and chem["kind"] == "rig"
    assert Studio3DEngine.narrator_spec(route("Mathematics", "x", use_llm=False)) is None
    assert Studio3DEngine.narrator_spec(None) is None
    assert {"distance", "pose_by_overlay", "default_pose", "voice", "photo"} <= set(physics) and "params" in chem


def test_character_configs_only_set_parameters_the_narrator_prefab_has():
    prefab = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "props", "narrator.json")))
    cfg_dir = os.path.join(os.path.dirname(STUDIO_DIR), "config", "characters")
    assert os.listdir(cfg_dir)
    for f in os.listdir(cfg_dir):
        if not f.endswith(".json"):
            continue
        char = json.load(open(os.path.join(cfg_dir, f)))
        if char.get("kind") == "photo":
            assert {"image", "crop", "landmarks", "motion", "frame", "voice"} <= set(char), f
            continue
        assert set(char["params"]) <= set(prefab["params"]), f
    poses = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "poses.json")))
    nar = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "narrator.json")))
    for pose in [nar["default_pose"], nar["last_scene_pose"], *nar["pose_by_overlay"].values()]:
        assert pose in poses, pose


def test_narrator_demo_lints_clean_and_layouts_without_a_slot_get_no_narrator():
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "narrator_demo.json")))
    assert Studio3DEngine.lint(spec) == []
    spec["layout"] = "maths"   # no narrator slot in this layout: the character is simply not drawn
    assert Studio3DEngine.lint(spec) == []


def test_build_spec_embeds_the_narrator_and_the_director_is_told_to_keep_the_corner_free():
    from types import SimpleNamespace
    from src.agents.scene3d_director import Scene3DDirector
    from src.services.concept_router import route
    scene = SimpleNamespace(scene_number=1, scene3d={"beat": 1, "camera": {"position": [0, 1, 6], "target": [0, 1, 0]}, "objects": []}, start_sec=0, end_sec=3)
    sb = SimpleNamespace(scenes=[scene], layout="explainer_window", header=["A", "B"], route=route("Physics", "x", use_llm=False))
    assert Studio3DEngine.build_spec(sb, look="obsidian_lab")["narrator"]["name"] == "einstein_photo"
    sb.route = route("Mathematics", "x", use_llm=False)
    assert "narrator" not in Studio3DEngine.build_spec(sb, look="maths_navy")
    assert "narrator character stands" in Scene3DDirector._system_prompt("physics")
    assert "narrator character stands" not in Scene3DDirector._system_prompt("maths")


def test_photo_narrator_has_its_source_and_licence_recorded_and_falls_back_to_the_rig_without_it(monkeypatch):
    base = os.path.join(os.path.dirname(STUDIO_DIR), "config", "characters")
    photo = json.load(open(os.path.join(base, "einstein_photo.json")))
    src = json.load(open(os.path.join(base, "photos", "einstein_turner_1947.source.json")))
    assert src["source"].startswith("https://commons.wikimedia.org/") and "EU/UK" in src["licence_note"]
    import hashlib
    assert hashlib.sha1(open(os.path.join(base, "photos", src["file"]), "rb").read()).hexdigest() == src["sha1_expected"]
    assert os.path.exists(os.path.join(os.path.dirname(STUDIO_DIR), photo["image"].lstrip("/")))
    from src.services.concept_router import route
    monkeypatch.setattr("os.path.exists", lambda p: False if str(p).endswith("_puppet.jpg") else os.path.isfile(p) or os.path.isdir(p))
    assert Studio3DEngine.narrator_spec(route("Physics", "x", use_llm=False))["kind"] == "rig"   # photo missing: cartoon rig fallback


def test_photo_narrator_demo_lints_clean():
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "narrator_demo_photo.json")))
    assert spec["narrator"]["kind"] == "photo" and Studio3DEngine.lint(spec) == []


def test_an_invented_material_preset_is_replaced_by_the_closest_real_one_and_never_fails_the_reel():
    from src.agents.scene3d_director import Scene3DDirector
    spec = json.load(open(FIXTURE))
    spec["scenes"][0]["objects"].append({"type": "sphere", "radius": 0.3, "position": [0, 1, 0], "material": "dark_steel"})
    spec["scenes"][0]["objects"].append({"type": "sphere", "radius": 0.3, "position": [1, 1, 0], "material": "zzz_unknown"})
    problems = [p for p in Studio3DEngine.lint(spec) if "material" in p]
    assert any('"dark_steel", using "metal"' in p for p in problems)
    assert any('"zzz_unknown"' in p for p in problems)
    assert all(Scene3DDirector._is_soft(p) for p in problems)


def test_subject_must_fill_the_picture_and_stay_clear_of_the_narrator_corner():
    from src.agents.scene3d_director import Scene3DDirector
    spec = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "narrator_demo_photo.json")))
    spec["scenes"][0]["objects"].append({"id": "ball", "type": "sphere", "radius": 0.5, "position": [1.6, 0.5, 0]})   # lands behind the portrait
    problems = Studio3DEngine.lint(spec)
    assert any("behind the narrator's portrait" in p for p in problems)
    tiny = json.load(open(os.path.join(STUDIO_DIR, "fixtures", "narrator_demo_photo.json")))
    tiny["scenes"][0]["camera"] = {"position": [0, 1.4, 30], "target": [0, 1.0, 0], "fov": 40}
    small = Studio3DEngine.lint(tiny)
    assert any("the subject fills only" in p for p in small)
    assert all(Scene3DDirector._is_soft(p) for p in problems + small if "narrator" in p or "fills only" in p)


def _lab_spec(params):
    return {"version": 1, "look": "daylight_studio", "layout": "explainer_window", "header": ["Chem", "Lab"], "duration": 8, "fps": 30, "captions": [],
            "scenes": [{"id": "a", "start": 0, "end": 8, "floor": False, "camera": {"position": [0.3, 1.8, 7.6], "target": [0.3, 2.0, 0]},
                        "objects": [{"type": "prop", "prefab": "particle_lab", "params": params, "position": [-0.4, 0, 0]}], "overlays": []}]}


def test_every_chemistry_recipe_renders_without_unknown_variables_or_functions():
    recipes = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "chem_recipes.json")))
    assert {"le_chatelier_pressure", "le_chatelier_concentration", "le_chatelier_temperature_exothermic", "equal_moles_no_shift", "boyle_law"} <= set(recipes)
    for name, r in recipes.items():
        problems = [p for p in Studio3DEngine.lint(_lab_spec(r["params"])) if "Unknown" in p or "black" in p or "NaN" in p]
        assert problems == [], (name, problems)


def test_particle_lab_documents_its_parameters_and_uses_the_solver_for_every_species():
    lab = json.load(open(os.path.join(os.path.dirname(STUDIO_DIR), "config", "props", "particle_lab.json")))
    assert set(lab["params"]) - {"K"} <= set(lab["params_doc"])
    species = [o for o in lab["objects"] if o["type"] == "particles"]
    assert len(species) == 4 and all("eqext(" in o["vars"]["xi"] and "xi" in o["radius"] for o in species)   # counts come from the solver
    assert lab["params"]["K"].startswith("Keq(")


def test_chemistry_claims_catch_unbalanced_equations_and_wrong_molar_masses():
    from src.services import math_verifier as mv
    C = lambda **k: mv.MathClaim(quote="q", **k)
    for ok in ("N2 + 3H2 <=> 2NH3", "2H2 + O2 -> 2H2O", "Ca(OH)2 + 2HCl -> CaCl2 + 2H2O", "CuSO4.5H2O -> CuSO4 + 5H2O", "C3H8 + 5O2 → 3CO2 + 4H2O", "H2(g) + I2(g) ⇌ 2HI(g)"):
        assert mv.check_claim(C(kind="balanced", expr=ok)) is None, ok
    bad = mv.check_claim(C(kind="balanced", expr="N2 + H2 -> NH3"))
    assert "not balanced" in bad and "N: 2 on the left, 1 on the right" in bad
    assert mv.check_claim(C(kind="balanced", expr="2 + 3")) is not None
    assert mv.check_claim(C(kind="molar_mass", expr="H2O", equals=18)) is None
    assert mv.check_claim(C(kind="molar_mass", expr="Ca(OH)2", equals=74.1)) is None
    assert "18.02" in mv.check_claim(C(kind="molar_mass", expr="H2O", equals=19))
    assert mv.check_claim(C(kind="molar_mass", expr="Xx2", equals=5)) is not None


def test_chemistry_prompt_requires_the_lab_and_balanced_ce_equations():
    from src.agents.scene3d_director import Scene3DDirector
    p = Scene3DDirector._system_prompt("chemistry")
    for needle in ("particle_lab", "eqext", "\\ce{N2(g)", "le_chatelier_temperature_exothermic", "molecule_h2o", "balanced"):
        assert needle in p, needle
    assert "{{" not in p and "le_chatelier_pressure" not in Scene3DDirector._system_prompt("maths")   # the recipes are only in the chemistry pack text


def test_lab_is_one_experiment_across_scenes_and_pop_words_are_checked_against_estimated_timings():
    lab = lambda **p: {"type": "prop", "id": "lab", "prefab": "particle_lab", "params": p}
    designs = {1: {"objects": [lab(a=2, b=1, c=2, d=0, nA=16, nB=8, nC=12, cA="#111111", lA="NO", vol=1)]},
               2: {"objects": [lab(a=1, b=3, c=2, d=0, nA=5, vol="mix(1,0.4,t)", dA=3)]}}
    Scene3DDirector._unify_labs(designs)
    second = designs[2]["objects"][0]["params"]
    assert (second["a"], second["b"], second["nA"], second["cA"], second["lA"]) == (2, 1, 16, "#111111", "NO")
    assert second["vol"] == "mix(1,0.4,t)" and second["dA"] == 3
    caps = Studio3DEngine.estimate_captions([("Squeeze the gas now", 2.0, 6.0)])
    assert [c["w"] for c in caps] == ["Squeeze", "the", "gas", "now"] and caps[0]["t0"] == 2.0 and caps[-1]["t1"] == 6.0
    spec = _lab_spec({})
    spec["captions"] = caps; spec["scenes"][0].update({"start": 2.0, "end": 6.0})
    spec["scenes"][0]["overlays"] = [{"kind": "pop", "word": "squeeze"}, {"kind": "pop", "word": "volcano"}]
    problems = [p for p in Studio3DEngine.lint(spec) if "pop word" in p]
    assert len(problems) == 1 and "volcano" in problems[0]


def test_triatomic_molecule_prefab_and_lab_legend_render_with_true_geometry():
    spec = _lab_spec({"lA": "NO", "lB": "O₂", "lC": "NO₂", "a": 2, "b": 1, "c": 2, "d": 0})
    spec["scenes"][0]["objects"].append({"type": "prop", "prefab": "molecule_triatomic", "position": [1.5, 1.0, 0], "params": {"angle": 134}})
    assert [p for p in Studio3DEngine.lint(spec) if "Unknown" in p or "NaN" in p] == []
    assert "molecule_triatomic" in json.dumps(load_json("props", "molecule_triatomic.json")["about"] and Scene3DDirector._prop_library())
    assert load_json("layouts", "explainer_window.json")["header"]["fit"] is True
