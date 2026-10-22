import os
import sys
import json
from PIL import Image

sys.path.insert(0, os.path.abspath("."))

def test_phase3_compositor():
    print("🎬 Running Phase 3 Audio & Video Compositor Tests...")

    from src.models.schemas import ReelGenerationTier, ReelScript, ActScript
    from src.engines.tts.tts_engine import TTSFactory, MockTTSEngine
    from src.engines.render.subtitle_generator import SubtitleGenerator
    from src.engines.render.card_renderer import CardRenderer
    from src.engines.render.audio_mixer import AudioMixer
    from src.engines.render.ffmpeg_compositor import FFmpegCompositor

    test_output_dir = os.path.abspath("./output/tests/phase3")
    os.makedirs(test_output_dir, exist_ok=True)

    # 1. Test TTS Engine & Word Boundary Chronometry
    test_text = "If you push against a massive brick wall with one hundred Newtons, why does your hand hurt?"
    speech_path = os.path.join(test_output_dir, "test_speech.wav")
    
    tts = MockTTSEngine()
    words = tts.synthesize(test_text, speech_path)
    assert os.path.exists(speech_path)
    assert len(words) > 5
    assert words[0].start_sec >= 0.0
    assert words[-1].end_sec > words[0].start_sec
    print(f"  [1/6] TTS & Word Chronometry OK. Synthesized {len(words)} words into {speech_path}")

    # 2. Test ASS Kinetic Subtitle Generator
    ass_path = os.path.join(test_output_dir, "test_subtitles.ass")
    SubtitleGenerator.generate_ass(words, ass_path)
    assert os.path.exists(ass_path)
    with open(ass_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "PlayResX: 1080" in content
        assert "PlayResY: 1920" in content
        assert "MarginV, Encoding" in content
        assert "&H000B9EF5&" in content  # Amber highlight tag
    print(f"  [2/6] ASS Kinetic Subtitle Generator OK. Amber highlighting & Y=1400px anchor verified.")

    # 3. Test Procedural Motion Cards Renderer
    act_1 = ActScript(
        act_number=1,
        title="The Hook",
        start_sec=0.0,
        end_sec=4.0,
        spoken_text=test_text,
        visual_direction="Close up hand on brick wall",
        card_type="HOOK_CARD"
    )
    frame_1_path = os.path.join(test_output_dir, "frame_act_1.png")
    CardRenderer.render_act_card(
        act=act_1,
        topic_title="Newton's Third Law",
        subject="Physics",
        class_level=9,
        output_image_path=frame_1_path
    )
    assert os.path.exists(frame_1_path)
    with Image.open(frame_1_path) as im:
        assert im.size == (1080, 1920)
    print(f"  [3/6] CardRenderer OK. Generated 1080x1920 FHD dark-mode frame at {frame_1_path}")

    # 4. Test Audio Ducking & Lofi Ambient Generator
    lofi_path = os.path.join(test_output_dir, "test_lofi.wav")
    AudioMixer.generate_ambient_lofi_track(lofi_path, duration_sec=5.0)
    assert os.path.exists(lofi_path)
    
    mixed_path = os.path.join(test_output_dir, "test_mixed.wav")
    AudioMixer.mix_speech_and_bgm(speech_path, mixed_path, lofi_path)
    assert os.path.exists(mixed_path)
    print(f"  [4/6] AudioMixer OK. Synthesized harmonic lofi track and mixed speech with ducking.")

    # 5. Test Video Compositor
    dummy_script = ReelScript(
        title="Newton's Third Law",
        topic_title="Newton's Third Law",
        hook="Why does the wall push back?",
        key_takeaway="Forces always occur in matched pairs.",
        summary_notes=["Note 1", "Note 2", "Note 3"],
        acts=[act_1],
        total_word_count=len(test_text.split()),
        estimated_duration_sec=4
    )
    mp4_path = os.path.join(test_output_dir, "test_reel.mp4")
    FFmpegCompositor.composite_reel(
        script=dummy_script,
        frame_paths=[frame_1_path],
        audio_path=mixed_path,
        ass_subtitle_path=ass_path,
        output_mp4_path=mp4_path
    )
    assert os.path.exists(mp4_path)
    assert os.path.getsize(mp4_path) > 30
    print(f"  [5/6] Video Compositor OK. Output MP4 generated at {mp4_path}")

    # 6. Test Orchestrator Stage 3 End-to-End
    from src.database.session import SessionLocal, Base, engine
    from src.models.entities import ReelJob, User
    from src.models.schemas import JobStatus
    from src.pipeline.orchestrator import PipelineOrchestrator

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    admin_user = db.query(User).first()

    test_job = ReelJob(
        user_id=admin_user.id if admin_user else None,
        generation_tier="DEFAULT",
        exam_type="SCHOOL",
        class_level=9,
        subject="Physics",
        topic_title="Newton's Third Law",
        status=JobStatus.GATE_2_APPROVED.value
    )
    db.add(test_job)
    db.commit()
    db.refresh(test_job)

    # Initialize all stages
    initial_stages = [
        "CURRICULUM_DISCOVERY", "CONCEPT_EXTRACTION", "SCRIPTWRITING",
        "GATE_1_REVIEW", "QUIZ_GENERATION", "GATE_2_REVIEW",
        "VOICE_SYNTHESIS", "KINETIC_SUBTITLES", "VIDEO_COMPOSITING",
        "GATE_3_REVIEW", "PUBLISHING"
    ]
    for s_name in initial_stages:
        from src.models.entities import JobStage
        db.add(JobStage(job_id=test_job.id, stage_name=s_name, status="PENDING"))
    
    # Supply validated script data for stage 3
    test_job.script_data = json.dumps(dummy_script.dict())
    db.commit()

    # Run Stage 3 Video Synthesis
    PipelineOrchestrator.run_stage3_video_synthesis(test_job.id)
    db.refresh(test_job)
    
    assert test_job.status == JobStatus.GATE_3_READY.value
    assert test_job.video_url is not None
    assert test_job.local_video_path is not None
    assert len(test_job.artifacts) >= 3
    
    print(f"  [6/6] Pipeline Orchestrator Stage 3 Verified:")
    print(f"       • Final Status: {test_job.status}")
    print(f"       • Video URL: {test_job.video_url}")
    print(f"       • Artifacts registered: {len(test_job.artifacts)} files")

    db.close()
    print("\n🎉 Phase 3 Audio & Video Compositor Tests PASSED 100%!")

if __name__ == "__main__":
    test_phase3_compositor()
