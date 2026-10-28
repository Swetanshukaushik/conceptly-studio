"""Spend ledger: every paid call is reserved before it is made and recorded after.

The cap is checked against spent + reserved + the estimate of the next call, so a call that would push the reel over its
cap is refused before any money moves. The ledger is plain data (`to_dict`) so it can be stored with the job.
"""
import threading
import time
from typing import Any, Dict, List, Optional


class BudgetExceeded(RuntimeError):
    def __init__(self, cap: float, spent: float, reserved: float, estimate: float, what: str):
        self.cap, self.spent, self.reserved, self.estimate, self.what = cap, spent, reserved, estimate, what
        super().__init__(f"Spend cap ${cap:.3f} would be exceeded by {what} (spent ${spent:.3f}, in flight ${reserved:.3f}, next ${estimate:.3f})")


class SpendLedger:
    sink = None   # optional callable(entry) the usage module sets so every settled entry also reaches the persistent log

    def __init__(self, cap_usd: float, margin: float = 1.0):
        if cap_usd < 0:
            raise ValueError("cap_usd must be >= 0")
        self.cap_usd = float(cap_usd)
        self.margin = float(margin)
        self.entries: List[Dict[str, Any]] = []
        self._reserved: Dict[int, float] = {}
        self._next = 0
        self._lock = threading.Lock()

    @property
    def spent(self) -> float:
        return round(sum(e["cost_usd"] for e in self.entries if e["status"] == "ok"), 6)

    @property
    def reserved(self) -> float:
        return round(sum(self._reserved.values()), 6)

    @property
    def remaining(self) -> float:
        return round(self.cap_usd - self.spent - self.reserved, 6)

    def carry(self, spent_usd: float, label: str = "earlier stage") -> None:
        """Account for money already spent by an earlier pipeline stage (the ledger is rebuilt per stage)."""
        if spent_usd > 0:
            with self._lock:
                self.entries.append({"token": self._next, "kind": "carried", "model": "", "label": label, "estimate_usd": spent_usd, "cost_usd": float(spent_usd), "status": "ok", "at": round(time.time(), 1)})
                self._next += 1

    def record(self, kind: str, model: str, cost_usd: float, label: str = "", **meta: Any) -> None:
        """A paid call that was not reserved first (text and vision calls are priced after the fact from their token counts)."""
        with self._lock:
            self.entries.append({"token": self._next, "kind": kind, "model": model, "label": label, "estimate_usd": 0.0, "cost_usd": float(cost_usd),
                                 "status": "ok", **meta, "at": round(time.time(), 1)})
            self._next += 1
            e = self.entries[-1]
        self._emit(e)

    def _emit(self, entry: Dict[str, Any]) -> None:
        if SpendLedger.sink:
            try:
                SpendLedger.sink(entry)
            except Exception:
                pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any], cap_usd: Optional[float] = None, margin: float = 1.0) -> "SpendLedger":
        """Rebuild the ledger a previous pipeline stage stored, so spend keeps adding up across stages."""
        led = cls(cap_usd if cap_usd is not None else data.get("cap_usd", 0.0), margin)
        for e in data.get("entries", []):
            led.entries.append({**e, "token": led._next}); led._next += 1
        return led

    def note_free(self, kind: str, model: str, label: str = "", **meta: Any) -> None:
        """Record a call that cost nothing (a cache hit), so the report shows what was saved."""
        with self._lock:
            self.entries.append({"token": self._next, "kind": kind, "model": model, "label": label, "estimate_usd": 0.0, "cost_usd": 0.0, "status": "cached", **meta, "at": round(time.time(), 1)})
            self._next += 1
            e = self.entries[-1]
        self._emit(e)

    def can_afford(self, estimate: float) -> bool:
        return estimate * self.margin <= self.remaining + 1e-9

    def reserve(self, kind: str, model: str, estimate: float, label: str = "") -> int:
        """Hold `estimate` against the cap. Raises BudgetExceeded without side effects when it does not fit."""
        with self._lock:
            if not self.can_afford(estimate):
                raise BudgetExceeded(self.cap_usd, self.spent, self.reserved, estimate * self.margin, f"{kind} '{label or model}'")
            token = self._next
            self._next += 1
            self._reserved[token] = estimate * self.margin
            self.entries.append({"token": token, "kind": kind, "model": model, "label": label, "estimate_usd": estimate,
                                 "cost_usd": 0.0, "status": "reserved", "at": round(time.time(), 1)})
            return token

    def commit(self, token: int, cost_usd: float, **meta: Any) -> None:
        with self._lock:
            self._reserved.pop(token, None)
            e = self._entry(token); e.update({"cost_usd": float(cost_usd), "status": "ok", **meta})
        self._emit(e)

    def release(self, token: int, reason: str, charged_usd: float = 0.0) -> None:
        """The call failed. Providers normally do not bill failures, so the hold is dropped; pass charged_usd if one did."""
        with self._lock:
            self._reserved.pop(token, None)
            e = self._entry(token); e.update({"cost_usd": float(charged_usd), "status": "ok" if charged_usd else "failed", "error": reason[:200]})
        self._emit(e)

    def _entry(self, token: int) -> Dict[str, Any]:
        for e in self.entries:
            if e["token"] == token:
                return e
        raise KeyError(token)

    def to_dict(self) -> Dict[str, Any]:
        by_kind: Dict[str, float] = {}
        for e in self.entries:
            if e["status"] == "ok":
                by_kind[e["kind"]] = round(by_kind.get(e["kind"], 0.0) + e["cost_usd"], 6)
        return {"cap_usd": self.cap_usd, "spent_usd": self.spent, "remaining_usd": self.remaining,
                "calls": len([e for e in self.entries if e["status"] == "ok"]),
                "cache_hits": len([e for e in self.entries if e["status"] == "cached"]),
                "failed_calls": len([e for e in self.entries if e["status"] == "failed"]),
                "by_kind": by_kind, "entries": self.entries}
