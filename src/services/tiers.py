"""Tier definitions live in config/tiers.json; this module only reads them."""
import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    with open(os.path.join(CONFIG_DIR, "tiers.json"), encoding="utf-8") as f:
        return json.load(f)


def resolve_tier(value: Optional[str]) -> str:
    """Map any stored tier value (legacy enum names included) to a configured tier key."""
    data = _load()
    needle = (value or "").strip().upper()
    for key, tier in data["tiers"].items():
        if needle == key.upper() or needle in [a.upper() for a in tier.get("aliases", [])]:
            return key
    return data["default_tier"]


def get_tier(value: Optional[str]) -> Dict[str, Any]:
    key = resolve_tier(value)
    return {"key": key, **_load()["tiers"][key]}


def require_available(value: Optional[str]) -> Dict[str, Any]:
    tier = get_tier(value)
    if tier["status"] != "available":
        raise RuntimeError(f"Tier '{tier['label']}' is {tier['status']} and cannot render yet.")
    return tier


def catalog() -> Dict[str, Any]:
    """All tiers in display order, for the API and UI."""
    data = _load()
    return {"default_tier": data["default_tier"], "tiers": [{"key": k, **v} for k, v in data["tiers"].items()]}
