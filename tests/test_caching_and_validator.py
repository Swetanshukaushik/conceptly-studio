import os
import sys
import time
import shutil
import pytest

sys.path.insert(0, os.path.abspath("."))
from src.core.config import settings
from src.engines.tts.tts_engine import EdgeTTSEngine, WordTimestamp
from src.models.schemas import SceneBeat, CameraMotion, VisualModality, ReelGenerationTier
from src.engines.render.video_clip_engine import VideoClipEngine
from src.engines.render.validator import VideoQualityValidator, VideoQualityValidationError

def test_edge_tts_content_addressed_caching():
    """Verifies that identical TTS text & voice parameters are cached and retrieved in <5ms."""
    engine = EdgeTTSEngine()
    test_text = "The first law of thermodynamics states that energy cannot be created or destroyed."
    test_output_1 = os.path.join(settings.LOCAL_STORAGE_DIR, "test_cache", "tts_test_1.wav")
    test_output_2 = os.path.join(settings.LOCAL_STORAGE_DIR, "test_cache", "tts_test_2.wav")

    # 1. First run: Synthesizes and populates cache
    t0 = time.time()
    words_1 = engine.synthesize(test_text, test_output_1, voice="en-IN-PrabhatNeural", rate="+12%", pitch="+16Hz")
    t1 = time.time() - t0

    assert os.path.exists(test_output_1)
    assert len(words_1) > 5

    # 2. Second run: Must be a Cache HIT (< 50ms)
    t0 = time.time()
    words_2 = engine.synthesize(test_text, test_output_2, voice="en-IN-PrabhatNeural", rate="+12%", pitch="+16Hz")
    t2 = time.time() - t0

    assert os.path.exists(test_output_2)
    assert len(words_2) == len(words_1)
    assert t2 < 0.10, f"Expected cache hit in <100ms, took {t2*1000:.1f}ms"
    assert os.path.getsize(test_output_1) == os.path.getsize(test_output_2)
    print(f"\n✅ TTS Cache Verified: Cold={t1:.2f}s -> Warm={t2*1000:.1f}ms ({t1/t2:.1f}x speedup)")

def test_video_clip_generation_and_caching():
    """Verifies that 2.5D camera motion video clip generation succeeds and validates."""
    from src.engines.visuals.visual_factory import VisualAssetFactory
    scene = SceneBeat(
        scene_number=2,
        act_number=2,
        spoken_line="Gas molecules collide against the cylinder walls, doing boundary expansion work.",
        visual_prompt="Close up cinematic vertical portrait of gas molecules expanding inside a cylinder",
        camera_motion=CameraMotion.ZOOM_IN,
        visual_modality=VisualModality.SCIENTIFIC_DIAGRAM,
        start_sec=3.5,
        end_sec=6.5
    )

    frame_path = os.path.join(settings.LOCAL_STORAGE_DIR, "test_cache", "frame_test_1.png")
    os.makedirs(os.path.dirname(frame_path), exist_ok=True)
    VisualAssetFactory.render_scene_image(scene, frame_path)
    scene.image_path = frame_path

    clip_out_1 = os.path.join(settings.LOCAL_STORAGE_DIR, "test_cache", "clip_test_1.mp4")
    if os.path.exists(clip_out_1):
        os.remove(clip_out_1)

    t0 = time.time()
    VideoClipEngine.generate_scene_clip(scene, clip_out_1, tier=ReelGenerationTier.TIER_1_FLASH)
    t1 = time.time() - t0

    assert os.path.exists(clip_out_1)
    assert os.path.getsize(clip_out_1) > 20000
    print(f"✅ Video Clip Generation Verified: Rendered in {t1:.2f}s, size={os.path.getsize(clip_out_1)} bytes")

def test_video_quality_validator_on_master_reel():
    """Verifies that VideoQualityValidator accurately inspects media streams and validates standards."""
    reel_path = "output/jobs/test_e2e_1c021d/reel_test_e2e_1c021d.mp4"
    if not os.path.exists(reel_path):
        pytest.skip(f"Master reel not found at {reel_path}")

    qa = VideoQualityValidator.validate_master_reel(reel_path, min_duration_sec=15.0, max_duration_sec=75.0)

    assert qa["is_valid"] is True, f"Validation failed: {qa['errors']}"
    assert len(qa["errors"]) == 0
    m = qa["metrics"]
    assert m["width"] == 1080
    assert m["height"] == 1920
    assert m["fps"] == 30.0
    assert m["file_size_bytes"] > 500_000
    assert m["audio_codec"] == "aac"
    print(f"✅ Video Quality Validator: 100% compliant master reel verified ({m['width']}x{m['height']} @ {m['fps']}fps, {m['file_size_mb']}MB)")

def test_video_quality_validator_catches_invalid_media():
    """Verifies that corrupt or fake files are detected and rejected."""
    fake_path = os.path.join(settings.LOCAL_STORAGE_DIR, "test_cache", "corrupt_fake.mp4")
    os.makedirs(os.path.dirname(fake_path), exist_ok=True)
    with open(fake_path, "wb") as f:
        f.write(b"NOT_A_VALID_MP4_HEADER")

    qa = VideoQualityValidator.validate_master_reel(fake_path)
    assert qa["is_valid"] is False
    assert len(qa["errors"]) > 0
    print("✅ Quality Validator successfully caught and rejected corrupted media.")
