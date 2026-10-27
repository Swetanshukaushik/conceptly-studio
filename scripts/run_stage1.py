"""Runs pipeline stage 1 (script, routing, 3D scene design, vision QA) for one topic using the real LLM keys in .env.

Usage: venv/bin/python scripts/run_stage1.py "Mathematics" "Parabola" [class_level] [exam_type]
Prints the route, the beats, the layout/header, QA notes and the model that answered each call,
and builds a contact sheet of the storyboard frames next to the job's files.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings  # noqa: E402
from src.database.session import SessionLocal  # noqa: E402
from src.models.entities import ReelJob  # noqa: E402
from src.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402


def main():
    subject, topic = sys.argv[1], sys.argv[2]
    class_level = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    exam = sys.argv[4] if len(sys.argv) > 4 else "SCHOOL"
    db = SessionLocal()
    job = ReelJob(subject=subject, topic_title=topic, class_level=class_level, exam_type=exam, generation_tier="FREE", script_generator="AUTO")
    db.add(job); db.commit(); job_id = job.id; db.close()
    PipelineOrchestrator.run_stage1_blueprint(job_id)

    db = SessionLocal(); job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    print("\nSTATUS", job.status, "| JOB", job_id)
    if job.error_message:
        print("ERROR", job.error_message)
    data = json.loads(job.script_data) if job.script_data else {}
    sb = data.get("storyboard") or {}
    print("ROUTE", json.dumps(sb.get("route")))
    print("LAYOUT", sb.get("layout"), "| HEADER", sb.get("header"), "| LOOK", sb.get("style_bible"))
    for sc in sb.get("scenes", []):
        d = sc.get("scene3d") or {}
        kinds = sorted({o.get("prefab") or o.get("type") for o in d.get("objects", [])})
        print(f"#{sc['scene_number']} [{sc['start_sec']:.1f}-{sc['end_sec']:.1f}] {sc['spoken_line'][:110]}")
        print(f"   intent: {d.get('intent')}\n   objects: {', '.join(kinds)} | overlays: {[o.get('kind') for o in d.get('overlays', [])]}")
    print("QA", json.dumps(sb.get("qa"), indent=1))
    frames = os.path.join(settings.LOCAL_STORAGE_DIR, "jobs", job_id, "storyboard_frames")
    print("FRAMES", frames)
    try:
        from PIL import Image
        files = sorted(f for f in os.listdir(frames) if f.endswith(".png"))
        ims = [Image.open(os.path.join(frames, f)).convert("RGB").resize((360, 640)) for f in files]
        cols = min(4, len(ims)); rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (360 * cols, 640 * rows))
        for i, im in enumerate(ims):
            sheet.paste(im, (360 * (i % cols), 640 * (i // cols)))
        out = os.path.join("scratch", f"stage1_{topic.lower().replace(' ', '_')}.jpg")
        sheet.save(out, quality=88); print("SHEET", out)
    except Exception as e:
        print("no contact sheet:", e)


if __name__ == "__main__":
    main()
