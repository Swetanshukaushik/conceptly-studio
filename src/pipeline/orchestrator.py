import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from src.core.config import settings
from src.database.session import SessionLocal
from src.models.entities import ReelJob, JobStage, ReelArtifact
from src.models.schemas import JobStatus, ReelGenerationTier, ReelScript, QuizPayload
from src.services.curriculum_resolver import curriculum_resolver
from src.agents.curriculum_agent import CurriculumAgent
from src.agents.script_agent import ScriptAgent
from src.agents.factcheck_agent import FactCheckAgent
from src.agents.quiz_agent import QuizAgent
from src.services.llm_factory import LLMFactory
from src.agents.scene_director import SceneDirectorAgent
from src.engines.visuals.visual_factory import VisualAssetFactory
from src.engines.tts.tts_engine import TTSFactory, EdgeTTSEngine
from src.engines.render.subtitle_generator import SubtitleGenerator
from src.engines.render.card_renderer import CardRenderer
from src.engines.render.audio_mixer import AudioMixer
from src.engines.render.ffmpeg_compositor import FFmpegCompositor
from src.engines.render.motion_compositor import FFmpegMotionCompositor
from src.engines.storage.storage_service import get_storage_service
from src.services.tiers import get_tier, require_available

class PipelineOrchestrator:
    """
    Coordinates asynchronous execution of the multi-agent pipeline and manages
    the Human-in-the-Loop (HITL) pause-and-resume states at:
    - GATE 1: Creative Blueprint (Script & Visual Cues)
    - GATE 2: Quiz Assessment
    - GATE 3: Final Reel Decision
    """

    @staticmethod
    def _update_stage(
        db: Session,
        job_id: str,
        stage_name: str,
        status: str,
        progress: int = 100,
        log_message: Optional[str] = None
    ):
        stage = db.query(JobStage).filter(
            JobStage.job_id == job_id,
            JobStage.stage_name == stage_name
        ).first()
        if stage:
            stage.status = status
            stage.progress_percent = progress
            if log_message:
                stage.log_message = log_message
            stage.updated_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def _archive_reel(job: Any, mp4_path: str, script_dict: Dict[str, Any], tier_label: str = "") -> Optional[str]:
        """Copies the finished reel and a small metadata file into the reels library folder. Test renders, not published reels."""
        import re
        import shutil
        from src.services.config_loader import load_json
        folder = load_json("pipeline.json").get("archive_dir")
        if not folder:
            return None
        root = folder if os.path.isabs(folder) else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), folder)
        os.makedirs(root, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", (job.topic_title or "reel").lower()).strip("_")[:50]
        stem = f"{datetime.utcnow().strftime('%Y-%m-%d_%H%M')}_{slug}_{job.id[:8]}"
        shutil.copyfile(mp4_path, os.path.join(root, stem + ".mp4"))
        sb = script_dict.get("storyboard") or {}
        meta = {
            "topic": job.topic_title, "subject": job.subject, "class_level": job.class_level, "exam_type": job.exam_type, "tier": tier_label,
            "job_id": job.id, "created_utc": datetime.utcnow().isoformat(), "status": "test render, not published, not reviewed",
            "layout": sb.get("layout"), "look": sb.get("style_bible"), "qa_notes": sb.get("qa"),
            "narration": [a.get("spoken_text") for a in (script_dict.get("acts") or [])],
        }
        with open(os.path.join(root, stem + ".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
        return os.path.join(root, stem + ".mp4")

    @staticmethod
    def _script_fingerprint(script: ReelScript) -> str:
        """Identifies the narration a pre-generated quiz was written for; an edited script invalidates it."""
        import hashlib
        return hashlib.sha1("\n".join(a.spoken_text.strip() for a in script.acts).encode("utf-8")).hexdigest()

    @classmethod
    def run_stage1_blueprint(cls, job_id: str, avatar_id: Optional[str] = "AUTO", auto_advance: bool = False):
        """
        Step 1: Curriculum Discovery -> Concept Extraction -> Scriptwriting -> Fact Check -> Scene Directing.
        If auto_advance is True, immediately advances through Gate 1 to Stage 2 and Stage 3 (Direct End-to-End).
        Otherwise pauses at GATE_1_READY for creator review.
        """
        db = SessionLocal()
        try:
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if not job:
                return

            tier = ReelGenerationTier(job.generation_tier)

            # Enforce API Key requirement: avoid silent fallback
            from src.services.llm_factory import LLMFactory
            if not LLMFactory.is_llm_configured() and not settings.ALLOW_OFFLINE_DEV_FALLBACK:
                raise RuntimeError("Missing GEMINI_API_KEY: Please configure your Google Gemini API key in .env to dynamically generate blueprints and screenplays without hardcoding.")

            # Tier-aware Visual Requirement: strictly NO silent fallbacks
            if tier in (ReelGenerationTier.TIER_4_CINEMA, ReelGenerationTier.PREMIUM):
                if not (settings.FAL_KEY or settings.KLING_API_KEY or settings.RUNWAY_API_KEY or settings.LUMA_API_KEY):
                    raise RuntimeError(
                        f"Credits Finished: Tier '{tier.value}' requires an external video model with active credits. "
                        "Please configure FAL_KEY (recommended for Fal.ai Kling / LTX) or RUNWAY_API_KEY in your .env file."
                    )

            # 1. Curriculum Discovery
            cls._update_stage(db, job_id, "CURRICULUM_DISCOVERY", "IN_PROGRESS", 20, "Resolving topic in curriculum hierarchy...")
            resolved = curriculum_resolver.resolve_topic(
                topic_title=job.topic_title,
                exam_type=job.exam_type,
                class_level=job.class_level,
                subject=job.subject
            )
            job.topic_id = resolved["topic_id"]
            db.commit()
            cls._update_stage(db, job_id, "CURRICULUM_DISCOVERY", "COMPLETED", 100, f"Resolved topicId: {job.topic_id}")

            # Resolve Character Avatar early so Domain Ingestion is attuned to the presenter persona
            from src.services.avatar_catalog import AvatarCatalogService
            avatar = AvatarCatalogService.resolve_avatar(
                exam_type=job.exam_type,
                subject=job.subject,
                tier=tier.value,
                avatar_id=avatar_id,
                topic_title=job.topic_title
            )

            # 2. Stage 0: Deep Domain & Pedagogical Assessment (Powered by selected Script Generator)
            script_gen = getattr(job, "script_generator", "AUTO") or "AUTO"
            cls._update_stage(db, job_id, "CONCEPT_EXTRACTION", "IN_PROGRESS", 40, f"Running Domain Assessment via {script_gen} engine...")
            from src.agents.domain_intelligence_agent import DomainIntelligenceAgent
            from src.services.config_loader import load_json as _pipeline_cfg
            # One request writes dossier, script and quiz together (falls back to the per-agent chain offline)
            use_writer = bool(_pipeline_cfg("pipeline.json").get("consolidated_writer")) and LLMFactory.is_llm_configured()
            pending_quiz = None
            if use_writer:
                from src.agents.writer_agent import WriterAgent
                dossier, script, pending_quiz = WriterAgent.write(
                    topic_title=job.topic_title, exam_type=job.exam_type, class_level=job.class_level, subject=job.subject,
                    tier=tier, avatar_name=f"{avatar.name} ({avatar.title})", provider=script_gen, topic_id=job.topic_id
                )
            else:
                dossier = DomainIntelligenceAgent.analyze_topic_domain(
                    topic_title=job.topic_title,
                    exam_type=job.exam_type,
                    class_level=job.class_level,
                    subject=job.subject,
                    tier=tier,
                    avatar_name=f"{avatar.name} ({avatar.title})",
                    provider=script_gen
                )
            concept = DomainIntelligenceAgent.to_concept_breakdown(dossier)
            cls._update_stage(db, job_id, "CONCEPT_EXTRACTION", "COMPLETED", 100, f"Hook: {dossier.counter_intuitive_hook} [{dossier.provider_used}]")

            # Dynamic Character Store Resolution: Update avatar if AI chose a specific persona
            if dossier.chosen_character_name and avatar_id in ("AUTO", "DEFAULT", None, ""):
                avatar = AvatarCatalogService.resolve_avatar(
                    exam_type=job.exam_type,
                    subject=job.subject,
                    tier=tier.value,
                    avatar_id="AUTO",
                    topic_title=job.topic_title,
                    ai_chosen_character_name=dossier.chosen_character_name,
                    ai_visual_brief=dossier.character_visual_brief_3d,
                    ai_voice_persona=dossier.character_voice_persona
                )

            # 3. Scriptwriting (Isaac Newton-inspired Natural Philosopher Spoken Narration)
            cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 60, f"Drafting spoken narration ({script_gen} engine)...")
            if not use_writer:
                script = ScriptAgent.generate_script(
                    concept=concept,
                    tier=tier,
                    target_duration_sec=60,
                    script_generator=script_gen
                )

            # 4. Fact Check & Guardrail
            is_valid, report, script = FactCheckAgent.verify_and_clean_script(script)

            # 5. Scene Directing
            tier_cfg = require_available(job.generation_tier)
            use_3d = tier_cfg["renderer"] == "studio3d"
            job_output_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "jobs", job_id)
            frames_dir = os.path.join(job_output_dir, "storyboard_frames")
            assets_dir = os.path.join(job_output_dir, "assets")
            os.makedirs(frames_dir, exist_ok=True)

            if use_3d:
                cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 80, "Designing 3D scenes for each narration beat...")
                from src.agents.scene3d_director import Scene3DDirector
                from src.engines.render.tier_free.studio3d_engine import Studio3DEngine
                from src.services.concept_router import route as route_topic
                route = route_topic(job.subject, job.topic_title, tier=tier, provider=script_gen)
                cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 80, f"Routed to the {route['label']} pack ({route['method']}). Designing 3D scenes...")
                storyboard = Scene3DDirector.direct_storyboard(
                    route=route, script=script, subject=job.subject, class_level=job.class_level, exam_type=job.exam_type,
                    assets_dir=assets_dir, tier=tier, provider=script_gen
                )
                # Gate 1 previews come from the same 3D scenes the final video plays, one frame per scene.
                # Vision QA scores each frame and re-designs low-scoring beats once before the creator sees them.
                from src.services.config_loader import load_json as _cfg
                qa_notes = list(storyboard.qa or [])
                if _cfg("qa.json").get("enabled", True):
                    cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 90, "Vision QA: reviewing each 3D scene...")
                    qa_notes += Scene3DDirector.vision_review(storyboard, assets_dir, frames_dir, tier=tier, provider=script_gen)
                    for scene in storyboard.scenes:
                        scene.image_url = f"/media/jobs/{job_id}/storyboard_frames/scene_{scene.scene_number:02d}.png"
                else:
                    preview_spec = Studio3DEngine.build_spec(storyboard, look=storyboard.style_bible)
                    mids = [sc.start_sec + 0.55 * (sc.end_sec - sc.start_sec) for sc in storyboard.scenes]
                    stills = Studio3DEngine.render_stills(preview_spec, mids, frames_dir, assets_dir=assets_dir)
                    for scene, still in zip(storyboard.scenes, stills):
                        target = os.path.join(frames_dir, f"scene_{scene.scene_number:02d}.png")
                        os.replace(still, target)
                        scene.image_path = target
                        scene.image_url = f"/media/jobs/{job_id}/storyboard_frames/scene_{scene.scene_number:02d}.png"
                storyboard.qa = qa_notes or None
            else:
                cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 80, f"Directing scenes with {avatar.name} ({avatar.title})...")
                storyboard = SceneDirectorAgent.direct_storyboard(
                    script=script,
                    subject=job.subject,
                    class_level=job.class_level,
                    exam_type=job.exam_type,
                    tier=tier,
                    avatar=avatar
                )
                VisualAssetFactory.reset_job_session()
                for scene in storyboard.scenes:
                    img_path = os.path.join(frames_dir, f"scene_{scene.scene_number:02d}.png")
                    VisualAssetFactory.render_scene_image(
                        scene=scene,
                        output_image_path=img_path,
                        tier=tier,
                        avatar=avatar
                    )
                    scene.image_path = img_path
                    scene.image_url = f"/media/jobs/{job_id}/storyboard_frames/scene_{scene.scene_number:02d}.png"

            script.storyboard = storyboard
            cls._update_stage(db, job_id, "SCRIPTWRITING", "COMPLETED", 100, f"Screenplay & {len(storyboard.scenes)} visual scenes generated.")

            # Save script, storyboard & assigned avatar persona to job
            script_dict = script.dict()
            script_dict["avatar"] = avatar.dict()
            script_dict["domain_dossier"] = dossier.dict()
            script_dict["script_generator"] = script_gen
            script_dict["tts_vocal_direction"] = script.tts_vocal_direction
            if pending_quiz is not None:
                script_dict["pending_quiz"] = pending_quiz.dict()
                script_dict["pending_quiz_for"] = cls._script_fingerprint(script)
            job.script_data = json.dumps(script_dict)

            if auto_advance:
                job.status = JobStatus.GATE_1_APPROVED.value
                cls._update_stage(db, job_id, "GATE_1_REVIEW", "COMPLETED", 100, "Auto-advanced: Screenplay and visual beats confirmed.")
                db.commit()
                db.close()
                cls.run_stage2_quiz(job_id=job_id, auto_advance=True)
                return
            else:
                job.status = JobStatus.GATE_1_READY.value
                cls._update_stage(db, job_id, "GATE_1_REVIEW", "IN_PROGRESS", 50, "Awaiting creator approval of screenplay and visual storyboard.")
                db.commit()

        except Exception as e:
            import traceback
            traceback.print_exc()
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
            print(f"❌ Stage 1 Pipeline Error on Job {job_id}: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

    @classmethod
    def run_stage2_quiz(cls, job_id: str, auto_advance: bool = False):
        """
        Step 2: Triggered after Gate 1 approval.
        Produces Quiz MCQs based on approved script.
        If auto_advance is True, immediately advances to Stage 3 Video Synthesis.
        Otherwise pauses at GATE_2_READY.
        """
        db = SessionLocal()
        try:
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if not job or not job.script_data:
                return

            tier = ReelGenerationTier(job.generation_tier)
            script_dict = json.loads(job.script_data)
            script = ReelScript.parse_obj(script_dict)

            cls._update_stage(db, job_id, "GATE_1_REVIEW", "COMPLETED", 100, "Script & Storyboard approved by creator.")
            cls._update_stage(db, job_id, "QUIZ_GENERATION", "IN_PROGRESS", 50, "Generating checkpoint concept-testing MCQs...")

            pending = script_dict.get("pending_quiz")
            if pending and script_dict.get("pending_quiz_for") == cls._script_fingerprint(script):
                quiz = QuizPayload.parse_obj(pending)  # written with the script in the one-call writer; script unchanged since
            else:
                quiz = QuizAgent.generate_quiz(
                    script=script,
                    topic_id=job.topic_id,
                    tier=tier,
                    domain_dossier=script_dict.get("domain_dossier")
                )

            job.quiz_data = json.dumps(quiz.dict())
            cls._update_stage(db, job_id, "QUIZ_GENERATION", "COMPLETED", 100, f"Generated {len(quiz.questions)} checkpoint questions.")

            if auto_advance:
                job.status = JobStatus.GATE_2_APPROVED.value
                cls._update_stage(db, job_id, "GATE_2_REVIEW", "COMPLETED", 100, "Auto-advanced: Checkpoint assessment confirmed.")
                db.commit()
                db.close()
                cls.run_stage3_video_synthesis(job_id=job_id)
                return
            else:
                job.status = JobStatus.GATE_2_READY.value
                cls._update_stage(db, job_id, "GATE_2_REVIEW", "IN_PROGRESS", 50, "Awaiting creator approval of quiz questions.")
                db.commit()

        except Exception as e:
            import traceback
            traceback.print_exc()
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
            print(f"❌ Stage 2 Pipeline Error on Job {job_id}: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

    @classmethod
    def run_pipeline_end_to_end(cls, job_id: str, avatar_id: Optional[str] = "AUTO"):
        """
        Direct End-to-End Autonomous Reel Factory:
        Executes Stage 1 (Creative Blueprint & Visual Scenes) -> Stage 2 (Assessment Quizzes)
        -> Stage 3 (Neural Speech, Karaoke Subtitles, Audio Mixing, and Video Clip Compositing)
        without intermediate human pause gates, delivering the final ready-to-view MP4.
        """
        cls.run_stage1_blueprint(job_id=job_id, avatar_id=avatar_id, auto_advance=True)

    @classmethod
    def _align_storyboard_to_word_timestamps(cls, storyboard: Any, word_timestamps: list):
        """Aligns each scene's start_sec and end_sec to real speech audio word timestamps."""
        if not word_timestamps or not storyboard or not storyboard.scenes:
            return
        
        import re
        total_audio_end = word_timestamps[-1].end_sec
        w_idx = 0
        num_words = len(word_timestamps)
        
        for i, scene in enumerate(storyboard.scenes):
            clean_line = scene.spoken_line.strip().strip('.')
            if clean_line.startswith('...'):
                clean_line = clean_line[3:].strip()
            s_words = [re.sub(r'[^a-zA-Z0-9]', '', w.lower()) for w in clean_line.split() if re.sub(r'[^a-zA-Z0-9]', '', w)]
            
            start_w = w_idx
            matched = 0
            while w_idx < num_words and matched < len(s_words):
                w_clean = re.sub(r'[^a-zA-Z0-9]', '', word_timestamps[w_idx].word.lower())
                if w_clean == s_words[matched]:
                    matched += 1
                w_idx += 1
            end_w = max(start_w, w_idx - 1)
            
            scene.start_sec = word_timestamps[start_w].start_sec if start_w < num_words else 0.0
            scene.end_sec = word_timestamps[min(end_w, num_words - 1)].end_sec
            
        # Seamlessly chain scene boundaries
        for i in range(len(storyboard.scenes) - 1):
            curr = storyboard.scenes[i]
            nxt = storyboard.scenes[i + 1]
            curr.end_sec = nxt.start_sec
            
        # Last scene finishes with a subtle buffer matching total audio duration
        last_scene = storyboard.scenes[-1]
        last_scene.end_sec = max(last_scene.start_sec + 2.5, total_audio_end + 0.6)

    @classmethod
    def run_stage3_video_synthesis(cls, job_id: str):
        """
        Step 3: Triggered after Gate 2 approval.
        Executes Voice Synthesis + Word Chronometry + Kinetic Subtitles + Movie Compositing.
        Pauses at GATE_3_READY with rendered MP4 inside the mobile simulator player.
        """
        db = SessionLocal()
        try:
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if not job or not job.script_data:
                return

            job.status = JobStatus.PROCESSING.value
            db.commit()

            tier = ReelGenerationTier(job.generation_tier)
            script_dict = json.loads(job.script_data)
            script = ReelScript.parse_obj(script_dict)

            job_output_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "jobs", job_id)
            os.makedirs(job_output_dir, exist_ok=True)

            # 1. Voice Synthesis & Word Chronometry directly from scene lines for 1-to-1 sync
            cls._update_stage(db, job_id, "VOICE_SYNTHESIS", "IN_PROGRESS", 20, f"Synthesizing neural speech ({tier.value} tier)...")
            tts_engine = TTSFactory.get_engine(tier)
            
            # Crucial: Synthesize from richly punctuated acts to preserve natural breathing, suspense pauses, and curious questions
            if script.acts:
                full_speech_text = "  ".join(act.spoken_text.strip() for act in script.acts)
            elif script.storyboard and script.storyboard.scenes:
                full_speech_text = "  ".join(s.spoken_line.strip() for s in script.storyboard.scenes)
            else:
                full_speech_text = job.topic_title

            raw_audio_path = os.path.join(job_output_dir, "speech_raw.wav")
            avatar_info = script_dict.get("avatar", {})
            avatar = avatar_info
            avatar_voice = avatar_info.get("voice_id") or settings.DEFAULT_EDGE_TTS_VOICE
            avatar_rate = avatar_info.get("voice_rate") or "+0%"
            avatar_pitch = avatar_info.get("voice_pitch") or "+0Hz"
            # A narrator character with its own voice (config/characters) overrides the generic presenter voice
            from src.engines.render.tier_free.studio3d_engine import Studio3DEngine
            nar_voice = ((Studio3DEngine.narrator_spec(((script_dict.get("storyboard") or {}).get("route"))) or {}).get("photo") or {}).get("voice")
            if nar_voice:
                avatar_voice, avatar_rate, avatar_pitch = nar_voice["id"], nar_voice.get("rate", avatar_rate), nar_voice.get("pitch", avatar_pitch)
            
            # Pass persona prosody (rate, pitch) if supported by TTS engine
            if isinstance(tts_engine, EdgeTTSEngine):
                word_timestamps = tts_engine.synthesize(
                    full_speech_text, raw_audio_path, voice=avatar_voice, rate=avatar_rate, pitch=avatar_pitch
                )
            else:
                word_timestamps = tts_engine.synthesize(full_speech_text, raw_audio_path, voice=avatar_voice)
            cls._update_stage(db, job_id, "VOICE_SYNTHESIS", "COMPLETED", 100, f"Extracted {len(word_timestamps)} word boundary timestamps.")

            # Align scene cuts to exact spoken audio chronometry
            if script.storyboard and script.storyboard.scenes:
                cls._align_storyboard_to_word_timestamps(script.storyboard, word_timestamps)
                script_dict["storyboard"] = script.storyboard.dict()
                job.script_data = json.dumps(script_dict)
                db.commit()

            # 2. Kinetic ASS Subtitle Compilation
            cls._update_stage(db, job_id, "KINETIC_SUBTITLES", "IN_PROGRESS", 40, "Compiling bouncing karaoke ASS subtitles...")
            ass_path = os.path.join(job_output_dir, "kinetic_subtitles.ass")
            SubtitleGenerator.generate_ass(word_timestamps, ass_path)
            cls._update_stage(db, job_id, "KINETIC_SUBTITLES", "COMPLETED", 100, "Subtitles anchored at Y=1400px (Amber active word highlight).")

            # 3. Audio Ducking, BGM & Cinematic Sound FX Mixing
            cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "IN_PROGRESS", 60, "Mixing speech, ambient BGM, and cinematic sound FX...")
            mixed_audio_path = os.path.join(job_output_dir, "audio_mixed.wav")
            AudioMixer.mix_speech_and_bgm(raw_audio_path, mixed_audio_path, storyboard=script.storyboard)

            # 4. Cinematic Motion Compositing
            final_mp4_path = os.path.join(job_output_dir, f"reel_{job_id}.mp4")

            # Enforce External Video Tool Requirement: strictly NO fallbacks
            if tier in (ReelGenerationTier.PREMIUM, ReelGenerationTier.ULTRA):
                if not (settings.FAL_KEY or settings.KLING_API_KEY or settings.RUNWAY_API_KEY or settings.LUMA_API_KEY):
                    raise RuntimeError(
                        f"Missing External Video AI Tool: Tier '{tier.value}' requires an external video diffusion model. "
                        "Please set FAL_KEY (recommended for Fal.ai Kling / LTX), KLING_API_KEY, or RUNWAY_API_KEY in your .env file."
                    )

            tier_cfg = require_available(job.generation_tier)
            if tier_cfg["renderer"] == "studio3d":
                from src.engines.render.tier_free.studio3d_engine import Studio3DEngine
                cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "IN_PROGRESS", 80, f"Rendering {len(script.storyboard.scenes)} real-time 3D scenes ({tier_cfg['label']} tier)...")
                render_spec = Studio3DEngine.build_spec(script.storyboard, look=script.storyboard.style_bible, word_timestamps=word_timestamps)
                render_info = Studio3DEngine.render_reel(
                    render_spec, final_mp4_path, audio_path=mixed_audio_path,
                    assets_dir=os.path.join(job_output_dir, "assets")
                )
                if render_info.get("warnings"):
                    print("⚠️ studio3d warnings:", render_info["warnings"])
            elif script.storyboard and script.storyboard.scenes:
                cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "IN_PROGRESS", 80, f"Synthesizing {len(script.storyboard.scenes)} moving video clips ({tier.value} tier)...")
                FFmpegMotionCompositor.composite_storyboard(
                    storyboard=script.storyboard,
                    audio_path=mixed_audio_path,
                    output_mp4_path=final_mp4_path,
                    ass_subtitle_path=ass_path,
                    tier=tier,
                    avatar=avatar
                )
            else:
                # Fallback to procedural card frames
                cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "IN_PROGRESS", 80, "Encoding procedural card frames...")
                frames_dir = os.path.join(job_output_dir, "frames")
                frame_paths = CardRenderer.render_reel_frames(
                    script=script,
                    subject=job.subject,
                    class_level=job.class_level,
                    output_dir=frames_dir
                )
                FFmpegCompositor.composite_reel(
                    script=script,
                    frame_paths=frame_paths,
                    audio_path=mixed_audio_path,
                    ass_subtitle_path=ass_path,
                    output_mp4_path=final_mp4_path
                )

            cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "COMPLETED", 100, "Composited Full HD 1080x1920 MP4.")

            # 5. Automated Video Quality & Technical Standard Validation
            cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "IN_PROGRESS", 95, "Validating 1080x1920 30fps container integrity & audio sync...")
            from src.engines.render.validator import VideoQualityValidator, VideoQualityValidationError
            est_dur = float(getattr(script, "estimated_duration_sec", 15.0) or 15.0)
            expected_min_dur = 15.0 if est_dur >= 15.0 else max(2.0, est_dur * 0.50)
            qa_result = VideoQualityValidator.validate_master_reel(final_mp4_path, min_duration_sec=expected_min_dur, max_duration_sec=80.0)
            if not qa_result["is_valid"]:
                error_msg = f"Reel failed QA standards: {'; '.join(qa_result['errors'])}"
                raise VideoQualityValidationError(error_msg, qa_result)
            print(f"✅ [Quality Validator] Reel passed 100% technical validation: {qa_result['metrics']}")

            # Keep a copy of every finished test render in a stable folder (config/pipeline.json archive_dir)
            try:
                cls._archive_reel(job, final_mp4_path, script_dict, tier_label=job.generation_tier)
            except Exception as archive_err:
                print(f"⚠️ Reel archive skipped: {archive_err}")

            # 6. Register Artifacts & Upload to Storage
            storage = get_storage_service()
            rel_media_name = f"reels/{job_id}/reel_{job_id}.mp4"
            accessible_video_url = storage.upload_file(final_mp4_path, rel_media_name)

            job.local_video_path = final_mp4_path
            job.video_url = accessible_video_url
            job.status = JobStatus.GATE_3_READY.value
            
            # Record Artifacts
            db.add(ReelArtifact(job_id=job.id, artifact_type="VIDEO_MP4", file_path=final_mp4_path, cloud_url=accessible_video_url))
            db.add(ReelArtifact(job_id=job.id, artifact_type="SUBTITLE_ASS", file_path=ass_path, cloud_url=None))
            db.add(ReelArtifact(job_id=job.id, artifact_type="AUDIO_WAV", file_path=mixed_audio_path, cloud_url=None))

            cls._update_stage(db, job_id, "GATE_3_REVIEW", "IN_PROGRESS", 50, "Ready for creator review in mobile simulator.")
            db.commit()

        except Exception as e:
            import traceback
            traceback.print_exc()
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
            print(f"❌ Stage 3 Compositor Error on Job {job_id}: {e}")
        finally:
            db.close()
