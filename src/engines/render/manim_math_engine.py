import os
import math
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from src.models.schemas import SceneBeat, VisualModality

class ManimMathPhysicsEngine:
    """
    Tier 1 FREE Manim-Style Mathematical & Calculus Physics Animation Engine:
    Renders 3Blue1Brown / Manim-aesthetic vector stroke animations at 30fps Full HD (1080x1920):
    1. Kinetic Vector Stroke Drawing: Curves, parabolas, and graphs draw progressively over time.
    2. Dynamic Calculus Tangents: Tangent derivative vectors (dy/dx) tracking moving points.
    3. Coordinate Space & Grid Transformations: High-contrast dark-neon mathematical grids.
    4. Simple Harmonic Motion: Oscillating springs, phase-space traces, and kinetic/potential energy conservation.
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
        """Checks if the scene requires Manim-style mathematical calculus or graph animation."""
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()
        keywords = [
            "projectile", "trajectory", "parabola", "calculus", "derivative", "tangent line",
            "harmonic oscillator", "spring oscillation"
        ]
        return any(kw in text for kw in keywords)

    @classmethod
    def render_math_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        duration: float = 3.5
    ) -> str:
        """
        Renders a 30fps Full HD Manim-style vector animation clip piped directly to FFmpeg.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        total_frames = max(30, int(duration * cls.FPS))
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()

        if any(w in text for w in ["harmonic", "spring", "oscillation", "energy"]):
            render_func = cls._render_frame_harmonic_oscillator
        elif any(w in text for w in ["calculus", "derivative", "tangent", "rate"]):
            render_func = cls._render_frame_calculus_derivative
        else:
            render_func = cls._render_frame_projectile_motion

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

        state: Dict[str, Any] = {"trace": []}
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
            raise RuntimeError(f"Manim math animation render error: {e}")

        return output_clip_path

    # ================= 1. PROJECTILE MOTION & KINETIC VECTOR STROKE =================
    @classmethod
    def _render_frame_projectile_motion(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        # Dark 3Blue1Brown chalkboard slate
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (10, 14, 23))
        draw = ImageDraw.Draw(img)

        # Coordinate System Origin
        origin_x, origin_y = 140, 1150
        max_w, max_h = 800, 520

        # Draw Coordinate Grid Lines (3Blue1Brown Style)
        for gx in range(origin_x, origin_x + max_w + 1, 80):
            draw.line([(gx, origin_y - max_h), (gx, origin_y + 40)], fill=(22, 32, 50), width=1)
        for gy in range(origin_y - max_h, origin_y + 41, 80):
            draw.line([(origin_x - 30, gy), (origin_x + max_w, gy)], fill=(22, 32, 50), width=1)

        # Main Axes (Glowing Cyan & Slate)
        draw.line([(origin_x, origin_y + 40), (origin_x, origin_y - max_h - 20)], fill=(56, 189, 248), width=3)
        draw.line([(origin_x - 30, origin_y), (origin_x + max_w + 40, origin_y)], fill=(56, 189, 248), width=3)
        draw.text((origin_x + max_w + 20, origin_y + 12), "x (Range)", fill=(56, 189, 248), font=cls._get_font(20))
        draw.text((origin_x - 100, origin_y - max_h - 15), "y (Height)", fill=(56, 189, 248), font=cls._get_font(20))

        # Projectile Equation: Parabolic Trajectory
        # y(x) = 4 * H_max * (x/R) * (1 - x/R)
        total_steps = 120
        cur_steps = int(total_steps * min(1.0, progress * 1.15))
        points = []
        for s in range(cur_steps + 1):
            px_ratio = s / float(total_steps)
            px = origin_x + px_ratio * max_w
            py_ratio = 4.0 * px_ratio * (1.0 - px_ratio)
            py = origin_y - py_ratio * max_h
            points.append((px, py))

        # Draw Glowing Parabolic Stroke
        if len(points) >= 2:
            # Glow halo
            for i in range(1, len(points)):
                draw.line([points[i-1], points[i]], fill=(6, 95, 120), width=8)
            # Core neon line
            for i in range(1, len(points)):
                draw.line([points[i-1], points[i]], fill=(34, 211, 238), width=3)

        # Active Projectile Point & Tangent Velocity Vector
        if points:
            curr_x, curr_y = points[-1]
            # Draw moving projectile mass
            draw.ellipse([curr_x - 12, curr_y - 12, curr_x + 12, curr_y + 12], fill=(250, 204, 21), outline=(255, 255, 255), width=2)

            # Tangent Velocity Vector components
            px_ratio = cur_steps / float(total_steps)
            slope = 4.0 * (1.0 - 2.0 * px_ratio)
            vx_len = 90
            vy_len = -int(slope * 45)

            # Vector v_x (horizontal, constant, amber)
            draw.line([(curr_x, curr_y), (curr_x + vx_len, curr_y)], fill=(251, 146, 60), width=3)
            draw.text((curr_x + vx_len + 8, curr_y - 12), "v_x", fill=(251, 146, 60), font=cls._get_font(18))

            # Vector v_y (vertical, gravity affected, cyan)
            draw.line([(curr_x, curr_y), (curr_x, curr_y + vy_len)], fill=(56, 189, 248), width=3)
            draw.text((curr_x - 45, curr_y + vy_len - 10), "v_y(t)", fill=(56, 189, 248), font=cls._get_font(18))

            # Resultant Velocity Vector v
            draw.line([(curr_x, curr_y), (curr_x + vx_len, curr_y + vy_len)], fill=(16, 185, 129), width=4)
            draw.text((curr_x + vx_len + 10, curr_y + vy_len - 15), "v(t)", fill=(16, 185, 129), font=cls._get_font(20))

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 220], radius=16, fill=(18, 24, 38, 230), outline=(56, 189, 248), width=2)
        draw.text((150, 165), "📐 MANIM CALCULUS & KINEMATICS: PROJECTILE MOTION", fill=(56, 189, 248), font=cls._get_font(22))

        # Bottom Formula HUD
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 23, 42, 240), outline=(250, 204, 21), width=2)
        draw.text((115, 1365), "EQUATION: y = x · tan(θ) - (g · x²) / (2 v₀² cos²θ)", fill=(255, 255, 255), font=cls._get_font(26))
        draw.text((115, 1412), "Horizontal velocity v_x is constant; vertical acceleration a_y = -g.", fill=(156, 163, 175), font=cls._get_font(19, bold=False))

        return img

    # ================= 2. CALCULUS DERIVATIVE & TANGENT SLOPE =================
    @classmethod
    def _render_frame_calculus_derivative(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (12, 16, 26))
        draw = ImageDraw.Draw(img)

        origin_x, origin_y = 150, 1050
        scale_x, scale_y = 750, 450

        # Grid lines
        for gx in range(origin_x, origin_x + scale_x + 1, 75):
            draw.line([(gx, origin_y - scale_y), (gx, origin_y + 30)], fill=(25, 35, 55), width=1)
        for gy in range(origin_y - scale_y, origin_y + 31, 75):
            draw.line([(origin_x - 30, gy), (origin_x + scale_x), gy], fill=(25, 35, 55), width=1)

        # Coordinate axes
        draw.line([(origin_x, origin_y + 30), (origin_x, origin_y - scale_y - 20)], fill=(148, 163, 184), width=3)
        draw.line([(origin_x - 20, origin_y), (origin_x + scale_x + 30, origin_y)], fill=(148, 163, 184), width=3)

        # Cubic Function Curve: f(x) = x^3 - 3x
        steps = 100
        points = []
        for s in range(steps + 1):
            t_val = -1.8 + (3.6 * (s / float(steps)))
            fx = t_val**3 - 2.5 * t_val
            px = origin_x + int((t_val + 2.0) / 4.0 * scale_x)
            py = origin_y - int((fx + 3.0) / 6.0 * scale_y)
            points.append((px, py))

        # Draw glowing curve
        for i in range(1, len(points)):
            draw.line([points[i-1], points[i]], fill=(147, 51, 234), width=4)

        # Moving Tangent Evaluation Point
        cur_t = -1.5 + 3.0 * progress
        cur_fx = cur_t**3 - 2.5 * cur_t
        slope = 3.0 * (cur_t**2) - 2.5  # f'(x)

        pt_x = origin_x + int((cur_t + 2.0) / 4.0 * scale_x)
        pt_y = origin_y - int((cur_fx + 3.0) / 6.0 * scale_y)

        # Draw Tangent Line
        tan_len = 160
        dx = tan_len
        dy = -int(slope * (scale_y / scale_x) * tan_len * 0.8)
        draw.line([(pt_x - dx, pt_y - dy), (pt_x + dx, pt_y + dy)], fill=(234, 179, 8), width=3)

        # Highlight Point P
        draw.ellipse([pt_x - 10, pt_y - 10, pt_x + 10, pt_y + 10], fill=(255, 255, 255), outline=(234, 179, 8), width=2)
        draw.text((pt_x + 15, pt_y - 25), f"P(x, f(x)) | Slope dy/dx = {slope:+.2f}", fill=(234, 179, 8), font=cls._get_font(20))

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 220], radius=16, fill=(24, 18, 38, 230), outline=(168, 85, 247), width=2)
        draw.text((150, 165), "📈 MANIM CALCULUS: INSTANTANEOUS RATE OF CHANGE", fill=(192, 132, 252), font=cls._get_font(22))

        # Bottom Formula HUD
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(18, 14, 28, 240), outline=(168, 85, 247), width=2)
        draw.text((115, 1365), "DEFINITION: f'(x) = lim (Δx→0) [ f(x+Δx) - f(x) ] / Δx", fill=(255, 255, 255), font=cls._get_font(25))
        draw.text((115, 1412), "The tangent line represents the instantaneous slope of the function.", fill=(216, 180, 254), font=cls._get_font(19, bold=False))

        return img

    # ================= 3. SIMPLE HARMONIC OSCILLATOR & ENERGY =================
    @classmethod
    def _render_frame_harmonic_oscillator(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (14, 20, 30))
        draw = ImageDraw.Draw(img)

        # Oscillator Spring Geometry
        wall_x = 120
        track_y = 650
        draw.line([(wall_x, track_y - 80), (wall_x, track_y + 80)], fill=(100, 116, 139), width=8)

        # Motion kinematics: x(t) = A * cos(omega * t)
        omega = 2.0 * math.pi * 1.2
        t = progress * 4.0
        amplitude = 220
        mass_x = wall_x + 380 + int(amplitude * math.cos(omega * t))
        velocity = -amplitude * omega * math.sin(omega * t)

        # Draw Spring Coils
        num_coils = 14
        spring_pts = [(wall_x, track_y)]
        spring_len = mass_x - wall_x - 40
        for c in range(1, num_coils):
            cx = wall_x + int(c * (spring_len / float(num_coils)))
            cy = track_y - 25 if c % 2 == 1 else track_y + 25
            spring_pts.append((cx, cy))
        spring_pts.append((mass_x - 40, track_y))

        for i in range(1, len(spring_pts)):
            draw.line([spring_pts[i-1], spring_pts[i]], fill=(56, 189, 248), width=3)

        # Draw Mass Block
        draw.rounded_rectangle([mass_x - 40, track_y - 45, mass_x + 40, track_y + 45], radius=10, fill=(30, 58, 138), outline=(96, 165, 250), width=2)
        draw.text((mass_x - 18, track_y - 12), "M", fill=(255, 255, 255), font=cls._get_font(24))

        # Real-time Sine Wave Phase Trace (Below track)
        trace_y = 1000
        state["trace"].append((track_y, mass_x))
        if len(state["trace"]) > 60:
            state["trace"].pop(0)

        for i in range(1, len(state["trace"])):
            y_offset = (len(state["trace"]) - i) * 6
            x_pos = state["trace"][i][1]
            draw.ellipse([x_pos - 3, trace_y + y_offset - 3, x_pos + 3, trace_y + y_offset + 3], fill=(0, 240, 255))

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 220], radius=16, fill=(18, 28, 45, 230), outline=(56, 189, 248), width=2)
        draw.text((150, 165), "〰️ MANIM OSCILLATIONS: SIMPLE HARMONIC MOTION", fill=(56, 189, 248), font=cls._get_font(22))

        # Bottom Formula HUD
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 23, 42, 240), outline=(56, 189, 248), width=2)
        draw.text((115, 1365), "CONSERVATION: Total E = 1/2 k x² + 1/2 m v²", fill=(255, 255, 255), font=cls._get_font(26))
        draw.text((115, 1412), "Continuous cyclic transfer between kinetic and potential energy.", fill=(156, 163, 175), font=cls._get_font(19, bold=False))

        return img
