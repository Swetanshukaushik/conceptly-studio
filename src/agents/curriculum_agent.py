from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from src.services.llm_factory import LLMFactory
from src.models.schemas import ReelGenerationTier

class ConceptBreakdown(BaseModel):
    canonical_topic: str
    target_misconception: str = Field(..., description="The primary false intuition students hold.")
    counter_intuitive_hook: str = Field(..., description="0-4s scroll-stopping question exposing the misconception.")
    single_takeaway: str = Field(..., description="One precise sentence takeaway within 45s budget.")
    core_analogy: str = Field(..., description="An everyday tangible analogy explaining the mechanism.")
    key_applications: list[str]

class CurriculumAgent:
    """
    Curriculum & Concept Extractor Agent:
    Takes curriculum topics (NCERT 6-10, IIT-JEE, NEET, UPSC) and isolates
    the counter-intuitive hook and single takeaway lesson.
    """

    SYSTEM_PROMPT = """You are the Lead Curriculum Architect for Conceptly, an elite vertical micro-learning platform for Indian curriculum (NCERT Classes 6-10, IIT-JEE, NEET, UPSC).
Your job is to take an educational topic and formulate a high-yield concept breakdown tailored for a 45-second vertical reel:
1. Identify the single biggest misconception students struggle with in exams.
2. Devise a 3-second counter-intuitive verbal or visual hook that challenges their flawed intuition.
3. Formulate one crisp, scientifically flawless takeaway sentence.
4. Select an everyday tangible analogy (e.g. wall push, skater, garden hose) that provides instant intuition.
Output strictly structured JSON."""

    @classmethod
    def extract_concept(
        cls,
        topic_title: str,
        exam_type: str = "SCHOOL",
        class_level: Optional[int] = 9,
        subject: str = "Physics",
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    ) -> ConceptBreakdown:
        user_prompt = f"""Target Curriculum Topic:
- Exam / Board: {exam_type}
- Class Level: {class_level or 'General'}
- Subject: {subject}
- Topic Title: {topic_title}

Extract the core concept, target misconception, scroll-stopping hook question, single takeaway sentence, and everyday analogy."""

        return LLMFactory.generate_json(
            system_prompt=cls.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ConceptBreakdown,
            tier=tier
        )
