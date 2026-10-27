"""Conceptly Core publisher: turns an approved reel job into the STUDIO_INTEGRATION_CONTRACT payloads and ingests them.

Nothing here pretends: a payload that breaks the contract, a video that is not publicly reachable, a missing API key or a
non-2xx reply is an error the caller sees, and only a confirmed ingestion is recorded on the job (so a retry never posts twice).
"""
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.core.config import settings
from src.models.entities import ReelJob

_LOCAL_HOST = re.compile(r"^https?://(localhost|127\.|0\.0\.0\.0|\[::1\])", re.I)


class PublishError(Exception):
    """Publishing did not happen (or only half happened); `detail` says what, `status` is an HTTP status for the API layer."""

    def __init__(self, detail: str, status: int = 502, result: Optional[Dict[str, Any]] = None):
        super().__init__(detail)
        self.detail, self.status, self.result = detail, status, result or {}


def build_payloads(job: ReelJob, script: Dict[str, Any], quiz: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    topic_id = job.topic_id or f"topic-{job.id}"
    reel = {
        "title": script.get("title") or job.topic_title,
        "topicId": topic_id,
        "videoUrl": job.video_url or "",
        "durationSec": int(round(job.duration_sec or script.get("estimated_duration_sec") or 0)),
        "keyTakeaway": script.get("keyTakeaway") or script.get("key_takeaway", ""),
        "summaryNotes": script.get("summaryNotes") or script.get("summary_notes", []),
        "interviewPitch": script.get("interviewPitch") or script.get("interview_pitch") or "",
    }
    quiz_payload = {
        "topicId": topic_id,
        "topicTitle": job.topic_title,
        "questions": [
            {"id": q["id"], "text": q["text"], "options": [{"id": o["id"], "text": o["text"]} for o in q["options"]],
             "correctOptionId": q["correctOptionId"], "explanation": q.get("explanation", "")}
            for q in quiz.get("questions", [])
        ],
    }
    return reel, quiz_payload


def validate_payloads(reel: Dict[str, Any], quiz: Dict[str, Any], require_public_video: bool = True) -> List[str]:
    """Contract section 7 checks. Returns blocking problems."""
    problems: List[str] = []
    for key in ("title", "topicId", "keyTakeaway"):
        if not str(reel.get(key) or "").strip():
            problems.append(f"reel.{key} is empty")
    if not reel.get("summaryNotes"):
        problems.append("reel.summaryNotes is empty")
    if not (isinstance(reel.get("durationSec"), int) and reel["durationSec"] > 0):
        problems.append("reel.durationSec must be a positive whole number of seconds")
    url = str(reel.get("videoUrl") or "")
    if not re.match(r"^https?://", url):
        problems.append("the video has no public URL; configure cloud storage so the reel is reachable (local /media paths are not)")
    elif require_public_video and _LOCAL_HOST.match(url):
        problems.append("the video URL points at this machine; Conceptly Core cannot fetch it")
    if not quiz.get("questions"):
        problems.append("the quiz has no questions")
    for q in quiz.get("questions", []):
        ids = [o.get("id") for o in q.get("options", [])]
        if ids != ["a", "b", "c", "d"]:
            problems.append(f"{q.get('id')}: options must be a, b, c, d (got {ids})")
        if q.get("correctOptionId") not in ids:
            problems.append(f"{q.get('id')}: correctOptionId is not one of the options")
        if not str(q.get("explanation") or "").strip():
            problems.append(f"{q.get('id')}: explanation is empty")
    return problems


def preflight(job: ReelJob, force: bool = False) -> Dict[str, Any]:
    """Everything publishing needs, decided without sending anything."""
    if not job.script_data or not job.quiz_data:
        return {"ready": False, "problems": ["the job has no script or quiz yet"], "warnings": [], "reel": None, "quiz": None}
    script, quiz = json.loads(job.script_data), json.loads(job.quiz_data)
    reel, quiz_payload = build_payloads(job, script, quiz)
    problems = validate_payloads(reel, quiz_payload)
    warnings: List[str] = []
    gate = script.get("quality_gate") or {}
    blocked = [c["label"] for c in gate.get("checks", []) if not c["ok"] and c["blocking"]]
    if blocked:
        (warnings if force else problems).append("quality gate not passed: " + ", ".join(blocked))
    if not settings.CONCEPTLY_API_KEY:
        problems.append("CONCEPTLY_API_KEY is not set")
    if (script.get("quiz_check") or {}).get("issues"):
        (warnings if force else problems).append("quiz still disagrees with the narration: " + "; ".join(script["quiz_check"]["issues"]))
    return {"ready": not problems, "problems": problems, "warnings": warnings, "reel": reel, "quiz": quiz_payload,
            "already_published": (script.get("publish") or {}).get("reel", {}).get("ok", False)}


class PublisherAgent:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, client: Optional[httpx.Client] = None):
        self._base_url, self._api_key = base_url, api_key
        self.client = client or httpx.Client(timeout=30.0)

    @property
    def base_url(self) -> str:
        return (self._base_url or settings.CONCEPTLY_API_BASE_URL).rstrip("/")

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key or settings.CONCEPTLY_API_KEY

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        last = ""
        for attempt in range(2):   # one retry for timeouts and 5xx; client errors are final
            try:
                res = self.client.post(f"{self.base_url}{path}", json=payload, headers=headers)
            except httpx.HTTPError as e:
                last = f"{type(e).__name__}: {e}"
                continue
            body = res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text
            if res.status_code < 300:
                return {"ok": True, "status_code": res.status_code, "response": body}
            if res.status_code < 500:
                return {"ok": False, "status_code": res.status_code, "response": body}
            last = f"HTTP {res.status_code}"
        return {"ok": False, "error": last}

    def publish_reel(self, job: ReelJob, force: bool = False) -> Dict[str, Any]:
        """Posts the reel then its quiz. Returns the record to store on the job; raises PublishError when either did not land."""
        check = preflight(job, force=force)
        if not check["ready"]:
            raise PublishError("; ".join(check["problems"]), status=409)
        script = json.loads(job.script_data)
        record = dict(script.get("publish") or {})
        record["attempted_utc"] = datetime.utcnow().isoformat()
        if not record.get("reel", {}).get("ok"):
            record["reel"] = self._post("/curriculum/reels", check["reel"])
        if record["reel"].get("ok") and not record.get("quiz", {}).get("ok"):
            record["quiz"] = self._post("/quizzes", check["quiz"])
        record["warnings"] = check["warnings"]
        if not (record.get("reel", {}).get("ok") and record.get("quiz", {}).get("ok")):
            failed = [k for k in ("reel", "quiz") if not record.get(k, {}).get("ok")]
            raise PublishError(f"Conceptly Core did not accept the {' and '.join(failed)}: " + json.dumps({k: record.get(k) for k in failed})[:400], result=record)
        record["published_utc"] = datetime.utcnow().isoformat()
        return record


publisher_agent = PublisherAgent()
