"""Premium visual director: plan shots, produce stills under the spend cap, compose studio3d scenes, check facts, report cost."""
import os
from typing import Any, Callable, Dict, Optional

from src.agents.scene3d_director import Scene3DDirector
from src.models.schemas import ReelScript, SceneBeat, Storyboard
from src.services.config_loader import load_json
from src.services.media.providers import MediaGateway, new_gateway
from src.services.premium import composer, facts, planner, stills, style


def direct_premium_storyboard(script: ReelScript, subject: str, class_level: Optional[int], exam_type: str, assets_dir: str, tier: Any, provider: str,
                              route: Dict[str, Any], gateway: Optional[MediaGateway] = None, planner_fn: Optional[Callable] = None,
                              judge: Optional[Callable] = None, resolver: Optional[Callable] = None, fact_fn: Optional[Callable] = None,
                              judge_sheet: Optional[Callable] = None, cache: Any = "default") -> Dict[str, Any]:
    """Returns {"storyboard": Storyboard, "premium": record}. The record is stored with the job: cost report, image sources, reviews, facts."""
    from src.services.tiers import get_tier
    beats = Scene3DDirector.split_beats(script)
    pack = route["pack"]
    gateway = gateway or new_gateway(get_tier("premium")["cost_cap_usd"])
    plan = (planner_fn or planner.plan_shots)(script.topic_title, subject, beats, pack, tier, provider)
    shots = plan["shots"]
    results = stills.produce_stills(shots, beats, pack, gateway, assets_dir, judge=judge, resolver=resolver, topic=script.topic_title, cache=cache)

    scenes, qa_notes, t = [], list(plan.get("notes", [])), 0.0
    shot_by_beat = {s.beat: s for s in shots}
    for b in beats:
        shot, still = shot_by_beat[b["beat"]], results[b["beat"]]
        scene3d = composer.compose_scene(shot, still, b)
        scenes.append(SceneBeat(scene_number=b["beat"], act_number=b["act"], start_sec=t, end_sec=t + b["seconds"], spoken_line=b["text"],
                                visual_prompt=shot.prompt, style_bible=style.style_for(pack)["look"], scene3d=scene3d))
        t += b["seconds"]
        if still.get("shared_with"):
            pass
        elif still["source"] in ("archive_fallback", "none"):
            qa_notes.append(f"beat {b['beat']}: {still.get('note') or 'no generated image'}")
        elif still.get("score") is not None and still["score"] < style.cfg()["judge"]["min_score"]:
            qa_notes.append(f"beat {b['beat']}: generated image scored {still['score']}/10 after one retry: {'; '.join(still['issues'])}")

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
    for e in record["cost"]["entries"]:
        e.pop("token", None)
    storyboard = Storyboard(topic_title=script.topic_title, total_scenes=len(scenes), style_bible=style.style_for(pack)["look"], layout="full",
                            header=None, qa=qa_notes or None, route=route, scenes=scenes)
    return {"storyboard": storyboard, "premium": record}
