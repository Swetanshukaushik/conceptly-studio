"""Style bible and people policy for generated stills: one style block shared by every image of a reel, a negative list, and
a sanitiser that keeps prompts free of text requests, named people and likeness hooks."""
import re
from typing import Any, Dict, List, Optional

from src.services.config_loader import load_json


def cfg() -> Dict[str, Any]:
    return load_json("premium.json")


def style_for(pack: Optional[str]) -> Dict[str, Any]:
    styles = cfg()["styles"]
    return styles.get(pack or "", styles["default"])


def style_block(pack: Optional[str]) -> str:
    return cfg()["style_template"].format(**{k: style_for(pack).get(k, "") for k in ("medium", "palette", "lighting", "lens", "era_note")}).replace("  ", " ").strip()


def sanitize_prompt(prompt: str, named_people: Optional[List[str]] = None) -> Dict[str, Any]:
    """Returns {prompt, notes}. Named people become a generic figure; text-request phrases are removed."""
    policy = cfg()["policy"]; notes: List[str] = []; text = " ".join((prompt or "").split())
    for name in sorted({n.strip() for n in (named_people or []) if n and n.strip()}, key=len, reverse=True):
        parts = [name] + [p for p in name.split() if len(p) > 3 and p[0].isupper()]
        for variant in parts:
            if re.search(re.escape(variant), text, flags=re.I):
                text = re.sub(re.escape(variant), policy["named_person_replacement"], text, flags=re.I)
                notes.append(f"replaced the name '{variant}' with a generic figure")
    for phrase in policy["banned_prompt_phrases"]:
        if re.search(re.escape(phrase), text, flags=re.I):
            text = re.sub(re.escape(phrase), "", text, flags=re.I); notes.append(f"removed '{phrase}'")
    text = " ".join(text.split())[: policy["max_prompt_chars"]]
    return {"prompt": text, "notes": notes}


def full_prompt(pack: Optional[str], shot_prompt: str, avoid: Optional[List[str]] = None) -> str:
    extra = (" Avoid: " + "; ".join(avoid) + ".") if avoid else ""
    return f"{style_block(pack)}\n\nScene: {shot_prompt}\n\n{cfg()['negative']}{extra}"
