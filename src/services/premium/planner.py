"""Shot planner: one LLM call turns the narration beats into a shot list (image prompt, framing, camera move, tags)."""
import math
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.services.config_loader import load_text
from src.services.premium import style


class Pin(BaseModel):
    text: str
    x: float = 0.5
    y: float = 0.5


class Shot(BaseModel):
    beat: int
    shot_type: Literal["establishing", "medium", "detail", "wide", "diagram"] = "medium"
    prompt: str
    named_people: List[str] = Field(default_factory=list)
    real_photo_query: Optional[str] = None
    motion: Literal["push_in", "pull_out", "pan_left", "pan_right", "drift_up", "drift_down"] = "push_in"
    title: Optional[str] = None
    pop_word: Optional[str] = None
    pins: List[Pin] = Field(default_factory=list)
    reuse_previous: bool = False


class ShotPlan(BaseModel):
    style_note: str = ""
    shots: List[Shot]


def system_prompt(pack_name: Optional[str]) -> str:
    from src.services.concept_router import get_pack, pack_prompt
    pack = get_pack(pack_name)
    pack_text = f"Domain: {pack['label']}. " + pack.get("summary", "")
    extra = style.style_for(pack_name)
    pack_text += f"\nHouse style: {extra['medium']}; palette {extra['palette']}; {extra['lighting']}; {extra['era_note']}"
    return load_text("prompts", "premium_planner.md").replace("{{PACK}}", pack_text)


def user_prompt(topic: str, subject: str, beats: List[Dict[str, Any]]) -> str:
    lines = "\n".join(f"Beat {b['beat']} | ~{b['seconds']}s | \"{b['text']}\"" for b in beats)
    return f"Topic: {topic}\nSubject: {subject}\n\nPlan one shot per beat:\n{lines}"


def _word_in(text: str, word: str) -> bool:
    return bool(word) and re.search(r"(?<!\w)" + re.escape(word.strip(" .,!?").lower()) + r"(?!\w)", text.lower()) is not None


def clean_plan(plan: ShotPlan, beats: List[Dict[str, Any]], pack_name: Optional[str]) -> Dict[str, Any]:
    """Enforces the people/text policy and drops anything the narration does not support. Returns {shots, notes}."""
    by_beat = {s.beat: s for s in plan.shots}; notes: List[str] = []; shots: List[Shot] = []
    for b in beats:
        shot = by_beat.get(b["beat"])
        if shot is None:   # the planner skipped a beat: reuse the neighbouring look with the narration as the prompt
            shot = Shot(beat=b["beat"], prompt=b["text"][:300]); notes.append(f"beat {b['beat']}: no shot planned, used the narration as the prompt")
        clean = style.sanitize_prompt(shot.prompt, shot.named_people)
        shot.prompt = clean["prompt"] or b["text"][:300]
        notes += [f"beat {b['beat']}: {n}" for n in clean["notes"]]
        if shot.pop_word and not _word_in(b["text"], shot.pop_word):
            shot.pop_word = None
        shots.append(shot)
    notes += enforce_sharing(shots)
    return {"shots": shots, "notes": notes}


def enforce_sharing(shots: List[Shot]) -> List[str]:
    """A still may only be shared by plain shots, and the share count is capped by config so cost stays predictable."""
    cfg = style.cfg()["sharing"]; comp = cfg["complement"]; notes: List[str] = []
    for i, s in enumerate(shots):
        prev = shots[i - 1] if i else None
        if s.reuse_previous and (prev is None or s.pins or s.real_photo_query or prev.real_photo_query or prev.pins):
            s.reuse_previous = False; notes.append(f"beat {s.beat}: cannot share the previous still, gets its own")
    limit = max(1, math.ceil(len(shots) * cfg["max_unique_fraction"]))
    for i, s in enumerate(shots):   # too many unique images: share every second plain shot, from the end of each run, until within the limit
        if sum(1 for x in shots if not x.reuse_previous) <= limit:
            break
        prev = shots[i - 1] if i else None
        if prev and not s.reuse_previous and not (s.pins or s.real_photo_query or prev.real_photo_query or prev.pins) and not prev.reuse_previous:
            s.reuse_previous = True; notes.append(f"beat {s.beat}: shares beat {prev.beat}'s still to stay within {limit} images")
    for i, s in enumerate(shots):
        if s.reuse_previous and s.motion == shots[i - 1].motion:
            s.motion = comp[s.motion]
    return notes


def plan_shots(topic: str, subject: str, beats: List[Dict[str, Any]], pack_name: Optional[str], tier: Any, provider: str = "AUTO") -> Dict[str, Any]:
    from src.services.llm_factory import LLMFactory
    plan = LLMFactory.generate_json(system_prompt=system_prompt(pack_name), user_prompt=user_prompt(topic, subject, beats),
                                    response_model=ShotPlan, tier=tier, provider=provider, profile="director")
    out = clean_plan(plan, beats, pack_name); out["style_note"] = plan.style_note
    return out
