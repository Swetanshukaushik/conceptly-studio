"""Premium phase-0 spike: generates stills through the Gemini image models for three topics and records time, tokens and output.

Usage: venv/bin/python scripts/premium_spike.py [model ...]   (default: the two candidates below)
Writes images and results.json to scratch/premium_spike/. Uses the live GEMINI_API_KEY; no key is printed or stored.
"""
import base64
import json
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.config import settings  # noqa: E402

OUT = "scratch/premium_spike"
STYLE = ("Consistent style for a whole video: painterly editorial illustration, warm muted palette with one accent colour, soft cinematic light, "
         "subtle paper grain, vertical 9:16 composition, large clear subject, absolutely no text, letters, numbers or captions anywhere.")
TOPICS = {
    "history_salt_march": [
        "An elderly man in a plain white dhoti with a wooden staff leads a long column of marchers along a sandy coastal road at dawn, seen from behind and slightly above.",
        "Medium shot of the same elderly man in white with a staff walking in front of a crowd of ordinary villagers, determined faces, dust in the golden light.",
        "Close detail: hands lifting a small pinch of white salt crystals from wet sand at the sea shore at sunrise.",
        "Wide view of thousands of people on the beach at sunrise, a single line of figures in white at the waterline, calm sea.",
    ],
    "civics_constituent_assembly": [
        "A grand 1940s assembly hall with rows of delegates in formal Indian and western dress, tall windows, warm light, seen from the gallery.",
        "Medium shot of a speaker at a wooden podium addressing seated delegates, one delegate leaning forward listening.",
        "Close detail: a hand signing a thick bound document with a fountain pen on a desk, soft light.",
        "Wide shot of the hall at dusk after the session, delegates leaving through large doors, long shadows.",
    ],
    "biology_heart": [
        "A clean cutaway illustration of a human heart showing four chambers, oxygen-rich blood in red and oxygen-poor blood in blue, no labels.",
        "Close view of one heart valve opening, blood flowing through as red streaks, soft glow.",
        "Cross section of an artery with red blood cells flowing along the vessel wall.",
        "A human figure in outline with the heart glowing at the centre and arteries branching through the body as red and blue lines.",
    ],
}


def generate(model: str, prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": f"{STYLE}\n\nScene: {prompt}"}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
    t0 = time.time()
    r = httpx.post(url, json=body, headers={"x-goog-api-key": settings.GEMINI_API_KEY}, timeout=180)
    dt = time.time() - t0
    info = {"model": model, "seconds": round(dt, 1), "status": r.status_code}
    if r.status_code != 200:
        info["error"] = r.text[:300]
        return info
    data = r.json()
    info["usage"] = data.get("usageMetadata")
    cand = (data.get("candidates") or [{}])[0]
    info["finish"] = cand.get("finishReason")
    for part in (cand.get("content") or {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline:
            info["bytes"] = base64.b64decode(inline["data"])
            info["mime"] = inline.get("mimeType") or inline.get("mime_type")
    return info


def main():
    models = sys.argv[1:] or ["gemini-3.1-flash-lite-image", "gemini-3.1-flash-image"]
    os.makedirs(OUT, exist_ok=True)
    results = []
    for model in models:
        for topic, shots in TOPICS.items():
            for i, prompt in enumerate(shots, 1):
                info = generate(model, prompt)
                raw = info.pop("bytes", None)
                if raw:
                    ext = "png" if "png" in (info.get("mime") or "") else "jpg"
                    path = f"{OUT}/{model}__{topic}__{i}.{ext}"
                    open(path, "wb").write(raw)
                    info["file"] = path; info["kb"] = len(raw) // 1024
                info.update({"topic": topic, "shot": i})
                results.append(info)
                print(json.dumps({k: v for k, v in info.items() if k != "usage"}), "usage:", info.get("usage"), flush=True)
    json.dump(results, open(f"{OUT}/results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
