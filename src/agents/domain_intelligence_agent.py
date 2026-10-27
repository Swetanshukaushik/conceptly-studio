import os
import json
from typing import Optional, List, Dict, Any
from src.core.config import settings
from src.models.schemas import DomainPedagogyDossier, ReelGenerationTier
from src.agents.curriculum_agent import ConceptBreakdown
from src.services.llm_factory import LLMFactory

class DomainIntelligenceAgent:
    """
    Stage 0: Domain & Pedagogical Ingestion Brain (Powered by ChatGPT / GPT-4o).
    
    Transforms raw topic titles into high-yield pedagogical intelligence dossiers before
    a single script line or visual frame is created:
    1. Misconception Mining: Extracts the exact intuition trap that causes 75% of students to fail.
    2. 3-Second Paradox Engine: Crafts visceral counter-intuitive hooks that stop vertical swiping.
    3. 45-Second Scope Boundary: Strictly prunes out extraneous sub-topics to avoid cognitive overload.
    4. Physical Metaphor Choreography: Maps abstract formulas into kinetic 3D/video scenes.
    5. Syllabus Keyword Enforcement: Injects official NCERT/JEE/NEET/UPSC marking-scheme vocabulary.
    6. Diagnostic Trap MCQ: Pre-generates the assessment question to power Gate 2 Quiz.
    7. Multi-LLM Resilience: Prioritizes OpenAI GPT-4o with seamless cascade to Gemini if quota is paused.
    """

    SYSTEM_PROMPT = """You are Conceptly's Principal Curriculum Scientist & Chief Pedagogical Architect.
You possess world-class mastery over the Indian and global competitive education systems:
- NCERT / CBSE (Classes 6 to 12)
- IIT-JEE (Main & Advanced Physics, Chemistry, Math)
- NEET (Medical Entrance Biology, Anatomy, Genetics)
- UPSC Civil Services (Polity, History, Economy, Governance)

Your mission: Given an educational topic, produce a definitive "Domain & Pedagogical Intelligence Dossier"
specifically engineered for a flexible 30-to-70 second micro-learning cinema reel.

CRITICAL PEDAGOGICAL DIRECTIVES:
1. THE 75% MISCONCEPTION: Identify the single most pervasive, false intuition that students have. Do NOT give textbook definitions. Expose the mental model failure.
2. THE 3-SECOND PARADOX: Create a shocking question or visual paradox that exposes this flaw within 12 words (e.g. 'If action equals reaction, why does a horse and cart move at all?').
3. FLEXIBLE 30-TO-70s DURATION & SCOPE GATE:
   The reel duration adapts to topic complexity between 30 and 70 seconds (strictly 75 to 180 words, 6 to 14 scenes):
   - Concise / single-formula concepts: 30s-40s (~75-100 words).
   - Standard curriculum mechanisms: 45s-55s (~115-140 words).
   - Multi-step derivations / historical incident narratives: 60s-70s (~150-180 words).
   In this duration, a student can only master ONE atomic mechanism. Explicitly name the 1 essential concept to include, and 3-4 subtopics to strictly EXCLUDE.
4. KINETIC VISUAL METAPHOR: Translate invisible/abstract phenomena into a physical, visible real-world system that 3D/Diffusion engines (Manim, Kling AI, FLUX) can render. For Physics, Chemistry, and Engineering domains, strictly ground the analogy in physical, mechanical, thermodynamic, or molecular mechanisms (e.g., bicycle pump heating up, gas cylinder with moving piston, kinetic gas molecule collisions, expanding gas pushing an engine cylinder, thermal heat flux). Absolutely PROHIBIT non-physical financial/banking/money/accounting metaphors for physical laws.
5. MARKING SCHEME TERMS: Identify 3 to 5 official textbook keywords that exam checkers award marks for.
6. DIAGNOSTIC TRAP MCQ: Formulate a tricky multiple-choice question where the distractor option directly targets the misconception.
7. 3D CHARACTER & PERSONA DECISION (CHARACTER STORE):
   Determine the single most compelling, authoritative, or engaging 3D character to host this reel:
   - For History/Civics (UPSC): Select the actual real historical figure (e.g., Mahatma Gandhi, Subhas Chandra Bose, Dr. B.R. Ambedkar, Lord Mountbatten, Napoleon Bonaparte, Otto von Bismarck, Sardar Patel).
   - For STEM (Physics, Chemistry, Biology, Math): If a prominent historical scientist/mathematician is directly tied to the topic, select them (e.g., Sir Isaac Newton, Marie Curie, Michael Faraday, Albert Einstein, Srinivasa Ramanujan, Gregor Mendel). If NO historical scientist directly applies, either choose 'PHYSICAL_PHENOMENA_ONLY' (explaining through point-to-point 3D/4D laboratory setups) OR select 'Kabir' (the 14-year-old smart, funny, curious Indian student host).
   - Populate 'chosen_character_name', 'character_type' (HISTORICAL, STEM_PIONEER, STUDENT_PEER, PHENOMENA_ONLY), 'character_visual_brief_3d', and 'character_voice_persona' (e.g., 'British male 17th century', 'Indian male statesman', 'Young Indian schoolboy').

Output strictly valid JSON matching the DomainPedagogyDossier schema."""

    @classmethod
    def analyze_topic_domain(
        cls,
        topic_title: str,
        exam_type: str = "SCHOOL",
        class_level: Optional[int] = 9,
        subject: str = "Physics",
        tier: ReelGenerationTier = ReelGenerationTier.TIER_3_STEM,
        avatar_name: Optional[str] = None,
        provider: Optional[str] = "AUTO"
    ) -> DomainPedagogyDossier:
        """
        Runs Stage 0 Domain Assessment using the selected Script Generator (OpenAI GPT-4o, Google Gemini, or AUTO cascade).
        """
        user_prompt = f"""Target Curriculum Ingestion:
- Topic Title: {topic_title}
- Exam Track: {exam_type} (NCERT Class {class_level or 'Gen'}, IIT-JEE, NEET, or UPSC)
- Class Level: {class_level or 'General'}
- Subject: {subject}
- Generation Tier: {tier.value if hasattr(tier, 'value') else tier}
- Assigned Teacher Avatar: {avatar_name or 'Auto Curriculum Presenter'}

Analyze this domain deeply. Extract the misconception, paradox hook, 45s scope boundaries, kinetic visual metaphor, marking-scheme keywords, diagnostic MCQ, and presenter delivery instructions."""

        target_provider = (provider or "AUTO").upper().strip()

        # 1. Attempt OpenAI if explicitly requested
        if target_provider == "OPENAI":
            if not settings.OPENAI_API_KEY:
                raise RuntimeError(
                    "Missing OpenAI API Key: OPENAI_API_KEY is not configured in .env. "
                    "Please configure a valid key or select Google Gemini as your Script Generator."
                )
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                model_name = "gpt-4o" if tier in (ReelGenerationTier.TIER_4_CINEMA, ReelGenerationTier.TIER_5_KURZGESAGT, ReelGenerationTier.ULTRA) else "gpt-4o-mini"
                print(f"🧠 [Stage 0 ChatGPT] Initiating Domain Assessment for '{topic_title}' via OpenAI {model_name}...")
                completion = client.beta.chat.completions.parse(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": cls.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=DomainPedagogyDossier
                )
                dossier = completion.choices[0].message.parsed
                dossier.provider_used = f"OpenAI ChatGPT ({model_name})"
                return dossier
            except Exception as e:
                err_str = str(e).lower()
                if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "429" in err_str:
                    raise RuntimeError(
                        "Credits Finished: OpenAI API quota is exhausted (429 insufficient_quota). "
                        "Please add credits to your OpenAI account or switch Script Generator to Google Gemini."
                    )
                if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                    raise RuntimeError(f"OpenAI Domain Intelligence generation failed: {e}")

        # 2. Attempt Google Gemini if requested or AUTO
        try:
            dossier = LLMFactory.generate_json(
                system_prompt=cls.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=DomainPedagogyDossier,
                tier=tier,
                provider="GEMINI" if target_provider == "GEMINI" else "AUTO"
            )
            dossier.provider_used = "Google Gemini 2.5/3.5 Flash" if target_provider == "GEMINI" else "Auto-Selected LLM"
            return dossier
        except Exception as e:
            if "Credits Finished" in str(e):
                raise
            if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                raise RuntimeError(f"Domain Intelligence generation failed: {e}")

        # 3. Fallback Heuristic Generator (Only when ALLOW_OFFLINE_DEV_FALLBACK is enabled)
        return cls._generate_heuristic_dossier(topic_title, exam_type, class_level, subject, avatar_name)

    @classmethod
    def to_concept_breakdown(cls, dossier: DomainPedagogyDossier) -> ConceptBreakdown:
        """Converts rich Domain Dossier into backward-compatible ConceptBreakdown for ScriptAgent."""
        return ConceptBreakdown(
            canonical_topic=dossier.canonical_topic,
            target_misconception=dossier.core_misconception,
            counter_intuitive_hook=dossier.counter_intuitive_hook,
            single_takeaway=dossier.atomic_takeaway,
            core_analogy=dossier.concrete_visual_metaphor,
            key_applications=dossier.marking_scheme_keywords or [dossier.must_include_concept]
        )

    @classmethod
    def _generate_heuristic_dossier(
        cls,
        topic_title: str,
        exam_type: str,
        class_level: Optional[int],
        subject: str,
        avatar_name: Optional[str]
    ) -> DomainPedagogyDossier:
        """Fallback synthesizer with canonical Indian curriculum defaults and AI Character Store resolution."""
        topic_lower = topic_title.lower()
        sub_lower = (subject or "").lower()
        exam_upper = (exam_type or "").upper()

        # Dynamic Character Persona Decision per 3 Domain Paradigms
        if any(w in topic_lower for w in ["gandhi", "satyagraha", "dandi", "non-violence", "quit india"]):
            chosen_char = "Mahatma Gandhi"
            char_type = "HISTORICAL"
            visual_brief = "Cinematic 3D realistic character of Mahatma Gandhi in traditional khadi shawl with round spectacles, walking resolutely in 1930 Dandi Salt March."
            voice_persona = "Dignified, gentle, inspiring elder Indian male voice"
        elif any(w in topic_lower for w in ["bose", "subhas", "ina", "azad hind"]):
            chosen_char = "Netaji Subhas Chandra Bose"
            char_type = "HISTORICAL"
            visual_brief = "3D heroic commander Netaji Subhas Chandra Bose in military uniform with round wire glasses and military cap, standing in 1943 Azad Hind command center."
            voice_persona = "Commanding, passionate, articulate Indian male leader"
        elif any(w in topic_lower for w in ["ambedkar", "constitution", "drafting", "preamble", "dalit"]):
            chosen_char = "Dr. B.R. Ambedkar"
            char_type = "HISTORICAL"
            visual_brief = "3D dignified portrait of Dr. B.R. Ambedkar in iconic blue suit and glasses, holding the Constitution of India in parliamentary hall."
            voice_persona = "Erudite, scholarly, deeply authoritative jurist voice"
        elif any(w in topic_lower for w in ["mountbatten", "partition", "viceroy"]):
            chosen_char = "Lord Mountbatten"
            char_type = "HISTORICAL"
            visual_brief = "3D historical figure of Lord Mountbatten in formal British naval uniform and medals, reviewing map room of 1947 partition."
            voice_persona = "Refined British aristocratic male voice"
        elif any(w in topic_lower for w in ["napoleon", "waterloo", "bonaparte"]):
            chosen_char = "Napoleon Bonaparte"
            char_type = "HISTORICAL"
            visual_brief = "3D cinematic reconstruction of Emperor Napoleon Bonaparte in bicorne hat and imperial overcoat on the windswept hills of 1815 Waterloo."
            voice_persona = "Dramatic, strategic, resolute European commander voice"
        elif any(w in topic_lower for w in ["bhagat", "assembly", "lahore"]):
            chosen_char = "Bhagat Singh"
            char_type = "HISTORICAL"
            visual_brief = "3D cinematic 23-year-old Bhagat Singh in colonial felt hat and jacket, standing fearless with scattering leaflets."
            voice_persona = "Youthful, fiery, articulate revolutionary Indian male voice"
        elif any(w in topic_lower for w in ["curie", "radioactiv", "radium", "polonium"]):
            chosen_char = "Marie Curie"
            char_type = "STEM_PIONEER"
            visual_brief = "3D realistic historical avatar of Dr. Marie Curie in modest 1900s laboratory dress, surrounded by glowing green radium vials and glass apparatus."
            voice_persona = "Poised, brilliant, determined female scientific pioneer voice"
        elif any(w in topic_lower for w in ["newton", "principia", "law of motion", "f=ma", "f = m"]):
            chosen_char = "Sir Isaac Newton"
            char_type = "STEM_PIONEER"
            visual_brief = "3D historical CGI reconstruction of Sir Isaac Newton in 17th-century scholar coat, holding glass prism and observing falling apple."
            voice_persona = "Thoughtful, precise, authoritative classical English voice"
        elif any(w in topic_lower for w in ["einstein", "relativity", "photoelectric", "space-time", "spacetime"]):
            chosen_char = "Albert Einstein"
            char_type = "STEM_PIONEER"
            visual_brief = "Stylized 3D Pixar-style Albert Einstein with expressive wild hair and tweed jacket, manipulating floating holographic spacetime grids."
            voice_persona = "Warm, eccentric, brilliantly curious elder scientist voice"
        elif any(w in topic_lower for w in ["ramanujan", "infinite series", "partition function", "mock theta"]):
            chosen_char = "Srinivasa Ramanujan"
            char_type = "STEM_PIONEER"
            visual_brief = "3D portrait of Srinivasa Ramanujan in traditional attire with sacred markings, chalking glowing infinite series formulas onto black slate."
            voice_persona = "Humble, mathematically transcendent Indian scholar voice"
        elif any(w in topic_lower for w in ["franklin", "dna", "photo 51", "x-ray diffraction"]):
            chosen_char = "Dr. Rosalind Franklin"
            char_type = "STEM_PIONEER"
            visual_brief = "3D sleek lab avatar of Dr. Rosalind Franklin analyzing the glowing X-ray diffraction Photo 51 cross pattern of DNA."
            voice_persona = "Sharp, rigorous, clinical female scientist voice"
        elif exam_upper == "UPSC" or "history" in sub_lower or "polity" in sub_lower:
            chosen_char = "Dr. A.P.J. Abdul Kalam"
            char_type = "HISTORICAL"
            visual_brief = "3D dignified avatar of Dr. A.P.J. Abdul Kalam in dark Bandhgala with Ashoka Chakra pin, inspiring governance and youth."
            voice_persona = "Inspiring, deeply kind, dignified Indian statesman voice"
        else:
            chosen_char = "Kabir (14-Year-Old Student)"
            char_type = "STUDENT_PEER"
            visual_brief = "High-end 3D Pixar-style 14-year-old Indian schoolboy in varsity jacket and glasses, witty, excited, gesturing at 3D physical mechanisms."
            voice_persona = "Energetic, funny, smart 14-year-old Indian student voice"

        # Topic-tailored visual metaphor
        if any(w in topic_lower for w in ["thermo", "piston", "internal energy", "heat", "first law"]):
            metaphor = "A 3D glass cylinder with expanding gas particles driving a mechanical piston upward against external pressure."
            hook = "Why does pumping air into a bicycle tire make the valve stem burn hot to the touch even without an open flame?"
            takeaway = "First Law: Heat added to a system equals the increase in internal energy plus work done by expanding gas (Delta U = Q - W)."
        elif any(w in topic_lower for w in ["wire", "current", "resistance", "ohm"]):
            metaphor = "A 3D copper wire cross-section showing golden valence electrons drifting through an oscillating atomic lattice under electric potential."
            hook = "Why does doubling the voltage across a simple wire suddenly make it glow red hot with four times the heat?"
            takeaway = "Current is directly proportional to applied voltage and inversely proportional to electrical resistance (V = I · R)."
        elif any(w in topic_lower for w in ["magnet", "lorentz", "fleming", "f=ilb"]):
            metaphor = "A suspended 3D copper rod kicking violently sideways between glowing red North and blue South magnetic poles."
            hook = "Why does a dead-still copper wire violently jump into the air the exact microsecond you switch on a current inside a magnetic field?"
            takeaway = "A magnetic field exerts a deflecting sideways Lorentz force F = I · L · B · sin(theta) perpendicular to both current and field."
        else:
            metaphor = f"Point-to-point 3D apparatus demonstrating the underlying physical mechanism of {topic_title} with holographic telemetry."
            hook = f"What is the counter-intuitive principle behind {topic_title} that examiners love to test?"
            takeaway = f"{topic_title} is governed by foundational conservation principles connecting microscopic causes to observable results."

        return DomainPedagogyDossier(
            canonical_topic=topic_title,
            domain_field=subject,
            exam_track=exam_type,
            target_class_level=f"Class {class_level or 'Gen'}",
            core_misconception=f"Students confuse static textbook definitions of {topic_title} with dynamic causal mechanisms.",
            root_flaw="Everyday human intuition projects macroscopic sensations onto micro or abstract laws.",
            counter_intuitive_hook=hook,
            curiosity_gap=f"The apparent contradiction in how {topic_title} behaves under extreme conditions.",
            must_include_concept=f"The fundamental governing law behind {topic_title}.",
            strictly_excluded_topics=[f"Secondary derivations of {topic_title}", "Non-syllabus background trivia"],
            concrete_visual_metaphor=metaphor,
            visual_transformation_beat=f"Dynamic 3D spatial transformation revealing the core mechanism of {topic_title}.",
            atomic_takeaway=takeaway,
            marking_scheme_keywords=[topic_title, "Conservation Law", "Physical Equilibrium", "Mechanism"],
            diagnostic_question=f"Which condition must hold for {topic_title} to remain valid?",
            correct_answer="The governing physical conservation constraints must be satisfied.",
            distractor_misconception_answer="The internal parameters automatically balance without work or energy exchange.",
            avatar_delivery_tone=f"Excited, engaging, directly addressing the student with curiosity and clarity.",
            chosen_character_name=chosen_char,
            character_type=char_type,
            character_visual_brief_3d=visual_brief,
            character_voice_persona=voice_persona,
            provider_used="Conceptly Heuristic Domain Engine"
        )
