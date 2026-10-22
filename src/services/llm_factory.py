import json
import os
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel
from src.core.config import settings
from src.models.schemas import ReelGenerationTier, ReelScript, QuizPayload, ActScript, QuizQuestion, QuizOption

T = TypeVar("T", bound=BaseModel)

class LLMFactory:
    """
    Dual-Tier LLM Provider Factory:
    - DEFAULT: Google Gemini 1.5 Flash (Ultra-fast, structured JSON, ~$0.0006/reel)
    - PREMIUM: Anthropic Claude 3.5 Sonnet / OpenAI GPT-4o (Deep conceptual rigor, ~$0.035/reel)
    - Fallback: Deterministic high-yield pedagogical heuristic generator for offline dev & tests
    """

    @classmethod
    def generate_json(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    ) -> T:
        # 1. Attempt Gemini 1.5 Flash for DEFAULT tier (or if only Gemini key is available)
        if (tier == ReelGenerationTier.DEFAULT or not settings.ANTHROPIC_API_KEY) and settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    system_instruction=system_prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = model.generate_content(user_prompt)
                parsed = json.loads(response.text)
                return response_model.model_validate(parsed)
            except Exception as e:
                print(f"⚠️ Gemini generation failed: {e}. Falling back...")

        # 2. Attempt Claude 3.5 Sonnet for PREMIUM tier
        if tier == ReelGenerationTier.PREMIUM and settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    system=system_prompt + "\nOutput ONLY valid JSON matching the requested schema. No markdown backticks.",
                    messages=[{"role": "user", "content": user_prompt}]
                )
                content = message.content[0].text
                parsed = json.loads(content)
                return response_model.model_validate(parsed)
            except Exception as e:
                print(f"⚠️ Anthropic generation failed: {e}. Falling back...")

        # 3. Attempt OpenAI if key is present
        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                model_name = "gpt-4o" if tier == ReelGenerationTier.PREMIUM else "gpt-4o-mini"
                completion = client.beta.chat.completions.parse(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=response_model
                )
                return completion.choices[0].message.parsed
            except Exception as e:
                print(f"⚠️ OpenAI generation failed: {e}. Falling back to heuristic generator...")

        # 4. Fallback Heuristic Generator (Guaranteed valid Pydantic model for offline dev & tests)
        return cls._generate_heuristic_fallback(user_prompt, response_model)

    @classmethod
    def _generate_heuristic_fallback(cls, prompt: str, response_model: Type[T]) -> T:
        """Generates deterministic syllabus-compliant data when external APIs are offline."""
        prompt_lower = prompt.lower()
        is_history = any(kw in prompt_lower for kw in ["history", "bhagat", "freedom", "independence", "lahore", "revolt", "upsc", "british"])
        is_bio = any(kw in prompt_lower for kw in ["bio", "cell", "chloroplast", "photosynthesis", "neet", "dna", "heart"])
        
        if is_history:
            topic_title = "Bhagat Singh: The 1929 Assembly & Power of Ideas"
        elif is_bio:
            topic_title = "Chloroplasts & Photosynthesis"
        elif "newton" in prompt_lower:
            topic_title = "Newton's Third Law"
        else:
            topic_title = "Core Principle"
        
        # Check if response_model is ConceptBreakdown by name or equality
        if getattr(response_model, "__name__", "") == "ConceptBreakdown":
            from src.agents.curriculum_agent import ConceptBreakdown
            if is_history:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly view Bhagat Singh merely as a violent militant rather than a deep ideological thinker who deliberately avoided human casualties.",
                    counter_intuitive_hook="Why did two young revolutionaries drop bombs inside a packed parliament, yet deliberately aim for empty desks?",
                    single_takeaway="Bhagat Singh used the colonial courtroom not to escape death, but as a national megaphone to prove ideas can never be executed.",
                    core_analogy="A bullet stops a heart, but a revolutionary idea ignites millions of minds without shedding a drop of blood.",
                    key_applications=["1929 Central Legislative Assembly action", "Lahore Conspiracy Trial & hunger strikes", "Philosophical writings in Lahore Central Jail"]
                )
            elif is_bio:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students think photosynthesis directly converts carbon dioxide into glucose in a single step without water photolysis.",
                    counter_intuitive_hook="Did you know plants don't make oxygen from carbon dioxide—they rip it straight out of water molecules using sunlight?",
                    single_takeaway="Chloroplasts use solar photons to split water molecules, generating the chemical energy required to fix carbon.",
                    core_analogy="Chloroplasts are like solar nano-factories that dismantle water like LEGO bricks to harvest electrons.",
                    key_applications=["Photolysis in Thylakoids", "Calvin Cycle in Stroma", "Global Atmospheric Oxygen Regulation"]
                )
            else:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly believe action and reaction cancel each other out on the same object.",
                    counter_intuitive_hook="If you push a brick wall with 100 Newtons, why does your hand hurt even if the wall never moves?",
                    single_takeaway="Forces always occur in matched pairs acting on different bodies, so they never cancel each other out.",
                    core_analogy="Pushing a wall pushes you backward; jumping pushes the Earth downward as Earth pushes you upward.",
                    key_applications=["Rocket propulsion in space vacuum", "Walking and running friction dynamics", "Recoil of firing artillery"]
                )

        if response_model == ReelScript:
            if is_history:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Historic Hook",
                        start_sec=0.0,
                        end_sec=5.0,
                        spoken_text="On April 8th, 1929, two young men dropped bombs into the British Central Assembly. But they deliberately aimed at empty desks. Why?",
                        visual_direction="Dramatic cinematic 35mm film still of 23-year-old Bhagat Singh in colonial Delhi, warm lantern light, yellow leaflets scattering.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="Ideological Turning Point",
                        start_sec=5.0,
                        end_sec=22.0,
                        spoken_text="Because their goal was never to shed blood, but as their leaflets proclaimed, 'to make the deaf hear'. Bhagat Singh and Batukeshwar Dutt did not run away. They deliberately stood their ground shouting Inquilab Zindabad, transforming the colonial courtroom into a national megaphone for Indian independence.",
                        visual_direction="Historic British colonial courtroom, Bhagat Singh standing fearless in handcuffs, morning sunbeams through barred windows.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="The Power of Ideas",
                        start_sec=22.0,
                        end_sec=38.0,
                        spoken_text="Inside Lahore Central Jail, he didn't mourn; he devoured philosophy and economic justice. He proved that while an empire can hang a body, no tyrant can execute an idea. On March 23rd, 1931, three young martyrs walked to the gallows smiling.",
                        visual_direction="Atmospheric jail cell manuscripts followed by silhouettes of three revolutionaries walking head held high into the twilight.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Legacy & Mastery Check",
                        start_sec=38.0,
                        end_sec=45.0,
                        spoken_text="Their ultimate sacrifice ignited an unstoppable fire that drove colonial rule out forever. Tap the quiz button below to test your history mastery!",
                        visual_direction="Glowing Indian tricolor fluttering majestically over the Red Fort with illuminated quiz CTA badge.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
            else:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Hook",
                        start_sec=0.0,
                        end_sec=4.0,
                        spoken_text="If you push against a massive brick wall with one hundred Newtons of force, why does your hand hurt even when the wall doesn't budge an inch?",
                        visual_direction="High-contrast close-up of a hand pressing into a solid brick surface with illuminated force vector arrows.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="Core Intuition",
                        start_sec=4.0,
                        end_sec=24.0,
                        spoken_text="Because forces never, ever exist alone in nature. Newton discovered that every push you create generates an equal push right back at you. When your palm exerts force on the bricks, the wall simultaneously exerts an identical force back onto your skin.",
                        visual_direction="Animated side-by-side vector diagram showing Action Force (F1) and Reaction Force (F2) on two separate bodies.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="Real-World Application",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="This fundamental principle is precisely how rockets fly through the vacuum of space. The engine pushes burning exhaust gas violently downward, and that escaping gas pushes the massive rocket directly upward into orbit.",
                        visual_direction="Sleek dark-mode rocket cross-section showing downward exhaust velocity matching upward thrust acceleration.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Recap & Quiz Callout",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Remember: action and reaction always act on two completely different objects, so they never cancel each other out! Tap the quiz button below to test your mastery!",
                        visual_direction="Spotlight summary card highlighting: 'Different Bodies Never Cancel' with glowing Quiz CTA arrow.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
            total_words = sum(len(a.spoken_text.split()) for a in acts)
            return ReelScript(
                title=f"{topic_title}",
                topic_title=topic_title,
                hook=acts[0].spoken_text,
                key_takeaway=acts[2].spoken_text,
                summary_notes=[
                    "Bhagat Singh prioritized ideological awakening over violent insurrection." if is_history else "A force cannot exist in isolation; it requires two interacting bodies.",
                    "The courtroom was used intentionally as a national megaphone." if is_history else "Action and reaction forces act on completely DIFFERENT objects.",
                    "Executed on March 23, 1931 in Lahore Central Jail." if is_history else "Rockets accelerate by expelling mass backwards, not by pushing off air."
                ],
                interview_pitch="Explain how Bhagat Singh transformed the colonial courtroom into a weapon of ideological warfare." if is_history else "Explain why you don't float away when taking a step on Earth versus space.",
                acts=acts,
                total_word_count=total_words,
                estimated_duration_sec=45
            )

        elif response_model == QuizPayload:
            if is_history:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="Why did Bhagat Singh and Batukeshwar Dutt throw low-intensity smoke bombs in the 1929 Central Assembly aiming at empty spaces?",
                        options=[
                            QuizOption(id="a", text="To protest repressive colonial bills and 'make the deaf hear' without killing anyone"),
                            QuizOption(id="b", text="Because their explosive chemicals were defective"),
                            QuizOption(id="c", text="The British Viceroy had already evacuated the chamber"),
                            QuizOption(id="d", text="To signal an immediate mutiny in the colonial armed forces")
                        ],
                        correctOptionId="a",
                        explanation="Their leaflets stated: 'To make the deaf hear'. They deliberately threw low-grade bombs into empty spaces to avoid human casualties while protesting the Trade Disputes and Public Safety Bills."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="On which historic date were Bhagat Singh, Rajguru, and Sukhdev martyred in Lahore Central Jail?",
                        options=[
                            QuizOption(id="a", text="March 23, 1931"),
                            QuizOption(id="b", text="August 15, 1947"),
                            QuizOption(id="c", text="January 26, 1930"),
                            QuizOption(id="d", text="October 2, 1929")
                        ],
                        correctOptionId="a",
                        explanation="Bhagat Singh, Rajguru, and Sukhdev were executed on the evening of March 23, 1931, commemorated nationwide as Martyrs' Day (Shaheed Diwas)."
                    )
                ]
                return QuizPayload(
                    topicId="topic-hist-upsc-bhagat-singh-1929",
                    topicTitle=topic_title,
                    questions=questions
                )
            else:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="If action and reaction forces are always equal and opposite, why do objects accelerate instead of canceling each other out?",
                        options=[
                            QuizOption(id="a", text="They act on two completely different objects"),
                            QuizOption(id="b", text="The reaction force occurs after a time delay"),
                            QuizOption(id="c", text="The action force is always slightly larger"),
                            QuizOption(id="d", text="Friction cancels the reaction force")
                        ],
                        correctOptionId="a",
                        explanation="Newton's third law pairs act on different bodies (e.g. foot on Earth, Earth on foot), so they never cancel out on a single object."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="How does a rocket accelerate in the vacuum of deep space where there is no air to push against?",
                        options=[
                            QuizOption(id="a", text="By pushing off gravitational waves"),
                            QuizOption(id="b", text="By expelling high-velocity gas mass backwards"),
                            QuizOption(id="c", text="By creating a solar vacuum pocket in front"),
                            QuizOption(id="d", text="Rockets cannot accelerate without atmosphere")
                        ],
                        correctOptionId="b",
                        explanation="The rocket pushes exhaust gas backward; the backward gas pushes the rocket forward with equal and opposite force."
                    )
                ]
                return QuizPayload(
                    topicId="topic-phys-9-newton-3",
                    topicTitle=topic_title,
                    questions=questions
                )

        raise ValueError(f"No fallback registered for schema: {response_model}")
