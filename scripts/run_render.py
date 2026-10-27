"""Continues a job that is at Gate 1: runs the quiz stage (re-using the writer's quiz when the script is unchanged) and the
full video synthesis (voice, 3D render, audio mix). Usage: venv/bin/python scripts/run_render.py <job_id>"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.session import SessionLocal  # noqa: E402
from src.models.entities import ReelJob  # noqa: E402
from src.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402


def main():
    job_id = sys.argv[1]
    PipelineOrchestrator.run_stage2_quiz(job_id)
    PipelineOrchestrator.run_stage3_video_synthesis(job_id)
    db = SessionLocal(); job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    print("\nSTATUS", job.status, "| ERROR", job.error_message)
    print("VIDEO", job.local_video_path, "| DURATION", job.duration_sec)
    quiz = json.loads(job.quiz_data) if job.quiz_data else {}
    for q in quiz.get("questions", []):
        print("QUIZ", q.get("text"), "->", q.get("correctOptionId") or q.get("correct_option_id"))


if __name__ == "__main__":
    main()
