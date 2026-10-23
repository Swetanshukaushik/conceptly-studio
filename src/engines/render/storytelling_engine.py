import os
import math
import random
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from src.models.schemas import SceneBeat, VisualModality

class MultiPlaneStorytellingEngine:
    """
    Tier 1 FREE Multi-Plane Cinematic Storytelling Engine:
    Renders dynamic multi-layered historical action scenes:
    1. The 1929 Assembly Bombing: Expanding smoke puff + fluttering yellow leaflets in 3D physics.
    2. The Colonial Courtroom Dock: Chiaroscuro volumetric beam + trial documents.
    3. The Lahore Prison Cell: Flickering lantern light + floating handwritten manuscripts.
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
    def _get_font(cls, size: int, bold: bool = True) -> ImageFont.ImageFont:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @classmethod
    def should_render(cls, scene: SceneBeat) -> bool:
        """Determines if the scene is an action-driven historical narrative cut."""
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()
        action_keywords = [
            "bombing", "leaflet", "pamphlet", "assembly hall", "central assembly",
            "courtroom dock", "court trial", "jail cell", "prison cell", "inquilab", "martyrdom"
        ]
        return any(kw in text for kw in action_keywords)

    @classmethod
    def render_narrative_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        duration: float = 3.5,
        base_image_path: Optional[str] = None
    ) -> str:
        """
        Renders a 30fps Full HD multi-plane animated historical action clip piped to FFmpeg.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        total_frames = max(30, int(duration * cls.FPS))
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()

        # Select scene renderer
        if any(w in text for w in ["bomb", "leaflet", "pamphlet", "scatter", "smoke", "assembly"]):
            render_func = cls._render_frame_assembly_bombing
        elif any(w in text for w in ["jail", "prison", "cell", "lamp", "writing"]):
            render_func = cls._render_frame_jail_cell
        else:
            render_func = cls._render_frame_courtroom_trial

        # Initialize multi-plane particles
        state: Dict[str, Any] = {
            # 45 Yellow revolutionary pamphlets with 3D tumble physics
            "leaflets": [
                {
                    "x": random.uniform(80, cls.WIDTH - 80),
                    "y": random.uniform(-400, 200),
                    "w": random.uniform(32, 55),
                    "h": random.uniform(45, 75),
                    "vx": random.uniform(-2.0, 2.0),
                    "vy": random.uniform(6.0, 14.0),
                    "rot": random.uniform(0, 360),
                    "rot_speed": random.uniform(-8.0, 8.0),
                    "tumble_phase": random.uniform(0, math.pi * 2),
                    "tumble_speed": random.uniform(3.0, 7.0),
                    "color": (250, 220 + random.randint(-20, 20), 80)  # Iconic yellow leaflet
                }
                for _ in range(48)
            ],
            # Smoke particles
            "smoke": [
                {
                    "x": cls.WIDTH // 2 + random.uniform(-100, 100),
                    "y": 1150 + random.uniform(0, 60),
                    "vx": random.uniform(-3.0, 3.0),
                    "vy": random.uniform(-4.0, -1.0),
                    "radius": random.uniform(25, 60),
                    "max_r": random.uniform(120, 220),
                    "alpha": random.uniform(160, 230),
                    "life": 1.0,
                    "decay": random.uniform(0.015, 0.035)
                }
                for _ in range(35)
            ]
        }

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

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for frame_idx in range(total_frames):
                progress = frame_idx / float(total_frames)
                img = render_func(frame_idx, total_frames, progress, state, scene)
                proc.stdin.write(img.tobytes())
            proc.stdin.close()
            proc.wait(timeout=60)
        except Exception as e:
            proc.kill()
            raise RuntimeError(f"Multi-plane narrative render error: {e}")

        return output_clip_path

    # ================= 1. ASSEMBLY HALL BOMBING & SCATTERING LEAFLETS =================
    @classmethod
    def _render_frame_assembly_bombing(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (25, 20, 18))
        draw = ImageDraw.Draw(img)

        # 1. Background: Historic Colonial Assembly Hall Architecture
        # Wooden gallery colonnade
        draw.rectangle([0, 0, cls.WIDTH, cls.HEIGHT], fill=(30, 24, 20))
        # Warm colonial chandelier glow at top
        for r in range(400, 50, -40):
            alpha = int(40 * (400 - r) / 400.0)
            draw.ellipse([cls.WIDTH//2 - r, 300 - r, cls.WIDTH//2 + r, 300 + r], fill=(50 + alpha, 40 + alpha, 25))

        # Gallery arches & pillars
        for x in range(60, cls.WIDTH, 240):
            draw.rectangle([x, 320, x + 70, 1200], fill=(45, 35, 28))
            draw.rectangle([x + 10, 320, x + 60, 1200], fill=(60, 48, 38))
            # Arch top
            draw.chord([x - 25, 280, x + 95, 380], 180, 360, fill=(45, 35, 28))

        # Wooden Benches & Railings
        draw.rectangle([0, 950, cls.WIDTH, 1020], fill=(55, 42, 32))
        draw.rectangle([0, 1100, cls.WIDTH, 1200], fill=(42, 32, 24))

        # 2. Midground: Expanding Smoke Plume from Low-Intensity Bomb
        for p in state["smoke"]:
            p["x"] += p["vx"] + math.sin(frame_idx * 0.1) * 0.8
            p["y"] += p["vy"]
            p["radius"] = min(p["max_r"], p["radius"] + 1.2)
            p["life"] -= p["decay"]
            if p["life"] > 0:
                alpha = int(p["alpha"] * p["life"])
                r = int(p["radius"])
                # Smoke cloud circle
                smoke_color = (180 + int(20 * p["life"]), 175 + int(20 * p["life"]), 165, alpha)
                draw.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=(160, 155, 145))

        # 3. Dynamic Foreground & Midground: Fluttering Revolutionary Leaflets
        # "To Make The Deaf Hear" - April 8, 1929
        for lf in state["leaflets"]:
            lf["y"] += lf["vy"]
            lf["x"] += lf["vx"] + math.sin(frame_idx * 0.15 + lf["tumble_phase"]) * 3.5
            lf["rot"] += lf["rot_speed"]
            tumble = math.sin(frame_idx * 0.2 + lf["tumble_phase"])

            # 3D perspective foreshortening width
            cur_w = max(4, int(lf["w"] * abs(tumble)))
            cur_h = int(lf["h"])

            # Draw leaflet rectangle with rotation tilt
            cx, cy = int(lf["x"]), int(lf["y"])
            if -100 <= cy <= cls.HEIGHT + 100:
                x1, y1 = cx - cur_w // 2, cy - cur_h // 2
                x2, y2 = cx + cur_w // 2, cy + cur_h // 2
                draw.rectangle([x1, y1, x2, y2], fill=lf["color"], outline=(180, 150, 40), width=1)
                # Simulated printed text lines on leaflet
                if cur_w > 15:
                    for ty in range(y1 + 8, y2 - 8, 8):
                        draw.line([(x1 + 4, ty), (x2 - 4, ty)], fill=(120, 100, 30), width=1)

        # 4. Cinematic Dramatic Camera Push-in
        zoom = 1.0 + 0.04 * progress

        # 5. Historic Chronicle Overlay HUD
        draw.rounded_rectangle([100, 140, cls.WIDTH - 100, 220], radius=16, fill=(20, 16, 14, 230), outline=(234, 179, 8), width=2)
        font_header = cls._get_font(24)
        draw.text((130, 165), "🏛️ CENTRAL LEGISLATIVE ASSEMBLY • APRIL 8, 1929", fill=(250, 204, 21), font=font_header)

        # Bottom Chronicle Card
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(18, 14, 12, 240), outline=(234, 179, 8), width=2)
        draw.text((115, 1365), "PROCLAMATION: 'TO MAKE THE DEAF HEAR'", fill=(255, 255, 255), font=cls._get_font(28))
        draw.text((115, 1412), "Non-lethal smoke bombs and leaflets dropped into empty benches.", fill=(214, 211, 209), font=cls._get_font(20, bold=False))

        return img

    # ================= 2. THE COLONIAL COURTROOM TRIAL =================
    @classmethod
    def _render_frame_courtroom_trial(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (15, 18, 25))
        draw = ImageDraw.Draw(img)

        # Dark Victorian courtroom arches
        for x in range(100, cls.WIDTH, 280):
            draw.rectangle([x, 260, x + 80, 1200], fill=(28, 35, 48))
            draw.chord([x - 30, 220, x + 110, 320], 180, 360, fill=(28, 35, 48))

        # Chiaroscuro volumetric interrogation spotlight beam
        beam_progress = math.sin(progress * math.pi)
        beam_x = int(cls.WIDTH * 0.45 + math.sin(frame_idx * 0.05) * 40)
        draw.polygon([
            (beam_x - 120, 0), (beam_x + 120, 0),
            (beam_x + 380, cls.HEIGHT), (beam_x - 380, cls.HEIGHT)
        ], fill=(35, 48, 70))

        # The Dock Wooden Railings
        draw.rectangle([140, 750, cls.WIDTH - 140, 820], fill=(45, 40, 35), outline=(100, 90, 80), width=2)
        for rx in range(180, cls.WIDTH - 140, 50):
            draw.line([(rx, 820), (rx, 1150)], fill=(60, 50, 42), width=8)

        # Iconic Slogan Badge in Courtroom
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 220], radius=16, fill=(18, 22, 32, 230), outline=(59, 130, 246), width=2)
        draw.text((150, 165), "⚖️ THE LAHORE TRIAL • THE COURT AS A MEGAPHONE", fill=(96, 165, 250), font=cls._get_font(22))

        # Bottom Card
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 20, 30, 240), outline=(239, 68, 68), width=2)
        draw.text((115, 1365), "SLOGAN: 'INQUILAB ZINDABAD!'", fill=(255, 255, 255), font=cls._get_font(30))
        draw.text((115, 1412), "Using the British colonial dock to amplify the call for total freedom.", fill=(156, 163, 175), font=cls._get_font(20, bold=False))

        return img

    # ================= 3. LAHORE PRISON CELL & SOLITARY LAMP =================
    @classmethod
    def _render_frame_jail_cell(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (16, 14, 18))
        draw = ImageDraw.Draw(img)

        # Brick Archway Architecture
        cx, cy = cls.WIDTH // 2, 800
        # Stone arch
        draw.arc([100, 350, cls.WIDTH - 100, 1100], 180, 360, fill=(50, 45, 55), width=45)

        # Flickering Oil Lamp / Lantern at Center
        flicker = 1.0 + 0.12 * math.sin(frame_idx * 0.8) + 0.06 * math.sin(frame_idx * 1.9)
        lamp_y = 650
        for r in range(450, 40, -35):
            intensity = int(flicker * 35 * (450 - r) / 450.0)
            draw.ellipse([cx - r, lamp_y - r, cx + r, lamp_y + r], fill=(45 + intensity, 30 + int(intensity * 0.7), 15))

        # Lantern Glass & Flame
        draw.rectangle([cx - 25, lamp_y - 40, cx + 25, lamp_y + 40], outline=(180, 140, 80), width=3)
        draw.ellipse([cx - 12, lamp_y - 20, cx + 12, lamp_y + 15], fill=(255, 220, 100))

        # Floating illuminated manuscript notes
        for i, angle in enumerate([0.2, 1.4, 2.7, 4.2]):
            px = int(cx + 260 * math.cos(angle + progress * 0.5))
            py = int(lamp_y + 200 * math.sin(angle + progress * 0.5))
            draw.rectangle([px - 35, py - 45, px + 35, py + 45], fill=(245, 230, 190), outline=(140, 110, 60))
            for ly in range(py - 30, py + 35, 12):
                draw.line([(px - 25, ly), (px + 25, ly)], fill=(80, 60, 40), width=1)

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 220], radius=16, fill=(24, 20, 26, 230), outline=(245, 158, 11), width=2)
        draw.text((150, 165), "📖 LAHORE CENTRAL JAIL • REVOLUTIONARY WRITINGS", fill=(251, 191, 36), font=cls._get_font(21))

        # Bottom Card
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(20, 16, 22, 240), outline=(245, 158, 11), width=2)
        draw.text((115, 1365), "'THE SWORD OF REVOLUTION IS SHARPENED ON IDEAS'", fill=(255, 255, 255), font=cls._get_font(24))
        draw.text((115, 1412), "Authoring 'Why I Am an Atheist' and jail diaries before martyrdom.", fill=(214, 211, 209), font=cls._get_font(19, bold=False))

        return img
