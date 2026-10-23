import os
import shutil
import subprocess
from typing import Optional
from src.models.schemas import SceneBeat, CameraMotion

class FlashMotionEngine:
    """
    Tier 1: FLASH (Photos with Audio)
    Renders clean 1080x1920 (9:16) 30fps H.264 video clips using
    FFmpeg's zoompan filter with smooth 2.5D camera trajectories:
    - ZOOM_IN: Slow dramatic push-in (scale 1.0 -> 1.15)
    - PAN_RIGHT: Smooth horizontal drift to the right
    - PAN_LEFT: Smooth horizontal drift to the left
    - PULL_BACK: Reveal wider context (scale 1.15 -> 1.0)
    """

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    @classmethod
    def _find_ffmpeg(cls) -> Optional[str]:
        candidates = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg",
            shutil.which("ffmpeg")
        ]
        for path in candidates:
            if path and os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    @classmethod
    def render_clip(
        cls,
        image_path: str,
        output_clip_path: str,
        duration: float,
        motion: CameraMotion = CameraMotion.ZOOM_IN
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        frames = int(duration * cls.FPS)

        if motion == CameraMotion.ZOOM_IN:
            vf = f"zoompan=z='min(zoom+0.0012,1.15)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={cls.WIDTH}x{cls.HEIGHT}:fps={cls.FPS}"
        elif motion == CameraMotion.PAN_RIGHT:
            vf = f"zoompan=z=1.12:x='min(x+1.5,iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s={cls.WIDTH}x{cls.HEIGHT}:fps={cls.FPS}"
        elif motion == CameraMotion.PAN_LEFT:
            vf = f"zoompan=z=1.12:x='max(x-1.5,0)':y='ih/2-(ih/zoom/2)':d={frames}:s={cls.WIDTH}x{cls.HEIGHT}:fps={cls.FPS}"
        elif motion == CameraMotion.PULL_BACK:
            vf = f"zoompan=z='if(lte(zoom,1.0),1.0,max(1.0,1.15-0.0012*on))':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={cls.WIDTH}x{cls.HEIGHT}:fps={cls.FPS}"
        else:
            vf = f"zoompan=z='min(zoom+0.0010,1.12)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={cls.WIDTH}x{cls.HEIGHT}:fps={cls.FPS}"

        cmd = [
            ffmpeg_bin, "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", vf,
            "-t", f"{duration:.2f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            output_clip_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"⚠️ Flash clip generation error: {res.stderr.decode('utf-8', errors='ignore')}")
        return output_clip_path
