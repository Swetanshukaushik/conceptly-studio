"""Premium visual director: plan shots, produce stills under the spend cap, compose studio3d scenes, check facts, report cost."""
import copy
import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional

from src.agents.scene3d_director import Scene3DDirector
from src.models.schemas import ReelScript, SceneBeat, Storyboard
from src.services.config_loader import load_json
from src.services.media.providers import MediaGateway, new_gateway
from src.services.premium import clips as clips_mod, composer, facts, planner, stills, style
from src.services.premium.planner import Shot

CHECKPOINT = "premium_checkpoint.json"


class Checkpoint:
    """Saves the shot plan and every finished still next to the job, so a rerun after a failure keeps all finished work
    and only plans/produces what is missing. Valid only for the same narration and domain pack."""

    def __init__(self, job_dir: str, beats: List[Dict[str, Any]], pack: str):
        self.path = os.path.join(job_dir, CHECKPOINT)
        self.key = hashlib.sha1(("|".join(b["text"] for b in beats) + "#" + str(pack)).encode()).hexdigest()[:16]
        self.data: Dict[str, Any] = {"key": self.key, "plan": None, "results": {}}
        try:
            with open(self.path, encoding="utf-8") as f:
                old = json.load(f)
            if old.get("key") == self.key:
                self.data = old
        except (OSError, ValueError):
            pass

    @property
    def plan(self) -> Optional[Dict[str, Any]]:
        saved = self.data.get("plan")
        return {"style_note": saved["style_note"], "notes": saved.get("notes", []), "shots": [Shot(**s) for s in saved["shots"]]} if saved else None

    @property
    def results(self) -> Dict[int, Dict[str, Any]]:
        return {int(k): v for k, v in self.data["results"].items()}

    def save_plan(self, plan: Dict[str, Any]) -> None:
        self.data["plan"] = {"style_note": plan.get("style_note", ""), "notes": plan.get("notes", []), "shots": [s.model_dump() for s in plan["shots"]]}
        self._write()

    def save_result(self, beat: int, result: Dict[str, Any]) -> None:
        self.data["results"][str(beat)] = result
        self._write()

    def _write(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)


def direct_premium_storyboard(script: ReelScript, subject: str, class_level: Optional[int], exam_type: str, assets_dir: str, tier: Any, provider: str,
                              route: Dict[str, Any], gateway: Optional[MediaGateway] = None, planner_fn: Optional[Callable] = None,
                              judge: Optional[Callable] = None, resolver: Optional[Callable] = None, fact_fn: Optional[Callable] = None,
                              judge_sheet: Optional[Callable] = None, cache: Any = "default", checkpoint: bool = True, clip_judge: Optional[Callable] = None) -> Dict[str, Any]:
    """Returns {"storyboard": Storyboard, "premium": record}. The record is stored with the job: cost report, image sources, reviews, facts."""
    from src.services.tiers import get_tier
    beats = Scene3DDirector.split_beats(script, wps=load_json("pacing.json")["tiers"]["premium"]["words_per_second"])
    pack = route["pack"]
    tier_cfg = get_tier(getattr(tier, "value", tier))
    clips_on = tier_cfg.get("scene_mode") == "generated_clips" and bool(style.cfg()["clips"]["enabled"])
    gateway = gateway or new_gateway(tier_cfg["cost_cap_usd"], clips=clips_on)
    ckpt = Checkpoint(os.path.dirname(assets_dir) or ".", beats, pack) if checkpoint else None
    earlier = copy.deepcopy(ckpt.results) if ckpt else {}   # what a failed run already finished, before this run touches it
    plan = ckpt.plan if ckpt else None
    if not plan:   # the plan is one paid call; after a failure later in the stage it is reused, not re-asked
        plan = (planner_fn or planner.plan_shots)(script.topic_title, subject, beats, pack, tier, provider)
        if ckpt:
            ckpt.save_plan(plan)
    shots = plan["shots"]
    results = stills.produce_stills(shots, beats, pack, gateway, assets_dir, judge=judge, resolver=resolver, topic=script.topic_title, cache=cache,
                                    prior=earlier, on_result=ckpt.save_result if ckpt else None)
    if clips_on:   # a few beats become video; each clip starts from its accepted still and falls back to it on any problem
        if cache == "default":
            from src.services.media.cache import default_cache
            cache = default_cache()
        clips_mod.produce_clips(shots, results, beats, gateway, assets_dir, judge=clip_judge, cache=cache, prior=earlier, on_result=ckpt.save_result if ckpt else None)

    scenes, qa_notes, t = [], list(plan.get("notes", [])), 0.0
    shot_by_beat = {s.beat: s for s in shots}
    for b in beats:
        shot, still = shot_by_beat[b["beat"]], results[b["beat"]]
        backdrop = None
        if still.get("src") and still.get("aspect") and abs(still["aspect"] - style.cfg()["plane"]["aspect"]) >= 0.08:
            backdrop = composer.make_backdrop(assets_dir, still["src"])
        scene3d = composer.compose_scene(shot, still, b, backdrop=backdrop)
        scenes.append(SceneBeat(scene_number=b["beat"], act_number=b["act"], start_sec=t, end_sec=t + b["seconds"], spoken_line=b["text"],
                                visual_prompt=shot.prompt, style_bible=style.style_for(pack)["look"], scene3d=scene3d))
        t += b["seconds"]
        if still.get("shared_with"):
            pass
        elif still["source"] in ("archive_fallback", "none"):
            qa_notes.append(f"beat {b['beat']}: {still.get('note') or 'no generated image'}")
        elif still.get("score") is not None and still["score"] < style.cfg()["judge"]["min_score"]:
            qa_notes.append(f"beat {b['beat']}: generated image scored {still['score']}/10 after one retry: {'; '.join(still['issues'])}")

    for b in beats:   # clips that were planned but did not happen are said plainly
        if results[b["beat"]].get("clip_note") and shot_by_beat[b["beat"]].clip_motion:
            qa_notes.append(f"beat {b['beat']}: {results[b['beat']]['clip_note']}")
    gen_paths = [os.path.join(assets_dir, r["src"]) for r in results.values() if r["source"] == "generated" and r.get("src")]
    consistency = stills.consistency_review(gen_paths, os.path.join(os.path.dirname(assets_dir) or ".", "stills_sheet.jpg"), judge_sheet) if gen_paths else {"score": None, "issues": [], "note": "no generated images"}
    narration = " ".join(b["text"] for b in beats)
    fact_report = (fact_fn or facts.verify_narration)(narration, script.topic_title, subject, tier=tier, provider=provider) if fact_fn or load_json("premium.json").get("facts") else {}

    counts = {k: sum(1 for r in results.values() if r["source"] == k and not r.get("shared_with")) for k in ("generated", "archive", "archive_fallback", "none")}
    counts["shared"] = sum(1 for r in results.values() if r.get("shared_with"))
    record = {
        "style_note": plan.get("style_note", ""), "pack": pack, "shots": len(shots), "images": counts,
        "per_beat": {str(k): {kk: vv for kk, vv in v.items() if kk != "src"} for k, v in results.items()},
        "consistency": consistency, "facts": fact_report, "cost": gateway.ledger.to_dict(), "policy_notes": plan.get("notes", []),
    }
    if clips_on:
        planned = [sh for sh in shots if sh.clip_motion]; got = [r["clip"] for r in results.values() if r.get("clip")]
        record["clips"] = {"planned": len(planned), "made": len(got), "seconds": round(sum(c["seconds"] for c in got), 1), "cost_usd": round(sum(c.get("cost_usd", 0) for c in got), 4),
                           "notes": [results[sh.beat]["clip_note"] for sh in planned if results[sh.beat].get("clip_note")]}
    for e in record["cost"]["entries"]:
        e.pop("token", None)
    storyboard = Storyboard(topic_title=script.topic_title, total_scenes=len(scenes), style_bible=style.style_for(pack)["look"], layout="full",
                            header=None, qa=qa_notes or None, route=route, scenes=scenes)
    return {"storyboard": storyboard, "premium": record}


def regenerate_beat_still(storyboard: Dict[str, Any], premium: Dict[str, Any], beat: int, assets_dir: str, new_prompt: Optional[str] = None,
                          gateway: Optional[MediaGateway] = None, judge: Optional[Callable] = None, resolver: Optional[Callable] = None) -> List[int]:
    """Redoes the still of one beat (and the beats that share it) from the saved shot plan, composes only those scenes again and
    updates the stored storyboard and cost record in place. Nothing else is touched. Returns the beats that changed."""
    from src.services.tiers import get_tier
    scenes = {s["scene_number"]: s for s in storyboard["scenes"]}
    beats = [{"beat": s["scene_number"], "act": s.get("act_number", 1), "text": s["spoken_line"], "seconds": float(s["end_sec"]) - float(s["start_sec"])}
             for s in storyboard["scenes"]]
    pack = (storyboard.get("route") or {}).get("pack") or premium.get("pack")
    plan = Checkpoint(os.path.dirname(assets_dir) or ".", beats, pack).plan
    if not plan:
        raise ValueError("This job has no saved shot plan; it cannot redo a single image.")
    shots = plan["shots"]
    idx = next((i for i, s in enumerate(shots) if s.beat == beat), None)
    if idx is None:
        raise ValueError(f"Beat {beat} is not in the shot plan.")
    group = [shots[idx]]
    for nxt in shots[idx + 1:]:
        if not nxt.reuse_previous:
            break
        group.append(nxt)
    first = group[0].model_copy(update={"reuse_previous": False, **({"prompt": new_prompt} if new_prompt else {})})
    group[0] = first
    gateway = gateway or new_gateway(get_tier("premium")["cost_cap_usd"])
    by_beat = {b["beat"]: b for b in beats}
    results = stills.produce_stills(group, [by_beat[s.beat] for s in group], pack, gateway, assets_dir, judge=judge, resolver=resolver,
                                    topic=storyboard.get("topic_title", ""), cache=None, allow_hero=False)
    ckpt = Checkpoint(os.path.dirname(assets_dir) or ".", beats, pack)
    for s in group:
        still, b = results[s.beat], by_beat[s.beat]
        backdrop = None
        if still.get("src") and still.get("aspect") and abs(still["aspect"] - style.cfg()["plane"]["aspect"]) >= 0.08:
            backdrop = composer.make_backdrop(assets_dir, still["src"])
        scenes[s.beat]["scene3d"] = composer.compose_scene(s, still, b, backdrop=backdrop)
        scenes[s.beat]["visual_prompt"] = s.prompt
        premium.setdefault("per_beat", {})[str(s.beat)] = {k: v for k, v in still.items() if k != "src"}
        ckpt.save_result(s.beat, still)
    if new_prompt:
        plan["shots"][idx] = first
        ckpt.save_plan(plan)
    spent = round(gateway.ledger.spent, 6)
    premium["regenerated"] = list(premium.get("regenerated", [])) + [{"beat": beat, "cost_usd": spent}]
    return [s.beat for s in group]
