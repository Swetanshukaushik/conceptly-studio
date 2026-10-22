from typing import Optional
from src.services.llm_factory import LLMFactory
from src.models.schemas import ReelScript, ReelGenerationTier
from src.agents.curriculum_agent import ConceptBreakdown

class ScriptAgent:
    """
    Scriptwriter & Hook Director Agent:
    Formulates a retention-optimized 4-act vertical screenplay adhering strictly
    to the 45-second attention budget and CONTRACT.md pacing specifications:
    - Act 1 (00s-04s): The Hook (Counter-intuitive question or visual paradox)
    - Act 2 (04s-25s): The Core Intuition (Everyday analogy + diagram direction)
    - Act 3 (25s-42s): Real-World Application (How technology or nature uses this)
    - Act 4 (42s-48s): 1-Second Takeaway + Call to Checkpoint Quiz
    """

    SYSTEM_PROMPT = """You are Conceptly's Principal Screenplay & Video Retention Director.
You write punchy, spoken vertical educational reels that keep students engaged without scrolling away.

CRITICAL TIMING & PACING CONTRACT (Total duration: 45 seconds, strictly 110-130 spoken words):
- ACT 1 [00s - 04s]: The Hook (Max 12-15 words). A counter-intuitive paradox or question that shocks the viewer.
- ACT 2 [04s - 25s]: The Core Intuition (Max 55-60 words). Explain the mechanism using the provided everyday analogy.
- ACT 3 [25s - 42s]: The Real-World Application (Max 40-45 words). Show how rockets, electricity, biology, or the cosmos rely on this.
- ACT 4 [42s - 48s]: The 1-Second Takeaway & Call to Quiz (Max 15-20 words). One final sentence, followed by 'Tap the quiz button below to test your mastery!'

For each act, provide:
1. 'spoken_text': Natural, rhythmic conversational English (or Indian English idiom for NCERT/JEE).
2. 'visual_direction': Exact instructions for the procedural motion card or visual illustration.
3. 'card_type': One of 'HOOK_CARD', 'ANALOGY_DIAGRAM', 'COMPARISON_BOX', 'FORMULA_SPOTLIGHT'.

Also provide:
- 'summary_notes': 3 high-yield bullet points for revision.
- 'interview_pitch': A thought-provoking conceptual question often asked in JEE/NEET/interviews.
Output strictly structured JSON conforming to the ReelScript schema."""

    @classmethod
    def generate_script(
        cls,
        concept: ConceptBreakdown,
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    ) -> ReelScript:
        user_prompt = f"""Generate the complete 4-Act Reel Screenplay based on this validated pedagogical blueprint:
- Topic: {concept.canonical_topic}
- Core Misconception to Debunk: {concept.target_misconception}
- Hook Idea: {concept.counter_intuitive_hook}
- Single Takeaway: {concept.single_takeaway}
- Primary Analogy: {concept.core_analogy}
- Key Applications: {', '.join(concept.key_applications)}

Strict rule: Total spoken word count across all 4 acts must be between 110 and 130 words!"""

        script = LLMFactory.generate_json(
            system_prompt=cls.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ReelScript,
            tier=tier
        )
        
        # Calculate real word count from acts
        actual_word_count = sum(len(act.spoken_text.split()) for act in script.acts)
        script.total_word_count = actual_word_count
        return script
