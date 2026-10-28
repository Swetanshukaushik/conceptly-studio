"""Sums everything the pipeline has spent, from the persistent usage log (output/usage_log.jsonl).

Usage: venv/bin/python scripts/spend_report.py [--since 2026-10-28] [--by model|job|kind|day|source] [--log path]
Every paid call (script and scene text, vision reviews, image generation, voice) is priced from config/providers.json by its token
count or per-image price. Compare the total with your Google AI Studio billing page: a gap means a call that is not instrumented
or a price that changed. Entries priced with an assumed rate are marked "estimated".
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.config_loader import load_json  # noqa: E402
from src.services.media import usage  # noqa: E402


def load(path: str, since: str):
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("status") in ("failed", "cached") or not r.get("cost_usd") and r.get("status") != "ok":
            continue
        if since and r.get("ts", "")[:10] < since:
            continue
        rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--by", default="model", choices=["model", "job", "kind", "day", "source"])
    ap.add_argument("--log", default=usage.log_path())
    a = ap.parse_args()
    rows = load(a.log, a.since)
    inr = load_json("providers.json")["usage"]["inr_per_usd"]
    key = {"model": lambda r: r.get("model") or "?", "job": lambda r: (r.get("job") or "no job")[:8], "kind": lambda r: r.get("kind") or "?",
           "day": lambda r: r.get("ts", "")[:10], "source": lambda r: r.get("source") or "?"}[a.by]
    tot, cnt, tok = collections.defaultdict(float), collections.Counter(), collections.Counter()
    for r in rows:
        k = key(r); tot[k] += r.get("cost_usd", 0); cnt[k] += 1; tok[k] += (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
    print(f"Usage log: {a.log}" + (f" (since {a.since})" if a.since else ""))
    print(f"{'':28}{'calls':>7}{'tokens':>12}{'USD':>10}{'INR':>9}")
    for k, v in sorted(tot.items(), key=lambda kv: -kv[1]):
        print(f"{k:28}{cnt[k]:>7}{tok[k]:>12,}{v:>10.3f}{v * inr:>9.0f}")
    total = sum(tot.values()); est = sum(r.get("cost_usd", 0) for r in rows if r.get("estimated"))
    print(f"{'TOTAL':28}{sum(cnt.values()):>7}{sum(tok.values()):>12,}{total:>10.3f}{total * inr:>9.0f}")
    print(f"INR at {inr}/USD (approximate). ${est:.3f} of the total uses an assumed price for a model that is not on the pricing page.")


if __name__ == "__main__":
    main()
