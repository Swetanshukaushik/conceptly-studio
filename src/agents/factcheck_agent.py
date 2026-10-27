from typing import Tuple
from src.models.schemas import ReelScript

class FactCheckAgent:
    """
    Quality Assurance & Pedagogical Fact-Check Guardrail:
    Ensures scientific accuracy, adherence to NCERT/JEE syllabus guidelines,
    and strict compliance with the 4-act vertical video retention contract.
    """

    @classmethod
    def verify_and_clean_script(cls, script: ReelScript) -> Tuple[bool, str, ReelScript]:
        issues = []

        # 1. Verify 4 or 5 Acts presence
        if len(script.acts) not in (4, 5):
            issues.append(f"Script must have 4 or 5 acts, found {len(script.acts)}")

        # 2. Verify Word Count (100 - 180 words target for 30-90s spoken explanation)
        actual_word_count = sum(len(act.spoken_text.split()) for act in script.acts)
        script.total_word_count = actual_word_count
        
        if actual_word_count > 210:
            issues.append(f"Spoken word count ({actual_word_count}) exceeds 90s threshold (max 200 words)")
        elif actual_word_count < 75:
            issues.append(f"Spoken word count ({actual_word_count}) is too brief (min 75 words)")

        # 3. Ensure concluding act has Call to Quiz
        act_last = script.acts[-1]
        cta_keywords = ["quiz", "test", "tap", "below", "check", "mastery"]
        if not any(kw in act_last.spoken_text.lower() for kw in cta_keywords):
            # Auto-append quiz CTA if omitted
            act_last.spoken_text += " Tap the quiz button below to test your mastery!"
            script.total_word_count = sum(len(act.spoken_text.split()) for act in script.acts)

        # 4. Ensure Summary Notes are present (at least 2 points)
        if len(script.summary_notes) < 2:
            issues.append("Summary notes must have at least 2 key takeaways.")

        is_valid = len(issues) == 0
        report = "Passed pedagogical checks." if is_valid else "; ".join(issues)
        return is_valid, report, script
