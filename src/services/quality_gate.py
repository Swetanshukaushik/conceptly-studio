"""Quality gate: a fixed, config-driven checklist every reel must pass before the creator sees it.

evaluate() reads only the script dict (so it works on stored jobs); thresholds live in config/quality_gate.json.
Figure and quiz consistency live in this module too: numbers drawn on screen must be numbers the narrator says or the
verifier checked, and the quiz key must agree with the narration.
"""
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.services.config_loader import load_json
from src.services.math_verifier import numbers_in


def _cfg() -> Dict[str, Any]:
    return load_json("quality_gate.json")


def _narration(script: Dict[str, Any]) -> str:
    sb = script.get("storyboard") or {}
    lines = [s.get("spoken_line", "") for s in sb.get("scenes", [])]
    return " ".join(lines) if lines else " ".join(a.get("spoken_text", "") for a in script.get("acts", []))


def _overlay_texts(scene3d: Dict[str, Any], kinds: List[str]) -> List[str]:
    out: List[str] = []
    for o in scene3d.get("overlays", []):
        if o.get("kind") not in kinds:
            continue
        for key in ("text", "latex", "caption", "value", "label"):
            if o.get(key):
                out.append(str(o[key]))
        out += [str(x) for x in o.get("lines", [])]
    return out


def figure_problems(script: Dict[str, Any]) -> List[str]:
    """Numbers shown in cards and tags that nobody says or verified. Small numbers (coefficients, counts) are ignored."""
    cfg = _cfg(); sb = script.get("storyboard") or {}
    allowed = set(numbers_in(_narration(script)))
    for claim in script.get("math_claims") or []:
        allowed.update(abs(float(x)) for x in claim.get("stated", []) if isinstance(x, (int, float)))
        allowed.update(numbers_in(claim.get("quote", "")))
    problems = []
    for sc in sb.get("scenes", []):
        for text in _overlay_texts(sc.get("scene3d") or {}, cfg["figure_text_kinds"]):
            for n in numbers_in(re.sub(r"\\[a-zA-Z]+", " ", text)):
                if n >= cfg["figure_ignore_below"] and n not in allowed:
                    problems.append(f"scene {sc.get('scene_number')}: the screen shows {n:g} but the narration never says it")
    return list(dict.fromkeys(problems))


class _QuestionVerdict(BaseModel):
    id: str
    ok: bool = True
    issue: str = ""


class _QuizVerdict(BaseModel):
    questions: List[_QuestionVerdict] = Field(default_factory=list)


def quiz_problems(quiz: Dict[str, Any], script: Dict[str, Any], tier: Any = None, provider: str = "AUTO") -> List[str]:
    """Asks one cheap model call whether each marked answer agrees with the narration and the verified claims. Never raises."""
    if not quiz or not quiz.get("questions"):
        return []
    cfg = _cfg()
    facts = "\n".join(f"- {c.get('quote', '')}" for c in script.get("math_claims") or []) or "(none)"
    rendered = "\n".join(
        f"{q['id']}: {q['text']} " + " | ".join(f"{o['id']}) {o['text']}" for o in q["options"]) + f" | marked correct: {q['correctOptionId']} | explanation: {q.get('explanation', '')}"
        for q in quiz["questions"])
    prompt = cfg["quiz_check_prompt"].replace("{narration}", _narration(script)).replace("{facts}", facts).replace("{quiz}", rendered)
    try:
        from src.services.llm_factory import LLMFactory
        if tier is None:
            from src.models.schemas import ReelGenerationTier
            tier = ReelGenerationTier.FREE
        verdict = LLMFactory.generate_json(system_prompt="You are a careful exam setter.", user_prompt=prompt, response_model=_QuizVerdict, tier=tier, provider=provider, profile="lite")
    except Exception:
        return []
    return [f"{v.id}: {v.issue or 'answer key disagrees with the narration'}" for v in verdict.questions if not v.ok]


def evaluate(script: Dict[str, Any], quiz_issues: Optional[List[str]] = None, tier_limits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Returns {passed, score, checks: [{id, label, ok, blocking, detail}]}."""
    cfg = _cfg(); sb = script.get("storyboard") or {}; scenes = sb.get("scenes", [])
    checks: List[Dict[str, Any]] = []

    def add(cid: str, label: str, ok: bool, detail: str = ""):
        checks.append({"id": cid, "label": label, "ok": bool(ok), "blocking": cid in cfg["blocking"], "detail": detail})

    total = scenes[-1]["end_sec"] if scenes else 0
    lo = (tier_limits or {}).get("min_seconds", cfg["min_seconds"]); hi = (tier_limits or {}).get("max_seconds", cfg["max_seconds"])
    add("duration", f"Length {lo}-{hi} s", lo <= total <= hi, f"{total:.0f} s")
    add("scenes", f"At least {cfg['min_scenes']} scenes", len(scenes) >= cfg["min_scenes"], f"{len(scenes)} scenes")
    longest = max((s["end_sec"] - s["start_sec"] for s in scenes), default=0)
    add("pacing", f"No beat longer than {cfg['max_beat_seconds']} s", longest <= cfg["max_beat_seconds"], f"longest {longest:.1f} s")

    first = scenes[0] if scenes else {}; first_len = first.get("end_sec", 0) - first.get("start_sec", 0)
    line = str(first.get("spoken_line", "")).lower()
    add("hook", "Opens with a hook in the first beat", first_len <= cfg["hook"]["max_first_beat_seconds"] and any(m in line for m in cfg["hook"]["markers"]),
        f"{first_len:.1f} s: \"{line[:70]}\"")

    header = sb.get("header") or []
    add("header", f"Header lines at most {cfg['max_header_line_chars']} characters", all(len(h) <= cfg["max_header_line_chars"] for h in header), " / ".join(header))

    mv = script.get("math_verification") or {}
    uncovered = [n for n in mv.get("notes", []) if "not covered" in n]
    add("verified_numbers", "Every narrated number is checked", mv.get("status") in ("verified", "no_numbers") and len(uncovered) <= cfg["max_uncovered_number_notes"],
        f"{mv.get('status', 'not run')}, {mv.get('claims', 0)} claims, {len(uncovered)} uncovered")

    fig = figure_problems(script)
    add("figures", "Numbers on screen are spoken or verified", not fig, "; ".join(fig[:3]))

    qa = sb.get("qa") or []
    weak = [n for n in qa if "after one retry" in n]
    add("vision", f"No scene stuck below {cfg['min_vision_score']}/10 after retry", not weak, "; ".join(weak[:2])[:200])
    add("qa_notes", f"At most {cfg['max_qa_notes']} layout notes", len(qa) <= cfg["max_qa_notes"], f"{len(qa)} notes")

    kinds = {o.get("kind") for s in scenes for o in (s.get("scene3d") or {}).get("overlays", [])}
    if not script.get("premium"):   # Premium scenes are single generated stills; variety comes from the images and camera moves
        add("variety", f"At least {cfg['min_distinct_overlay_kinds']} kinds of on-screen elements", len(kinds) >= cfg["min_distinct_overlay_kinds"], ", ".join(sorted(k for k in kinds if k)))

    add("quiz", "Quiz answers agree with the narration", not quiz_issues, "; ".join(quiz_issues or [])[:200])

    prem = script.get("premium")
    if prem:
        pc = cfg["premium"]; img = prem.get("images", {}); total_imgs = max(1, sum(v for k, v in img.items() if k != "shared"))
        frac = img.get("generated", 0) / total_imgs
        add("images_generated", f"At least {int(pc['min_generated_fraction'] * 100)}% of stills are generated", frac >= pc["min_generated_fraction"],
            f"{img.get('generated', 0)} generated, {img.get('archive', 0)} archive, {img.get('archive_fallback', 0)} fallback, {img.get('none', 0)} none")
        scores = [v["score"] for v in prem.get("per_beat", {}).values() if v.get("source") == "generated" and v.get("score") is not None]
        add("image_quality", f"Generated stills score {pc['min_image_score']}+/10 on review", all(sc >= pc["min_image_score"] for sc in scores), f"lowest {min(scores):g}" if scores else "no reviewed stills")
        cons = (prem.get("consistency") or {}).get("score")
        add("consistency", f"Stills look like one video ({pc['min_consistency']}+/10)", cons is None or cons >= pc["min_consistency"], "not reviewed" if cons is None else f"{cons:g}/10")
        fr = prem.get("facts") or {}
        add("facts", "No claim contradicts its sources", fr.get("status") != "flagged",
            ("; ".join(f"{c['claim']} ({c.get('note', '')})" for c in fr.get("claims", []) if c.get("verdict") == "contradicted")[:200]) if fr.get("status") == "flagged"
            else f"{fr.get('status', 'not run')}: {fr.get('supported', 0)} supported, {fr.get('unverified', 0)} unverified")
        cost = prem.get("cost") or {}
        add("cost", "Spend within the per-reel cap", cost.get("spent_usd", 0) <= cost.get("cap_usd", 0) + 1e-9, f"${cost.get('spent_usd', 0):.3f} of ${cost.get('cap_usd', 0):.2f}")

    ok = sum(1 for c in checks if c["ok"])
    return {"passed": all(c["ok"] for c in checks if c["blocking"]), "score": f"{ok}/{len(checks)}", "checks": checks}
