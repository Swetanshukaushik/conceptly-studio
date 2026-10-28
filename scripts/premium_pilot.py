"""Premium pilot: runs stage 1 (and optionally stages 2-3) for three topics per domain and prints a cost report per reel.

Usage: venv/bin/python scripts/premium_pilot.py [--render] [--only "Salt March"]
Needs GEMINI_API_KEY with image credits for real generation; without credits every still falls back to archive photos and the
gate blocks the reel (images_generated). Exit bar: gate passes, spend at or under the cap, owner approves the look.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.session import SessionLocal  # noqa: E402
from src.models.entities import ReelJob  # noqa: E402
from src.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402

PILOT = {
    "History": [("History", "The Salt March"), ("History", "The Revolt of 1857"), ("Civics", "How the Indian Constitution was drafted")],
    "Biology": [("Biology", "How the human heart pumps blood"), ("Biology", "How DNA is copied"), ("Biology", "How a neuron fires")],
}


def run(subject: str, topic: str, render: bool) -> dict:
    db = SessionLocal()
    job = ReelJob(subject=subject, topic_title=topic, class_level=10, exam_type="SCHOOL", generation_tier="PREMIUM", script_generator="AUTO")
    db.add(job); db.commit(); job_id = job.id; db.close()
    PipelineOrchestrator.run_stage1_blueprint(job_id)
    if render:
        PipelineOrchestrator.run_stage2_quiz(job_id)
        PipelineOrchestrator.run_stage3_video_synthesis(job_id)
    db = SessionLocal(); job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    data = json.loads(job.script_data) if job.script_data else {}
    out = {"topic": topic, "job": job_id, "status": job.status, "error": job.error_message, "premium": data.get("premium") or {}, "gate": data.get("quality_gate") or {}}
    db.close()
    return out


def report(r: dict) -> None:
    p, g = r["premium"], r["gate"]; cost = p.get("cost", {})
    print(f"\n== {r['topic']} | job {r['job']} | {r['status']}" + (f" | ERROR {r['error']}" if r["error"] else ""))
    print(f"   gate {g.get('score')} {'PASSED' if g.get('passed') else 'BLOCKED'} | spend ${cost.get('spent_usd', 0):.3f} of ${cost.get('cap_usd', 0):.2f} | images {p.get('images')}")
    print(f"   consistency {p.get('consistency', {}).get('score')} | facts {p.get('facts', {}).get('status')} ({p.get('facts', {}).get('supported', 0)} supported, {p.get('facts', {}).get('contradicted', 0)} contradicted, {p.get('facts', {}).get('unverified', 0)} unverified)")
    print(f"   cost by kind {cost.get('by_kind')}")
    for c in g.get("checks", []):
        if not c["ok"]:
            print("   FAIL", c["id"], "-", c["label"], "|", c["detail"])


def main() -> None:
    args = sys.argv[1:]; render = "--render" in args
    only = args[args.index("--only") + 1] if "--only" in args else None
    results = []
    for domain, topics in PILOT.items():
        for subject, topic in topics:
            if only and only.lower() not in topic.lower():
                continue
            r = run(subject, topic, render); report(r); results.append(r)
    total = sum(r["premium"].get("cost", {}).get("spent_usd", 0) for r in results)
    passed = sum(1 for r in results if r["gate"].get("passed"))
    print(f"\nPILOT {len(results)} reels | gate passed {passed} | total spend ${total:.3f} | average ${total / max(1, len(results)):.3f} per reel")
    os.makedirs("scratch", exist_ok=True)
    json.dump(results, open("scratch/premium_pilot.json", "w"), indent=1)


if __name__ == "__main__":
    main()
