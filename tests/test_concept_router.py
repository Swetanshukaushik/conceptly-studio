import glob
import os

import pytest

from src.agents.scene3d_director import Scene3DDirector
from src.services import concept_router as cr
from src.services.config_loader import CONFIG_DIR, load_looks


@pytest.mark.parametrize("subject,pack", [
    ("Physics", "physics"), ("  physics ", "physics"), ("Class 11 Physics", "physics"),
    ("Chemistry", "chemistry"), ("Mathematics", "maths"), ("Maths", "maths"),
    ("Biology", "biology"), ("History", "history_civics"), ("Indian Polity", "history_civics"),
    ("System Design", "tech"), ("Product Management", "tech"), ("Software Development", "tech"),
])
def test_rule_routing_by_subject(subject, pack):
    d = cr.route(subject, "any topic", use_llm=False)
    assert d["pack"] == pack and d["method"] == "rule"


def test_unknown_subject_falls_back_without_llm():
    d = cr.route("Origami", "Crane", use_llm=False)
    assert d["pack"] == "generic" and d["method"] == "fallback"


def test_unknown_subject_uses_llm_choice(monkeypatch):
    monkeypatch.setattr(cr, "_classify_with_llm", lambda *a, **k: cr._RouteChoice(pack="biology", reason="cells"))
    d = cr.route("Zoology", "Cell division")
    assert (d["pack"], d["method"]) == ("biology", "llm")


def test_llm_failure_or_bad_pack_falls_back(monkeypatch):
    monkeypatch.setattr(cr, "_classify_with_llm", lambda *a, **k: None)
    assert cr.route("Zoology", "x")["pack"] == "generic"


def test_rule_match_never_calls_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLM must not be called for a known subject")
    monkeypatch.setattr(cr, "_classify_with_llm", boom)
    assert cr.route("Physics", "Projectile Motion")["pack"] == "physics"


def test_every_pack_is_consistent_with_the_rest_of_the_config():
    looks = load_looks()
    layouts = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(CONFIG_DIR, "layouts", "*.json"))}
    for name, pack in cr.load_packs().items():
        assert pack["name"] == name
        assert pack["look_hint"] in looks and pack["layout_hint"] in layouts
        assert cr.pack_prompt(name)
        assert pack["status"] in {"ready", "partial", "planned"}


def test_subject_aliases_do_not_collide():
    seen = {}
    for name, pack in cr.load_packs().items():
        for s in pack.get("subjects", []):
            assert s not in seen, f"'{s}' claimed by {seen[s]} and {name}"
            seen[s] = name


def test_director_prompt_carries_the_pack_and_only_physics_carries_the_simulator_manual():
    physics = Scene3DDirector._system_prompt("physics")
    maths = Scene3DDirector._system_prompt("maths")
    assert "Domain pack: Physics" in physics and "motion simulator" in physics and "sim =" in physics
    assert "Domain pack: Mathematics" in maths and "sim =" not in maths
    assert "{{" not in physics and "{{" not in maths
    assert "Domain pack: General explainer" in Scene3DDirector._system_prompt(None)


def test_gemini_requests_have_a_configured_timeout_so_a_hung_call_falls_through_to_the_next_model():
    from src.services.llm_factory import LLMFactory
    assert 30 <= LLMFactory._gemini_timeout() <= 600
    import inspect
    src = inspect.getsource(LLMFactory.generate_json)
    assert src.count("generate_content(user_prompt, request_options") == 2 and "generate_content(user_prompt)" not in src
