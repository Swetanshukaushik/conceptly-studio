"""One-call writer: domain dossier + spoken script + checkpoint quiz in a single LLM request.

The three prompts keep their original text (they are the agents' own SYSTEM_PROMPT constants); this agent only
orders the work (dossier, then script from the dossier, then quiz from the script) and asks for all three results
in one structured response, so a reel needs one request instead of three.
"""
from typing import List, Optional, Tuple

from pydantic import BaseModel

from src.agents.domain_intelligence_agent import DomainIntelligenceAgent
from src.agents.quiz_agent import QuizAgent
from src.agents.script_agent import ScriptAgent
from src.models.schemas import DomainPedagogyDossier, QuizPayload, ReelGenerationTier, ReelScript
from src.services.config_loader import load_json
from src.services import math_verifier
from src.services.llm_factory import LLMFactory


class WriterOutput(BaseModel):
    dossier: DomainPedagogyDossier
    script: ReelScript
    quiz: QuizPayload
    claims: List[math_verifier.MathClaim] = []


class MathVerificationError(RuntimeError):
    """A narrated number or equation is wrong (or its claim disagrees with the narration) and could not be repaired."""


class WriterAgent:
    PREAMBLE = (
        "You will do three jobs in order inside ONE response, and return all three results.\n"
        "JOB 1 (`dossier`): follow PART A and produce the Domain & Pedagogical Intelligence Dossier.\n"
        "JOB 2 (`script`): follow PART B and write the spoken reel script FROM YOUR OWN dossier (its hook, misconception, takeaway, "
        "analogy, applications). The script must obey the word-count rules given in the request.\n"
        "JOB 3 (`quiz`): follow PART C and write the checkpoint MCQs FROM YOUR OWN script and dossier (use the diagnostic trap and distractor "
        "from the dossier). Quiz questions must be answerable from what the script teaches.\n"
        "BINDING LINKS BETWEEN THE JOBS (these keep the three parts consistent, do not skip them):\n"
        "- Act 1 `spoken_text` must open with the dossier's `counter_intuitive_hook` (same idea, spoken naturally) and `script.hook` must restate it.\n"
        "- The script must debunk the dossier's `core_misconception` explicitly in the explanation acts and teach only the dossier's `must_include_concept`.\n"
        "- If the topic is quantitative, the script must include one concrete worked example with real numbers and units, spoken in words.\n"
        "- Quiz question 1 must be the dossier's `diagnostic_question`, with the `distractor_misconception_answer` as one of its options; "
        "quiz question 2 must test the script's key takeaway in a new situation. Every distractor must be a plausible student mistake.\n"
        "- Count the words of your acts before answering; the total must be inside the range given in the request.\n"
        "JOB 4 (`claims`): list every checkable statement of numbers, points, equations or computed values that the narration speaks, so a program can recompute it. "
        "Each claim has `kind` (one of: value, holds, identity, distance, distance_to_line, table, root, derivative, derivative_expr, balanced, molar_mass), `quote` (the exact words from the "
        "narration, copied verbatim, at most one sentence), `stated` (every number that quote says, as plain numbers; spoken words become digits) and the data to recompute it: "
        "value {expr, equals}; holds {lhs, rhs, at:{x:..,y:..}} (an equation is true at a point); identity {lhs, rhs, var} (true for all values); distance {a, b, equals}; "
        "distance_to_line {point:[x,y], line:[A,B,C] for Ax+By+C=0, equals}; table {function, var, rows:[[x,y],...]}; root {lhs, rhs, var, roots}; derivative {function, var, at:{x:..}, equals}; balanced {expr: the chemical equation as written, e.g. 'N2 + 3H2 <=> 2NH3'} (every chemical equation you state); molar_mass {expr: formula, equals: g/mol}; "
        "derivative_expr {function, var, derivative}. Expressions use + - * / ^ ( ), sqrt, sin, cos, tan, ln, pi. Compute every value yourself with care BEFORE you write the narration; "
        "a wrong number, point or equation is rejected and the reel is not produced. If the narration states no numbers, return an empty list. Never state a number in the narration that you have not checked.\n"
        "Return one JSON object with exactly the keys `dossier`, `script`, `quiz`, `claims`, each matching its schema. Where the parts below say to "
        "output a single schema, output that schema as the value of the matching key."
    )

    @classmethod
    def system_prompt(cls) -> str:
        return (f"{cls.PREAMBLE}\n\n=== PART A: DOMAIN DOSSIER ===\n{DomainIntelligenceAgent.SYSTEM_PROMPT}\n\n"
                f"=== PART B: SCRIPT ===\n{ScriptAgent.SYSTEM_PROMPT}\n\n=== PART C: QUIZ ===\n{QuizAgent.SYSTEM_PROMPT}")

    @classmethod
    def write(
        cls,
        topic_title: str,
        exam_type: str,
        class_level: Optional[int],
        subject: str,
        tier: ReelGenerationTier,
        avatar_name: Optional[str] = None,
        provider: Optional[str] = "AUTO",
        target_duration_sec: int = 60,
        topic_id: Optional[str] = None,
    ) -> Tuple[DomainPedagogyDossier, ReelScript, QuizPayload]:
        duration = max(30, min(90, target_duration_sec))
        tier_pace = load_json("pacing.json").get("tiers", {}).get(getattr(tier, "value", str(tier)).lower())
        if tier_pace:   # a tier whose voice speaks at a different speed gets a word range that fits its measured pace
            min_words, max_words = max(70, int(duration * tier_pace["min_wps"])), min(190, int(duration * tier_pace["max_wps"]))
        else:
            min_words, max_words = max(90, int(duration * 2.1)), min(190, int(duration * 2.7))
        user = (
            f"Target Curriculum Ingestion (for JOB 1):\n- Topic Title: {topic_title}\n- Exam Track: {exam_type}\n"
            f"- Class Level: {class_level or 'General'}\n- Subject: {subject}\n"
            f"- Generation Tier: {tier.value if hasattr(tier, 'value') else tier}\n- Assigned Teacher Avatar: {avatar_name or 'Auto Curriculum Presenter'}\n\n"
            f"Script requirements (for JOB 2): target spoken duration {duration} seconds; total spoken word count across all acts strictly "
            f"between {min_words} and {max_words} words; write for the ear; equations in spoken words; no markdown tables; no visual deictic phrases; "
            f"embed ellipses (...) for dramatic pauses and em dashes for pivots; 4 to 5 acts.\n\n"
            f"Quiz requirements (for JOB 3): 2 high-yield MCQs testing the core intuition, topic id {topic_id or 'unassigned'}."
        )
        profile = load_json("pipeline.json").get("writer_profile", "default")
        out = LLMFactory.generate_json(system_prompt=cls.system_prompt(), user_prompt=user, response_model=WriterOutput,
                                       tier=tier, provider=provider or "AUTO", profile=profile)
        out, verification = cls._verified(out, subject, user, tier, provider or "AUTO", profile)
        dossier, script, quiz = out.dossier, out.script, out.quiz
        script.math_claims = [c.model_dump(exclude_none=True) for c in out.claims] or None
        script.math_verification = verification
        if len(script.acts) < 4:
            raise RuntimeError(f"Writer returned {len(script.acts)} acts; at least 4 are required.")
        dossier.provider_used = "Auto-Selected LLM (one-call writer)"
        script.total_word_count = sum(len(a.spoken_text.split()) for a in script.acts)
        script.estimated_duration_sec = duration
        script.script_generator = provider or "AUTO"
        script.tts_vocal_direction = ScriptAgent.TTS_VOCAL_DIRECTION
        quiz.topicId = topic_id
        quiz.topicTitle = script.topic_title
        return dossier, script, quiz

    @classmethod
    def _verified(cls, out: WriterOutput, subject: str, user: str, tier: ReelGenerationTier, provider: str, profile: str):
        """Recomputes every claim; on any problem asks the writer once to correct its answer, then blocks the reel."""
        from src.services.concept_router import get_pack, route
        rules = get_pack(route(subject, use_llm=False)["pack"]).get("claims", {})
        require, coverage = bool(rules.get("required")), rules.get("coverage", "off")
        repairs = int(load_json("math_verify.json").get("repair", {}).get("max_repairs", 1)); attempts = 0
        while True:
            narration = " ".join(a.spoken_text for a in out.script.acts)
            problems, notes = math_verifier.verify(out.claims, narration, require=require, coverage=coverage if coverage != "off" else "off")
            if coverage == "off":
                notes = []
            if not problems:
                return out, {"status": "verified" if out.claims else "no_numbers", "attempts": attempts + 1, "claims": len(out.claims), "notes": notes}
            if attempts >= repairs:
                raise MathVerificationError("Narrated maths failed verification, so the reel was not produced:\n- " + "\n- ".join(problems))
            attempts += 1
            repair = (user + "\n\nYour previous answer failed the automatic maths check. Fix the narration (and the claims) so every number, point and equation is correct and every claim "
                      "matches the narration word for word. Problems:\n- " + "\n- ".join(problems) + "\n\nPrevious answer:\n" + out.model_dump_json())
            out = LLMFactory.generate_json(system_prompt=cls.system_prompt(), user_prompt=repair, response_model=WriterOutput, tier=tier, provider=provider, profile=profile)
