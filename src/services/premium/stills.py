"""Produces the still for every shot: generate (through the spend gateway), have a vision judge score it, regenerate once with the
judge's objections, and fall back to an archival photo when the cap, the provider or the judge says no."""
import hashlib
import os
from typing import Any, Callable, Dict, List, Optional

from src.services.config_loader import load_json
from src.services.media.ledger import BudgetExceeded
from src.services.media.providers import ImageRequest, MediaGateway, ProviderError
from src.services.premium import style


def default_judge(path: str, shot_prompt: str, narration: str) -> Dict[str, Any]:
    from src.services.vision_judge import ask_image
    prompt = style.cfg()["judge_prompt"].replace("{narration}", narration).replace("{prompt}", shot_prompt)
    data = ask_image(path, prompt)
    return {"score": float(data.get("score", 0)), "issues": [str(i) for i in data.get("issues", [])][:4]}


def default_resolver(query: str, assets_dir: str, narration: str) -> Dict[str, Any]:
    from src.services.image_resolver import resolve_images
    obj = {"type": "image", "query": query}
    problems = resolve_images([obj], assets_dir, narration=narration)
    return {"src": obj.get("src"), "aspect": obj.get("aspect"), "title": obj.get("source_title"), "problems": problems}


def _save(assets_dir: str, data: bytes, mime: str, tag: str) -> str:
    os.makedirs(assets_dir, exist_ok=True)
    ext = ".png" if "png" in (mime or "") else ".jpg"
    name = "gen_" + hashlib.sha1(data[:4096] + tag.encode()).hexdigest()[:14] + ext
    with open(os.path.join(assets_dir, name), "wb") as f:
        f.write(data)
    return name


def produce_stills(shots: List[Any], beats: List[Dict[str, Any]], pack: Optional[str], gateway: MediaGateway, assets_dir: str,
                   judge: Optional[Callable] = None, resolver: Optional[Callable] = None, topic: str = "", cache: Any = "default") -> Dict[int, Dict[str, Any]]:
    """Returns beat -> {src, source, aspect, score, issues, attempts, cost_usd, note, shared_with?}.
    source is generated | archive | archive_fallback | none. A shot marked reuse_previous shares the previous beat's still at no cost."""
    cfg = style.cfg(); judge = judge or default_judge; resolver = resolver or default_resolver
    if cache == "default":
        from src.services.media.cache import default_cache
        cache = default_cache()
    narr = {b["beat"]: b["text"] for b in beats}
    results: Dict[int, Dict[str, Any]] = {}
    stop_generating = False
    generated = 0       # paid generations this reel (cache hits are free and not counted)
    first_hero_used = False

    def archive(shot, kind: str, why: str = "") -> Optional[Dict[str, Any]]:
        query = shot.real_photo_query or " ".join(filter(None, [topic, shot.title or ""])).strip()
        if not query:
            return None
        try:
            hit = resolver(query, assets_dir, narr[shot.beat])
        except Exception:
            return None
        if hit.get("src"):
            return {"src": hit["src"], "source": kind, "aspect": hit.get("aspect"), "score": None, "issues": [], "attempts": 0, "note": why or f"archive photo: {hit.get('title', '')}"}
        return None

    prev_beat: Optional[int] = None
    for shot in shots:
        cost_before = gateway.ledger.spent
        if getattr(shot, "reuse_previous", False) and prev_beat is not None and results.get(prev_beat, {}).get("src"):
            results[shot.beat] = {**results[prev_beat], "attempts": 0, "cost_usd": 0.0, "shared_with": results[prev_beat].get("shared_with", prev_beat), "note": f"shares beat {prev_beat}'s still"}
            prev_beat = shot.beat
            continue
        if shot.real_photo_query:   # a specific real person/place/object: archival photo only, never a generated likeness
            hit = archive(shot, "archive", "real subject: archival photo")
            if hit:
                hit["cost_usd"] = 0.0; results[shot.beat] = hit; prev_beat = shot.beat; continue
        best: Optional[Dict[str, Any]] = None; avoid: List[str] = []; note = ""
        attempts = 0; max_attempts = 1 + int(cfg["regenerations_per_shot"])
        can_generate = not stop_generating and generated < int(cfg["max_images_per_reel"])
        if not can_generate and not stop_generating:
            note = f"image limit of {cfg['max_images_per_reel']} per reel reached"
        while can_generate and attempts < max_attempts:
            attempts += 1
            hero = cfg["hero"]["enabled"] and (not cfg["hero"]["first_shot_only"] or (not first_hero_used and attempts == 1))
            model = gateway.hero_model() if hero else None
            req = ImageRequest(style.full_prompt(pack, shot.prompt, avoid), model=model, label=f"beat {shot.beat}")
            eff_model = req.model or gateway.default_model()
            hit = cache.get(eff_model, req.prompt) if cache else None
            if hit:   # reviewed and accepted in an earlier run: free
                name = _save(assets_dir, hit["data"], hit["mime"], f"{shot.beat}-cache")
                gateway.ledger.note_free("image", eff_model, f"beat {shot.beat}", from_cache=True)
                if hero:
                    first_hero_used = True
                best = {"src": name, "source": "generated", "aspect": 0.5625, "score": hit.get("score"), "issues": [], "attempts": attempts, "cached": True}
                break
            try:
                res = gateway.generate_image(req)
            except BudgetExceeded as e:
                note = f"spend cap reached: {e}"; break
            except ProviderError as e:
                note = f"provider error: {e}"
                if e.status in cfg["stop_generating_on_status"]:
                    stop_generating = True
                    note += " (generation stopped for the rest of the reel)"
                break
            generated += 1
            if hero:
                first_hero_used = True
            name = _save(assets_dir, res.data, res.mime, f"{shot.beat}-{attempts}")
            try:
                verdict = judge(os.path.join(assets_dir, name), shot.prompt, narr[shot.beat])
            except Exception as e:
                verdict = {"score": None, "issues": [f"image review unavailable ({str(e)[:80]})"]}
            cand = {"src": name, "source": "generated", "aspect": 0.5625, "score": verdict["score"], "issues": verdict["issues"], "attempts": attempts}
            if best is None or (cand["score"] or 0) > (best["score"] or 0):
                best = cand
            if cand["score"] is not None and cand["score"] >= cfg["judge"]["min_score"] and cache:
                cache.put(eff_model, req.prompt, res.data, res.mime, cand["score"])
            if cand["score"] is None or cand["score"] >= cfg["judge"]["min_score"]:
                break
            avoid = verdict["issues"]
        if best and (best["score"] is None or best["score"] >= cfg["judge"]["min_score"]):
            best["note"] = note; results[shot.beat] = best
        else:
            fb = archive(shot, "archive_fallback", note or "generated image rejected by the reviewer")
            if fb:
                fb["issues"] = (best or {}).get("issues", []); results[shot.beat] = fb
            elif best:
                best["note"] = (note + " " if note else "") + "below the review score and no archive photo found; kept the best attempt"; results[shot.beat] = best
            else:
                results[shot.beat] = {"src": None, "source": "none", "aspect": None, "score": None, "issues": [], "attempts": attempts, "note": note or "no image"}
        results[shot.beat]["cost_usd"] = round(gateway.ledger.spent - cost_before, 6)
        prev_beat = shot.beat
    return results


def consistency_review(paths: List[str], out_path: str, judge_sheet: Optional[Callable] = None) -> Dict[str, Any]:
    """One vision call over a contact sheet of the generated stills: do they look like one video?"""
    cfg = style.cfg()["consistency"]
    if len(paths) < cfg["min_images"]:
        return {"score": None, "issues": [], "note": "too few generated images to compare"}
    from PIL import Image
    ims = [Image.open(p).convert("RGB").resize((270, 480)) for p in paths[:8]]
    cols = min(4, len(ims)); rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (270 * cols, 480 * rows), "black")
    for i, im in enumerate(ims):
        sheet.paste(im, (270 * (i % cols), 480 * (i // cols)))
    sheet.save(out_path, quality=85)
    try:
        if judge_sheet:
            data = judge_sheet(out_path)
        else:
            from src.services.vision_judge import ask_image
            data = ask_image(out_path, style.cfg()["consistency_prompt"])
        return {"score": float(data.get("score", 0)), "issues": [str(i) for i in data.get("issues", [])][:4]}
    except Exception as e:
        return {"score": None, "issues": [f"consistency review unavailable ({str(e)[:80]})"]}
