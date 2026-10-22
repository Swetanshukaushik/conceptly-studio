import json
from typing import Dict, Any, Optional
import httpx

from src.core.config import settings
from src.models.entities import ReelJob
from src.models.schemas import ReelScript, QuizPayload

class PublisherAgent:
    """
    Conceptly Core Publisher Agent:
    Translates finished reel jobs into CONTRACT.md ingestion payloads
    and syncs them directly to the Conceptly live API:
    - POST /v1/curriculum/reels
    - POST /v1/quizzes
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or settings.CONCEPTLY_API_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.CONCEPTLY_API_KEY
        self.client = httpx.Client(timeout=15.0)

    def publish_reel(self, job: ReelJob) -> Dict[str, Any]:
        """
        Ingests both the Reel and the Checkpoint Quizzes into Conceptly Core.
        """
        if not job.script_data or not job.quiz_data:
            raise ValueError(f"Job {job.id} is missing script_data or quiz_data")

        script_dict = json.loads(job.script_data)
        quiz_dict = json.loads(job.quiz_data)

        # 1. Prepare Reel Ingestion Payload (CONTRACT.md Section 4A)
        reel_payload = {
            "title": script_dict.get("title", job.topic_title),
            "topicId": job.topic_id or f"topic-{job.id}",
            "videoUrl": job.video_url or f"https://media.conceptly.app/reels/{job.id}.mp4",
            "durationSec": job.duration_sec or script_dict.get("estimated_duration_sec", 45),
            "keyTakeaway": script_dict.get("keyTakeaway") or script_dict.get("key_takeaway", ""),
            "summaryNotes": script_dict.get("summaryNotes") or script_dict.get("summary_notes", []),
            "interviewPitch": script_dict.get("interviewPitch") or script_dict.get("interview_pitch", "")
        }

        # 2. Prepare Quiz Ingestion Payload (CONTRACT.md Section 4B)
        quiz_payload = {
            "topicId": job.topic_id or f"topic-{job.id}",
            "topicTitle": job.topic_title,
            "questions": [
                {
                    "id": q["id"],
                    "text": q["text"],
                    "options": [
                        {"id": opt["id"], "text": opt["text"]}
                        for opt in q["options"]
                    ],
                    "correctOptionId": q["correctOptionId"],
                    "explanation": q.get("explanation", "")
                }
                for q in quiz_dict.get("questions", [])
            ]
        }

        results = {
            "reel_ingestion": {"status": "mocked", "payload": reel_payload},
            "quiz_ingestion": {"status": "mocked", "payload": quiz_payload}
        }

        # 3. Dispatch to live Conceptly Core API if configured
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if self.api_key and not self.base_url.startswith("http://mock"):
            try:
                # A. Ingest Reel
                reel_res = self.client.post(
                    f"{self.base_url}/curriculum/reels",
                    json=reel_payload,
                    headers=headers
                )
                results["reel_ingestion"] = {
                    "status_code": reel_res.status_code,
                    "response": reel_res.json() if reel_res.headers.get("content-type", "").startswith("application/json") else reel_res.text
                }
            except Exception as e:
                print(f"⚠️ Live Reel publication warning: {e}")
                results["reel_ingestion"]["error"] = str(e)

            try:
                # B. Ingest Quiz
                quiz_res = self.client.post(
                    f"{self.base_url}/quizzes",
                    json=quiz_payload,
                    headers=headers
                )
                results["quiz_ingestion"] = {
                    "status_code": quiz_res.status_code,
                    "response": quiz_res.json() if quiz_res.headers.get("content-type", "").startswith("application/json") else quiz_res.text
                }
            except Exception as e:
                print(f"⚠️ Live Quiz publication warning: {e}")
                results["quiz_ingestion"]["error"] = str(e)

        return results

publisher_agent = PublisherAgent()
