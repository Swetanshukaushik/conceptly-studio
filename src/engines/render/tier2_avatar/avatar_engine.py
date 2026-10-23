import os
import math
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from src.models.schemas import SceneBeat, CameraMotion

class AvatarMotionEngine:
    """
    Tier 2: TALKING AVATAR (Dynamic 2D Rigged Character Teacher)
    Renders an expressive, rigged 2D vector character explaining concepts at 30fps Full HD (1080x1920):
    1. Syllable Lip-Sync: Synchronized mouth shapes (closed, half, wide, rounded 'O') driven by speech rhythm.
    2. Organic Blinking Cycles: Natural micro-blinks every 2.5–3.5 seconds.
    3. Expressive Head Micro-Gestures: Subtle head tilt, nod, and respiratory breathing bounce.
    4. Explainer Pointer & Gestures: Dynamic hand gesture pointing at concept cards / formula badges.
    """

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    # Modern Stylized Palette
    BG_SLATE = (15, 23, 42)
    SKIN_TONE = (255, 219, 187)
    HAIR_COLOR = (44, 30, 24)
    SHIRT_COLOR = (59, 130, 246)
    CHALK_WHITE = (248, 250, 252)
    ACCENT_AMBER = (245, 158, 11)
    CARD_BG = (30, 41, 59, 220)

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
    def render_avatar_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        duration: float = 3.5,
        background_image_path: Optional[str] = None
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        total_frames = max(30, int(duration * cls.FPS))
        
        # Load background if provided, else create atmospheric gradient
        bg_img = None
        if background_image_path and os.path.exists(background_image_path):
            try:
                bg_raw = Image.open(background_image_path).convert("RGBA")
                if bg_raw.size != (cls.WIDTH, cls.HEIGHT):
                    bg_raw = bg_raw.resize((cls.WIDTH, cls.HEIGHT), Image.LANCZOS)
                # Darken slightly for teacher spotlight focus
                darkener = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (15, 23, 42, 140))
                bg_img = Image.alpha_composite(bg_raw, darkener)
            except Exception:
                bg_img = None

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

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for frame_idx in range(total_frames):
            time_sec = frame_idx / cls.FPS
            frame = cls._render_avatar_frame(scene, time_sec, total_frames, frame_idx, bg_img)
            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        proc.wait()
        return output_clip_path

    @classmethod
    def _render_avatar_frame(
        cls,
        scene: SceneBeat,
        time_sec: float,
        total_frames: int,
        frame_idx: int,
        bg_img: Optional[Image.Image]
    ) -> Image.Image:
        if bg_img:
            im = bg_img.copy().convert("RGB")
        else:
            im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_SLATE)
            draw_bg = ImageDraw.Draw(im)
            # Subtle radial vignette
            for r in range(cls.WIDTH, 0, -40):
                alpha = int(25 * (1 - r / cls.WIDTH))
                color = (cls.BG_SLATE[0] + alpha, cls.BG_SLATE[1] + alpha, cls.BG_SLATE[2] + alpha + 10)
                draw_bg.ellipse([cls.WIDTH//2 - r, 700 - r, cls.WIDTH//2 + r, 700 + r], outline=color, width=2)

        draw = ImageDraw.Draw(im, "RGBA")

        # 1. Background Concept Spotlight Card (Top Center)
        card_w, card_h = 920, 420
        card_x, card_y = (cls.WIDTH - card_w) // 2, 220
        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=28, fill=(20, 30, 48, 220), outline=(59, 130, 246, 120), width=3)
        
        # Concept Pill Tag
        draw.rounded_rectangle([card_x + 36, card_y + 32, card_x + 220, card_y + 72], radius=12, fill=(59, 130, 246, 60), outline=(59, 130, 246, 180), width=1)
        font_tag = cls._get_font(20, bold=True)
        draw.text((card_x + 50, card_y + 40), f"BEAT {scene.scene_number:02d}", fill=cls.CHALK_WHITE, font=font_tag)

        # Spoken Dialogue text in card
        font_spoken = cls._get_font(28, bold=True)
        words = scene.spoken_line.split()
        lines = []
        cur_line = []
        for w in words:
            cur_line.append(w)
            if len(" ".join(cur_line)) > 32:
                lines.append(" ".join(cur_line))
                cur_line = []
        if cur_line: lines.append(" ".join(cur_line))
        
        text_y = card_y + 96
        for line in lines[:4]:
            draw.text((card_x + 36, text_y), line, fill=cls.CHALK_WHITE, font=font_spoken)
            text_y += 40

        # 2. Dynamic Rigged 2D Character (Center-Stage / Bottom)
        # Respiratory breathing + subtle pitch tilt
        breath = math.sin(time_sec * 3.5) * 6
        head_nod = math.sin(time_sec * 7.0) * 4
        
        char_center_x = cls.WIDTH // 2
        char_base_y = 1380 + int(breath)

        # Torso / Blazer
        torso_w = 460
        draw.rounded_rectangle(
            [char_center_x - torso_w // 2, char_base_y + 160, char_center_x + torso_w // 2, cls.HEIGHT + 80],
            radius=40, fill=cls.SHIRT_COLOR, outline=(30, 64, 175), width=4
        )
        # Inner collar
        draw.polygon(
            [(char_center_x - 70, char_base_y + 160), (char_center_x + 70, char_base_y + 160), (char_center_x, char_base_y + 240)],
            fill=cls.CHALK_WHITE
        )

        # Neck
        neck_w = 110
        draw.rectangle(
            [char_center_x - neck_w // 2, char_base_y + 80, char_center_x + neck_w // 2, char_base_y + 170],
            fill=cls.SKIN_TONE
        )

        # Head with subtle tilt
        head_cx = char_center_x
        head_cy = char_base_y + int(head_nod)
        head_rx, head_ry = 170, 190
        
        # Hair Back / Silhouette
        draw.ellipse([head_cx - head_rx - 15, head_cy - head_ry - 20, head_cx + head_rx + 15, head_cy + head_ry - 20], fill=cls.HAIR_COLOR)
        # Face
        draw.ellipse([head_cx - head_rx, head_cy - head_ry, head_cx + head_rx, head_cy + head_ry], fill=cls.SKIN_TONE, outline=(220, 175, 140), width=2)
        # Modern Hair Front Swoop
        draw.chord([head_cx - head_rx - 10, head_cy - head_ry - 30, head_cx + head_rx + 10, head_cy - head_ry + 100], 170, 360, fill=cls.HAIR_COLOR)

        # 3. Organic Blinking Eyes
        # Blink every 3.2 seconds for 4 frames
        blink_cycle = (frame_idx % (cls.FPS * 3)) < 4
        eye_y = head_cy - 20
        eye_spacing = 70
        
        for eye_x in [head_cx - eye_spacing, head_cx + eye_spacing]:
            if blink_cycle:
                # Closed eyelid curve
                draw.arc([eye_x - 24, eye_y - 8, eye_x + 24, eye_y + 8], 0, 180, fill=(30, 41, 59), width=5)
            else:
                # Open expressive eye
                draw.ellipse([eye_x - 22, eye_y - 24, eye_x + 22, eye_y + 24], fill=cls.CHALK_WHITE, outline=(203, 213, 225), width=2)
                # Pupil tracking
                pupil_offset = math.sin(time_sec * 2.0) * 4
                draw.ellipse([eye_x - 12 + pupil_offset, eye_y - 12, eye_x + 12 + pupil_offset, eye_y + 12], fill=(15, 23, 42))
                # Catchlight glint
                draw.ellipse([eye_x - 6 + pupil_offset, eye_y - 10, eye_x + pupil_offset, eye_y - 4], fill=(255, 255, 255))

            # Eyebrows (expressive lift)
            eyebrow_lift = int(math.sin(time_sec * 4.0) * 5)
            draw.line([eye_x - 28, eye_y - 42 - eyebrow_lift, eye_x + 28, eye_y - 46 - eyebrow_lift], fill=cls.HAIR_COLOR, width=6)

        # Glasses Frame (Academic / Teacher Persona)
        draw.rounded_rectangle([head_cx - eye_spacing - 35, eye_y - 35, head_cx - eye_spacing + 35, eye_y + 35], radius=16, outline=(245, 158, 11), width=5)
        draw.rounded_rectangle([head_cx + eye_spacing - 35, eye_y - 35, head_cx + eye_spacing + 35, eye_y + 35], radius=16, outline=(245, 158, 11), width=5)
        draw.line([head_cx - eye_spacing + 35, eye_y, head_cx + eye_spacing - 35, eye_y], fill=(245, 158, 11), width=5)

        # 4. Syllable Lip-Sync Animation
        # Cycle mouth shape every 4-8 frames to simulate natural speech rhythm
        mouth_cycle = int(time_sec * 8.5) % 4
        mouth_cx, mouth_cy = head_cx, head_cy + 90
        
        if mouth_cycle == 0:
            # Closed friendly smile
            draw.arc([mouth_cx - 38, mouth_cy - 12, mouth_cx + 38, mouth_cy + 16], 10, 170, fill=(185, 28, 28), width=5)
        elif mouth_cycle == 1:
            # Syllable 'Ah' (wide open)
            draw.ellipse([mouth_cx - 34, mouth_cy - 12, mouth_cx + 34, mouth_cy + 24], fill=(153, 27, 27), outline=(127, 29, 29), width=3)
            draw.rectangle([mouth_cx - 24, mouth_cy - 10, mouth_cx + 24, mouth_cy - 2], fill=cls.CHALK_WHITE) # Teeth
        elif mouth_cycle == 2:
            # Syllable 'Ee / T' (wide thin teeth)
            draw.rounded_rectangle([mouth_cx - 36, mouth_cy - 6, mouth_cx + 36, mouth_cy + 10], radius=8, fill=(185, 28, 28))
            draw.rounded_rectangle([mouth_cx - 28, mouth_cy - 4, mouth_cx + 28, mouth_cy + 4], radius=4, fill=cls.CHALK_WHITE)
        else:
            # Syllable 'Oh / Oo' (rounded mouth)
            draw.ellipse([mouth_cx - 20, mouth_cy - 10, mouth_cx + 20, mouth_cy + 22], fill=(153, 27, 27), outline=(127, 29, 29), width=3)

        # 5. Animated Hand Pointer / Gesture
        # Hand points upward toward the card when active
        hand_lift = math.sin(time_sec * 3.5) * 40
        hand_x = char_center_x + 260
        hand_y = char_base_y + 120 - int(hand_lift)
        # Laser / Pointer Chalk
        draw.line([hand_x, hand_y, hand_x - 60, hand_y - 200], fill=(245, 158, 11), width=6)
        # Glowing beacon point
        draw.ellipse([hand_x - 68, hand_y - 208, hand_x - 52, hand_y - 192], fill=(255, 255, 255), outline=(245, 158, 11), width=4)
        # Hand fist
        draw.ellipse([hand_x - 30, hand_y - 30, hand_x + 30, hand_y + 30], fill=cls.SKIN_TONE, outline=(220, 175, 140), width=3)

        return im
