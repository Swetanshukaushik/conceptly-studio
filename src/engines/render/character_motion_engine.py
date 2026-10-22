import os
import math
import random
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from src.models.schemas import SceneBeat, VisualModality, CameraMotion

class CharacterMotionEngine:
    """
    Tier 1 FREE Cinematic Living Character & Historical Motion Engine:
    Transforms authentic static historical and character portraits (e.g. Bhagat Singh 1929)
    into living, breathing 1080x1920 (9:16) cinematic video clips at 30fps with $0.00 GPU cost.

    Key Cinematic Techniques:
    1. 2.5D Respiratory Micro-Motion: Natural human breathing cycle (torso expands/contracts).
    2. Cinematic Volumetric Light Sweep & Eye Glint: Warm spotlight sweeps across face & highlights eyes.
    3. 3D Floating Particle Parallax: Embers, dust motes, and revolutionary sparks drifting through the frame.
    4. 35mm Celluloid Film Dynamics: Organic handheld micro-shake and subtle vintage grain shimmer.
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
    def should_animate_character(cls, scene: SceneBeat) -> bool:
        """Determines if the scene beat focuses on a historical leader, character, or person."""
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()
        keywords = [
            "bhagat", "singh", "portrait", "face", "leader", "revolutionary", "person",
            "man", "woman", "soldier", "scientist", "galileo", "newton", "curie", "gandhi",
            "subhas", "bose", "historical figure", "eyes", "headshot"
        ]
        return any(kw in text for kw in keywords)

    @classmethod
    def render_living_character_clip(
        cls,
        image_path: str,
        output_clip_path: str,
        duration: float = 3.5,
        scene: Optional[SceneBeat] = None
    ) -> str:
        """
        Renders a 30fps living character video clip piped directly to FFmpeg.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        # Load base character portrait
        try:
            base_img = Image.open(image_path).convert("RGB")
            if base_img.size != (cls.WIDTH, cls.HEIGHT):
                base_img = base_img.resize((cls.WIDTH, cls.HEIGHT), Image.LANCZOS)
        except Exception as e:
            raise RuntimeError(f"Failed to load character image {image_path}: {e}")

        total_frames = max(30, int(duration * cls.FPS))

        # FFmpeg rawvideo pipe command
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{cls.WIDTH}x{cls.HEIGHT}",
            "-pix_fmt", "rgb24",
            "-r", str(cls.FPS),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            output_clip_path
        ]

        # Initialize floating particles (embers/dust)
        is_revolutionary = False
        if scene:
            text = f"{scene.visual_prompt} {scene.spoken_line}".lower()
            is_revolutionary = any(w in text for w in ["bhagat", "revolution", "assembly", "freedom", "bomb", "revolt"])

        particles: List[Dict[str, Any]] = []
        num_particles = 45
        for _ in range(num_particles):
            particles.append({
                "x": random.uniform(0, cls.WIDTH),
                "y": random.uniform(0, cls.HEIGHT),
                "vx": random.uniform(-1.2, 1.2),
                "vy": random.uniform(-3.5, -0.8) if is_revolutionary else random.uniform(-1.0, 1.0),
                "radius": random.uniform(2.0, 6.0),
                "alpha": random.randint(100, 220),
                "phase": random.uniform(0, math.pi * 2),
                "is_ember": is_revolutionary and (random.random() > 0.4)
            })

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for frame_idx in range(total_frames):
                progress = frame_idx / float(total_frames)

                # 1. Human Respiratory Cycle & Subtle 2.5D Scale (Organic Breathing)
                # Breathing frequency ~ 0.25 Hz (one breath per 4 seconds)
                breath_cycle = math.sin(progress * 2.0 * math.pi)
                breath_scale = 1.0 + 0.012 * breath_cycle  # 1.2% chest rise/fall

                # Slow camera push-in combined with breathing
                zoom = 1.0 + 0.05 * progress
                total_scale = zoom * breath_scale

                # Handheld micro-shake (subtle organic motion)
                shake_x = 1.5 * math.sin(frame_idx * 0.35)
                shake_y = 1.0 * math.cos(frame_idx * 0.28) + 3.0 * breath_cycle

                # Crop and resample base image for zoom & breathing
                crop_w = int(cls.WIDTH / total_scale)
                crop_h = int(cls.HEIGHT / total_scale)
                cx = cls.WIDTH // 2 + int(shake_x)
                cy = int(cls.HEIGHT * 0.42) + int(shake_y)  # Focus slightly above center (head/eye level)

                x1 = max(0, min(cls.WIDTH - crop_w, cx - crop_w // 2))
                y1 = max(0, min(cls.HEIGHT - crop_h, cy - crop_h // 2))
                x2 = x1 + crop_w
                y2 = y1 + crop_h

                cropped = base_img.crop((x1, y1, x2, y2))
                frame_img = cropped.resize((cls.WIDTH, cls.HEIGHT), Image.BILINEAR)

                # 2. Cinematic Volumetric Light Sweep & Eye Glint
                # Sweeps light beam across face around 30% - 70% of the clip
                sweep_progress = math.sin(progress * math.pi)
                sweep_x = int(-200 + sweep_progress * (cls.WIDTH + 400))
                
                # Create lighting overlay layer
                light_layer = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
                light_draw = ImageDraw.Draw(light_layer)

                # Volumetric diagonal light beam
                beam_w = 320
                light_alpha = int(45 * sweep_progress)
                light_color = (255, 230, 180, light_alpha) if is_revolutionary else (200, 230, 255, light_alpha)
                light_draw.polygon([
                    (sweep_x - beam_w, 0),
                    (sweep_x + beam_w, 0),
                    (sweep_x + beam_w + 300, cls.HEIGHT),
                    (sweep_x - beam_w + 300, cls.HEIGHT)
                ], fill=light_color)

                # Eye glint highlight when sweep crosses face center
                if 0.25 <= progress <= 0.75:
                    eye_y = int(cls.HEIGHT * 0.38)  # Approximate face/eye line
                    eye_intensity = int(80 * math.sin((progress - 0.25) / 0.5 * math.pi))
                    # Eye glint accent
                    light_draw.ellipse([cls.WIDTH // 2 - 120, eye_y - 20, cls.WIDTH // 2 + 120, eye_y + 20], fill=(255, 245, 220, eye_intensity))

                # Composite light sweep with soft blur
                light_layer = light_layer.filter(ImageFilter.GaussianBlur(radius=18))
                frame_img.paste(Image.alpha_composite(frame_img.convert("RGBA"), light_layer).convert("RGB"))

                # 3. Dynamic Atmospheric Floating Particles (Embers / Dust Motes)
                p_draw = ImageDraw.Draw(frame_img)
                for p in particles:
                    # Update position
                    p["x"] = (p["x"] + p["vx"] + math.sin(frame_idx * 0.08 + p["phase"]) * 0.8) % cls.WIDTH
                    p["y"] = (p["y"] + p["vy"]) % cls.HEIGHT
                    r = p["radius"]
                    if p["is_ember"]:
                        # Glowing golden fire ember
                        p_color = (255, random.randint(140, 200), random.randint(30, 70))
                        p_draw.ellipse([p["x"] - r - 1, p["y"] - r - 1, p["x"] + r + 1, p["y"] + r + 1], fill=(255, 100, 20))
                        p_draw.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=p_color)
                    else:
                        # Soft atmospheric dust mote
                        p_alpha = int(140 + 40 * math.sin(frame_idx * 0.1 + p["phase"]))
                        p_draw.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=(p_alpha, p_alpha, p_alpha))

                # 4. Cinematic Vignette Pulse
                vignette_alpha = 40 + int(12 * math.sin(frame_idx * 0.15))
                # Soft corner darkening
                p_draw.rectangle([0, 0, cls.WIDTH, 120], fill=(0, 0, 0, vignette_alpha))
                p_draw.rectangle([0, cls.HEIGHT - 120, cls.WIDTH, cls.HEIGHT], fill=(0, 0, 0, vignette_alpha))

                # Write frame to FFmpeg pipe
                proc.stdin.write(frame_img.tobytes())

            proc.stdin.close()
            proc.wait(timeout=60)
        except Exception as e:
            proc.kill()
            raise RuntimeError(f"Character motion clip render error: {e}")

        return output_clip_path
