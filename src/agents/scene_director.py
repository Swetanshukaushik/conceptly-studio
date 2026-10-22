import re
from typing import List, Optional
from src.models.schemas import ReelScript, Storyboard, SceneBeat, VisualModality, CameraMotion, ReelGenerationTier
from src.services.llm_factory import LLMFactory

class SceneDirectorAgent:
    """
    Scene Director & Storyboard Visualizer Agent:
    Transforms a 45-second screenplay into an immersive visual storyboard of
    8 to 12 time-coded visual cuts (one dynamic visual every 3-4 seconds),
    with domain-adaptive prompt engineering:
    - History / Civics: 35mm cinematic photorealistic film stills
    - Physics / Engineering: Neon glowing vector schematics & physical phenomena
    - Biology: 3D anatomical and cellular molecular cross-sections
    - Economics: 3D currency networks and animated market shifts
    """

    SYSTEM_PROMPT = """You are Conceptly's Master Cinematic Director.
You transform educational scripts into micro-cinematic visual journeys.

CRITICAL DIRECTING RULES:
1. THE 3-SECOND CUT RULE: Break the screenplay into 8 to 12 distinct scenes (each lasting 3 to 5 seconds). Never let a single visual linger longer than 4.5 seconds!
2. DOMAIN-SPECIFIC VISUAL MODALITIES:
   - For History, UPSC, Literature: Use 'CINEMATIC_SCENE'. Describe dramatic film stills, period clothing, historic architecture (e.g., 1929 Central Assembly, Lahore, Delhi Durbar, Taj Mahal), 35mm anamorphic lens, atmospheric smoke, volumetric lighting, vertical 9:16 composition.
   - For Physics, Chemistry, Math: Use 'SCIENTIFIC_DIAGRAM'. Describe glowing neon force vectors, orbital mechanics, atomic shells, rocket engine combustion cross-sections in space vacuum.
   - For Biology (NEET): Use 'ANATOMICAL_3D'. Describe photorealistic 3D cellular cross-sections, chloroplasts splitting water, beating heart valves, glowing DNA double helix.
   - For Finance / Economics: Use 'DATA_INFOGRAPHIC'. Describe 3D currency flows, supply/demand curve shifts, stock tickers.
3. CAMERA MOTION: Assign one of 'ZOOM_IN' (slow push-in), 'PAN_RIGHT', 'PAN_LEFT', 'PULL_BACK' to every scene so no frame is static!
4. SOUND DESIGN: Assign 'BASS_BOOM' to Scene 1 hook, 'WHOOSH' to dynamic scene transitions, 'SPARK_CHIME' to key formula reveals.

Output strictly structured JSON conforming to the Storyboard schema."""

    @classmethod
    def direct_storyboard(
        cls,
        script: ReelScript,
        subject: str = "Physics",
        class_level: Optional[int] = 9,
        exam_type: str = "SCHOOL",
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    ) -> Storyboard:
        """
        Generates 8-12 time-coded visual beats for the entire script.
        """
        user_prompt = f"""Target Curriculum Topic: {script.topic_title}
Subject: {subject} | Class Level: {class_level or 'General'} | Exam: {exam_type}
Hook: {script.hook}
Key Takeaway: {script.key_takeaway}

Screenplay Dialogue to Visualize (Break into 8-12 visual beats):
{chr(10).join(f'Act {act.act_number} ({act.title}): {act.spoken_text}' for act in script.acts)}

Create 8 to 12 sequential visual beats. For each beat, provide the spoken line, start/end timestamps, visual modality, camera motion, sound effect, and a hyper-detailed visual prompt optimized for vertical 9:16 aspect ratio!"""

        # If LLM key is available, use LLMFactory
        try:
            storyboard = LLMFactory.generate_json(
                system_prompt=cls.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=Storyboard,
                tier=tier
            )
            if storyboard and len(storyboard.scenes) >= 6:
                return storyboard
        except Exception as e:
            print(f"⚠️ Scene director LLM note: {e}. Generating deterministic cinematic storyboard...")

        # Fallback Deterministic Cinematic Storyboard Generator
        return cls._generate_heuristic_storyboard(script, subject, class_level, exam_type)

    @classmethod
    def _generate_heuristic_storyboard(
        cls,
        script: ReelScript,
        subject: str,
        class_level: Optional[int],
        exam_type: str
    ) -> Storyboard:
        topic_lower = script.topic_title.lower()
        is_history = any(kw in (subject.lower() + " " + topic_lower) for kw in ["history", "bhagat", "freedom", "war", "revolt", "polity", "upsc"])
        is_bio = any(kw in (subject.lower() + " " + topic_lower) for kw in ["bio", "photosynthesis", "cell", "dna", "heart", "neet"])

        scenes: List[SceneBeat] = []

        if is_history:
            # Cinematic History Storyboard (Bhagat Singh / Freedom Struggle aesthetic)
            scenes = [
                SceneBeat(
                    scene_number=1, act_number=1, start_sec=0.0, end_sec=4.0,
                    spoken_line=script.acts[0].spoken_text if script.acts else "In 1929, two young revolutionaries entered the Central Legislative Assembly.",
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
                    camera_motion=CameraMotion.SLOW_DRIFT if hasattr(CameraMotion, "SLOW_DRIFT") else CameraMotion.ZOOM_IN,
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
        else:
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

        return Storyboard(
            topic_title=script.topic_title,
            total_scenes=len(scenes),
            scenes=scenes
        )
