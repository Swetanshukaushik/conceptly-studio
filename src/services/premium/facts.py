"""Source-backed fact check for history and biology narrations: retrieve encyclopedia extracts for the topic, then one model call
lists the checkable claims and judges each against those extracts only. Sources and verdicts are stored with the job."""
import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from src.services.premium import style

WIKI = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "ConceptlyStudio/1.0 (contact@conceptly.app)"}


def _get_json(params: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(WIKI + "?" + urllib.parse.urlencode(params), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def retrieve_sources(topic: str, subject: str = "", fetch: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """Top encyclopedia articles for the topic, as plain-text extracts. Returns [] when nothing could be fetched."""
    cfg = style.cfg()["facts"]; fetch = fetch or _get_json
    try:
        hits = fetch({"action": "query", "list": "search", "srsearch": f"{topic} {subject}".strip(), "srlimit": cfg["max_sources"], "format": "json"})["query"]["search"]
        titles = [h["title"] for h in hits][: cfg["max_sources"]]
        if not titles:
            return []
        data = fetch({"action": "query", "prop": "extracts", "explaintext": 1, "exsectionformat": "plain", "titles": "|".join(titles), "format": "json", "redirects": 1})
    except Exception:
        return []
    out = []
    for page in data.get("query", {}).get("pages", {}).values():
        text = (page.get("extract") or "").strip()
        if text:
            out.append({"title": page.get("title", ""), "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page.get("title", "").replace(" ", "_")), "text": text[: cfg["max_source_chars"]]})
    return out


class _Claim(BaseModel):
    claim: str
    verdict: str = "unverified"
    source: str = ""
    note: str = ""


class _Verdicts(BaseModel):
    claims: List[_Claim] = Field(default_factory=list)


def verify_narration(narration: str, topic: str, subject: str = "", tier: Any = None, provider: str = "AUTO",
                     fetch: Optional[Callable] = None, ask: Optional[Callable] = None) -> Dict[str, Any]:
    """Returns {status: verified|flagged|unverified|skipped, claims, sources, supported, contradicted, unverified, note}. Never raises."""
    cfg = style.cfg()["facts"]
    sources = retrieve_sources(topic, subject, fetch)
    if not sources:
        return {"status": "skipped", "claims": [], "sources": [], "supported": 0, "contradicted": 0, "unverified": 0, "note": "no sources could be retrieved"}
    prompt = cfg["prompt"].replace("{narration}", narration).replace("{sources}", "\n\n".join(f"[{s['title']}]\n{s['text']}" for s in sources))
    try:
        if ask:
            verdicts = ask(prompt)
        else:
            from src.services.llm_factory import LLMFactory
            if tier is None:
                from src.models.schemas import ReelGenerationTier
                tier = ReelGenerationTier.PREMIUM
            verdicts = LLMFactory.generate_json(system_prompt="You are a careful fact checker. Judge only against the sources given.", user_prompt=prompt,
                                                response_model=_Verdicts, tier=tier, provider=provider, profile="lite")
    except Exception as e:
        return {"status": "skipped", "claims": [], "sources": [{"title": s["title"], "url": s["url"]} for s in sources], "supported": 0, "contradicted": 0,
                "unverified": 0, "note": f"fact check unavailable ({str(e)[:80]})"}
    claims = [c.model_dump() if hasattr(c, "model_dump") else c for c in verdicts.claims][: cfg["max_claims"]]
    count = lambda v: sum(1 for c in claims if c["verdict"] == v)
    sup, con, unv = count("supported"), count("contradicted"), count("unverified")
    if con:
        status = "flagged"
    elif claims and sup / len(claims) >= cfg["min_supported_fraction"]:
        status = "verified"
    else:
        status = "unverified"
    return {"status": status, "claims": claims, "sources": [{"title": s["title"], "url": s["url"]} for s in sources], "supported": sup, "contradicted": con, "unverified": unv, "note": ""}
