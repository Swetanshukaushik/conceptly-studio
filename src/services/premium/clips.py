"""Premium Video: turns the approved stills of a few chosen beats into short video clips (image-to-video through the spend gateway).

A clip is only ever made from a still the reviewer already accepted, is checked for drift on a contact sheet of its frames, and is
extracted to a frame sequence the renderer plays back frame-exactly. Anything that goes wrong (cap, provider, drift, ffmpeg) leaves the
beat as its still with a camera move, so a clip can never fail the reel."""
import hashlib
import os
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional

from src.services.media.ledger import BudgetExceeded
from src.services.media.providers import ClipRequest, MediaGateway, ProviderError, video_config
from src.services.premium import style


def default_clip_judge(sheet_path: str, narration: str, motion: str) -> Dict[str, Any]:
    from src.services.vision_judge import ask_image
    prompt = style.cfg()["clips"]["judge_prompt"].replace("{narration}", narration).replace("{motion}", motion)
    data = ask_image(sheet_path, prompt)
    return {"score": float(data.get("score", 0)), "issues": [str(i) for i in data.get("issues", [])][:4]}


def clip_key(still_bytes: bytes, motion: str) -> str:
    return "clip|" + hashlib.sha256(still_bytes).hexdigest()[:24] + "|" + motion.strip().lower()


def build_prompt(motion: str, shot_type: str) -> str:
    camera = "locked off, no camera movement" if shot_type in ("detail", "diagram") else "a very slow, steady move that follows the action"
    return style.cfg()["clips"]["prompt"].replace("{camera}", camera).replace("{motion}", motion)


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg") or next((p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg") if os.path.exists(p)), None)
    if not path:
        raise RuntimeError("ffmpeg not found")
    return path


def extract_frames(mp4_path: str, out_dir: str, fps: int, width: int, max_seconds: float, quality: int) -> int:
    shutil.rmtree(out_dir, ignore_errors=True); os.makedirs(out_dir, exist_ok=True)
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", mp4_path, "-t", f"{max_seconds:.2f}", "-vf", f"fps={fps},scale={width}:-2",
                    "-q:v", str(quality), os.path.join(out_dir, "f_%04d.jpg")], check=True, timeout=180)
    return len([f for f in os.listdir(out_dir) if f.endswith(".jpg")])


def contact_sheet(frames_dir: str, count: int, out_path: str, n: int = 6) -> str:
    from PIL import Image
    picks = sorted({min(count, max(1, round(1 + i * (count - 1) / (n - 1)))) for i in range(n)})
    ims = [Image.open(os.path.join(frames_dir, f"f_{k:04d}.jpg")).convert("RGB").resize((240, 427)) for k in picks]
    cols = min(3, len(ims)); rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (240 * cols, 427 * rows), "black")
    for i, im in enumerate(ims):
        sheet.paste(im, (240 * (i % cols), 427 * (i // cols)))
    sheet.save(out_path, quality=85)
    return out_path


def _reusable(prior: Optional[Dict[str, Any]], key: str, assets_dir: str) -> bool:
    c = (prior or {}).get("clip")
    return bool(c and c.get("key") == key and os.path.isdir(os.path.join(assets_dir, c["dir"])) and c.get("count"))


def produce_clips(shots: List[Any], results: Dict[int, Dict[str, Any]], beats: List[Dict[str, Any]], gateway: MediaGateway, assets_dir: str,
                  judge: Optional[Callable] = None, cache: Any = None, prior: Optional[Dict[int, Dict[str, Any]]] = None,
                  on_result: Optional[Callable] = None, sleep: Callable[[float], None] = None) -> Dict[int, Dict[str, Any]]:
    """Adds results[beat]["clip"] (frames dir, count, fps, seconds, score, cost) for each beat that got a clip, or results[beat]["clip_note"] saying why not.
    Returns the same dict. Only beats whose shot has `clip_motion` and whose still is generated and accepted are tried."""
    import time
    sleep = sleep or time.sleep
    cfg = style.cfg()["clips"]; judge = judge or default_clip_judge
    narr = {b["beat"]: b["text"] for b in beats}
    model = video_config()["default_model"]
    made, stop = 0, False
    for shot in shots:
        r = results.get(shot.beat)
        if not getattr(shot, "clip_motion", None) or not r:
            continue
        for stale in ("clip", "clip_note", "clip_rejected"):
            r.pop(stale, None)   # a result kept from an earlier run is judged again below; its clip is reused only through `prior`

        def done(note: str = "") -> None:
            if note:
                r["clip_note"] = note
            if on_result:
                on_result(shot.beat, r)
        if r.get("source") != "generated" or not r.get("src") or r.get("shared_with"):
            done("kept the still: only an accepted generated still becomes a clip"); continue
        if r.get("score") is not None and r["score"] < cfg["min_still_score"]:
            done(f"kept the still: scored {r['score']}/10, too weak to animate"); continue
        still_path = os.path.join(assets_dir, r["src"])
        try:
            still_bytes = open(still_path, "rb").read()
        except OSError:
            done("kept the still: file missing"); continue
        key = clip_key(still_bytes, shot.clip_motion)
        if _reusable(prior.get(shot.beat) if prior else None, key, assets_dir):
            r["clip"] = {**prior[shot.beat]["clip"], "cost_usd": 0.0, "kept": True}; made += 1; done(); continue
        if stop or made >= int(cfg["max_clips_per_reel"]):
            done("kept the still: " + ("clip generation stopped for the rest of the reel" if stop else "clip limit reached")); continue
        cost_before = gateway.ledger.spent; cached = False; mp4: Optional[bytes] = None; seconds = 0.0
        hit = cache.get(model, key) if cache else None
        if hit:
            mp4, seconds, cached = hit["data"], 0.0, True
            gateway.ledger.note_free("video", model, f"beat {shot.beat}", from_cache=True)
        else:
            req = ClipRequest(image=still_bytes, image_mime="image/png" if r["src"].endswith(".png") else "image/jpeg",
                              prompt=build_prompt(shot.clip_motion, shot.shot_type), label=f"clip beat {shot.beat}")
            tries = 0
            while mp4 is None:
                try:
                    res = gateway.generate_clip(req)
                    mp4, seconds = res.data, res.seconds
                except BudgetExceeded as e:
                    done(f"kept the still: spend cap reached ({e})"); stop = True; break
                except ProviderError as e:
                    tries += 1
                    if e.retryable and tries <= 1 and e.status not in cfg["stop_on_status"]:
                        sleep(3.0); continue
                    stop = e.status in cfg["stop_on_status"]
                    done(f"kept the still: clip failed ({e})" + (" (clip generation stopped for the rest of the reel)" if stop else "")); break
            if mp4 is None:
                continue
        name = f"clip_{shot.beat}"
        mp4_path = os.path.join(assets_dir, name + ".mp4")
        with open(mp4_path, "wb") as f:
            f.write(mp4)
        try:
            count = extract_frames(mp4_path, os.path.join(assets_dir, name), int(cfg["fps"]), int(cfg["frame_width"]), float(cfg["max_clip_seconds"]), int(cfg["frame_quality"]))
        except Exception as e:
            done(f"kept the still: could not read the clip ({str(e)[:80]})"); continue
        if count < 2:
            done("kept the still: the clip had no usable frames"); continue
        try:
            verdict = judge(contact_sheet(os.path.join(assets_dir, name), count, os.path.join(assets_dir, name + "_sheet.jpg")), narr.get(shot.beat, ""), shot.clip_motion)
        except Exception as e:
            verdict = {"score": None, "issues": [f"clip review unavailable ({str(e)[:80]})"]}
        if verdict["score"] is not None and verdict["score"] < cfg["min_score"]:
            r["clip_rejected"] = {"score": verdict["score"], "issues": verdict["issues"], "cost_usd": round(gateway.ledger.spent - cost_before, 6)}
            shutil.rmtree(os.path.join(assets_dir, name), ignore_errors=True)
            done(f"kept the still: clip scored {verdict['score']}/10 ({'; '.join(verdict['issues'])})"); continue
        if cache and not cached and (verdict["score"] is not None):
            cache.put(model, key, mp4, "video/mp4", verdict["score"])
        r["clip"] = {"key": key, "dir": name, "count": count, "fps": int(cfg["fps"]), "seconds": round(count / int(cfg["fps"]), 2), "score": verdict["score"],
                     "issues": verdict["issues"], "cached": cached, "cost_usd": round(gateway.ledger.spent - cost_before, 6)}
        made += 1; done()
    return results
