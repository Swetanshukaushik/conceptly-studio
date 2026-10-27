import re
from typing import List, Optional, Any, Dict
from src.models.schemas import ReelScript, Storyboard, SceneBeat, VisualModality, CameraMotion, ReelGenerationTier, HudOverlay
from src.services.llm_factory import LLMFactory

class SceneDirectorAgent:
    """
    Scene Director & Storyboard Visualizer Agent:
    Transforms a 45-second screenplay into a structured Reel Plan:
    1. STYLE BIBLE: Anchors visual aesthetic, lighting, palette, and camera across all cuts.
    2. STRICT LAYER SEPARATION:
       - 'GEN' shots: Pure photorealistic 3D cinematic visual plate (ZERO text / words / glyphs).
       - 'OVERLAY' shots: Crisp deterministic code-rendered mathematical HUD card (formula, label, units).
    3. TIMED BEATS: 6 to 10 sequential cuts lasting 3 to 6 seconds each.
    """

    SYSTEM_PROMPT = """You are Conceptly's Master Cinematic Visual Director.
You transform educational scripts into a structured Reel Plan with distinct visual cuts and razor-sharp scientific precision.

CORE PRINCIPLES OF THE REEL PLAN:
1. UNIFIED STYLE BIBLE:
   Define a 'style_bible' that anchors the visual identity of the entire reel (e.g. "35mm anamorphic photography, warm tungsten laboratory lighting, dark slate and amber palette, shallow depth of field, 9:16 vertical cinematography, photorealistic, clean background plate, zero text watermarks, no letters").

2. STRICT LAYER SEPARATION (GEN VS OVERLAY):
   - AI diffusion models can NEVER be trusted with text, equations, numbers, or labels.
   - For every shot:
     * 'shot_type': "GEN" (cinematic visual background / physical phenomena) or "OVERLAY" (concept / formula focus).
     * 'visual_prompt': Describe ONLY the physical visual elements, lighting, camera angle, and atmosphere. STRICT NEGATIVE RULE: NEVER write letters, text, equations, or labels in 'visual_prompt'. Diffusion models must generate pure, clean visual imagery.
     * 'hud_overlay': When a scientific principle, equation, or law is introduced, specify it in 'hud_overlay' with:
       - 'formula': exact mathematical equation (e.g. "L = I · ω", "ΔU = Q - W", "F = I · L · B · sin(θ)", "E = h · ν")
       - 'label': uppercase concept title (e.g. "ANGULAR MOMENTUM CONSERVATION")
       - 'units': standard SI units (e.g. "kg · m² / s")
       - 'concept_tag': curriculum tag (e.g. "NCERT CLASS 11")

3. 3-SECOND CUT CADENCE:
   Break the screenplay into 6 to 10 sequential visual cuts (each lasting 3 to 6 seconds).

4. 3D CAMERA TRAJECTORIES:
   Assign purposeful camera motion: 'ZOOM_IN' (macro dive into atomic depth), 'PAN_RIGHT' (sweeping perspective), 'PAN_LEFT', 'PULL_BACK' (revealing wider scale).

5. SOUND DESIGN:
   Assign 'BASS_BOOM' for Scene 1 hook, 'WHOOSH' for camera pushes, 'SPARK_CHIME' for formula HUD reveals.

Output strictly structured JSON conforming to the Storyboard schema."""

    @classmethod
    def direct_storyboard(
        cls,
        script: ReelScript,
        subject: str = "Physics",
        class_level: Optional[int] = 9,
        exam_type: str = "SCHOOL",
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT,
        avatar: Optional[Any] = None
    ) -> Storyboard:
        """
        Generates 8-12 time-coded visual beats for the entire script.
        Integrates character avatar persona tokens for seamless cross-scene visual consistency.
        """
        avatar_section = ""
        avatar_style_bible = ""
        if avatar:
            av_name = getattr(avatar, 'name', '')
            av_prompt = getattr(avatar, 'prompt', '')
            avatar_section = (
                f"\n\nPRESENTER AVATAR PERSONA: {av_name} ({getattr(avatar, 'title', '')})\n"
                f"STYLE REFERENCE TOKENS: {av_prompt}\n"
                "CRITICAL CONTINUITY DIRECTIVE: Seamlessly feature or anchor this specific presenter in key visual cuts "
                "(especially Scene 1 Hook and Scene 4 Takeaway / Formula Spotlight), maintaining their signature clothing, props, and lighting for 100% visual consistency!"
            )
            avatar_style_bible = f"Featured presenter: {av_name}. Signature setting: {av_prompt}. "

        user_prompt = f"""Target Curriculum Topic: {script.topic_title}
Subject: {subject} | Class Level: {class_level or 'General'} | Exam: {exam_type}
Hook: {script.hook}
Key Takeaway: {script.key_takeaway}{avatar_section}

Screenplay Dialogue to Visualize (Break into 6-10 visual beats):
{chr(10).join(f'Act {act.act_number} ({act.title}): {act.spoken_text}' for act in script.acts)}

Create 6 to 10 sequential visual beats conforming to the Reel Plan.
Define a unified 'style_bible' for the entire reel.
For every beat, provide spoken_line, start/end timestamps, visual_modality, shot_type ("GEN" or "OVERLAY"), visual_prompt (ZERO text/words/letters!), hud_overlay (exact formula and label), camera_motion, and sound_effect."""

        # If LLM key is available, use LLMFactory
        try:
            storyboard = LLMFactory.generate_json(
                system_prompt=cls.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=Storyboard,
                tier=tier
            )
            if storyboard and len(storyboard.scenes) >= 4:
                # Guarantee style_bible propagation
                default_style = f"{avatar_style_bible}Cinematic 35mm vertical photography, volumetric lighting, dark atmospheric studio, 9:16 portrait, photorealistic, clean plate, zero text watermarks, no letters".strip()
                if not storyboard.style_bible:
                    storyboard.style_bible = default_style
                for sc in storyboard.scenes:
                    if not sc.style_bible:
                        sc.style_bible = storyboard.style_bible
                    if sc.hud_overlay and (sc.hud_overlay.formula or sc.hud_overlay.label):
                        sc.shot_type = "OVERLAY"
                return storyboard
        except Exception as e:
            print(f"⚠️ Scene director LLM note: {e}.")
            if not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                raise RuntimeError(f"Credits Finished: Storyboard generation failed for '{script.topic_title}': {e}. Please recharge credits or configure a valid API key.")

        # Fallback Deterministic Cinematic Storyboard Generator (Only when ALLOW_OFFLINE_DEV_FALLBACK is enabled)
        return cls._generate_heuristic_storyboard(script, subject, class_level, exam_type, avatar=avatar)

    @classmethod
    def _generate_heuristic_storyboard(
        cls,
        script: Optional[ReelScript] = None,
        subject: str = "Physics",
        class_level: Optional[int] = 9,
        exam_type: str = "SCHOOL",
        topic_override: Optional[str] = None,
        avatar: Optional[Any] = None
    ) -> Storyboard:
        title = topic_override or (script.topic_title if script else "Core Principle")
        topic_lower = (subject.lower() + " " + title.lower())

        is_magnetism = any(kw in topic_lower for kw in [
            "magnet", "lorentz", "f=ilb", "f=i*l*b", "ilb", "fleming", "solenoid",
            "magnetic force", "magnetic field", "tesla", "flux density", "biot", "ampere"
        ])
        is_history = any(kw in topic_lower for kw in ["history", "bhagat", "freedom", "war", "revolt", "polity", "upsc"])
        is_bio = any(kw in topic_lower for kw in ["bio", "photosynthesis", "cell", "dna", "heart", "neet", "thylakoid"])
        is_newton_rocket = any(kw in topic_lower for kw in [
            "newton's third law", "newton 3", "action and reaction", "action-reaction",
            "rocket propulsion", "rocket exhaust"
        ])

        scenes: List[SceneBeat] = []

        if is_magnetism:
            # Magnetic Force on Conductor (F = I L B) & Lorentz Force Storyboard
            act1_text = script.acts[0].spoken_text if (script and script.acts) else "Place a copper wire between two powerful magnets and switch on the current. Instantly, the wire kicks violently upward! Why?"
            act2_text = script.acts[1].spoken_text if (script and len(script.acts) > 1) else "Because whenever electric charges drift through a magnetic field, they experience a sideways Lorentz deflection."
            act3_text = script.acts[2].spoken_text if (script and len(script.acts) > 2) else "The magnitude is quantified by F equals I times L times B times sine theta, powering 600 km/h Maglev trains."
            act4_text = script.acts[3].spoken_text if (script and len(script.acts) > 3) else "Remember: magnetic force is always perpendicular to both current and magnetic field! Tap the quiz button below to test your mastery!"

            scenes = [
                SceneBeat(
                    scene_number=1, act_number=1, start_sec=0.0, end_sec=4.0,
                    spoken_line=act1_text,
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
                    spoken_line="The drifting electrons collide with the wire's crystal lattice, pushing the entire conductor outward.",
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
                    spoken_line="The magnitude is quantified by F equals I times L times B times sine theta. Increase current, length, or field, and the force surges!",
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
                    spoken_line=act4_text,
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt="Glowing summary card with illuminated equation F = I · L · B · sin(θ) and interactive neon quiz CTA badge pointing downward, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                )
            ]
        elif is_history:
            # Cinematic History Storyboard (Bhagat Singh / Freedom Struggle aesthetic)
            scenes = [
                SceneBeat(
                    scene_number=1, act_number=1, start_sec=0.0, end_sec=4.0,
                    spoken_line=script.acts[0].spoken_text if (script and script.acts) else "In 1929, two young revolutionaries entered the Central Legislative Assembly.",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Dramatic cinematic 35mm film still of 23-year-old Bhagat Singh in 1929 colonial Delhi, intense focused eyes, wearing felt hat and khaki coat, warm atmospheric dust and golden-hour backlighting, shallow depth of field, photorealistic, 8k vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                ),
                SceneBeat(
                    scene_number=2, act_number=2, start_sec=4.0, end_sec=10.0,
                    spoken_line="Their goal was not to shed blood, but to make the deaf British Empire hear the voice of freedom.",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Historic Central Legislative Assembly hall filled with British officials in colonial suits, wooden gallery, sudden flash of low-intensity smoke bomb with yellow leaflets scattering through air, dramatic chiaroscuro lighting, vertical 9:16",
                    camera_motion=CameraMotion.PAN_RIGHT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=3, act_number=2, start_sec=10.0, end_sec=18.0,
                    spoken_line="They deliberately stayed behind to be arrested, using the colonial courtroom as a national megaphone.",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Historic British colonial courtroom in Lahore, Bhagat Singh standing tall in the dock with handcuffs, fearless smile, wooden dock, rays of morning sunlight cutting through high barred windows, photorealistic, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=4, act_number=3, start_sec=18.0, end_sec=28.0,
                    spoken_line="He wrote revolutionary essays in prison, proving that ideas are bullets that no empire can ever execute.",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Atmospheric Lahore Central Jail cell, stone walls, oil lantern casting warm glow on handwritten revolutionary Urdu and English manuscripts on a wooden plank, reading Karl Marx, vertical 9:16",
                    camera_motion=CameraMotion.PAN_LEFT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=5, act_number=3, start_sec=28.0, end_sec=38.0,
                    spoken_line="On March 23, 1931, Bhagat Singh, Rajguru, and Sukhdev walked to the gallows singing songs of liberty.",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Silhouettes of three young revolutionaries walking with head held high down prison corridor towards twilight sky, dramatic orange and deep blue twilight, epic historic cinematography, vertical 9:16",
                    camera_motion=CameraMotion.PULL_BACK,
                    sound_effect="SPARK_CHIME"
                ),
                SceneBeat(
                    scene_number=6, act_number=4, start_sec=38.0, end_sec=45.0,
                    spoken_line="Their sacrifice ignited an unstoppable fire that drove the British out. Tap the quiz button below to test your history mastery!",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Glowing tricolor Indian national flag fluttering majestically over the Red Fort at sunrise, dramatic golden rays, cinematic lens flare, inspiring patriotic composition, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                )
            ]
        elif is_bio:
            # 3D Cellular & Molecular Biology Storyboard
            scenes = [
                SceneBeat(
                    scene_number=1, act_number=1, start_sec=0.0, end_sec=4.0,
                    spoken_line="Every breath you take depends on a molecular solar engine running inside green leaves.",
                    visual_modality=VisualModality.ANATOMICAL_3D,
                    visual_prompt="Macro 3D render zooming into green leaf vein structure, translucent plant cell walls glowing with emerald cytoplasm, golden sun rays penetrating leaf cuticle, hyper-detailed 8k vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                ),
                SceneBeat(
                    scene_number=2, act_number=2, start_sec=4.0, end_sec=14.0,
                    spoken_line="Inside chloroplasts, tiny stacks called thylakoids capture incoming sunlight photons.",
                    visual_modality=VisualModality.ANATOMICAL_3D,
                    visual_prompt="Translucent 3D chloroplast organelle cutaway showing glowing thylakoid disc stacks (grana), luminous green stroma fluid, incoming golden photon energy beams striking photosystem complexes, vertical 9:16",
                    camera_motion=CameraMotion.PAN_RIGHT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=3, act_number=2, start_sec=14.0, end_sec=25.0,
                    spoken_line="The solar energy physically tears water molecules apart, releasing oxygen gas into our atmosphere.",
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt="Molecular chemical reaction diagram: H2O molecule splitting into 2H+ and Oxygen gas with glowing blue electron sparks, glowing chemical bonds, dark navy background with neon cyan highlights, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="SPARK_CHIME"
                ),
                SceneBeat(
                    scene_number=4, act_number=3, start_sec=25.0, end_sec=36.0,
                    spoken_line="In the dark reactions, carbon dioxide is captured and converted into life-giving glucose sugar.",
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt="Calvin cycle biochemical pathway rotating 3D schematic, RuBisCO enzyme fixing CO2 into glucose rings, glowing amber energy ATP and NADPH molecules, vertical 9:16",
                    camera_motion=CameraMotion.PAN_LEFT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=5, act_number=4, start_sec=36.0, end_sec=45.0,
                    spoken_line="Without photosynthesis, Earth would be a lifeless rock. Tap the quiz below to master this concept!",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Breathtaking orbital view of lush green Earth continent from space, vibrant sunburst over ocean horizon, pure oxygen atmosphere glowing blue, 8k vertical 9:16",
                    camera_motion=CameraMotion.PULL_BACK,
                    sound_effect="BASS_BOOM"
                )
            ]
        elif is_newton_rocket:
            # Physics / Engineering Storyboard (Newton's Third Law / Rocket Principle)
            scenes = [
                SceneBeat(
                    scene_number=1, act_number=1, start_sec=0.0, end_sec=4.0,
                    spoken_line="If you push against a massive brick wall with one hundred Newtons, why does your hand hurt?",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Extreme macro close-up of a human hand pressing hard into an ancient dark brick wall, dust particles floating, dramatic spotlight illuminating tension in fingers, cinematic film lighting, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                ),
                SceneBeat(
                    scene_number=2, act_number=2, start_sec=4.0, end_sec=12.0,
                    spoken_line="Because forces never, ever exist alone in nature. Every push creates an identical push in reverse.",
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt="Neon cybernetic physics schematic: Hand and Brick wall with opposing glowing vector arrows, Action Vector (+100N in neon amber) pointing right, Reaction Vector (-100N in neon cobalt) pointing left, dark slate background, vertical 9:16",
                    camera_motion=CameraMotion.PAN_RIGHT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=3, act_number=2, start_sec=12.0, end_sec=22.0,
                    spoken_line="When your hand pushes the wall, the wall simultaneously pushes your hand right back with the exact same force.",
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt="Close up schematic diagram illustrating contact surface between hand and wall, atomic repulsion force vectors glowing between skin molecules and stone molecules, high-contrast scientific visual, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="SPARK_CHIME"
                ),
                SceneBeat(
                    scene_number=4, act_number=3, start_sec=22.0, end_sec=32.0,
                    spoken_line="This principle is precisely how rockets fly through the pure vacuum of space where there is no air.",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Epic photorealistic cinematic shot of a heavy rocket ascending through Earth's upper atmosphere, massive Mach diamonds in rocket exhaust, blinding orange fire plumes, pure black space background, 70mm IMAX cinematography, vertical 9:16",
                    camera_motion=CameraMotion.PULL_BACK,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=5, act_number=3, start_sec=32.0, end_sec=40.0,
                    spoken_line="The rocket engine expels burning exhaust downward, and the expelled gas pushes the rocket directly upward into orbit.",
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt="Rocket cutaway engineering schematic: combustion chamber expelling gas downward (Vector F_gas in glowing red), rocket accelerating upward (Vector F_thrust in glowing cyan), labeled 'Action-Reaction Pair', vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="SPARK_CHIME"
                ),
                SceneBeat(
                    scene_number=6, act_number=4, start_sec=40.0, end_sec=45.0,
                    spoken_line="Action and reaction always act on different objects, so they never cancel! Tap the quiz button below to test your mastery!",
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt="Astronaut floating gracefully in deep space beside a gleaming space station, Earth illuminated below, glowing quiz badge arrow pointing down, breathtaking cinematic vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                )
            ]
        else:
            # Dynamic Procedural Storyboard for Custom Topics (Derived from script acts)
            clean_title = title
            act1_text = script.acts[0].spoken_text if (script and script.acts) else f"Understanding the fundamental mechanism behind {clean_title}."
            act2_text = script.acts[1].spoken_text if (script and len(script.acts) > 1) else f"The core intuition and mathematical relationships governing {clean_title}."
            act3_text = script.acts[2].spoken_text if (script and len(script.acts) > 2) else f"Real-world scientific and engineering applications of {clean_title}."
            act4_text = script.acts[3].spoken_text if (script and len(script.acts) > 3) else f"Test your knowledge of {clean_title} in the checkpoint quiz below!"

            scenes = [
                SceneBeat(
                    scene_number=1, act_number=1, start_sec=0.0, end_sec=5.0,
                    spoken_line=act1_text,
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM if subject.lower() in ["physics", "chemistry", "mathematics"] else VisualModality.CINEMATIC_SCENE,
                    visual_prompt=f"Striking high-contrast vertical schematic introducing {clean_title}, glowing neon vectors, sleek dark mode background, cinematic 9:16 composition",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                ),
                SceneBeat(
                    scene_number=2, act_number=2, start_sec=5.0, end_sec=15.0,
                    spoken_line=act2_text,
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt=f"Detailed analytical diagram illustrating the primary governing variables and step-by-step mechanism of {clean_title}, neon cyan and amber labels, vertical 9:16",
                    camera_motion=CameraMotion.PAN_RIGHT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=3, act_number=2, start_sec=15.0, end_sec=25.0,
                    spoken_line="Notice how each parameter interacts directly to determine the final system behavior.",
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt=f"Microscopic and macro perspective correlation schematic for {clean_title}, glowing data indicators and mathematical overlays, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="SPARK_CHIME"
                ),
                SceneBeat(
                    scene_number=4, act_number=3, start_sec=25.0, end_sec=36.0,
                    spoken_line=act3_text,
                    visual_modality=VisualModality.CINEMATIC_SCENE,
                    visual_prompt=f"Modern high-tech industrial and scientific application relying on {clean_title}, dynamic lighting, cinematic depth of field, 8k vertical 9:16",
                    camera_motion=CameraMotion.PAN_LEFT,
                    sound_effect="WHOOSH"
                ),
                SceneBeat(
                    scene_number=5, act_number=4, start_sec=36.0, end_sec=45.0,
                    spoken_line=act4_text,
                    visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
                    visual_prompt=f"Illuminated summary spotlight highlighting key takeaways and formulas of {clean_title} with glowing interactive quiz CTA arrow, vertical 9:16",
                    camera_motion=CameraMotion.ZOOM_IN,
                    sound_effect="BASS_BOOM"
                )
            ]

        style_bible = "Cinematic 35mm vertical photography, volumetric lighting, dark atmospheric studio, 9:16 portrait, photorealistic, clean plate, zero text watermarks, no letters"
        for sc in scenes:
            if not sc.style_bible:
                sc.style_bible = style_bible

        return Storyboard(
            topic_title=title,
            total_scenes=len(scenes),
            style_bible=style_bible,
            scenes=scenes
        )
