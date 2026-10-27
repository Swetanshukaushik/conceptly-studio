import os
import sys
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
from src.main import app
from src.core.config import settings
from src.services.llm_factory import LLMFactory

def _wait_for(client, job_id, headers, status, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/reels/{job_id}", headers=headers).json()
        if data["status"] == status:
            return data
        assert data["status"] != "FAILED", f"Job failed: {data.get('error_message')}"
        time.sleep(1.0)
    raise AssertionError(f"Timed out waiting for {status}")


def _canned_visual_plan(monkeypatch):
    """The Free tier asks an LLM to design 3D scenes; tests replay the documented examples instead."""
    import json
    from src.models.scene3d import ReelVisualPlan
    from src.services.config_loader import CONFIG_DIR
    from src.agents.scene3d_director import Scene3DDirector
    example = json.load(open(os.path.join(CONFIG_DIR, "prompts", "scene3d_example.json")))

    def fake(system_prompt, user_prompt, response_model, **kw):
        if response_model is not ReelVisualPlan:
            return LLMFactory.generate_json.__wrapped__(system_prompt=system_prompt, user_prompt=user_prompt, response_model=response_model, **kw)
        import re
        beats = [int(n) for n in re.findall(r"^Beat (\d+) \|", user_prompt, re.M)]
        scenes = []
        for i, b in enumerate(beats):
            sc = json.loads(json.dumps(example["scenes"][i % len(example["scenes"])]))
            sc["beat"] = b
            scenes.append(sc)
        return ReelVisualPlan.model_validate({"look": example["look"], "scenes": scenes})
    return fake


def test_api_full_flow(monkeypatch):
    print("🚀 Testing Complete 3-Gate Pipeline via FastAPI Endpoints...")
    settings.ALLOW_OFFLINE_DEV_FALLBACK = True
    # Hermetic: never spend real API credits from the test suite, and keep test renders out of the reels library
    monkeypatch.setattr("src.pipeline.orchestrator.PipelineOrchestrator._archive_reel", staticmethod(lambda *a, **k: None))
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setattr(settings, key, None)
    from src.services.llm_factory import LLMFactory as _F
    original = _F.generate_json
    fake = _canned_visual_plan(monkeypatch)

    def routed(*a, **kw):
        rm = kw.get("response_model")
        from src.models.scene3d import ReelVisualPlan
        if rm is ReelVisualPlan:
            return fake(kw["system_prompt"], kw["user_prompt"], rm)
        return original(*a, **kw)
    monkeypatch.setattr("src.services.llm_factory.LLMFactory.generate_json", classmethod(lambda cls, *a, **kw: routed(*a, **kw)))
    
    with TestClient(app) as client:
        # 1. Health check
        res = client.get("/api/health")
        assert res.status_code == 200
        print("  [1/7] Health check OK.")
        
        # 2. Login as Admin
        login_res = client.post("/api/auth/login", json={
            "email": settings.ADMIN_EMAIL,
            "password": settings.ADMIN_PASSWORD
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [2/7] Admin login OK.")
        
        # 3. Create Reel Job
        create_payload = {
            "topic_title": "Newton's Third Law: The Rocket Principle",
            "exam_type": "SCHOOL",
            "class_level": 9,
            "subject": "Physics",
            "generation_tier": "DEFAULT",
            "direct_synthesis": False
        }
        create_res = client.post("/api/reels/create", json=create_payload, headers=headers)
        assert create_res.status_code == 200
        job_id = create_res.json()["id"]
        print(f"  [3/7] Reel Job Created (ID: {job_id})")
        
        job_data = _wait_for(client, job_id, headers, "GATE_1_READY")
        assert job_data["status"] == "GATE_1_READY"
        assert job_data["script_data"] is not None
        storyboard = job_data["script_data"].get("storyboard")
        assert storyboard is not None, "Storyboard must be generated in Gate 1"
        assert len(storyboard["scenes"]) > 0, "Storyboard must have scene beats"
        print(f"  [4/7] Gate 1 Ready: {len(job_data['script_data']['acts'])} acts & {len(storyboard['scenes'])} visual beats generated.")

        # Test Single-Scene Visual Re-roll / Regeneration
        regen_res = client.post(
            f"/api/reels/{job_id}/scenes/1/regenerate",
            json={
                "visual_prompt": "Cinematic 35mm view of rocket engine nozzle spewing blue luminous plasma in vacuum",
                "camera_motion": "PAN_RIGHT"
            },
            headers=headers
        )
        assert regen_res.status_code == 200, f"Scene regeneration failed: {regen_res.text}"
        updated_scene = regen_res.json()
        assert updated_scene["camera_motion"] == "PAN_RIGHT"
        assert "rocket engine nozzle" in updated_scene["visual_prompt"]
        print(f"        [✓] Scene 1 Re-roll verified (Motion: {updated_scene['camera_motion']}).")
        
        # 5. Approve Gate 1
        g1_res = client.post(f"/api/reels/{job_id}/gate1/approve", json={"script_data": job_data["script_data"]}, headers=headers)
        assert g1_res.status_code == 200
        
        job_data2 = _wait_for(client, job_id, headers, "GATE_2_READY")
        assert job_data2["status"] == "GATE_2_READY"
        assert job_data2["quiz_data"] is not None
        print(f"  [5/7] Gate 2 Ready (Quiz): {len(job_data2['quiz_data']['questions'])} MCQs generated.")
        
        # 7. Approve Gate 2 (Triggers Stage 3 Video Synthesis)
        g2_res = client.post(f"/api/reels/{job_id}/gate2/approve", json={"quiz_data": job_data2["quiz_data"]}, headers=headers)
        assert g2_res.status_code == 200
        print("  [6/7] Gate 2 Approved. Video synthesis triggered in background...")
        
        # Wait for video synthesis to complete (real 3D render)
        job_data3 = _wait_for(client, job_id, headers, "GATE_3_READY", timeout=420)
        assert job_data3["status"] == "GATE_3_READY"
        assert job_data3["video_url"] is not None
        assert len(job_data3["artifacts"]) >= 3
        print(f"  [7/7] Gate 3 Ready (Final Reel Review):")
        print(f"        Video URL: {job_data3['video_url']}")
        print(f"        Total Artifacts: {len(job_data3['artifacts'])}")
        
    print("\n🎉 Full 3-Gate Pipeline Lifecycle Successfully Verified 100%!")

if __name__ == "__main__":
    test_api_full_flow()


def test_gate1_approval_keeps_pipeline_keys(monkeypatch):
    """Approving Gate 1 must not drop the avatar/voice, dossier or pre-written quiz stored with the script."""
    import json as _json
    from src.database.session import SessionLocal
    from src.models.entities import ReelJob
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            script = {"title": "t", "topic_title": "t", "hook": "h", "key_takeaway": "k", "summary_notes": [], "total_word_count": 4, "acts": [
                {"act_number": 1, "title": "a", "start_sec": 0, "end_sec": 5, "spoken_text": "one two", "visual_direction": ""}],
                "avatar": {"voice_id": "en-IN-PrabhatNeural"}, "pending_quiz": {"topicTitle": "t", "questions": []}, "pending_quiz_for": "abc"}
            job = ReelJob(subject="Physics", topic_title="t", generation_tier="FREE", status="GATE_1_READY", script_data=_json.dumps(script))
            db.add(job); db.commit(); db.refresh(job); job_id = job.id
        finally:
            db.close()
        monkeypatch.setattr("src.api.reels.PipelineOrchestrator.run_stage2_quiz", staticmethod(lambda *a, **k: None))
        res = client.post(f"/api/reels/{job_id}/gate1/approve", json={"script_data": {k: v for k, v in script.items() if k not in ("avatar", "pending_quiz", "pending_quiz_for")}}, headers=headers)
        assert res.status_code == 200
        db = SessionLocal()
        try:
            kept = _json.loads(db.query(ReelJob).filter(ReelJob.id == job_id).first().script_data)
        finally:
            db.close()
        assert kept["avatar"]["voice_id"] == "en-IN-PrabhatNeural" and kept["pending_quiz_for"] == "abc"
