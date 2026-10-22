import uuid
import httpx
from typing import Optional, Dict, Any, List
from src.core.config import settings

# Built-in curriculum seed database for fast offline development and fallback
BUILTIN_CURRICULUM_SEEDS = {
    # NCERT Class 9 Physics
    "newton's third law": {
        "id": "topic-phys-9-newton-3",
        "title": "Newton's Third Law: Action and Reaction",
        "subject": "Physics",
        "classLevel": 9,
        "examType": "SCHOOL",
        "keyTakeaway": "Forces always occur in matched pairs acting on different bodies."
    },
    "universal law of gravitation": {
        "id": "topic-phys-9-gravitation",
        "title": "Universal Law of Gravitation",
        "subject": "Physics",
        "classLevel": 9,
        "examType": "SCHOOL",
        "keyTakeaway": "Every object in the universe attracts every other object with a force proportional to product of masses and inversely proportional to square of distance."
    },
    "work and energy": {
        "id": "topic-phys-9-work-energy",
        "title": "Work, Energy and Power",
        "subject": "Physics",
        "classLevel": 9,
        "examType": "SCHOOL",
        "keyTakeaway": "Work is done only when a force causes displacement in the direction of the force."
    },
    # NCERT Class 10 Science
    "photosynthesis": {
        "id": "topic-bio-10-photosynthesis",
        "title": "Photosynthesis & Light Reactions",
        "subject": "Biology",
        "classLevel": 10,
        "examType": "SCHOOL",
        "keyTakeaway": "Plants convert solar energy into chemical energy using chlorophyll to split water and fix carbon dioxide."
    },
    "ohm's law": {
        "id": "topic-phys-10-ohms-law",
        "title": "Ohm's Law: Voltage, Current & Resistance",
        "subject": "Physics",
        "classLevel": 10,
        "examType": "SCHOOL",
        "keyTakeaway": "Current through a conductor between two points is directly proportional to voltage across the two points, provided temperature remains constant."
    },
    # IIT-JEE Physics
    "projectile motion": {
        "id": "topic-jee-projectile",
        "title": "Projectile Motion & Trajectory Parabola",
        "subject": "Physics",
        "classLevel": 11,
        "examType": "IIT_JEE",
        "keyTakeaway": "Horizontal and vertical motions in a projectile are completely independent of each other under uniform gravity."
    },
    # NEET Biology
    "dna replication": {
        "id": "topic-neet-dna-replication",
        "title": "Semi-Conservative DNA Replication",
        "subject": "Biology",
        "classLevel": 12,
        "examType": "NEET",
        "keyTakeaway": "Each newly synthesized DNA molecule contains one original parent strand and one newly assembled daughter strand."
    },
    # UPSC / Class 10 History
    "bhagat singh": {
        "id": "topic-hist-upsc-bhagat-singh-1929",
        "title": "Bhagat Singh: 1929 Central Assembly & The Ideology of Revolution",
        "subject": "History",
        "classLevel": 10,
        "examType": "UPSC",
        "keyTakeaway": "Bhagat Singh used the colonial courtroom as a national megaphone, demonstrating that revolutionary ideas are immune to physical execution."
    }
}

class CurriculumResolver:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.CONCEPTLY_API_BASE_URL).rstrip("/")
        self.client = httpx.Client(timeout=5.0)

    def resolve_topic(
        self,
        topic_title: str,
        exam_type: str = "SCHOOL",
        class_level: Optional[int] = 9,
        subject: str = "Physics"
    ) -> Dict[str, Any]:
        """
        Attempts to resolve topic from live Conceptly Core API.
        Falls back to local seed ontology or generates a deterministic UUID if unindexed.
        """
        normalized_title = topic_title.strip().lower()

        # 1. Check live Conceptly Core API (if configured and reachable)
        if settings.CONCEPTLY_API_KEY:
            try:
                # Query curriculum topics endpoint
                response = self.client.get(
                    f"{self.base_url}/curriculum/classes/{class_level}/subjects",
                    headers={"Authorization": f"Bearer {settings.CONCEPTLY_API_KEY}"}
                )
                if response.status_code == 200:
                    subjects = response.json()
                    # Fuzzy match if subjects returned
                    for s in subjects:
                        if s.get("name", "").lower() == subject.lower():
                            pass
            except Exception:
                pass  # Fallback to local resolver

        # 2. Check local seed dictionary for exact or substring match
        for key, seed in BUILTIN_CURRICULUM_SEEDS.items():
            if key in normalized_title or normalized_title in key:
                return {
                    "topic_id": seed["id"],
                    "canonical_title": seed["title"],
                    "subject": seed["subject"],
                    "class_level": seed["classLevel"],
                    "exam_type": seed["examType"],
                    "is_resolved": True,
                    "seed_takeaway": seed.get("keyTakeaway")
                }

        # 3. Generate deterministic namespace UUID for custom or newly introduced topics
        namespace_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"conceptly.{exam_type}.{class_level}.{subject}.{normalized_title}"))
        return {
            "topic_id": namespace_uuid,
            "canonical_title": topic_title,
            "subject": subject,
            "class_level": class_level,
            "exam_type": exam_type,
            "is_resolved": False,
            "seed_takeaway": None
        }

curriculum_resolver = CurriculumResolver()
