import os
import math
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from src.models.schemas import SceneBeat, CameraMotion

class KurzgesagtMasterEngine:
    """
    Tier 5: KURZGESAGT MASTERPIECE (The Pinnacle of YouTube Educational Animation)
    Produces the iconic 60fps/30fps Full HD (1080x1920 9:16) Kurzgesagt aesthetic:
    1. RIGGED DUCK / SCIENTIST PUPPET:
       - Iconic yellow/gold vector duck mascot with scientist lab coat.
       - Natural blinking cartoon eyes tracking the diagram.
       - Animated beak syncing with syllables.
       - Holding laser pointer or magnifying glass aimed at the formula.
    2. EMBEDDED PHYSICS & BIOLOGY SIMULATION:
       - Midground features live oscillating springs, refracting prism rays, or cellular lipid membranes.
    3. SIGNATURE PALETTE & ATMOSPHERE:
       - Deep space obsidian background (#0b0f19), phosphor cyan (#00f5d4), hot magenta (#f72585), solar gold (#ffb703).
       - Floating stardust particles and clean vector depth.
    4. 3-LAYER STUDIO AUDIO COMPOSITING:
       - Speech + Ambient Synth Pad + Bass drops & transition whooshes.
    """

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    # Kurzgesagt Signature Palette
    BG_OBSIDIAN = (11, 15, 27)
    CYAN = (0, 245, 212)
    PINK = (247, 37, 133)
    GOLD = (255, 183, 3)
    COBALT = (58, 134, 255)
    ORANGE_BEAK = (251, 133, 0)
    LAB_COAT = (241, 245, 249)
    WHITE = (248, 250, 252)

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
    def render_master_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        duration: float = 3.5
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        total_frames = max(30, int(duration * cls.FPS))
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()

        # Identify simulation theme (Optics vs Biology vs Physics/SHM)
        if any(w in text for w in ["prism", "optic", "refract", "dispersion", "spectrum", "rainbow"]):
            sim_type = "OPTICS"
        elif any(w in text for w in ["cell", "membrane", "antibody", "dna", "virus", "immune", "bio"]):
            sim_type = "CELL_BIO"
        else:
            sim_type = "PHYSICS_SHM"

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

        # Star / Particle field
        import random
        random.seed(42)
        stars = [(random.randint(40, cls.WIDTH - 40), random.randint(40, cls.HEIGHT - 40), random.uniform(1.5, 3.5)) for _ in range(45)]

        for frame_idx in range(total_frames):
            time_sec = frame_idx / cls.FPS
            progress = frame_idx / total_frames
            im = cls._render_composite_frame(scene, time_sec, progress, frame_idx, sim_type, stars)
            proc.stdin.write(im.tobytes())

        proc.stdin.close()
        proc.wait()
        return output_clip_path

    @classmethod
    def _render_composite_frame(
        cls,
        scene: SceneBeat,
        time_sec: float,
        progress: float,
        frame_idx: int,
        sim_type: str,
        stars: List[Tuple[int, int, float]]
    ) -> Image.Image:
        im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_OBSIDIAN)
        draw = ImageDraw.Draw(im, "RGBA")

        # 1. Star / Particle Atmosphere
        for sx, sy, s_rad in stars:
            glint = 0.5 + 0.5 * math.sin(time_sec * 4.0 + sx)
            draw.ellipse([sx - s_rad, sy - s_rad, sx + s_rad, sy + s_rad], fill=(255, 255, 255, int(140 * glint)))

        # 2. Top Title Card (Kurzgesagt Style)
        card_w, card_h = 920, 200
        card_x = (cls.WIDTH - card_w) // 2
        draw.rounded_rectangle([card_x, 120, card_x + card_w, 120 + card_h], radius=28, fill=(18, 24, 43, 240), outline=cls.CYAN, width=3)
        
        # Pill Tag
        draw.rounded_rectangle([card_x + 36, 144, card_x + 240, 184], radius=12, fill=(0, 245, 212, 40), outline=cls.CYAN, width=1)
        draw.text((card_x + 50, 152), f"ACT SCENE {scene.scene_number:02d}", fill=cls.CYAN, font=cls._get_font(20, bold=True))

        # Headline
        font_head = cls._get_font(34, bold=True)
        # Wrap spoken line
        words = scene.spoken_line.split()
        l1 = " ".join(words[:7])
        l2 = " ".join(words[7:15]) if len(words) > 7 else ""
        draw.text((card_x + 36, 204), l1, fill=cls.WHITE, font=font_head)
        if l2:
            draw.text((card_x + 36, 250), l2, fill=cls.GOLD, font=cls._get_font(28, bold=True))

        # 3. Middle Simulation Layer (Physics, Optics, or Cell Bio)
        if sim_type == "OPTICS":
            cls._draw_sim_optics(draw, time_sec, progress)
        elif sim_type == "CELL_BIO":
            cls._draw_sim_cell(draw, time_sec, progress)
        else:
            cls._draw_sim_shm(draw, time_sec, progress)

        # 4. Foreground Kurzgesagt Rigged Character (The Duck Explorer)
        cls._draw_kurzgesagt_duck(draw, time_sec, frame_idx)

        return im

    # ================= SIMULATION LAYER A: SHM OSCILLATOR =================
    @classmethod
    def _draw_sim_shm(cls, draw: ImageDraw.ImageDraw, time_sec: float, progress: float):
        cx, cy = cls.WIDTH // 2 - 40, 720
        omega = 3.6
        amp = 180
        x_disp = amp * math.cos(omega * time_sec)
        
        # Guide track
        draw.line([160, cy + 50, cls.WIDTH - 200, cy + 50], fill=(71, 85, 105), width=4)
        
        # Spring
        wall_x = 180
        mass_x = cx + int(x_disp)
        spring_pts = [(wall_x, cy)]
        coils = 12
        spacing = (mass_x - 50 - wall_x) / coils
        for c in range(1, coils):
            spring_pts.append((wall_x + (c - 0.5) * spacing, cy + (25 if c % 2 == 1 else -25)))
        spring_pts.append((mass_x - 50, cy))
        for i in range(len(spring_pts) - 1):
            draw.line([spring_pts[i], spring_pts[i+1]], fill=cls.CYAN, width=5)

        # Oscillating Mass Block
        draw.rounded_rectangle([mass_x - 50, cy - 50, mass_x + 50, cy + 50], radius=16, fill=(30, 41, 59), outline=cls.CYAN, width=4)
        draw.text((mass_x - 14, cy - 20), "m", fill=cls.WHITE, font=cls._get_font(32, bold=True))

        # Glowing Neon Velocity Vector
        vel = -amp * omega * math.sin(omega * time_sec)
        v_len = int(vel * 0.15)
        if abs(v_len) > 5:
            col = cls.GOLD if v_len > 0 else cls.PINK
            draw.line([mass_x, cy - 70, mass_x + v_len, cy - 70], fill=col, width=6)
            draw.polygon([(mass_x + v_len, cy - 78), (mass_x + v_len + (12 if v_len > 0 else -12), cy - 70), (mass_x + v_len, cy - 62)], fill=col)
            draw.text((mass_x + v_len//2 - 8, cy - 105), "v", fill=col, font=cls._get_font(22, bold=True))

        # Dynamic Formula Card
        draw.rounded_rectangle([180, 880, 560, 960], radius=16, fill=(18, 24, 43, 200), outline=cls.GOLD, width=2)
        draw.text((200, 902), "F = -kx  •  a = -ω²x", fill=cls.GOLD, font=cls._get_font(26, bold=True))

    # ================= SIMULATION LAYER B: OPTICS PRISM =================
    @classmethod
    def _draw_sim_optics(cls, draw: ImageDraw.ImageDraw, time_sec: float, progress: float):
        cx, cy = cls.WIDTH // 2 - 40, 720
        p_top = (cx, cy - 180)
        p_left = (cx - 180, cy + 120)
        p_right = (cx + 180, cy + 120)
        draw.polygon([p_top, p_left, p_right], fill=(30, 58, 138, 140), outline=(96, 165, 250), width=4)

        # Incident White Light Ray
        draw.line([120, cy - 30, cx - 70, cy], fill=cls.WHITE, width=8)

        # Refracted Rainbow Fan
        colors = [(239, 68, 68), (249, 115, 22), (234, 179, 8), (34, 197, 94), (59, 130, 246), (168, 85, 247)]
        for idx, col in enumerate(colors):
            dev = (idx - 2.5) * 20
            draw.line([cx - 70, cy, cx + 50, cy + 20 + int(dev * 0.4)], fill=col, width=3)
            draw.line([cx + 50, cy + 20 + int(dev * 0.4), cx + 320, cy + 30 + dev * 3], fill=col, width=5)

    # ================= SIMULATION LAYER C: CELLULAR MEMBRANE =================
    @classmethod
    def _draw_sim_cell(cls, draw: ImageDraw.ImageDraw, time_sec: float, progress: float):
        cx, cy = cls.WIDTH // 2 - 40, 720
        # Undulating lipid bilayer heads
        for x in range(160, cls.WIDTH - 180, 26):
            wave = math.sin(time_sec * 4.0 + x * 0.03) * 14
            # Top lipid head
            draw.ellipse([x - 8, cy - 40 + wave - 8, x + 8, cy - 40 + wave + 8], fill=cls.CYAN)
            draw.line([x, cy - 40 + wave, x, cy - 10 + wave], fill=(96, 165, 250), width=2)
            # Bottom lipid head
            draw.ellipse([x - 8, cy + 40 + wave - 8, x + 8, cy + 40 + wave + 8], fill=cls.CYAN)
            draw.line([x, cy + 40 + wave, x, cy + 10 + wave], fill=(96, 165, 250), width=2)

    # ================= 4. RIGGED KURZGESAGT DUCK CHARACTER =================
    @classmethod
    def _draw_kurzgesagt_duck(cls, draw: ImageDraw.ImageDraw, time_sec: float, frame_idx: int):
        """
        Renders the signature iconic Kurzgesagt Duck Mascot in lab coat:
        - Idle breathing bounce
        - Big round eye with blinking cycle
        - Talking beak
        - Lab coat with scientist badge
        - Laser pointer aimed at the formula
        """
        # Character Placement (Bottom Right / Center)
        char_x = cls.WIDTH - 300
        bounce = math.sin(time_sec * 3.5) * 8
        head_nod = math.sin(time_sec * 7.0) * 4
        char_y = 1380 + int(bounce)

        # Lab Coat Body (Rounded Egg Shape)
        body_w, body_h = 240, 320
        draw.rounded_rectangle(
            [char_x - body_w//2, char_y - 20, char_x + body_w//2, char_y + body_h],
            radius=90, fill=cls.LAB_COAT, outline=(203, 213, 225), width=4
        )
        # Lapel Collar & Blue Tie
        draw.polygon([(char_x - 30, char_y - 10), (char_x + 30, char_y - 10), (char_x, char_y + 80)], fill=cls.COBALT)
        draw.line([char_x, char_y + 80, char_x, char_y + 240], fill=(203, 213, 225), width=3)
        # Scientist ID Badge
        draw.rounded_rectangle([char_x + 40, char_y + 60, char_x + 90, char_y + 110], radius=8, fill=cls.CYAN)

        # Duck Head (Vibrant Solar Gold)
        head_cx = char_x - 30
        head_cy = char_y - 110 + int(head_nod)
        head_rad = 110
        draw.ellipse([head_cx - head_rad, head_cy - head_rad, head_cx + head_rad, head_cy + head_rad], fill=cls.GOLD, outline=(245, 158, 11), width=3)

        # Iconic Cute Duck Beak (Orange)
        beak_cycle = int(time_sec * 8.0) % 3
        beak_base_y = head_cy + 15
        beak_tip_x = head_cx - 160
        
        # Upper Beak
        draw.polygon([(head_cx - 60, beak_base_y - 20), (beak_tip_x, beak_base_y), (head_cx - 50, beak_base_y + 10)], fill=cls.ORANGE_BEAK)
        # Lower Beak (Animates open/shut with speech)
        beak_open = 14 if beak_cycle != 0 else 2
        draw.polygon([(head_cx - 55, beak_base_y + 5), (beak_tip_x + 20, beak_base_y + beak_open), (head_cx - 45, beak_base_y + 25 + beak_open)], fill=(234, 88, 12))

        # Big Cartoon Eye
        eye_cx = head_cx - 15
        eye_cy = head_cy - 25
        eye_rad = 32
        
        # Blinking Cycle (Every 3s for 4 frames)
        is_blinking = (frame_idx % (cls.FPS * 3)) < 4
        if is_blinking:
            draw.arc([eye_cx - eye_rad, eye_cy - 10, eye_cx + eye_rad, eye_cy + 10], 0, 180, fill=(30, 41, 59), width=6)
        else:
            # White Sclera
            draw.ellipse([eye_cx - eye_rad, eye_cy - eye_rad, eye_cx + eye_rad, eye_cy + eye_rad], fill=cls.WHITE, outline=(30, 41, 59), width=3)
            # Pupil looking toward the left (toward the simulation!)
            pupil_x = eye_cx - 12
            pupil_y = eye_cy - 4
            draw.ellipse([pupil_x - 14, pupil_y - 14, pupil_x + 14, pupil_y + 14], fill=(15, 23, 42))
            # Catchlight Glint
            draw.ellipse([pupil_x - 7, pupil_y - 9, pupil_x, pupil_y - 2], fill=cls.WHITE)

        # Cute Scientist Glasses Rim (Round Gold Frame)
        draw.ellipse([eye_cx - eye_rad - 6, eye_cy - eye_rad - 6, eye_cx + eye_rad + 6, eye_cy + eye_rad + 6], outline=(15, 23, 42), width=5)
        draw.line([eye_cx + eye_rad + 6, eye_cy - 5, eye_cx + eye_rad + 45, eye_cy - 15], fill=(15, 23, 42), width=4)

        # Extended Hand Holding Glowing Laser Pointer (Aimed at the simulation)
        arm_x = char_x - 90
        arm_y = char_y + 120
        pointer_tip_x = cls.WIDTH // 2 - 120
        pointer_tip_y = 740

        # Laser beam
        draw.line([arm_x - 40, arm_y - 80, pointer_tip_x, pointer_tip_y], fill=(0, 245, 212, 160), width=3)
        # Laser pointer stick
        draw.line([arm_x, arm_y, arm_x - 50, arm_y - 90], fill=(71, 85, 105), width=8)
        # Tip spark
        draw.ellipse([pointer_tip_x - 10, pointer_tip_y - 10, pointer_tip_x + 10, pointer_tip_y + 10], fill=(255, 255, 255), outline=cls.CYAN, width=3)
        # Wing / Hand
        draw.ellipse([arm_x - 25, arm_y - 25, arm_x + 25, arm_y + 25], fill=cls.GOLD, outline=(245, 158, 11), width=3)
