import os
import json
from datetime import datetime
from typing import Optional
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
from src.agents.scene_director import SceneDirectorAgent
from src.engines.visuals.visual_factory import VisualAssetFactory
from src.engines.tts.tts_engine import TTSFactory
from src.engines.render.subtitle_generator import SubtitleGenerator
from src.engines.render.card_renderer import CardRenderer
from src.engines.render.audio_mixer import AudioMixer
from src.engines.render.ffmpeg_compositor import FFmpegCompositor
from src.engines.render.motion_compositor import FFmpegMotionCompositor
from src.engines.storage.storage_service import get_storage_service

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

    @classmethod
    def run_stage1_blueprint(cls, job_id: str):
        """
        Step 1: Curriculum Discovery -> Concept Extraction -> Scriptwriting -> Fact Check -> Scene Directing.
        Pauses at GATE_1_READY with full Storyboard gallery for creator review.
        """
        db = SessionLocal()
        try:
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if not job:
                return

            tier = ReelGenerationTier(job.generation_tier)

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

            # 2. Concept Extraction
            cls._update_stage(db, job_id, "CONCEPT_EXTRACTION", "IN_PROGRESS", 40, "Extracting core misconception and takeaway...")
            concept = CurriculumAgent.extract_concept(
                topic_title=job.topic_title,
                exam_type=job.exam_type,
                class_level=job.class_level,
                subject=job.subject,
                tier=tier
            )
            cls._update_stage(db, job_id, "CONCEPT_EXTRACTION", "COMPLETED", 100, f"Hook: {concept.counter_intuitive_hook}")

            # 3. Scriptwriting
            cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 60, "Drafting 4-Act screenplay with strict vertical retention pacing...")
            script = ScriptAgent.generate_script(concept=concept, tier=tier)

            # 4. Fact Check & Guardrail
            is_valid, report, script = FactCheckAgent.verify_and_clean_script(script)

            # 5. Scene Directing & Storyboard Generation (8-12 visual beats)
            cls._update_stage(db, job_id, "SCRIPTWRITING", "IN_PROGRESS", 80, "Directing 8-12 cinematic visual beats...")
            storyboard = SceneDirectorAgent.direct_storyboard(
                script=script,
                subject=job.subject,
                class_level=job.class_level,
                exam_type=job.exam_type,
                tier=tier
            )

            job_output_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "jobs", job_id)
            frames_dir = os.path.join(job_output_dir, "storyboard_frames")
            os.makedirs(frames_dir, exist_ok=True)

            for scene in storyboard.scenes:
                img_path = os.path.join(frames_dir, f"scene_{scene.scene_number:02d}.png")
                VisualAssetFactory.render_scene_image(scene, img_path, tier=tier)
                scene.image_path = img_path
                scene.image_url = f"/media/jobs/{job_id}/storyboard_frames/scene_{scene.scene_number:02d}.png"

            script.storyboard = storyboard
            cls._update_stage(db, job_id, "SCRIPTWRITING", "COMPLETED", 100, f"Screenplay & {len(storyboard.scenes)} visual scenes generated.")

            # Save script & storyboard to job and transition to GATE_1_READY
            job.script_data = json.dumps(script.dict())
            job.status = JobStatus.GATE_1_READY.value
            cls._update_stage(db, job_id, "GATE_1_REVIEW", "IN_PROGRESS", 50, "Awaiting creator approval of screenplay and visual storyboard.")
            db.commit()

        except Exception as e:
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
            print(f"❌ Stage 1 Pipeline Error on Job {job_id}: {e}")
        finally:
            db.close()

    @classmethod
    def run_stage2_quiz(cls, job_id: str):
        """
        Step 2: Triggered after Gate 1 approval.
        Produces Quiz MCQs based on approved script and pauses at GATE_2_READY.
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

            quiz = QuizAgent.generate_quiz(
                script=script,
                topic_id=job.topic_id,
                tier=tier
            )

            job.quiz_data = json.dumps(quiz.dict())
            job.status = JobStatus.GATE_2_READY.value
            cls._update_stage(db, job_id, "QUIZ_GENERATION", "COMPLETED", 100, f"Generated {len(quiz.questions)} checkpoint questions.")
            cls._update_stage(db, job_id, "GATE_2_REVIEW", "IN_PROGRESS", 50, "Awaiting creator approval of quiz questions.")
            db.commit()

        except Exception as e:
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
            print(f"❌ Stage 2 Pipeline Error on Job {job_id}: {e}")
        finally:
            db.close()

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

            # 1. Voice Synthesis & Word Chronometry
            cls._update_stage(db, job_id, "VOICE_SYNTHESIS", "IN_PROGRESS", 20, f"Synthesizing neural speech ({tier.value} tier)...")
            tts_engine = TTSFactory.get_engine(tier)
            
            full_speech_text = " ".join(act.spoken_text for act in script.acts)
            raw_audio_path = os.path.join(job_output_dir, "speech_raw.wav")
            word_timestamps = tts_engine.synthesize(full_speech_text, raw_audio_path)
            cls._update_stage(db, job_id, "VOICE_SYNTHESIS", "COMPLETED", 100, f"Extracted {len(word_timestamps)} word boundary timestamps.")

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

            if script.storyboard and script.storyboard.scenes:
                cls._update_stage(db, job_id, "VIDEO_COMPOSITING", "IN_PROGRESS", 80, f"Synthesizing {len(script.storyboard.scenes)} moving video clips ({tier.value} tier)...")
                FFmpegMotionCompositor.composite_storyboard(
                    storyboard=script.storyboard,
                    audio_path=mixed_audio_path,
                    output_mp4_path=final_mp4_path,
                    tier=tier
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

            # 5. Register Artifacts & Upload to Storage
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
            job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = str(e)
                db.commit()
            print(f"❌ Stage 3 Compositor Error on Job {job_id}: {e}")
        finally:
            db.close()
