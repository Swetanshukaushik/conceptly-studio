"""Produces the still for every shot: generate (through the spend gateway), have a vision judge score it, regenerate once with the
judge's objections, and fall back to an archival photo when the cap, the provider or the judge says no."""
import hashlib
import os
import time
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


def shot_key(shot: Any) -> str:
    """Identity of what a shot asks for. A finished still is only reused while this is unchanged."""
    return hashlib.sha1(f"{shot.prompt}|{shot.real_photo_query or ''}|{int(bool(getattr(shot, 'reuse_previous', False)))}".encode()).hexdigest()[:12]


def reusable(prior: Optional[Dict[str, Any]], shot: Any, assets_dir: str) -> bool:
    """A still from an earlier run counts as done when it answers the same shot and its file is still there.
    Fallbacks and failures are not done: they are retried, so a rerun redoes only what went wrong."""
    return bool(prior and prior.get("src") and prior.get("shot_key") == shot_key(shot) and prior.get("source") in ("generated", "archive")
                and os.path.exists(os.path.join(assets_dir, prior["src"])))


def produce_stills(shots: List[Any], beats: List[Dict[str, Any]], pack: Optional[str], gateway: MediaGateway, assets_dir: str,
                   judge: Optional[Callable] = None, resolver: Optional[Callable] = None, topic: str = "", cache: Any = "default",
                   prior: Optional[Dict[int, Dict[str, Any]]] = None, on_result: Optional[Callable] = None,
                   sleep: Callable[[float], None] = time.sleep, allow_hero: bool = True) -> Dict[int, Dict[str, Any]]:
    """Returns beat -> {src, source, aspect, score, issues, attempts, cost_usd, note, shared_with?}.
    source is generated | archive | archive_fallback | none. A shot marked reuse_previous shares the previous beat's still at no cost.
    `prior` holds the results of an earlier run: finished shots are kept as they are and only the rest is produced.
    `on_result(beat, result)` is called after each shot so progress can be saved while the reel is still being made."""
    cfg = style.cfg(); judge = judge or default_judge; resolver = resolver or default_resolver
    prior = prior or {}
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
        if reusable(prior.get(shot.beat), shot, assets_dir) and not getattr(shot, "reuse_previous", False):
            results[shot.beat] = {**prior[shot.beat], "attempts": 0, "cost_usd": 0.0, "note": "kept from an earlier run"}
            if prior[shot.beat].get("source") == "generated":
                first_hero_used = True
            prev_beat = shot.beat
            if on_result:
                on_result(shot.beat, results[shot.beat])
            continue
        if getattr(shot, "reuse_previous", False) and prev_beat is not None and results.get(prev_beat, {}).get("src"):
            results[shot.beat] = {**results[prev_beat], "attempts": 0, "cost_usd": 0.0, "shared_with": results[prev_beat].get("shared_with", prev_beat), "note": f"shares beat {prev_beat}'s still", "shot_key": shot_key(shot)}
            prev_beat = shot.beat
            if on_result:
                on_result(shot.beat, results[shot.beat])
            continue
        if shot.real_photo_query:   # a specific real person/place/object: archival photo only, never a generated likeness
            hit = archive(shot, "archive", "real subject: archival photo")
            if hit:
                hit["cost_usd"] = 0.0; hit["shot_key"] = shot_key(shot); results[shot.beat] = hit; prev_beat = shot.beat
                if on_result:
                    on_result(shot.beat, hit)
                continue
        best: Optional[Dict[str, Any]] = None; avoid: List[str] = []; note = ""
        attempts = 0; max_attempts = 1 + int(cfg["regenerations_per_shot"])
        can_generate = not stop_generating and generated < int(cfg["max_images_per_reel"])
        if not can_generate and not stop_generating:
            note = f"image limit of {cfg['max_images_per_reel']} per reel reached"
        while can_generate and attempts < max_attempts:
            attempts += 1
            hero = allow_hero and cfg["hero"]["enabled"] and (not cfg["hero"]["first_shot_only"] or (not first_hero_used and attempts == 1))
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
            res = None; tries = 0
            while res is None:   # a timeout or a 5xx retries this one image; nothing else is redone
                try:
                    res = gateway.generate_image(req)
                except BudgetExceeded as e:
                    note = f"spend cap reached: {e}"; break
                except ProviderError as e:
                    tries += 1
                    if e.retryable and tries <= int(cfg.get("transient_retries", 0)) and e.status not in cfg["stop_generating_on_status"]:
                        sleep(float(cfg.get("transient_backoff_seconds", 0)) * tries)
                        continue
                    note = f"provider error: {e}" + (f" (after {tries} tries)" if tries > 1 else "")
                    if e.status in cfg["stop_generating_on_status"]:
                        stop_generating = True
                        note += " (generation stopped for the rest of the reel)"
                    break
            if res is None:
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
        results[shot.beat]["shot_key"] = shot_key(shot)
        prev_beat = shot.beat
        if on_result:
            on_result(shot.beat, results[shot.beat])
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
