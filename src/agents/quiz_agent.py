from typing import Optional
from src.services.llm_factory import LLMFactory
from src.models.schemas import QuizPayload, ReelScript, ReelGenerationTier

class QuizAgent:
    """
    Quiz Generator Agent:
    Produces 2-3 concept-testing multiple-choice questions matching CONTRACT.md
    and Conceptly Core backend schema. Questions test the core takeaway and
    debunk common distractors.
    """

    SYSTEM_PROMPT = """You are Conceptly's Master Assessment & Quiz Specialist.
Your job is to generate 2 to 3 conceptual multiple-choice checkpoint questions that test whether a student truly understood the 45-second reel.

CRITICAL SCHEMA CONTRACT:
Each question must have:
- 'id': Unique question ID ('q1', 'q2', 'q3')
- 'text': Clear, unambiguous problem statement testing conceptual reasoning (NOT rote memorization).
- 'options': Exactly 4 options with ids 'a', 'b', 'c', 'd'. Distractors must represent common intuitive mistakes students make.
- 'correctOptionId': The correct option id ('a', 'b', 'c', or 'd').
- 'explanation': 1-2 sentence pedagogical explanation explaining why the correct option is right and why the intuition breaks down in others.

Output strictly structured JSON conforming to the QuizPayload schema."""

    @classmethod
    def generate_quiz(
        cls,
        script: ReelScript,
        topic_id: Optional[str] = None,
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    ) -> QuizPayload:
        user_prompt = f"""Generate 2 Checkpoint MCQs for this reel:
- Topic: {script.topic_title}
- Takeaway Lesson: {script.key_takeaway}
- Full Script:
Act 1: {script.acts[0].spoken_text}
Act 2: {script.acts[1].spoken_text}
Act 3: {script.acts[2].spoken_text}
Act 4: {script.acts[3].spoken_text}

Summary Points:
{chr(10).join(f'- {n}' for n in script.summary_notes)}

Requirements:
- Target Topic ID: {topic_id or 'unassigned'}
- Create 2 high-yield MCQs testing the core intuition."""

        quiz_payload = LLMFactory.generate_json(
            system_prompt=cls.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=QuizPayload,
            tier=tier
        )
        
        quiz_payload.topicId = topic_id
        quiz_payload.topicTitle = script.topic_title
        return quiz_payload
