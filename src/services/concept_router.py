"""Concept Router: picks the domain pack for a topic.

Packs live in config/packs/*.json (one per domain, plus `generic`). Routing is rule-based first
(subject aliases declared in each pack), then one cheap LLM classification for subjects no pack claims,
then the generic pack. The decision is plain data, stored with the storyboard so Gate 1 can show it.
"""
import glob
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.services.config_loader import CONFIG_DIR, load_json, load_text

FALLBACK_PACK = "generic"


@lru_cache(maxsize=1)
def load_packs() -> Dict[str, Dict[str, Any]]:
    packs: Dict[str, Dict[str, Any]] = {}
    for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "packs", "*.json"))):
        pack = load_json("packs", os.path.basename(path))
        packs[pack["name"]] = pack
    if FALLBACK_PACK not in packs:
        raise RuntimeError(f"config/packs must define the '{FALLBACK_PACK}' pack")
    return packs


def get_pack(name: Optional[str]) -> Dict[str, Any]:
    packs = load_packs()
    return packs.get(name or "", packs[FALLBACK_PACK])


def pack_prompt(name: Optional[str]) -> str:
    return load_text("prompts", *get_pack(name)["prompt"].split("/")).strip()


def _norm(text: Optional[str]) -> str:
    return " ".join((text or "").lower().replace("&", " and ").replace("-", " ").split())


def _match_subject(subject: str) -> Optional[str]:
    needle = _norm(subject)
    if not needle:
        return None
    for name, pack in load_packs().items():
        if needle in [_norm(s) for s in pack.get("subjects", [])]:
            return name
    padded = f" {needle} "
    for name, pack in load_packs().items():   # whole-word containment, e.g. "Class 11 Physics"
        if any(f" {_norm(s)} " in padded for s in pack.get("subjects", []) if s):
            return name
    return None


class _RouteChoice(BaseModel):
    pack: str = Field(..., description="Exactly one pack name from the list")
    reason: str = Field(..., description="One short sentence")


def _classify_with_llm(subject: str, topic: str, tier: Any, provider: str) -> Optional[_RouteChoice]:
    from src.services.llm_factory import LLMFactory
    packs = load_packs()
    listing = "\n".join(
        f"- {n}: {p['summary']} Subjects: {', '.join(p.get('subjects', [])) or 'none'}" for n, p in packs.items() if n != FALLBACK_PACK
    )
    system = (
        "You route an educational topic to the one domain pack best suited to teach it as a short video. "
        f"Pick exactly one pack name from the list, or '{FALLBACK_PACK}' when none fits.\n" + listing
    )
    try:
        choice = LLMFactory.generate_json(
            system_prompt=system, user_prompt=f"Subject: {subject}\nTopic: {topic}",
            response_model=_RouteChoice, tier=tier, provider=provider, profile="lite",
        )
    except Exception:
        return None
    return choice if choice.pack in packs else None


def route(subject: str, topic_title: str = "", tier: Any = None, provider: str = "AUTO", use_llm: bool = True) -> Dict[str, Any]:
    """Return the routing decision for a topic. Never raises: unknown subjects fall back to the generic pack."""
    method, reason, name = "rule", "subject matches the pack", _match_subject(subject)
    if name is None and use_llm and (subject or topic_title):
        if tier is None:
            from src.models.schemas import ReelGenerationTier
            tier = ReelGenerationTier.FREE
        choice = _classify_with_llm(subject, topic_title, tier, provider)
        if choice:
            name, method, reason = choice.pack, "llm", choice.reason
    if name is None:
        name, method, reason = FALLBACK_PACK, "fallback", "no pack claims this subject"
    pack = get_pack(name)
    return {
        "pack": name, "label": pack["label"], "method": method, "reason": reason, "status": pack["status"],
        "layout_hint": pack.get("layout_hint"), "look_hint": pack.get("look_hint"), "requires_sim": bool(pack.get("requires_sim")),
        "kits": list(pack.get("kits", [])), "verification": list(pack.get("verification", [])), "persona": pack.get("persona"),
    }


def catalog() -> List[Dict[str, Any]]:
    return [{k: v for k, v in p.items() if k != "prompt"} for p in load_packs().values()]
