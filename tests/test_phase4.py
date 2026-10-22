import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))

def test_phase4_publishing():
    print("🚀 Running Phase 4 Conceptly Core Ingestion Tests...")

    from src.database.session import SessionLocal, Base, engine
    from src.models.entities import ReelJob, User, JobStage
    from src.models.schemas import JobStatus
    from src.agents.publisher_agent import publisher_agent

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    admin_user = db.query(User).first()

    # 1. Create a job at GATE_3_READY state
    test_job = ReelJob(
        user_id=admin_user.id if admin_user else None,
        generation_tier="DEFAULT",
        exam_type="SCHOOL",
        class_level=9,
        subject="Physics",
        topic_title="Newton's Third Law: The Rocket Principle",
        topic_id="topic-phys-9-newton-3",
        status=JobStatus.GATE_3_READY.value,
        video_url="/media/reels/test_reel.mp4",
        duration_sec=48
    )
    test_job.script_data = json.dumps({
        "title": "Newton's Third Law: The Rocket Principle",
        "topic_title": "Newton's Third Law",
        "key_takeaway": "Forces always occur in matched pairs: action and equal opposite reaction.",
        "summary_notes": [
            "A force cannot exist in isolation; it requires two interacting objects.",
            "Rockets accelerate not by pushing against air, but by expelling mass backwards.",
            "Action and reaction act on DIFFERENT bodies, so they never cancel each other out."
        ],
        "interview_pitch": "Explain why you don't float away when taking a step on Earth vs space."
    })
    test_job.quiz_data = json.dumps({
        "topicId": "topic-phys-9-newton-3",
        "topicTitle": "Newton's Third Law",
        "questions": [
            {
                "id": "q1",
                "text": "If action and reaction forces are always equal and opposite, why do objects accelerate instead of canceling each other out?",
                "options": [
                    {"id": "a", "text": "They act on two completely different objects"},
                    {"id": "b", "text": "Reaction force occurs after a slight time delay"},
                    {"id": "c", "text": "Action force is always slightly greater than reaction"},
                    {"id": "d", "text": "Friction eliminates the reaction force"}
                ],
                "correctOptionId": "a",
                "explanation": "Newton's third law pairs act on different bodies, so they never cancel on a single object."
            }
        ]
    })
    db.add(test_job)
    db.commit()
    db.refresh(test_job)

    # Add PUBLISHING and GATE_3_REVIEW stages
    db.add(JobStage(job_id=test_job.id, stage_name="GATE_3_REVIEW", status="IN_PROGRESS", progress_percent=50))
    db.add(JobStage(job_id=test_job.id, stage_name="PUBLISHING", status="PENDING", progress_percent=0))
    db.commit()

    # 2. Test Publisher Agent Direct Payload Generation
    results = publisher_agent.publish_reel(test_job)
    assert "reel_ingestion" in results
    assert "quiz_ingestion" in results

    reel_payload = results["reel_ingestion"]["payload"]
    assert reel_payload["title"] == "Newton's Third Law: The Rocket Principle"
    assert reel_payload["topicId"] == "topic-phys-9-newton-3"
    assert reel_payload["durationSec"] == 48
    assert len(reel_payload["summaryNotes"]) == 3
    print("  [1/3] Reel Ingestion Payload conforming to CONTRACT.md Section 4A verified.")

    quiz_payload = results["quiz_ingestion"]["payload"]
    assert quiz_payload["topicId"] == "topic-phys-9-newton-3"
    assert len(quiz_payload["questions"]) == 1
    assert quiz_payload["questions"][0]["correctOptionId"] == "a"
    print("  [2/3] Quiz Ingestion Payload conforming to CONTRACT.md Section 4B verified.")

    # 3. Test HTTP Publish Gate 3 Endpoint
    from fastapi.testclient import TestClient
    from src.main import app
    from src.core.config import settings

    with TestClient(app) as client:
        login_res = client.post("/api/auth/login", json={
            "email": settings.ADMIN_EMAIL,
            "password": settings.ADMIN_PASSWORD
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        publish_res = client.post(
            f"/api/reels/{test_job.id}/gate3/publish",
            json={"publish_to_conceptly": True},
            headers=headers
        )
        assert publish_res.status_code == 200, publish_res.text
        data = publish_res.json()
        assert data["status"] == "PUBLISHED"
        print("  [3/3] Gate 3 Live Publishing Endpoint verified. Job marked as PUBLISHED.")

    db.close()
    print("\n🎉 Phase 4 Conceptly Core Ingestion Tests PASSED 100%!")

if __name__ == "__main__":
    test_phase4_publishing()
