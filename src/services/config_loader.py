import json
import os
from functools import lru_cache
from typing import Any, Dict

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")


@lru_cache(maxsize=None)
def load_json(*parts: str) -> Dict[str, Any]:
    with open(os.path.join(CONFIG_DIR, *parts), encoding="utf-8") as f:
        return json.load(f)


def load_text(*parts: str) -> str:
    with open(os.path.join(CONFIG_DIR, *parts), encoding="utf-8") as f:
        return f.read()


def load_looks() -> Dict[str, Dict[str, Any]]:
    looks_dir = os.path.join(CONFIG_DIR, "looks")
    out: Dict[str, Dict[str, Any]] = {}
    for name in sorted(os.listdir(looks_dir)):
        if name.endswith(".json"):
            look = load_json("looks", name)
            out[look.get("name", name[:-5])] = look
    return out
