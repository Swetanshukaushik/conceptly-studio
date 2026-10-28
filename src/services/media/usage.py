"""One place that knows about money: every paid model call (text, vision, image, voice) ends up here.

- Token usage of Gemini, OpenAI and Anthropic calls is priced from config/providers.json and added to the active job ledger.
- Each entry is also appended to a persistent log (output/usage_log.jsonl) so spend can be summed per day, job or model.
- Live calls can be blocked (tests set CONCEPTLY_BLOCK_LIVE=1), and optional calls (reviews, fact checks) are skipped once a
  reel's cap is used up. Mandatory calls (script, scenes) are never blocked but are always recorded.
"""
import contextvars
import datetime
import json
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from src.services.config_loader import load_json
from src.services.media.ledger import BudgetExceeded, SpendLedger

_ledger: contextvars.ContextVar = contextvars.ContextVar("conceptly_ledger", default=None)
_job: contextvars.ContextVar = contextvars.ContextVar("conceptly_job", default=None)
_lock = threading.Lock()
_patched = False


class LiveCallBlocked(RuntimeError):
    """A paid call was attempted while live calls are blocked (tests)."""


def check_live(what: str) -> None:
    if os.environ.get("CONCEPTLY_BLOCK_LIVE") == "1":
        raise LiveCallBlocked(f"Live {what} call blocked (CONCEPTLY_BLOCK_LIVE=1). Mock it, or mark the test @pytest.mark.live and run with --live.")


# ---------- pricing ----------
def text_price(model: str, on: Optional[datetime.date] = None) -> Dict[str, Any]:
    cfg = load_json("providers.json")["text"]
    entry = cfg["models"].get(model) or {**cfg["default"], "estimated": True}
    on = on or datetime.date.today()
    after = entry.get("after")
    if after and on >= datetime.date.fromisoformat(after["date"]):
        entry = {**entry, **{k: v for k, v in after.items() if k != "date"}}
    return entry


def price_tokens(model: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
    p = text_price(model)
    cost = input_tokens * p["input_per_m"] / 1e6 + output_tokens * p["output_per_m"] / 1e6
    return {"cost_usd": round(cost, 6), "estimated": bool(p.get("estimated"))}


# ---------- scopes ----------
def current_ledger() -> Optional[SpendLedger]:
    return _ledger.get()


def current_job_id() -> Optional[str]:
    return (_job.get() or {}).get("job")


@contextmanager
def job_scope(job_id: str, ledger: SpendLedger, tier: str = "") -> Iterator[SpendLedger]:
    """Everything paid inside this block is recorded on `ledger` and tagged with the job."""
    t1, t2 = _ledger.set(ledger), _job.set({"job": job_id, "tier": tier})
    try:
        yield ledger
    finally:
        _ledger.reset(t1); _job.reset(t2)


@contextmanager
def optional_call(label: str) -> Iterator[None]:
    """For calls the pipeline can do without (reviews, fact checks): refused once the active ledger has no budget left."""
    led = current_ledger()
    if led is not None and led.remaining <= 0:
        raise BudgetExceeded(led.cap_usd, led.spent, led.reserved, 0.0, label)
    yield


def check_budget(label: str) -> None:
    """Raise BudgetExceeded when the active ledger has nothing left. Call before an optional paid call."""
    with optional_call(label):
        pass


# ---------- persistent log ----------
def log_path() -> str:
    env = os.environ.get("CONCEPTLY_USAGE_LOG")
    if env:
        return env
    from src.core.config import settings
    return os.path.join(settings.LOCAL_STORAGE_DIR, load_json("providers.json")["usage"]["log_file"])


def write_log(entry: Dict[str, Any]) -> None:
    job = _job.get() or {}
    row = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "job": job.get("job"), "tier": job.get("tier"),
           "source": "test" if os.environ.get("PYTEST_CURRENT_TEST") else ("job" if job else "script"),
           **{k: entry.get(k) for k in ("kind", "model", "label", "input_tokens", "output_tokens", "cost_usd", "estimated", "status", "from_cache")}}
    try:
        path = log_path(); os.makedirs(os.path.dirname(path), exist_ok=True)
        with _lock, open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({k: v for k, v in row.items() if v is not None}) + "\n")
    except Exception:
        pass   # accounting must never break a render


def record(kind: str, model: str, cost_usd: float, label: str = "", **meta: Any) -> None:
    """Add a paid call to the active ledger (if any) and to the persistent log."""
    led = current_ledger()
    if led is not None:
        led.record(kind, model, cost_usd, label, **meta)   # the ledger's sink writes the log line
    else:
        write_log({"kind": kind, "model": model, "label": label, "cost_usd": float(cost_usd), "status": "ok", **meta})


def record_llm(provider: str, model: str, input_tokens: int, output_tokens: int, label: str = "") -> float:
    priced = price_tokens(model, int(input_tokens or 0), int(output_tokens or 0))
    record("llm", model, priced["cost_usd"], label, input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0), estimated=priced["estimated"])
    return priced["cost_usd"]


def record_gemini_response(model: str, response: Any, label: str = "") -> None:
    um = getattr(response, "usage_metadata", None)
    if um is None:
        return
    prompt = int(getattr(um, "prompt_token_count", 0) or 0)
    cand = int(getattr(um, "candidates_token_count", 0) or 0)
    total = int(getattr(um, "total_token_count", 0) or 0)
    thoughts = int(getattr(um, "thoughts_token_count", 0) or 0) or max(0, total - prompt - cand)   # thinking bills as output
    record_llm("gemini", model, prompt, cand + thoughts, label)


def record_openai(completion: Any, model: str, label: str = "") -> None:
    u = getattr(completion, "usage", None)
    if u is not None:
        record_llm("openai", model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0), label)


def record_anthropic(message: Any, model: str, label: str = "") -> None:
    u = getattr(message, "usage", None)
    if u is not None:
        record_llm("anthropic", model, getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0), label)


# ---------- Gemini SDK instrumentation ----------
def genai_module():
    """google.generativeai with generate_content wrapped once: blocked in tests, priced and recorded otherwise."""
    global _patched
    import google.generativeai as genai
    with _lock:
        if not _patched:
            original = genai.GenerativeModel.generate_content

            def generate_content(self, *args: Any, **kwargs: Any):
                check_live("Gemini")
                response = original(self, *args, **kwargs)
                try:
                    record_gemini_response(str(getattr(self, "model_name", "")).replace("models/", ""), response)
                except Exception:
                    pass
                return response
            genai.GenerativeModel.generate_content = generate_content
            _patched = True
    return genai


SpendLedger.sink = write_log
