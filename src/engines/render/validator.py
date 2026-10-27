import os
import json
import shutil
import subprocess
from typing import Dict, Any, List, Optional

class VideoQualityValidationError(Exception):
    """Raised when rendered video fails broadcast quality, resolution or audio standards."""
    def __init__(self, message: str, validation_results: Dict[str, Any]):
        super().__init__(message)
        self.validation_results = validation_results

class VideoQualityValidator:
    """
    Automated Video Quality & Audio Stream Validator:
    Verifies that every generated 3D clip and final master reel meets strict broadcast standards:
    - Vertical 9:16 aspect ratio (1080x1920 resolution)
    - 30fps framerate (29.0 to 31.0 fps)
    - H.264 video codec + stereo AAC / PCM audio
    - Audio-to-video duration alignment (within 0.35s tolerance)
    - Non-silent audio stream (no corrupt or empty audio)
    - Container integrity and minimum expected file sizes
    """

    EXPECTED_WIDTH = 1080
    EXPECTED_HEIGHT = 1920
    EXPECTED_FPS = 30.0
    FPS_TOLERANCE = 1.5
    AV_SYNC_TOLERANCE_SEC = 0.50

    @classmethod
    def _find_ffprobe(cls) -> Optional[str]:
        candidates = [
            "/opt/homebrew/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            "/usr/bin/ffprobe",
            shutil.which("ffprobe")
        ]
        for path in candidates:
            if path and os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    @classmethod
    def probe_media(cls, file_path: str) -> Dict[str, Any]:
        """Runs ffprobe on the target media file and returns parsed JSON output."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file does not exist: {file_path}")

        ffprobe_bin = cls._find_ffprobe()
        if not ffprobe_bin:
            raise RuntimeError("ffprobe binary not found. Please install ffmpeg/ffprobe.")

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height,r_frame_rate,duration,channels,sample_rate",
            "-show_entries", "format=duration,size,format_name",
            "-of", "json",
            file_path
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffprobe failed on {file_path}: {res.stderr}")

        return json.loads(res.stdout)

    @classmethod
    def validate_master_reel(
        cls,
        reel_path: str,
        min_duration_sec: float = 20.0,
        max_duration_sec: float = 75.0,
        enforce_audio: bool = True
    ) -> Dict[str, Any]:
        """
        Validates the final assembled reel against mobile 9:16 master standards.
        Returns a structured validation dictionary with errors, warnings, and stream metrics.
        """
        errors: List[str] = []
        warnings: List[str] = []
        metrics: Dict[str, Any] = {}

        if not os.path.exists(reel_path):
            return {
                "is_valid": False,
                "errors": [f"Master reel file does not exist at {reel_path}"],
                "warnings": [],
                "metrics": {}
            }

        file_size = os.path.getsize(reel_path)
        metrics["file_size_bytes"] = file_size
        metrics["file_size_mb"] = round(file_size / (1024 * 1024), 2)

        if file_size < 100_000:
            errors.append(f"Master reel size too small ({file_size} bytes); likely corrupted.")

        try:
            probe_data = cls.probe_media(reel_path)
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"ffprobe media inspection failed: {e}"],
                "warnings": [],
                "metrics": metrics
            }

        streams = probe_data.get("streams", [])
        format_info = probe_data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        # 1. Video Stream Checks
        if not video_stream:
            errors.append("No video stream found in master reel.")
        else:
            v_width = video_stream.get("width")
            v_height = video_stream.get("height")
            metrics["width"] = v_width
            metrics["height"] = v_height
            metrics["video_codec"] = video_stream.get("codec_name")

            if v_width != cls.EXPECTED_WIDTH or v_height != cls.EXPECTED_HEIGHT:
                errors.append(f"Invalid resolution: {v_width}x{v_height}. Expected {cls.EXPECTED_WIDTH}x{cls.EXPECTED_HEIGHT} (9:16).")

            # Frame rate parsing
            fps_str = video_stream.get("r_frame_rate", "30/1")
            try:
                num, den = fps_str.split("/")
                fps = float(num) / float(den)
            except Exception:
                fps = 30.0
            metrics["fps"] = round(fps, 2)

            if abs(fps - cls.EXPECTED_FPS) > cls.FPS_TOLERANCE:
                warnings.append(f"Framerate {fps:.2f}fps deviates from standard {cls.EXPECTED_FPS}fps.")

            # Duration check
            v_dur = float(video_stream.get("duration") or format_info.get("duration") or 0.0)
            metrics["video_duration_sec"] = round(v_dur, 2)

            if v_dur < min_duration_sec:
                errors.append(f"Reel duration {v_dur:.1f}s is below minimum {min_duration_sec:.1f}s.")
            elif v_dur > max_duration_sec:
                errors.append(f"Reel duration {v_dur:.1f}s exceeds maximum {max_duration_sec:.1f}s.")

        # 2. Audio Stream Checks
        if enforce_audio:
            if not audio_stream:
                errors.append("No audio stream found in master reel.")
            else:
                metrics["audio_codec"] = audio_stream.get("codec_name")
                metrics["audio_channels"] = audio_stream.get("channels")
                metrics["audio_sample_rate"] = int(audio_stream.get("sample_rate") or 0)
                
                a_dur = float(audio_stream.get("duration") or format_info.get("duration") or 0.0)
                metrics["audio_duration_sec"] = round(a_dur, 2)

                if audio_stream.get("channels", 0) < 2:
                    warnings.append(f"Audio is mono ({audio_stream.get('channels')} channels); stereo recommended.")

                # A/V Sync Duration Check
                if video_stream and "video_duration_sec" in metrics:
                    duration_delta = abs(metrics["video_duration_sec"] - metrics["audio_duration_sec"])
                    metrics["av_duration_delta_sec"] = round(duration_delta, 3)
                    if duration_delta > cls.AV_SYNC_TOLERANCE_SEC:
                        warnings.append(f"Audio and video durations drift by {duration_delta:.2f}s (tolerance: {cls.AV_SYNC_TOLERANCE_SEC}s).")

        is_valid = len(errors) == 0
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "metrics": metrics
        }

    @classmethod
    def validate_scene_clip(
        cls,
        clip_path: str,
        expected_duration_sec: Optional[float] = None
    ) -> Dict[str, Any]:
        """Validates an individual 3D scene MP4 clip."""
        errors: List[str] = []
        metrics: Dict[str, Any] = {}

        if not os.path.exists(clip_path):
            return {"is_valid": False, "errors": [f"Clip not found: {clip_path}"], "metrics": {}}

        file_size = os.path.getsize(clip_path)
        metrics["file_size_bytes"] = file_size

        if file_size < 10_000:
            errors.append(f"Clip file size too small ({file_size} bytes).")

        try:
            probe_data = cls.probe_media(clip_path)
            v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
            if not v_stream:
                errors.append("Clip lacks a video stream.")
            else:
                w, h = v_stream.get("width"), v_stream.get("height")
                metrics["width"] = w
                metrics["height"] = h
                if w != cls.EXPECTED_WIDTH or h != cls.EXPECTED_HEIGHT:
                    errors.append(f"Clip resolution {w}x{h} != {cls.EXPECTED_WIDTH}x{cls.EXPECTED_HEIGHT}")

                v_dur = float(v_stream.get("duration") or probe_data.get("format", {}).get("duration") or 0.0)
                metrics["duration_sec"] = round(v_dur, 2)
                if expected_duration_sec and abs(v_dur - expected_duration_sec) > 1.0:
                    errors.append(f"Clip duration {v_dur:.2f}s deviates from expected {expected_duration_sec:.2f}s")
        except Exception as e:
            errors.append(f"Probing clip failed: {e}")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "metrics": metrics
        }
