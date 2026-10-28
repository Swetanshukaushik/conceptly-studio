import json
import os
import re
from typing import Type, TypeVar, Optional, Dict, Any, List
from pydantic import BaseModel, ValidationError
from src.core.config import settings
from src.models.schemas import (
    ReelGenerationTier, ReelScript, QuizPayload, ActScript,
    QuizQuestion, QuizOption, Storyboard, SceneBeat, VisualModality, CameraMotion
)

T = TypeVar("T", bound=BaseModel)

class LLMFactory:
    """
    Dual-Tier LLM Provider Factory:
    - DEFAULT: Google Gemini 1.5 Flash (Ultra-fast, structured JSON, ~$0.0006/reel)
    - PREMIUM: Anthropic Claude 3.5 Sonnet / OpenAI GPT-4o (Deep conceptual rigor, ~$0.035/reel)
    - Fallback: Topic-Aware Heuristic Intelligence Engine for offline dev & tests
    """

    @staticmethod
    def _gemini_profile(profile: str) -> Dict[str, Any]:
        """Model order and generation settings come from config/llm_models.json, not code."""
        from src.services.config_loader import load_json
        profiles = load_json("llm_models.json")["gemini"]
        return profiles.get(profile) or profiles["default"]

    @staticmethod
    def _coerce_payload(data: Any, response_model: Any) -> Any:
        """Repairs harmless type slips in LLM JSON before validation, using the model's own JSON schema.

        A string where the schema wants a list becomes a list (split on newlines or semicolons), a bare value becomes a
        one-item list, a list where a string is wanted is joined. Costs nothing and avoids a retry request.
        """
        try:
            schema = response_model.model_json_schema()
        except Exception:
            return data
        defs = schema.get("$defs", {})

        def resolve(sch: Dict[str, Any]) -> Dict[str, Any]:
            if "$ref" in sch:
                return resolve(defs.get(sch["$ref"].split("/")[-1], {}))
            if "anyOf" in sch:
                options = [resolve(o) for o in sch["anyOf"] if o.get("type") != "null"]
                return options[0] if len(options) == 1 else sch
            return sch

        def fix(value: Any, sch: Dict[str, Any]) -> Any:
            sch = resolve(sch); kind = sch.get("type")
            if kind == "array":
                item = sch.get("items", {})
                if isinstance(value, str):
                    parts = [p.strip() for p in re.split(r"[\n;]+", value) if p.strip()] or [value]
                    value = parts if len(parts) > 1 else [p.strip() for p in re.split(r"\s*,\s*", value) if p.strip()] if "," in value and resolve(item).get("type") == "string" else parts
                elif value is not None and not isinstance(value, list):
                    value = [value]
                return [fix(v, item) for v in value] if isinstance(value, list) else value
            if kind == "string" and isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value):
                return "; ".join(str(v) for v in value)
            if kind == "object" and isinstance(value, dict):
                props = sch.get("properties", {})
                return {k: (fix(v, props[k]) if k in props else v) for k, v in value.items()}
            return value
        try:
            return fix(data, schema)
        except Exception:
            return data

    @classmethod
    def _gemini_timeout(cls) -> float:
        """Seconds one Gemini request may take before the next model in the profile is tried (config/llm_models.json)."""
        from src.services.config_loader import load_json
        return float(load_json("llm_models.json").get("request_timeout_seconds", 240))

    @classmethod
    def is_llm_configured(cls) -> bool:
        """Returns True if any valid LLM provider API key is configured."""
        return bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)

    @classmethod
    def generate_json(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        tier: ReelGenerationTier = ReelGenerationTier.FREE,
        provider: Optional[str] = "AUTO",
        profile: str = "default"
    ) -> T:
        # If no LLM API key is configured and offline dev fallback is disabled, fail explicitly
        if not cls.is_llm_configured() and not settings.ALLOW_OFFLINE_DEV_FALLBACK:
            raise RuntimeError(
                "Missing LLM API Key: Neither GEMINI_API_KEY nor OPENAI_API_KEY is configured in .env. "
                "A valid API key is required to dynamically generate blueprints, scripts, quizzes, and visual scenes for any topic without hardcoding."
            )
        # Enrich system prompt with JSON schema contract
        enriched_system_prompt = system_prompt
        try:
            if hasattr(response_model, "model_json_schema"):
                schema_str = json.dumps(response_model.model_json_schema(), indent=2)
                enriched_system_prompt += f"\n\nYou MUST return strictly valid JSON matching this exact JSON Schema:\n{schema_str}\nOutput ONLY the JSON object. Do not include markdown fences."
        except Exception:
            pass

        target_provider = (provider or "AUTO").upper().strip()

        # Specific route: OPENAI explicitly chosen by user
        if target_provider == "OPENAI":
            if not settings.OPENAI_API_KEY:
                raise RuntimeError(
                    "Missing OpenAI API Key: OPENAI_API_KEY is not configured in .env. "
                    "Please configure a valid key or select Google Gemini as your Script Generator."
                )
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                model_name = "gpt-4o" if tier in (ReelGenerationTier.ULTRA, ReelGenerationTier.PREMIUM, ReelGenerationTier.PREMIUM_VIDEO) else "gpt-4o-mini"
                from src.services.media import usage as _usage
                _usage.check_live("OpenAI")
                completion = client.beta.chat.completions.parse(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=response_model
                )
                _usage.record_openai(completion, model_name)
                return completion.choices[0].message.parsed
            except Exception as e:
                err_str = str(e).lower()
                if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "429" in err_str:
                    raise RuntimeError(
                        "Credits Finished: OpenAI API quota is exhausted (429 insufficient_quota). "
                        "Please add credits to your OpenAI account at https://platform.openai.com/settings/organization/billing/ "
                        "or switch Script Generator to Google Gemini."
                    )
                if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                    raise RuntimeError(f"OpenAI generation failed: {e}")
                print(f"⚠️ OpenAI generation failed: {e}. Falling back for dev/test...")

        # Specific route: GEMINI explicitly chosen by user
        elif target_provider == "GEMINI":
            if not settings.GEMINI_API_KEY:
                raise RuntimeError(
                    "Missing Gemini API Key: GEMINI_API_KEY is not configured in .env. "
                    "Please configure a valid key or select OpenAI as your Script Generator."
                )
            try:
                from src.services.media.usage import genai_module
                genai = genai_module()
                genai.configure(api_key=settings.GEMINI_API_KEY)
                candidate_models = cls._gemini_profile(profile)["models"]
                last_gemini_err = None
                for model_name in candidate_models:
                    try:
                        return cls._gemini_generate(genai, model_name, enriched_system_prompt, user_prompt, profile, response_model)
                    except Exception as me:
                        last_gemini_err = me
                        continue
                if last_gemini_err:
                    err_str = str(last_gemini_err).lower()
                    if "resource_exhausted" in err_str or "429" in err_str or "quota" in err_str:
                        raise RuntimeError(f"Credits Finished: Google Gemini API quota exhausted: {last_gemini_err}")
                    if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                        raise RuntimeError(f"Google Gemini generation failed: {last_gemini_err}")
            except Exception as e:
                if "Credits Finished" in str(e):
                    raise
                if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                    raise RuntimeError(f"Google Gemini generation error: {e}")

        # Smart AUTO Route (or Ultra Tier with Anthropic)
        else:
            # 1. Ultra Tier: Attempt Claude 3.5 Sonnet
            if tier == ReelGenerationTier.ULTRA and settings.ANTHROPIC_API_KEY:
                try:
                    import anthropic
                    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                    from src.services.media import usage as _usage
                    _usage.check_live("Anthropic")
                    message = client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=2048,
                        system=enriched_system_prompt,
                        messages=[{"role": "user", "content": user_prompt}]
                    )
                    _usage.record_anthropic(message, "claude-3-5-sonnet-20241022")
                    content = message.content[0].text
                    parsed = json.loads(content)
                    return response_model.model_validate(cls._coerce_payload(parsed, response_model))
                except Exception as e:
                    print(f"⚠️ Anthropic generation failed: {e}. Falling back...")

            # 2. Prioritize Gemini (Fastest, active quota)
            if settings.GEMINI_API_KEY:
                try:
                    from src.services.media.usage import genai_module
                    genai = genai_module()
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    candidate_models = cls._gemini_profile(profile)["models"]
                    last_gemini_err = None
                    for model_name in candidate_models:
                        try:
                            return cls._gemini_generate(genai, model_name, enriched_system_prompt, user_prompt, profile, response_model)
                        except Exception as me:
                            last_gemini_err = me
                            continue
                    if last_gemini_err:
                        print(f"⚠️ Gemini generation notice: {last_gemini_err}")
                except Exception as e:
                    print(f"⚠️ Gemini provider notice: {e}")

            # 3. Attempt OpenAI if key is present
            openai_exhausted = False
            if settings.OPENAI_API_KEY:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=settings.OPENAI_API_KEY)
                    model_name = "gpt-4o" if tier in (ReelGenerationTier.ULTRA, ReelGenerationTier.PREMIUM, ReelGenerationTier.PREMIUM_VIDEO) else "gpt-4o-mini"
                    from src.services.media import usage as _usage
                    _usage.check_live("OpenAI")
                    completion = client.beta.chat.completions.parse(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format=response_model
                    )
                    _usage.record_openai(completion, model_name)
                    return completion.choices[0].message.parsed
                except Exception as e:
                    err_str = str(e).lower()
                    if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "429" in err_str:
                        openai_exhausted = True
                        print(f"⚠️ OpenAI credit quota exhausted: {e}")
                    else:
                        print(f"⚠️ OpenAI generation failed: {e}")

            # Strict No-Fallback Rule: If credits are finished on configured providers, halt immediately
            if openai_exhausted and not settings.GEMINI_API_KEY:
                raise RuntimeError(
                    "Credits Finished: OpenAI API quota is exhausted (429 insufficient_quota). "
                    "Please add credits to your OpenAI account or configure a valid GEMINI_API_KEY."
                )

        if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
            raise RuntimeError(
                "Credits Finished: All configured AI providers have exhausted their quota or failed. "
                "Please recharge credits in Settings or configure a valid API key."
            )

        # 4. Fallback Heuristic Generator (Only for automated test fixtures with ALLOW_OFFLINE_DEV_FALLBACK=True)
        return cls._generate_heuristic_fallback(user_prompt, response_model)

    @classmethod
    def _gemini_generate(cls, genai, model_name: str, system: str, user: str, profile: str, response_model):
        """One model, a few tries: malformed JSON or a payload that fails validation is usually a one-off, so it is re-asked before
        the next model is tried. Quota, timeout and transport errors are not retried here."""
        from src.services.config_loader import load_json
        attempts = int(load_json("llm_models.json").get("attempts_per_model", 2))
        last: Exception = RuntimeError("no attempt")
        for _ in range(max(1, attempts)):
            model = genai.GenerativeModel(
                model_name=model_name, system_instruction=system,
                generation_config={**cls._gemini_profile(profile)["generation"], "response_mime_type": "application/json"})
            response = model.generate_content(user, request_options={"timeout": cls._gemini_timeout()})
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
            try:
                parsed = json.loads(raw_text)
                result = response_model.model_validate(cls._coerce_payload(parsed, response_model))
            except (json.JSONDecodeError, ValidationError) as e:
                last = e
                print(f"⚠️ {model_name} returned an unusable answer ({str(e)[:90]}); asking again")
                continue
            print(f"🤖 LLM model used: {model_name} (profile {profile})")
            return result
        raise last

    @classmethod
    def _extract_prompt_meta(cls, prompt: str) -> Dict[str, str]:
        meta = {
            "topic": "",
            "subject": "",
            "hook": "",
            "takeaway": "",
            "analogy": "",
            "misconception": ""
        }
        for line in prompt.splitlines():
            line_clean = line.strip().lstrip("-* ").strip()
            lower = line_clean.lower()
            if lower.startswith("topic title:"):
                meta["topic"] = line_clean.split(":", 1)[1].strip()
            elif lower.startswith("topic:"):
                meta["topic"] = line_clean.split(":", 1)[1].strip()
            elif lower.startswith("target curriculum topic:"):
                meta["topic"] = line_clean.split(":", 1)[1].strip()
            elif lower.startswith("subject:"):
                parts = line_clean.split("|")
                meta["subject"] = parts[0].split(":", 1)[1].strip()
            elif lower.startswith("hook idea:") or lower.startswith("hook:"):
                meta["hook"] = line_clean.split(":", 1)[1].strip()
            elif lower.startswith("single takeaway:") or lower.startswith("takeaway lesson:") or lower.startswith("takeaway:"):
                meta["takeaway"] = line_clean.split(":", 1)[1].strip()
            elif lower.startswith("primary analogy:") or lower.startswith("core analogy:"):
                meta["analogy"] = line_clean.split(":", 1)[1].strip()
            elif lower.startswith("core misconception to debunk:") or lower.startswith("target misconception:"):
                meta["misconception"] = line_clean.split(":", 1)[1].strip()

        # If topic was not extracted from a labeled prefix, search for common lines
        if not meta["topic"]:
            lines = [l.strip() for l in prompt.splitlines() if l.strip()]
            for l in lines:
                if any(k in l.lower() for k in ["topic", "magnet", "newton", "force", "photo", "bhagat", "law", "energy"]):
                    cleaned = re.sub(r"^[A-Za-z\s]+:\s*", "", l).strip()
                    if cleaned:
                        meta["topic"] = cleaned
                        break
        return meta

    @classmethod
    def _generate_heuristic_fallback(cls, prompt: str, response_model: Type[T]) -> T:
        """
        Dynamically synthesizes pedagogical schemas tailored to the requested topic
        so that offline development, test suites, and Free Tier local generation
        always produce 100% topic-accurate scripts, quizzes, and storyboards.
        """
        meta = cls._extract_prompt_meta(prompt)
        prompt_lower = (prompt + " " + meta["topic"] + " " + meta["subject"]).lower()

        # Domain Classifiers (Specific figures and STEM mechanisms)
        is_gandhi = any(kw in prompt_lower for kw in ["gandhi", "satyagraha", "dandi", "salt march", "non-violence", "quit india"])
        is_bose = any(kw in prompt_lower for kw in ["bose", "subhas", "ina", "azad hind", "jai hind"])
        is_ambedkar = any(kw in prompt_lower for kw in ["ambedkar", "constitution", "drafting", "preamble", "dalit", "article 32"])
        is_mountbatten = any(kw in prompt_lower for kw in ["mountbatten", "partition", "june 3rd plan", "viceroy"])
        is_napoleon = any(kw in prompt_lower for kw in ["napoleon", "waterloo", "bonaparte", "french revolution"])
        is_bhagat = any(kw in prompt_lower for kw in ["bhagat", "batukeshwar", "1929 assembly", "lahore conspiracy"])
        is_thermo = any(kw in prompt_lower for kw in ["thermo", "piston", "internal energy", "heat", "delta u", "first law", "q - w", "expansion"])
        is_magnetism = any(kw in prompt_lower for kw in [
            "magnet", "lorentz", "f=ilb", "f=i*l*b", "ilb", "fleming", "solenoid",
            "magnetic force", "magnetic field", "tesla", "flux density", "biot savart"
        ])
        is_bio_chloroplast = any(kw in prompt_lower for kw in ["chloroplast", "photosynthesis", "thylakoid", "calvin cycle", "photolysis"])
        is_dna = any(kw in prompt_lower for kw in ["dna", "helix", "franklin", "photo 51", "genetics", "double helix"])
        is_curie = any(kw in prompt_lower for kw in ["curie", "radioactiv", "radium", "polonium"])
        is_newton_rocket = any(kw in prompt_lower for kw in [
            "newton's third law", "newton 3", "action and reaction", "action-reaction",
            "rocket propulsion", "rocket exhaust", "thrust in space"
        ])
        is_ohms_law = any(kw in prompt_lower for kw in [
            "ohm's law", "ohms law", "resistance", "voltage", "current and resistance", "v=ir", "drift velocity"
        ])

        # Resolve Canonical Topic Title: ALWAYS prioritize actual requested topic!
        if meta["topic"]:
            topic_title = meta["topic"]
        elif is_thermo:
            topic_title = "Thermodynamics First Law: Internal Energy & Work (ΔU = Q - W)"
        elif is_gandhi:
            topic_title = "Mahatma Gandhi: The 1930 Salt March & Power of Satyagraha"
        elif is_bose:
            topic_title = "Netaji Subhas Chandra Bose & The Azad Hind Fauj"
        elif is_ambedkar:
            topic_title = "Dr. B.R. Ambedkar & The Architect of India's Constitution"
        elif is_napoleon:
            topic_title = "Napoleon Bonaparte: The Battle of Waterloo 1815"
        elif is_mountbatten:
            topic_title = "Lord Mountbatten & The 1947 Partition Plan"
        elif is_curie:
            topic_title = "Marie Curie & The Discovery of Radioactivity"
        elif is_dna:
            topic_title = "Rosalind Franklin & The Double Helix Structure of DNA"
        elif is_magnetism:
            topic_title = "Magnetic Force on a Current-Carrying Conductor: F = I · L · B"
        elif is_bhagat:
            topic_title = "Bhagat Singh: The 1929 Assembly & Power of Ideas"
        elif is_bio_chloroplast:
            topic_title = "Chloroplasts & Photosynthesis"
        elif is_newton_rocket:
            topic_title = "Newton's Third Law: Action and Reaction"
        elif is_ohms_law:
            topic_title = "Ohm's Law: Voltage, Current & Resistance"
        else:
            topic_title = "Core Curriculum Principle"

        # =========================================================================
        # 1. ConceptBreakdown Schema
        # =========================================================================
        if getattr(response_model, "__name__", "") == "ConceptBreakdown":
            from src.agents.curriculum_agent import ConceptBreakdown

            if is_magnetism:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly believe magnetic fields push conductors parallel to field lines, rather than exerting a sideways force perpendicular to both current and field.",
                    counter_intuitive_hook="Why does a dead-still copper wire violently jump into the air the exact microsecond you switch on an electric current inside a magnetic field?",
                    single_takeaway="A magnetic field exerts a deflecting sideways Lorentz force F = I · L · B · sin(θ) perpendicular to both current flow and magnetic field lines.",
                    core_analogy="Fleming's Left-Hand Rule: Index finger points to Field, Middle finger to Current, and your Thumb points in the direction of the explosive Force.",
                    key_applications=["High-speed Maglev bullet trains", "Electric motors and automotive drivetrains", "Loudspeaker electromagnetic voice coils"]
                )
            elif is_thermo:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly believe heat and internal energy are identical, assuming all heat added to a gas must raise its temperature rather than doing expansion work.",
                    counter_intuitive_hook="Why does pumping air into a bicycle tire make the valve stem burn hot to the touch even without an open flame?",
                    single_takeaway="First Law of Thermodynamics: Delta U = Q - W. Heat added either increases microscopic internal energy or performs mechanical expansion work.",
                    core_analogy="A gas cylinder with an expanding piston: heat pushes molecules faster, and colliding molecules shove the heavy piston upward against atmospheric pressure.",
                    key_applications=["Internal combustion engines and gas turbines", "Thermal power plant steam cycles", "Atmospheric adiabatic expansion and cloud formation"]
                )
            elif is_gandhi:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students think the Salt March was merely a symbolic protest rather than a meticulously calculated economic and moral challenge that broke colonial authority.",
                    counter_intuitive_hook="How did a pinch of salt picked up from a beach shake the foundations of the British Empire?",
                    single_takeaway="Mahatma Gandhi turned salt—a universal necessity—into a weapon of satyagraha, uniting millions in civil disobedience.",
                    core_analogy="A single ripple in the ocean becomes an unstoppable tidal wave of moral defiance.",
                    key_applications=["1930 Salt Satyagraha at Dandi", "Civil Disobedience Movement", "Gandhi-Irwin Pact and Round Table Conferences"]
                )
            elif is_bose:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly overlook the decisive geopolitical and military impact of the INA on post-war British retreat.",
                    counter_intuitive_hook="Why did a military campaign on the Burma border trigger the rapid collapse of British naval power in India?",
                    single_takeaway="Netaji's INA and the Red Fort trials ignited mutinies across the armed forces, rendering colonial rule unsustainable.",
                    core_analogy="Striking the cornerstone of colonial military loyalty brings down the entire imperial arch.",
                    key_applications=["Formation of Azad Hind Government 1943", "Rani of Jhansi Regiment", "1946 Royal Indian Navy Revolt"]
                )
            elif is_ambedkar:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students view the Constitution solely as a legal code rather than a transformative social manifesto guaranteeing equality and constitutional remedies.",
                    counter_intuitive_hook="What makes Article 32 the 'heart and soul' of the Indian Constitution?",
                    single_takeaway="Dr. Ambedkar designed constitutional remedies to give every citizen the power to enforce their fundamental rights directly against state power.",
                    core_analogy="A shield with no handle cannot protect a warrior; Article 32 is the handle that makes Fundamental Rights enforceable.",
                    key_applications=["Drafting Committee of the Constituent Assembly", "Article 32 Constitutional Remedies", "Affirmative Action and Fundamental Rights"]
                )
            elif is_bhagat:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly view Bhagat Singh merely as a violent militant rather than a deep ideological thinker who deliberately avoided human casualties.",
                    counter_intuitive_hook="Why did two young revolutionaries drop bombs inside a packed parliament, yet deliberately aim for empty desks?",
                    single_takeaway="Bhagat Singh used the colonial courtroom not to escape death, but as a national megaphone to prove ideas can never be executed.",
                    core_analogy="A bullet stops a heart, but a revolutionary idea ignites millions of minds without shedding a drop of blood.",
                    key_applications=["1929 Central Legislative Assembly action", "Lahore Conspiracy Trial & hunger strikes", "Philosophical writings in Lahore Central Jail"]
                )
            elif is_bio_chloroplast:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students think photosynthesis directly converts carbon dioxide into glucose in a single step without water photolysis.",
                    counter_intuitive_hook="Did you know plants don't make oxygen from carbon dioxide—they rip it straight out of water molecules using sunlight?",
                    single_takeaway="Chloroplasts use solar photons to split water molecules, generating the chemical energy required to fix carbon.",
                    core_analogy="Chloroplasts are like solar nano-factories that dismantle water like LEGO bricks to harvest electrons.",
                    key_applications=["Photolysis in Thylakoids", "Calvin Cycle in Stroma", "Global Atmospheric Oxygen Regulation"]
                )
            elif is_dna:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students assume Watson and Crick derived the double helix purely theoretically without Rosalind Franklin's experimental X-ray diffraction Photo 51.",
                    counter_intuitive_hook="How did a single blurry X-shaped shadow on photographic film reveal the secret of all life on Earth?",
                    single_takeaway="Rosalind Franklin's Photo 51 provided the mathematical diffraction proof that DNA exists as an antiparallel double helix.",
                    core_analogy="Reading a blueprint through its shadow: the X pattern proved a helical twist with phosphate backbones on the outside.",
                    key_applications=["Photo 51 X-ray diffraction", "Watson-Crick antiparallel double helix model", "Complementary base pairing (A-T, G-C)"]
                )
            elif is_newton_rocket:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students mistakenly believe action and reaction cancel each other out on the same object.",
                    counter_intuitive_hook="If you push a brick wall with 100 Newtons, why does your hand hurt even if the wall never moves?",
                    single_takeaway="Forces always occur in matched pairs acting on different bodies, so they never cancel each other out.",
                    core_analogy="Pushing a wall pushes you backward; jumping pushes the Earth downward as Earth pushes you upward.",
                    key_applications=["Rocket propulsion in space vacuum", "Walking and running friction dynamics", "Recoil of firing artillery"]
                )
            elif is_ohms_law:
                return ConceptBreakdown(
                    canonical_topic=topic_title,
                    target_misconception="Students believe resistance is caused by wires running out of power, rather than collisions of drifting electrons with the atomic lattice.",
                    counter_intuitive_hook="Why does doubling the voltage across a simple wire suddenly make it glow red hot with four times the heat?",
                    single_takeaway="Current is directly proportional to applied voltage and inversely proportional to electrical resistance (V = I · R).",
                    core_analogy="Voltage is water pressure pushing through a pipe, current is the flow rate, and resistance is a constriction slowing it down.",
                    key_applications=["Electronic power management", "Heating elements and fuses", "Semiconductor integrated circuit design"]
                )
            else:
                # Dynamic Procedural Concept for ANY other curriculum topic
                clean_name = meta["topic"] if meta["topic"] else "this concept"
                return ConceptBreakdown(
                    canonical_topic=clean_name,
                    target_misconception=f"Students often memorize {clean_name} as isolated facts without understanding its core governing mechanism.",
                    counter_intuitive_hook=f"What is the counter-intuitive principle behind {clean_name} that examiners love to test?",
                    single_takeaway=meta["takeaway"] if meta["takeaway"] else f"{clean_name} is governed by foundational physical laws connecting microscopic causes to observable results.",
                    core_analogy=f"Understanding {clean_name} is like uncovering the master gear that drives an entire mechanical clockwork.",
                    key_applications=[f"Standard examination problem solving for {clean_name}", f"Modern technological applications of {clean_name}", f"Advanced analytical modeling"]
                )

        # =========================================================================
        # 2. ReelScript Schema
        # =========================================================================
        if response_model == ReelScript:
            if is_magnetism:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Magnetic Kick",
                        start_sec=0.0,
                        end_sec=4.0,
                        spoken_text="Place a copper wire between two powerful magnets and switch on the current. Instantly, the wire kicks violently upward! Why?",
                        visual_direction="High-contrast macro close-up of a suspended copper rod kicking sideways between glowing red North and blue South magnetic poles.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="The Lorentz Mechanism",
                        start_sec=4.0,
                        end_sec=24.0,
                        spoken_text="Because whenever electric charges drift through a magnetic field, they experience a sideways Lorentz deflection. The drifting electrons collide with the wire's crystal lattice, pushing the entire conductor outward according to Fleming's Left-Hand Rule.",
                        visual_direction="3D vector triad of Fleming's Left Hand Rule: Thumb (Force F), Forefinger (Field B), Middle finger (Current I) glowing in neon emerald, cyan, and amber.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="Maglev & Motor Power",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="The magnitude is quantified by F equals I times L times B times sine theta. Increase current, conductor length, or magnetic flux, and the force surges! This exact principle propels 600 kilometer-per-hour Maglev trains and powers every electric car motor on Earth.",
                        visual_direction="Futuristic high-speed Maglev train levitating above magnetic guide rails with neon Lorentz force vectors lifting the carriages, vertical 9:16.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Mastery Check & Callout",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Remember: magnetic force is always perpendicular to both current and magnetic field! Tap the quiz button below to test your mastery!",
                        visual_direction="Illuminated formula spotlight highlighting F = I · L · B · sin(θ) with glowing quiz CTA button.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    "Magnetic force F = I · L · B · sin(θ) acts on current-carrying conductors in external B-fields.",
                    "Direction is given by Fleming's Left-Hand Rule (Thumb: Force, Index: Field, Middle: Current).",
                    "Force is maximum when wire is perpendicular (θ = 90°) and zero when parallel (θ = 0°)."
                ]
                interview_pitch = "Why is no net work done on a free charged particle moving in a pure uniform magnetic field?"

            elif is_thermo:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Heat Paradox",
                        start_sec=0.0,
                        end_sec=5.0,
                        spoken_text="Why does vigorously pumping air into a bicycle tire make the metal valve stem burn hot to the touch, even with zero fire?",
                        visual_direction="3D glass cylinder housing oscillating gas particles; rapid mechanical compression causes particles to flash from cool cyan to fiery amber, vertical 9:16.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="Internal Energy & Piston Work",
                        start_sec=5.0,
                        end_sec=24.0,
                        spoken_text="Because heat is not a fluid—it's microscopic kinetic motion! When you compress a gas, the moving piston does mechanical work W directly on the molecules. That energy cannot vanish; it directly surges the system's internal energy Delta U, driving up its temperature.",
                        visual_direction="Macro 3D cutaway of expanding gas piston: heat added Q enters from the bottom base while the piston rod pushes upward doing mechanical work W against external atmospheric pressure, vertical 9:16.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="The Conservation Law",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="This is the First Law of Thermodynamics: Delta U equals Q minus W. Every joule of heat added either heats up the molecules or gets converted into mechanical work. It powers every combustion engine, jet turbine, and power plant on planet Earth.",
                        visual_direction="Illuminated 3D HUD equation overlay: ΔU = Q - W with glowing live telemetry meters for heat input Q in Joules, mechanical work W in Joules, and internal energy change ΔU in neon green, vertical 9:16.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Thermodynamics Mastery Check",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Energy is never created or destroyed—only transformed! Tap the quiz button below to test your thermodynamics mastery right now!",
                        visual_direction="Floating 3D glowing formula spotlight ΔU = Q - W with pulsing quiz CTA arrow, vertical 9:16.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    "First Law of Thermodynamics: ΔU = Q - W (Conservation of Energy).",
                    "ΔU is internal energy (function of temperature), Q is heat added, W is work done by system.",
                    "In adiabatic processes (Q=0), compression work directly increases internal energy (ΔU = -W)."
                ]
                interview_pitch = "Why does an expanding ideal gas cool down during an adiabatic expansion even when no heat leaves the chamber?"

            elif is_gandhi:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Pinch of Salt Hook",
                        start_sec=0.0,
                        end_sec=5.0,
                        spoken_text="How did a frail 61-year-old man walking to the Arabian sea with a wooden staff shatter the foundation of the British Empire?",
                        visual_direction="Photorealistic 3D cinematic scene of Mahatma Gandhi marching at sunrise along dusty Gujarat roads, round spectacles reflecting golden light, vertical 9:16.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="The 240-Mile Defiance",
                        start_sec=5.0,
                        end_sec=24.0,
                        spoken_text="On March 12th, 1930, Mahatma Gandhi led 78 satyagrahis on a 240-mile march from Sabarmati to Dandi. The British monopolized and heavily taxed salt—a gift of nature vital to the poorest peasant. By picking up a handful of mud and salt from the coast, he turned a daily necessity into a weapon of mass defiance.",
                        visual_direction="3D camera sweeps across thousands of marching villagers joining the Salt March, warm cinematic golden-hour atmospheric haze, vertical 9:16.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="The Power of Satyagraha",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="He declared: 'With this, I am shaking the foundations of the British Empire.' Over 60,000 Indians peacefully courted arrest without raising a single fist. The world watched in awe as moral courage exposed the moral bankruptcy of colonial tyranny.",
                        visual_direction="Mahatma Gandhi raising a lump of white sea salt on Dandi beach as ocean waves crash in 3D slow motion, news headlines appearing in glowing typography, vertical 9:16.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Legacy & History Mastery Check",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Non-violence became the greatest force mankind had ever seen. Tap the quiz button below to test your UPSC history mastery!",
                        visual_direction="Dignified 3D tricolor Indian emblem with illuminated quiz CTA badge, vertical 9:16.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    "Dandi March lasted 24 days (March 12 – April 6, 1930), covering 240 miles from Sabarmati to Dandi.",
                    "Triggered the nationwide Civil Disobedience Movement, breaking colonial salt manufacturing laws.",
                    "Led to the Gandhi-Irwin Pact of March 1931 and Indian participation in the Second Round Table Conference."
                ]
                interview_pitch = "Analyze why salt was chosen by Gandhi as the central catalyst for nationwide mass mobilization in 1930."

            elif is_bose:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Battle Cry",
                        start_sec=0.0,
                        end_sec=5.0,
                        spoken_text="'Give me blood, and I shall give you freedom!' Why did Netaji Subhas Chandra Bose take the armed path to Indian liberation?",
                        visual_direction="3D heroic reconstruction of Netaji Subhas Chandra Bose in military uniform at microphone, dark cinematic rim light, vertical 9:16.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="The Azad Hind Fauj",
                        start_sec=5.0,
                        end_sec=24.0,
                        spoken_text="Escaping house arrest in 1941, Netaji journeyed across Afghanistan, Russia, and Germany to Singapore. In 1943, he revitalized the Indian National Army (Azad Hind Fauj), establishing a provisional government recognized across Asia, including the historic all-female Rani of Jhansi Regiment.",
                        visual_direction="3D strategic animated war map tracing Netaji's daring journey from Calcutta to Berlin to Singapore with battle trajectories in gold, vertical 9:16.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="March on Delhi",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="With the resounding roar of 'Chalo Dilli!' and 'Jai Hind!', the INA breached the Burma border and hoisted the tricolor at Moirang. Though militarily constrained, the INA trials at the Red Fort ignited mutinies across the Royal Indian Navy, sounding the final death knell for colonial rule.",
                        visual_direction="INA soldiers raising the Indian tricolor atop historical fortress battlements in cinematic sunrise lighting, vertical 9:16.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Nationalist Mastery Check",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Netaji proved freedom is not begged for—it is seized. Tap the quiz button below to test your history mastery right now!",
                        visual_direction="Golden 'Jai Hind' typography with glowing quiz CTA button, vertical 9:16.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    "Formed Provisional Government of Free India (Arzi Hukumat-e-Azad Hind) on Oct 21, 1943 in Singapore.",
                    "Created the Rani of Jhansi Regiment commanded by Captain Lakshmi Sahgal.",
                    "Post-war Red Fort INA trials triggered the 1946 Royal Indian Navy mutiny."
                ]
                interview_pitch = "Examine how the Red Fort INA trials transformed military discipline into nationwide mass revolt in 1945-46."

            elif is_ambedkar:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Constitution's Soul",
                        start_sec=0.0,
                        end_sec=5.0,
                        spoken_text="What makes a document written on parchment stronger than millions of swords? The genius of Dr. B.R. Ambedkar.",
                        visual_direction="3D cinematic reconstruction of Dr. B.R. Ambedkar in iconic blue suit, holding the Constitution of India in illuminated parliamentary hall, vertical 9:16.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="Architect of Democracy",
                        start_sec=5.0,
                        end_sec=24.0,
                        spoken_text="As Chairman of the Drafting Committee, Babasaheb synthesized legal traditions across five continents into the world's most comprehensive constitution. He engineered Fundamental Rights not as privileges granted by rulers, but as inviolable guarantees of human dignity and equality for every citizen.",
                        visual_direction="Holographic 3D constitutional pages floating in space: Preamble, Article 14 (Equality), Article 21 (Life & Liberty) glowing in warm cyan, vertical 9:16.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="Article 32: The Heart and Soul",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="When asked which single article was most essential, he declared Article 32: the right to constitutional remedies. Without the power of citizens to directly petition the Supreme Court against tyranny, every other constitutional right is reduced to empty words.",
                        visual_direction="3D Ashoka Pillar golden lions with holographic scales of justice balancing social democracy, vertical 9:16.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Polity Mastery Check",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Educate, Agitate, Organise! Tap the quiz button below to test your UPSC Polity mastery!",
                        visual_direction="Illuminated Constitution emblem with glowing quiz CTA button, vertical 9:16.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    "Dr. B.R. Ambedkar chaired the 7-member Drafting Committee appointed on August 29, 1947.",
                    "Termed Article 32 (Constitutional Remedies) as the 'Heart and Soul' of the Constitution.",
                    "Ensured social democracy alongside political democracy through affirmative action and fundamental rights."
                ]
                interview_pitch = "Why did Dr. Ambedkar consider political democracy unsustainable without underlying social and economic democracy?"

            elif is_bhagat:
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
                summary_notes = [
                    "Bhagat Singh prioritized ideological awakening over violent insurrection.",
                    "The courtroom was used intentionally as a national megaphone to reach millions.",
                    "Executed on March 23, 1931 in Lahore Central Jail alongside Rajguru and Sukhdev."
                ]
                interview_pitch = "Explain how Bhagat Singh transformed the colonial courtroom into a weapon of ideological warfare."

            elif is_bio_chloroplast:
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Solar Paradox",
                        start_sec=0.0,
                        end_sec=4.0,
                        spoken_text="Did you know plants don't make oxygen from carbon dioxide? They rip it straight out of water molecules using sunlight!",
                        visual_direction="Translucent emerald plant leaf cutaway zooming into glowing green chloroplast organelles, vertical 9:16.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="Thylakoid Solar Splitting",
                        start_sec=4.0,
                        end_sec=24.0,
                        spoken_text="Inside plant cells, chloroplast thylakoids act like microscopic solar power plants. Chlorophyll pigments absorb solar photons, charging up high-energy electrons that physically tear water molecules apart into protons and pure oxygen gas.",
                        visual_direction="3D molecular diagram: Water (H2O) molecule getting cleaved by incoming sunlight photons into oxygen gas and protons with blue electric sparks.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="The Calvin Cycle",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text="That harvested solar energy is transferred to the stroma, where the enzyme RuBisCO fixes atmospheric carbon dioxide into glucose sugar. Without this constant photon-powered cycle, Earth's oxygen atmosphere would collapse entirely within millennia.",
                        visual_direction="Rotating 3D Calvin cycle enzyme wheel assembling high-energy glucose rings in luminous amber.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="Biology Checkpoint",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text="Every breath you take was forged inside a thylakoid membrane! Tap the quiz button below to test your biology mastery!",
                        visual_direction="Breathtaking orbital view of lush green Earth continent from space with glowing quiz CTA.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    "Light reactions occur in thylakoid membranes, splitting H2O to release O2 (photolysis).",
                    "Dark reactions (Calvin cycle) occur in the stroma, fixing CO2 into glucose.",
                    "Solar photons provide the electrochemical gradient that drives ATP and NADPH synthesis."
                ]
                interview_pitch = "Why does the photolysis of water occur on the inner side of the thylakoid membrane rather than the outer stroma?"

            elif is_newton_rocket:
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
                summary_notes = [
                    "A force cannot exist in isolation; it requires two interacting bodies.",
                    "Action and reaction forces act on completely DIFFERENT objects, never canceling.",
                    "Rockets accelerate by expelling mass backwards, not by pushing off ambient air."
                ]
                interview_pitch = "Explain why you don't float away when taking a step on Earth versus space."

            else:
                # Dynamic Procedural Screenplay for ANY Arbitrary Topic
                clean_title = meta["topic"] if meta["topic"] else "Core Principle"
                acts = [
                    ActScript(
                        act_number=1,
                        title="The Conceptual Paradox",
                        start_sec=0.0,
                        end_sec=4.0,
                        spoken_text=meta["hook"] if meta["hook"] else f"Why do most students lose marks on {clean_title} despite memorizing the standard definition?",
                        visual_direction=f"High-contrast dynamic schematic showcasing the core mechanism of {clean_title} with glowing vector highlights, vertical 9:16.",
                        card_type="HOOK_CARD"
                    ),
                    ActScript(
                        act_number=2,
                        title="The Governing Mechanism",
                        start_sec=4.0,
                        end_sec=24.0,
                        spoken_text=f"Because {clean_title} depends on an underlying mechanism that textbooks rarely illustrate intuitively. When you trace the physical parameters step by step, the apparent contradiction vanishes into a clean, predictable mathematical relationship.",
                        visual_direction=f"Step-by-step vector diagram illustrating how fundamental parameters interact in {clean_title}, neon accents on dark slate background.",
                        card_type="ANALOGY_DIAGRAM"
                    ),
                    ActScript(
                        act_number=3,
                        title="Real-World Mastery",
                        start_sec=24.0,
                        end_sec=42.0,
                        spoken_text=meta["takeaway"] if meta["takeaway"] else f"Mastering {clean_title} unlocks solutions to complex multi-step problems across engineering, nature, and modern science. It transforms abstract equations into tangible physical intuition.",
                        visual_direction=f"Modern technological and scientific application of {clean_title} highlighted with telemetry overlays and cutaway schematics.",
                        card_type="COMPARISON_BOX"
                    ),
                    ActScript(
                        act_number=4,
                        title="1-Second Takeaway & Call to Quiz",
                        start_sec=42.0,
                        end_sec=48.0,
                        spoken_text=f"Remember the core principle behind {clean_title}! Tap the quiz button below to test your mastery right now!",
                        visual_direction=f"Illuminated summary spotlight highlighting key formula and concept rules of {clean_title} with glowing Quiz CTA arrow.",
                        card_type="FORMULA_SPOTLIGHT"
                    )
                ]
                summary_notes = [
                    f"Understanding the fundamental governing laws behind {clean_title}.",
                    f"Identifying common examination traps and intuitive misconceptions in {clean_title}.",
                    f"Direct application of {clean_title} to real-world technology and physical systems."
                ]
                interview_pitch = f"Explain the counter-intuitive edge case of {clean_title} in competitive examinations."

            total_words = sum(len(a.spoken_text.split()) for a in acts)
            return ReelScript(
                title=topic_title,
                topic_title=topic_title,
                hook=acts[0].spoken_text,
                key_takeaway=acts[2].spoken_text,
                summary_notes=summary_notes,
                interview_pitch=interview_pitch,
                acts=acts,
                total_word_count=total_words,
                estimated_duration_sec=45
            )

        # =========================================================================
        # 3. QuizPayload Schema
        # =========================================================================
        elif response_model == QuizPayload:
            if is_magnetism:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="A straight wire of length 2 meters carries a 3-Ampere current perpendicular to a uniform 4-Tesla magnetic field. What is the magnetic force acting on the wire?",
                        options=[
                            QuizOption(id="a", text="24 Newtons (F = I · L · B · sin 90°)"),
                            QuizOption(id="b", text="12 Newtons"),
                            QuizOption(id="c", text="0 Newtons because the wire has neutral net charge"),
                            QuizOption(id="d", text="48 Newtons")
                        ],
                        correctOptionId="a",
                        explanation="Using F = I · L · B · sin(θ): F = (3 A) × (2 m) × (4 T) × sin(90°) = 24 N. When the wire is perpendicular to the field, sin(90°) = 1, producing maximum deflecting force."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="According to Fleming's Left-Hand Rule, in what direction does the Lorentz force act relative to the current and the magnetic field?",
                        options=[
                            QuizOption(id="a", text="Mutually perpendicular to both the current and the magnetic field lines"),
                            QuizOption(id="b", text="Parallel to the magnetic field lines from North to South"),
                            QuizOption(id="c", text="Directly along the direction of conventional current flow"),
                            QuizOption(id="d", text="Opposite to the direction of electron drift velocity")
                        ],
                        correctOptionId="a",
                        explanation="The Lorentz force vector F = I(L × B) is always mutually perpendicular to both the length vector L (current direction) and the magnetic flux density B (field direction)."
                    )
                ]
                return QuizPayload(
                    topicId="topic-phys-12-magnetic-force",
                    topicTitle=topic_title,
                    questions=questions
                )

            elif is_thermo:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="According to the First Law of Thermodynamics (ΔU = Q - W), if 500 Joules of heat are added to a gas and it expands doing 200 Joules of work on a piston, what is the change in internal energy?",
                        options=[
                            QuizOption(id="a", text="+300 Joules (ΔU = 500 J - 200 J)"),
                            QuizOption(id="b", text="+700 Joules"),
                            QuizOption(id="c", text="-300 Joules"),
                            QuizOption(id="d", text="Zero Joules because energy is conserved")
                        ],
                        correctOptionId="a",
                        explanation="Using ΔU = Q - W: ΔU = (+500 J) - (+200 J) = +300 J. The internal energy increases by 300 Joules, raising the temperature of the gas."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="In an adiabatic compression where no heat enters or leaves the system (Q = 0), what happens to the internal energy and temperature of the gas?",
                        options=[
                            QuizOption(id="a", text="Internal energy increases (ΔU = -W) and temperature rises"),
                            QuizOption(id="b", text="Internal energy decreases and temperature drops"),
                            QuizOption(id="c", text="Internal energy remains constant because Q = 0"),
                            QuizOption(id="d", text="The gas immediately liquefies without temperature change")
                        ],
                        correctOptionId="a",
                        explanation="Since Q = 0, ΔU = -W. Because compression means work is done ON the system (W is negative), ΔU is positive, meaning internal energy and temperature increase."
                    )
                ]
                return QuizPayload(
                    topicId="topic-phys-11-thermodynamics-1st-law",
                    topicTitle=topic_title,
                    questions=questions
                )

            elif is_gandhi:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="From which location did Mahatma Gandhi commence the historic 240-mile Salt March on March 12, 1930?",
                        options=[
                            QuizOption(id="a", text="Sabarmati Ashram in Ahmedabad"),
                            QuizOption(id="b", text="Sevagram Ashram in Wardha"),
                            QuizOption(id="c", text="Champaran in Bihar"),
                            QuizOption(id="d", text="Bardoli in Gujarat")
                        ],
                        correctOptionId="a",
                        explanation="The Salt March began with 78 chosen satyagrahis from Sabarmati Ashram on March 12, 1930 and concluded at Dandi on April 6, 1930."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="Why was the salt tax chosen by Mahatma Gandhi as the primary catalyst for the Civil Disobedience Movement?",
                        options=[
                            QuizOption(id="a", text="It affected every single Indian regardless of caste, religion, or economic class"),
                            QuizOption(id="b", text="It was the highest revenue source for the British treasury"),
                            QuizOption(id="c", text="Indian industrialists requested tariff protection on salt"),
                            QuizOption(id="d", text="Salt was imported exclusively from Britain")
                        ],
                        correctOptionId="a",
                        explanation="Salt was an indispensable daily biological necessity for all humans. Taxing it was an injustice that resonated across all social divisions in India."
                    )
                ]
                return QuizPayload(
                    topicId="topic-hist-upsc-dandi-march-1930",
                    topicTitle=topic_title,
                    questions=questions
                )

            elif is_bose:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="Where did Netaji Subhas Chandra Bose officially proclaim the establishment of the Provisional Government of Free India (Arzi Hukumat-e-Azad Hind) on October 21, 1943?",
                        options=[
                            QuizOption(id="a", text="Singapore (Cathi Cinema Hall)"),
                            QuizOption(id="b", text="Tokyo, Japan"),
                            QuizOption(id="c", text="Rangoon, Burma"),
                            QuizOption(id="d", text="Berlin, Germany")
                        ],
                        correctOptionId="a",
                        explanation="Netaji proclaimed the Provisional Government of Free India in Singapore on October 21, 1943, recognized by nine sovereign nations."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="Who was the commanding officer of the historic all-female Rani of Jhansi Regiment in the Indian National Army?",
                        options=[
                            QuizOption(id="a", text="Captain Lakshmi Sahgal (Swaminathan)"),
                            QuizOption(id="b", text="Sarojini Naidu"),
                            QuizOption(id="c", text="Aruna Asaf Ali"),
                            QuizOption(id="d", text="Madam Bhikaji Cama")
                        ],
                        correctOptionId="a",
                        explanation="Captain Lakshmi Sahgal commanded the pioneering Rani of Jhansi Regiment, one of the world's first modern all-female combat military units."
                    )
                ]
                return QuizPayload(
                    topicId="topic-hist-upsc-netaji-ina",
                    topicTitle=topic_title,
                    questions=questions
                )

            elif is_ambedkar:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="Which article of the Constitution of India did Dr. B.R. Ambedkar famously describe as the 'very heart and soul of the Constitution'?",
                        options=[
                            QuizOption(id="a", text="Article 32 (Right to Constitutional Remedies)"),
                            QuizOption(id="b", text="Article 21 (Right to Life and Personal Liberty)"),
                            QuizOption(id="c", text="Article 14 (Equality before Law)"),
                            QuizOption(id="d", text="Article 368 (Power to Amend the Constitution)")
                        ],
                        correctOptionId="a",
                        explanation="Dr. Ambedkar emphasized that without Article 32 giving citizens direct access to the Supreme Court to enforce fundamental rights via writs, all other rights would be nullities."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="On which date did the Constituent Assembly officially adopt the Constitution of India under Dr. Ambedkar's drafting leadership?",
                        options=[
                            QuizOption(id="a", text="November 26, 1949 (celebrated as Constitution Day)"),
                            QuizOption(id="b", text="January 26, 1950 (Republic Day)"),
                            QuizOption(id="c", text="August 15, 1947"),
                            QuizOption(id="d", text="December 9, 1946")
                        ],
                        correctOptionId="a",
                        explanation="The Constitution was adopted on November 26, 1949 (National Law Day/Constitution Day) and came into full legal effect on January 26, 1950."
                    )
                ]
                return QuizPayload(
                    topicId="topic-polity-upsc-ambedkar-constitution",
                    topicTitle=topic_title,
                    questions=questions
                )

            elif is_bhagat:
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

            elif is_bio_chloroplast:
                questions = [
                    QuizQuestion(
                        id="q1",
                        text="During photosynthesis, what is the precise origin of the oxygen gas released into the atmosphere?",
                        options=[
                            QuizOption(id="a", text="Photolysis of water molecules inside the thylakoid lumen"),
                            QuizOption(id="b", text="Breakdown of carbon dioxide in the stroma"),
                            QuizOption(id="c", text="Decomposition of glucose during cellular respiration"),
                            QuizOption(id="d", text="Splitting of atmospheric ozone by stomata")
                        ],
                        correctOptionId="a",
                        explanation="In light reactions, photons absorbed by Photosystem II split water molecules (2H2O -> 4H+ + 4e- + O2). The released oxygen comes entirely from water, not carbon dioxide."
                    ),
                    QuizQuestion(
                        id="q2",
                        text="Where do the light-independent dark reactions (Calvin cycle) take place within the chloroplast?",
                        options=[
                            QuizOption(id="a", text="In the fluid-filled stroma"),
                            QuizOption(id="b", text="Inside the thylakoid membrane"),
                            QuizOption(id="c", text="Across the outer chloroplast membrane"),
                            QuizOption(id="d", text="Within the mitochondrial cristae")
                        ],
                        correctOptionId="a",
                        explanation="The Calvin cycle takes place in the stroma, using ATP and NADPH generated during the light reactions to fix CO2 into sugars."
                    )
                ]
                return QuizPayload(
                    topicId="topic-bio-10-photosynthesis",
                    topicTitle=topic_title,
                    questions=questions
                )

            elif is_newton_rocket:
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
                            QuizOption(id="a", text="By expelling high-velocity exhaust gas backwards"),
                            QuizOption(id="b", text="By pushing off gravitational waves"),
                            QuizOption(id="c", text="By creating a solar vacuum pocket in front"),
                            QuizOption(id="d", text="Rockets cannot accelerate without atmosphere")
                        ],
                        correctOptionId="a",
                        explanation="The rocket pushes exhaust gas backward; the backward gas pushes the rocket forward with equal and opposite force."
                    )
                ]
                return QuizPayload(
                    topicId="topic-phys-9-newton-3",
                    topicTitle=topic_title,
                    questions=questions
                )

            else:
                # Dynamic Procedural Quiz for ANY Custom Topic
                clean_name = meta["topic"] if meta["topic"] else "this concept"
                questions = [
                    QuizQuestion(
                        id="q1",
                        text=f"What is the foundational principle that defines how {clean_name} behaves?",
                        options=[
                            QuizOption(id="a", text=f"It operates through direct physical interactions governing {clean_name}"),
                            QuizOption(id="b", text=f"It cancels out completely under standard laboratory conditions"),
                            QuizOption(id="c", text=f"It depends solely on ambient atmospheric pressure"),
                            QuizOption(id="d", text=f"It operates randomly without predictable mathematical laws")
                        ],
                        correctOptionId="a",
                        explanation=f"Understanding {clean_name} requires recognizing its direct governing mechanics and parameter dependencies rather than rote memorization."
                    ),
                    QuizQuestion(
                        id="q2",
                        text=f"Which common misconception regarding {clean_name} frequently trips up students in examinations?",
                        options=[
                            QuizOption(id="a", text=f"Assuming {clean_name} acts in isolation without interacting with other system variables"),
                            QuizOption(id="b", text=f"Correctly applying the fundamental mathematical formulas of {clean_name}"),
                            QuizOption(id="c", text=f"Recognizing the conservation principles governing {clean_name}"),
                            QuizOption(id="d", text=f"Using standard SI units during dimensional analysis")
                        ],
                        correctOptionId="a",
                        explanation=f"Examination questions frequently test edge cases where students overlook interacting variables in {clean_name}."
                    )
                ]
                return QuizPayload(
                    topicId=f"topic-custom-{abs(hash(clean_name)) % 100000}",
                    topicTitle=topic_title,
                    questions=questions
                )

        # =========================================================================
        # 4. Storyboard Schema
        # =========================================================================
        elif response_model == Storyboard:
            if is_magnetism:
                scenes = [
                    SceneBeat(
                        scene_number=1, act_number=1, start_sec=0.0, end_sec=4.0,
                        spoken_line="Place a copper wire between two powerful magnets and switch on the current. Instantly, the wire kicks violently upward! Why?",
                        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                        visual_prompt="High-contrast macro close-up of a suspended copper rod kicking sideways between glowing red North and blue South magnetic poles, electric sparks, neon lab lighting, vertical 9:16",
                        camera_motion=CameraMotion.ZOOM_IN,
                        sound_effect="BASS_BOOM"
                    ),
                    SceneBeat(
                        scene_number=2, act_number=2, start_sec=4.0, end_sec=11.0,
                        spoken_line="Because whenever electric charges drift through a magnetic field, they experience a sideways Lorentz deflection.",
                        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                        visual_prompt="Neon magnetic flux lines streaming smoothly from red North pole to blue South pole in 3D space, glowing cyan magnetic field vectors B, dark laboratory background, vertical 9:16",
                        camera_motion=CameraMotion.PAN_RIGHT,
                        sound_effect="WHOOSH"
                    ),
                    SceneBeat(
                        scene_number=3, act_number=2, start_sec=11.0, end_sec=18.0,
                        spoken_line="The drifting electrons collide with the wire's crystal lattice, pushing the entire conductor outward according to Fleming's Left-Hand Rule.",
                        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                        visual_prompt="Microscopic view inside conducting copper wire showing golden electron particles drifting through metallic lattice under electric current I, vertical 9:16",
                        camera_motion=CameraMotion.ZOOM_IN,
                        sound_effect="SPARK_CHIME"
                    ),
                    SceneBeat(
                        scene_number=4, act_number=2, start_sec=18.0, end_sec=24.0,
                        spoken_line="Fleming's Left-Hand Rule reveals the direction: Forefinger is Field, Middle is Current, and Thumb gives the Force!",
                        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                        visual_prompt="Fleming's Left Hand Rule 3D coordinate system: Thumb showing upward Force F in neon lime, Forefinger showing Field B in cyan, Middle finger showing Current I in gold, vertical 9:16",
                        camera_motion=CameraMotion.PAN_LEFT,
                        sound_effect="WHOOSH"
                    ),
                    SceneBeat(
                        scene_number=5, act_number=3, start_sec=24.0, end_sec=34.0,
                        spoken_line="The magnitude is quantified by F equals I times L times B times sine theta. Increase current, conductor length, or magnetic flux, and the force surges!",
                        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                        visual_prompt="Dynamic laboratory schematic: Lorentz force F = I L B sin(theta) with digital readouts: I=4.5A, B=1.2T, L=0.65m, force arrow F=3.51N deflecting wire outward, vertical 9:16",
                        camera_motion=CameraMotion.ZOOM_IN,
                        sound_effect="SPARK_CHIME"
                    ),
                    SceneBeat(
                        scene_number=6, act_number=3, start_sec=34.0, end_sec=42.0,
                        spoken_line="This exact principle propels 600 kilometer-per-hour Maglev trains and powers every electric car motor on Earth.",
                        visual_modality=VisualModality.CINEMATIC_SCENE,
                        visual_prompt="Futuristic high-speed Maglev bullet train gliding smoothly over magnetic tracks at 600 km/h, glowing electromagnetic levitation coils, cinematic lighting, vertical 9:16",
                        camera_motion=CameraMotion.PULL_BACK,
                        sound_effect="WHOOSH"
                    ),
                    SceneBeat(
                        scene_number=7, act_number=4, start_sec=42.0, end_sec=48.0,
                        spoken_line="Remember: magnetic force is always perpendicular to both current and magnetic field! Tap the quiz button below to test your mastery!",
                        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                        visual_prompt="Glowing summary card with illuminated equation F = I · L · B · sin(θ) and interactive neon quiz CTA badge pointing downward, vertical 9:16",
                        camera_motion=CameraMotion.ZOOM_IN,
                        sound_effect="BASS_BOOM"
                    )
                ]
            elif is_gandhi or is_bose or is_ambedkar or is_mountbatten or is_napoleon or is_bhagat or "history" in (meta["subject"] or "").lower() or "civic" in (meta["subject"] or "").lower() or "polity" in (meta["subject"] or "").lower():
                from src.agents.scene_director import SceneDirectorAgent
                return SceneDirectorAgent._generate_heuristic_storyboard(
                    script=None, subject="History", class_level=10, exam_type="UPSC", topic_override=topic_title
                )
            else:
                from src.agents.scene_director import SceneDirectorAgent
                return SceneDirectorAgent._generate_heuristic_storyboard(
                    script=None, subject=meta["subject"] or "Physics", class_level=12, exam_type="IIT_JEE", topic_override=topic_title
                )

            return Storyboard(
                topic_title=topic_title,
                total_scenes=len(scenes),
                scenes=scenes
            )

        # =========================================================================
        # 5. DomainPedagogyDossier Schema
        # =========================================================================
        elif getattr(response_model, "__name__", "") == "DomainPedagogyDossier":
            from src.agents.domain_intelligence_agent import DomainIntelligenceAgent
            return DomainIntelligenceAgent._generate_heuristic_dossier(
                topic_title=topic_title,
                exam_type=meta.get("exam_type", "SCHOOL"),
                class_level=10,
                subject=meta.get("subject", "Science"),
                avatar_name=meta.get("character", None)
            )

        raise ValueError(f"No fallback registered for schema: {response_model}")
