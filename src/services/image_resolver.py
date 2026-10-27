"""Fetches public-domain / freely licensed photographs for `image` objects in a scene plan.

The scene director supplies a precise `query`; we search Wikimedia Commons and download the best
raster match into the job's assets folder, then rewrite the object to point at it (`src`).
"""
import hashlib
import os
from typing import Any, Dict, List, Optional

from src.services.config_loader import load_json

import json
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "ConceptlyStudio/1.0 (contact@conceptly.app)"}
RASTER = (".jpg", ".jpeg", ".png", ".webp")


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


WIKI = "https://en.wikipedia.org/w/api.php"


def _usable(url: Optional[str], width: int, mime: str, min_width: int) -> bool:
    return bool(url) and url.split("?")[0].lower().endswith(RASTER) and width >= min_width and not mime.startswith("application")


def _commons(query: str, min_width: int) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    params = {
        "action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": 1400, "format": "json",
    }
    data = json.loads(_get(API + "?" + urllib.parse.urlencode(params), timeout=15))
    for page in sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if _usable(url, info.get("width", 0), info.get("mime", ""), min_width):
            found.append({"url": url, "title": page.get("title", "")})
    return found


def _wikipedia_lead(query: str, min_width: int) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    """Lead image of the best-matching encyclopedia articles: usually the most representative picture."""
    params = {
        "action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": 5, "prop": "pageimages",
        "piprop": "thumbnail|original", "pithumbsize": 1400, "format": "json",
    }
    data = json.loads(_get(WIKI + "?" + urllib.parse.urlencode(params), timeout=15))
    for page in sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 0)):
        thumb = page.get("thumbnail") or {}
        if _usable(thumb.get("source"), thumb.get("width", 0), "", min_width):
            found.append({"url": thumb["source"], "title": page.get("title", "")})
    return found


def _candidates(query: str, min_width: int, limit: int) -> List[Dict[str, Any]]:
    """Distinct candidate images: full phrase first, then shorter phrases; Commons files then article lead images."""
    words = query.split()
    variants = [query] + [" ".join(words[:n]) for n in range(len(words) - 1, 1, -1)]
    seen, out = set(), []
    for q in variants:
        for finder in (_commons, _wikipedia_lead):
            try:
                hits = finder(q, min_width)
            except Exception:
                hits = []
            for hit in hits:
                if hit["url"] not in seen and ".svg" not in hit["url"].lower():
                    seen.add(hit["url"]); hit["query_used"] = q; out.append(hit)
            if len(out) >= limit:
                return out[:limit]
    return out


def resolve_images(objects: List[Dict[str, Any]], assets_dir: str, narration: str = "") -> List[str]:
    """Walks the object tree; fills `src` (and `aspect`) for every `image` object with a `query`.

    Candidates are downloaded in order and, when images.json enables it, judged by a vision model against
    the narration. Objects with no acceptable image are left without `src` and reported in the result.
    """
    from PIL import Image
    cfg = load_json("images.json")
    os.makedirs(assets_dir, exist_ok=True)
    problems: List[str] = []

    def visit(obj: Dict[str, Any]) -> None:
        if obj.get("type") == "image" and obj.get("query") and not obj.get("src"):
            tried: List[str] = []
            for hit in _candidates(obj["query"], cfg["min_width"], cfg["max_candidates"]):
                try:
                    ext = os.path.splitext(hit["url"].split("?")[0])[1].lower() or ".jpg"
                    name = hashlib.sha1(hit["url"].encode()).hexdigest()[:16] + ext
                    path = os.path.join(assets_dir, name)
                    if not os.path.exists(path):
                        with open(path, "wb") as f:
                            f.write(_get(hit["url"], timeout=40))
                    if cfg["verify_with_vision"]:
                        from src.services.vision_judge import judge_image
                        verdict = judge_image(path, narration, obj["query"])
                        if not verdict["match"]:
                            tried.append(f"{hit['title']}: {verdict['reason']}")
                            continue
                    with Image.open(path) as im:
                        obj["aspect"] = round(im.width / im.height, 4)
                    obj["src"], obj["source_title"] = name, hit["title"]
                    break
                except Exception as e:
                    tried.append(f"{hit['title']}: {e}")
            if not obj.get("src"):
                problems.append(f"No acceptable image for '{obj['query']}' ({len(tried)} rejected: {'; '.join(tried[:3])})")
        for child in obj.get("children") or []:
            visit(child)

    for o in objects:
        visit(o)
    return problems
