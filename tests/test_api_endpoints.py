import os
import sys
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
from src.main import app
from src.core.config import settings

def test_api_full_flow():
    print("🚀 Testing Complete 3-Gate Pipeline via FastAPI Endpoints...")
    
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
            "generation_tier": "DEFAULT"
        }
        create_res = client.post("/api/reels/create", json=create_payload, headers=headers)
        assert create_res.status_code == 200
        job_id = create_res.json()["id"]
        print(f"  [3/7] Reel Job Created (ID: {job_id})")
        
        time.sleep(1.0)
        
        # 4. Check Gate 1
        get_res = client.get(f"/api/reels/{job_id}", headers=headers)
        job_data = get_res.json()
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
        
        time.sleep(1.0)
        
        # 6. Check Gate 2
        get_res2 = client.get(f"/api/reels/{job_id}", headers=headers)
        job_data2 = get_res2.json()
        assert job_data2["status"] == "GATE_2_READY"
        assert job_data2["quiz_data"] is not None
        print(f"  [5/7] Gate 2 Ready (Quiz): {len(job_data2['quiz_data']['questions'])} MCQs generated.")
        
        # 7. Approve Gate 2 (Triggers Stage 3 Video Synthesis)
        g2_res = client.post(f"/api/reels/{job_id}/gate2/approve", json={"quiz_data": job_data2["quiz_data"]}, headers=headers)
        assert g2_res.status_code == 200
        print("  [6/7] Gate 2 Approved. Video synthesis triggered in background...")
        
        # Wait for video synthesis to complete
        time.sleep(3.0)
        
        # 8. Check Gate 3
        get_res3 = client.get(f"/api/reels/{job_id}", headers=headers)
        job_data3 = get_res3.json()
        assert job_data3["status"] == "GATE_3_READY"
        assert job_data3["video_url"] is not None
        assert len(job_data3["artifacts"]) >= 3
        print(f"  [7/7] Gate 3 Ready (Final Reel Review):")
        print(f"        Video URL: {job_data3['video_url']}")
        print(f"        Total Artifacts: {len(job_data3['artifacts'])}")
        
    print("\n🎉 Full 3-Gate Pipeline Lifecycle Successfully Verified 100%!")

if __name__ == "__main__":
    test_api_full_flow()
