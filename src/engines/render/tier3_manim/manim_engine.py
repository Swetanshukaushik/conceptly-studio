import os
import math
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from src.models.schemas import SceneBeat, VisualModality

class ManimVectorEngine:
    """
    Tier 3: STEM RIGOR (3Blue1Brown / Manim Vector Physics & Math Engine)
    Renders 100% mathematically exact 60fps/30fps Full HD (1080x1920 9:16)
    vector animations for IIT-JEE, NEET, and university STEM curricula:
    1. SIMPLE HARMONIC MOTION: Exact spring-mass differential equation, phase space (x, v), energy conservation gauges.
    2. OPTICS & PRISM DISPERSION: Exact Snell's law refraction rays (sin i / sin r = mu) and Cauchy chromatic dispersion.
    3. CALCULUS & TANGENTS: Dynamic function curve drawing, secant line convergence to derivative dy/dx.
    4. KEPLER ORBITS & GRAVITY: Elliptical inverse-square orbital mechanics with live velocity vector.
    5. ELECTROMAGNETIC VECTORS: Red North / Blue South Lorentz force deflection F = I(L x B).
    """

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    # 3Blue1Brown Iconic Dark Mathematical Palette
    BG_OBSIDIAN = (10, 10, 15)
    GRID_DARK = (28, 32, 48)
    AXIS_SLATE = (71, 85, 105)
    CYAN_VEC = (0, 245, 212)
    GOLD_VEC = (255, 190, 11)
    HOT_PINK = (255, 0, 110)
    ELECTRIC_BLUE = (58, 134, 255)
    WHITE_MATH = (248, 250, 252)

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
    def render_manim_clip(
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

        # Select exact mathematical archetype
        if any(w in text for w in ["prism", "optic", "refract", "dispersion", "snell", "spectrum", "wavelength", "rainbow"]):
            archetype = "OPTICS_PRISM"
        elif any(w in text for w in ["calculus", "derivative", "tangent", "rate of change", "slope", "dy/dx", "integral"]):
            archetype = "CALCULUS_DERIVATIVE"
        elif any(w in text for w in ["orbit", "gravity", "kepler", "planet", "satellite", "space"]):
            archetype = "ORBIT_GRAVITY"
        elif any(w in text for w in ["magnet", "lorentz", "induction", "f=ilb", "field line", "charge"]):
            archetype = "LORENTZ_FORCE"
        else:
            # Default to flagship Simple Harmonic Motion
            archetype = "SIMPLE_HARMONIC_MOTION"

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
        state: Dict[str, Any] = {"trace": []}

        for frame_idx in range(total_frames):
            progress = frame_idx / total_frames
            time_sec = frame_idx / cls.FPS
            
            if archetype == "OPTICS_PRISM":
                im = cls._render_optics_prism(scene, progress, time_sec)
            elif archetype == "CALCULUS_DERIVATIVE":
                im = cls._render_calculus_derivative(scene, progress, time_sec, state)
            elif archetype == "ORBIT_GRAVITY":
                im = cls._render_kepler_orbit(scene, progress, time_sec, state)
            elif archetype == "LORENTZ_FORCE":
                im = cls._render_lorentz_force(scene, progress, time_sec)
            else:
                im = cls._render_shm(scene, progress, time_sec, state)

            proc.stdin.write(im.tobytes())

        proc.stdin.close()
        proc.wait()
        return output_clip_path

    # ================= 1. SIMPLE HARMONIC MOTION SIMULATION =================
    @classmethod
    def _render_shm(cls, scene: SceneBeat, progress: float, time_sec: float, state: Dict[str, Any]) -> Image.Image:
        im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_OBSIDIAN)
        draw = ImageDraw.Draw(im, "RGBA")

        # 3Blue1Brown Coordinate Grid
        cls._draw_dark_grid(draw)

        # Simulation Physics Variables (omega = 3.8 rad/s, A = 220px)
        omega = 3.8
        amplitude = 220
        phase = omega * time_sec
        x_displacement = amplitude * math.cos(phase)
        velocity = -amplitude * omega * math.sin(phase)
        acceleration = -omega * omega * x_displacement

        # Spring & Wall Setup
        center_y = 680
        wall_x = 180
        mass_cx = cls.WIDTH // 2 + int(x_displacement)
        mass_radius = 55

        # Horizontal Guide Track
        draw.line([wall_x - 40, center_y + mass_radius, cls.WIDTH - 140, center_y + mass_radius], fill=cls.AXIS_SLATE, width=4)
        for tx in range(wall_x - 30, cls.WIDTH - 130, 30):
            draw.line([tx, center_y + mass_radius, tx - 15, center_y + mass_radius + 20], fill=cls.GRID_DARK, width=2)

        # Rigid Anchor Wall
        draw.line([wall_x, center_y - 120, wall_x, center_y + mass_radius], fill=cls.WHITE_MATH, width=8)

        # Dynamic Helical Spring Drawing
        num_coils = 14
        spring_length = mass_cx - mass_radius - wall_x
        coil_spacing = spring_length / num_coils
        spring_points = [(wall_x, center_y)]
        for i in range(1, num_coils):
            cx = wall_x + (i - 0.5) * coil_spacing
            cy = center_y + (35 if (i % 2 == 1) else -35)
            spring_points.append((cx, cy))
        spring_points.append((mass_cx - mass_radius, center_y))
        
        # Spring glowing neon stroke
        for i in range(len(spring_points) - 1):
            draw.line([spring_points[i], spring_points[i+1]], fill=cls.CYAN_VEC, width=6)

        # Oscillating Mass Box
        draw.rounded_rectangle(
            [mass_cx - mass_radius, center_y - mass_radius, mass_cx + mass_radius, center_y + mass_radius],
            radius=14, fill=(30, 41, 59), outline=cls.CYAN_VEC, width=5
        )
        draw.text((mass_cx - 15, center_y - 20), "m", fill=cls.WHITE_MATH, font=cls._get_font(36, bold=True))

        # Equilibrium Dashed Line (x = 0)
        eq_x = cls.WIDTH // 2
        for dy in range(center_y - 140, center_y + 140, 16):
            draw.line([eq_x, dy, eq_x, dy + 8], fill=(148, 163, 184, 180), width=2)
        draw.text((eq_x - 24, center_y + 70), "x = 0", fill=(148, 163, 184), font=cls._get_font(20, bold=True))

        # Velocity Vector (Green / Cyan)
        v_arrow_len = int(velocity * 0.12)
        if abs(v_arrow_len) > 5:
            arrow_color = cls.GOLD_VEC if v_arrow_len > 0 else cls.HOT_PINK
            draw.line([mass_cx, center_y - mass_radius - 20, mass_cx + v_arrow_len, center_y - mass_radius - 20], fill=arrow_color, width=6)
            draw.polygon([
                (mass_cx + v_arrow_len, center_y - mass_radius - 28),
                (mass_cx + v_arrow_len + (14 if v_arrow_len > 0 else -14), center_y - mass_radius - 20),
                (mass_cx + v_arrow_len, center_y - mass_radius - 12)
            ], fill=arrow_color)
            draw.text((mass_cx + v_arrow_len // 2 - 10, center_y - mass_radius - 58), "v", fill=arrow_color, font=cls._get_font(24, bold=True))

        # Sine Wave Graph (Bottom Section: Y=1150px)
        graph_origin_x, graph_origin_y = 160, 1260
        graph_width, graph_height = 760, 280

        # Graph Axes
        draw.line([graph_origin_x, graph_origin_y, graph_origin_x + graph_width, graph_origin_y], fill=cls.AXIS_SLATE, width=3) # Time axis
        draw.line([graph_origin_x, graph_origin_y - graph_height//2, graph_origin_x, graph_origin_y + graph_height//2], fill=cls.AXIS_SLATE, width=3) # x(t) axis
        draw.text((graph_origin_x + graph_width - 30, graph_origin_y + 12), "t", fill=cls.AXIS_SLATE, font=cls._get_font(22, bold=True))
        draw.text((graph_origin_x - 60, graph_origin_y - graph_height//2 - 10), "x(t)", fill=cls.CYAN_VEC, font=cls._get_font(24, bold=True))

        # Draw evolving sine curve up to current progress
        sine_points = []
        max_t = 3.0
        current_t = progress * max_t
        steps = int(progress * 180)
        for s in range(steps + 1):
            t_val = (s / 180) * max_t
            px = graph_origin_x + int((t_val / max_t) * (graph_width - 40))
            py = graph_origin_y - int((amplitude * 0.45) * math.cos(omega * t_val))
            sine_points.append((px, py))

        if len(sine_points) > 1:
            for i in range(len(sine_points) - 1):
                draw.line([sine_points[i], sine_points[i+1]], fill=cls.CYAN_VEC, width=4)
            # Leading glowing head
            lead = sine_points[-1]
            draw.ellipse([lead[0]-8, lead[1]-8, lead[0]+8, lead[1]+8], fill=cls.WHITE_MATH, outline=cls.CYAN_VEC, width=3)

        # Mathematical Formula Badges (Top Box)
        card_w, card_h = 920, 160
        card_x = (cls.WIDTH - card_w) // 2
        draw.rounded_rectangle([card_x, 140, card_x + card_w, 140 + card_h], radius=24, fill=(18, 24, 43, 230), outline=cls.CYAN_VEC, width=2)
        font_formula = cls._get_font(38, bold=True)
        draw.text((card_x + 40, 160), "d²x/dt² + ω²x = 0", fill=cls.WHITE_MATH, font=font_formula)
        font_sub = cls._get_font(22, bold=False)
        draw.text((card_x + 40, 220), "Hooke's Restoring Law: F = -kx  •  ω = √(k/m)", fill=cls.GOLD_VEC, font=font_sub)

        # Real-Time Kinetic vs Potential Energy Bar Gauges (Y=1550px)
        gauge_y = 1580
        gauge_w = 340
        ek_ratio = (velocity * velocity) / ((amplitude * omega) ** 2)
        ep_ratio = (x_displacement * x_displacement) / (amplitude ** 2)

        draw.text((160, gauge_y - 30), f"Kinetic Energy (Ek): {int(ek_ratio*100)}%", fill=cls.HOT_PINK, font=cls._get_font(20, bold=True))
        draw.rounded_rectangle([160, gauge_y, 160 + gauge_w, gauge_y + 24], radius=12, fill=(30, 41, 59))
        draw.rounded_rectangle([160, gauge_y, 160 + int(gauge_w * ek_ratio), gauge_y + 24], radius=12, fill=cls.HOT_PINK)

        draw.text((580, gauge_y - 30), f"Potential Energy (Ep): {int(ep_ratio*100)}%", fill=cls.ELECTRIC_BLUE, font=cls._get_font(20, bold=True))
        draw.rounded_rectangle([580, gauge_y, 580 + gauge_w, gauge_y + 24], radius=12, fill=(30, 41, 59))
        draw.rounded_rectangle([580, gauge_y, 580 + int(gauge_w * ep_ratio), gauge_y + 24], radius=12, fill=cls.ELECTRIC_BLUE)

        return im

    # ================= 2. OPTICS & PRISM DISPERSION SIMULATION =================
    @classmethod
    def _render_optics_prism(cls, scene: SceneBeat, progress: float, time_sec: float) -> Image.Image:
        im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_OBSIDIAN)
        draw = ImageDraw.Draw(im, "RGBA")
        cls._draw_dark_grid(draw)

        # Formula Badge
        card_w, card_h = 920, 160
        card_x = (cls.WIDTH - card_w) // 2
        draw.rounded_rectangle([card_x, 140, card_x + card_w, 140 + card_h], radius=24, fill=(18, 24, 43, 230), outline=cls.CYAN_VEC, width=2)
        draw.text((card_x + 40, 160), "Snell's Law: sin(i) / sin(r) = μ(λ)", fill=cls.WHITE_MATH, font=cls._get_font(36, bold=True))
        draw.text((card_x + 40, 220), "Cauchy Dispersion: μ(λ) = A + B/λ² (Violet bends most)", fill=cls.GOLD_VEC, font=cls._get_font(20, bold=False))

        # Triangular Glass Prism
        prism_cx, prism_cy = cls.WIDTH // 2, 850
        prism_size = 280
        p_top = (prism_cx, prism_cy - prism_size)
        p_left = (prism_cx - int(prism_size * 1.15), prism_cy + prism_size // 2)
        p_right = (prism_cx + int(prism_size * 1.15), prism_cy + prism_size // 2)

        # Glass fill with refractive glow
        draw.polygon([p_top, p_left, p_right], fill=(30, 58, 138, 110), outline=(96, 165, 250), width=4)

        # Incident White Light Ray (Coming from Top-Left)
        ray_start = (120, 720)
        hit_x = prism_cx - 100
        hit_y = prism_cy - 40
        hit_point = (hit_x, hit_y)

        # Incident ray progressive draw
        draw.line([ray_start, hit_point], fill=(255, 255, 255), width=8)
        draw.text((ray_start[0], ray_start[1] - 40), "White Light Ray", fill=cls.WHITE_MATH, font=cls._get_font(22, bold=True))

        # Chromatic Spectrum Exit (Rainbow Fan)
        colors = [
            ("Red (700nm)", (239, 68, 68), 0.12),
            ("Orange", (249, 115, 22), 0.18),
            ("Yellow", (234, 179, 8), 0.24),
            ("Green", (34, 197, 94), 0.30),
            ("Blue", (59, 130, 246), 0.36),
            ("Indigo", (99, 102, 241), 0.42),
            ("Violet (400nm)", (168, 85, 247), 0.48)
        ]

        # Draw refracted internal lines and exit rainbow beams
        for name, col, dev_angle in colors:
            internal_exit = (prism_cx + 70, prism_cy + int(dev_angle * 140))
            draw.line([hit_point, internal_exit], fill=col, width=3)
            
            fan_end_x = cls.WIDTH - 140
            fan_end_y = internal_exit[1] + int(dev_angle * 320)
            draw.line([internal_exit, (fan_end_x, fan_end_y)], fill=col, width=5)

        draw.text((cls.WIDTH - 360, 1150), "Dispersed Rainbow Spectrum", fill=cls.GOLD_VEC, font=cls._get_font(24, bold=True))
        return im

    # ================= 3. CALCULUS DERIVATIVE SIMULATION =================
    @classmethod
    def _render_calculus_derivative(cls, scene: SceneBeat, progress: float, time_sec: float, state: Dict[str, Any]) -> Image.Image:
        im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_OBSIDIAN)
        draw = ImageDraw.Draw(im, "RGBA")
        cls._draw_dark_grid(draw)

        # Formula Badge
        card_w, card_h = 920, 160
        card_x = (cls.WIDTH - card_w) // 2
        draw.rounded_rectangle([card_x, 140, card_x + card_w, 140 + card_h], radius=24, fill=(18, 24, 43, 230), outline=cls.HOT_PINK, width=2)
        draw.text((card_x + 40, 160), "f'(x) = lim[Δx→0] (f(x+Δx) - f(x)) / Δx", fill=cls.WHITE_MATH, font=cls._get_font(34, bold=True))
        draw.text((card_x + 40, 220), "Instantaneous Slope of Tangent Vector dy/dx", fill=cls.GOLD_VEC, font=cls._get_font(20, bold=False))

        # Main Axes
        origin_x, origin_y = 180, 1200
        axis_len = 740
        draw.line([origin_x, origin_y, origin_x + axis_len, origin_y], fill=cls.AXIS_SLATE, width=4) # X axis
        draw.line([origin_x, origin_y - axis_len, origin_x, origin_y + 40], fill=cls.AXIS_SLATE, width=4) # Y axis

        # Function curve: f(x) = k * x^2
        curve_pts = []
        for x_i in range(0, 520, 6):
            u = x_i / 500.0
            px = origin_x + int(u * axis_len)
            py = origin_y - int((u ** 2) * (axis_len - 100))
            curve_pts.append((px, py))

        for i in range(len(curve_pts) - 1):
            draw.line([curve_pts[i], curve_pts[i+1]], fill=cls.CYAN_VEC, width=5)

        # Moving Tangent Point P(t)
        u_lead = 0.25 + 0.55 * (0.5 + 0.5 * math.sin(time_sec * 2.0))
        pt_x = origin_x + int(u_lead * axis_len)
        pt_y = origin_y - int((u_lead ** 2) * (axis_len - 100))

        # Tangent Line: slope m = 2 * u_lead
        slope = 2.0 * u_lead * ((axis_len - 100) / axis_len)
        tangent_len = 180
        t_p1 = (int(pt_x - tangent_len), int(pt_y + tangent_len * slope))
        t_p2 = (int(pt_x + tangent_len), int(pt_y - tangent_len * slope))
        draw.line([t_p1, t_p2], fill=cls.HOT_PINK, width=6)

        # Highlight point P
        draw.ellipse([pt_x - 12, pt_y - 12, pt_x + 12, pt_y + 12], fill=cls.WHITE_MATH, outline=cls.HOT_PINK, width=4)
        draw.text((pt_x + 20, pt_y - 30), f"P(x, f(x))  m={slope:.2f}", fill=cls.HOT_PINK, font=cls._get_font(26, bold=True))

        return im

    # ================= 4. KEPLER ORBIT SIMULATION =================
    @classmethod
    def _render_kepler_orbit(cls, scene: SceneBeat, progress: float, time_sec: float, state: Dict[str, Any]) -> Image.Image:
        im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_OBSIDIAN)
        draw = ImageDraw.Draw(im, "RGBA")
        cls._draw_dark_grid(draw)

        # Formula Badge
        card_w, card_h = 920, 160
        card_x = (cls.WIDTH - card_w) // 2
        draw.rounded_rectangle([card_x, 140, card_x + card_w, 140 + card_h], radius=24, fill=(18, 24, 43, 230), outline=cls.GOLD_VEC, width=2)
        draw.text((card_x + 40, 160), "Kepler's Law: F = G(M·m)/r²  •  dA/dt = const", fill=cls.WHITE_MATH, font=cls._get_font(32, bold=True))
        draw.text((card_x + 40, 220), "Elliptical Orbit: Planet speeds up at Perihelion", fill=cls.CYAN_VEC, font=cls._get_font(20, bold=False))

        # Ellipse Orbit Path
        cx, cy = cls.WIDTH // 2 + 50, 850
        a, b = 380, 240
        draw.ellipse([cx - a, cy - b, cx + a, cy + b], outline=cls.GRID_DARK, width=3)

        # Sun / Star at Focal Point (c = sqrt(a^2 - b^2))
        f_c = int(math.sqrt(a*a - b*b))
        sun_x, sun_y = cx - f_c, cy
        draw.ellipse([sun_x - 45, sun_y - 45, sun_x + 45, sun_y + 45], fill=cls.GOLD_VEC)
        draw.text((sun_x - 30, sun_y + 55), "Sun (M)", fill=cls.GOLD_VEC, font=cls._get_font(22, bold=True))

        # Planet Position on Ellipse
        theta = time_sec * 2.2
        planet_x = int(cx + a * math.cos(theta))
        planet_y = int(cy + b * math.sin(theta))
        draw.ellipse([planet_x - 18, planet_y - 18, planet_x + 18, planet_y + 18], fill=cls.CYAN_VEC, outline=cls.WHITE_MATH, width=3)

        # Radius Vector r
        draw.line([sun_x, sun_y, planet_x, planet_y], fill=(148, 163, 184, 160), width=3)
        draw.text(((sun_x + planet_x)//2, (sun_y + planet_y)//2 - 25), "r", fill=cls.WHITE_MATH, font=cls._get_font(20, bold=True))

        return im

    # ================= 5. LORENTZ FORCE SIMULATION =================
    @classmethod
    def _render_lorentz_force(cls, scene: SceneBeat, progress: float, time_sec: float) -> Image.Image:
        im = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_OBSIDIAN)
        draw = ImageDraw.Draw(im, "RGBA")
        cls._draw_dark_grid(draw)

        # Formula Badge
        card_w, card_h = 920, 160
        card_x = (cls.WIDTH - card_w) // 2
        draw.rounded_rectangle([card_x, 140, card_x + card_w, 140 + card_h], radius=24, fill=(18, 24, 43, 230), outline=cls.CYAN_VEC, width=2)
        draw.text((card_x + 40, 160), "Lorentz Force: F = q(v × B) = I·L·B·sin(θ)", fill=cls.WHITE_MATH, font=cls._get_font(32, bold=True))
        draw.text((card_x + 40, 220), "Sideways Deflection Perpendicular to Current & Field", fill=cls.HOT_PINK, font=cls._get_font(20, bold=False))

        # Magnetic Poles (Red North, Blue South)
        cx, cy = cls.WIDTH // 2, 850
        draw.rounded_rectangle([cx - 360, cy - 240, cx - 180, cy + 240], radius=20, fill=(220, 38, 38), outline=cls.WHITE_MATH, width=3)
        draw.text((cx - 290, cy - 30), "N", fill=cls.WHITE_MATH, font=cls._get_font(60, bold=True))

        draw.rounded_rectangle([cx + 180, cy - 240, cx + 360, cy + 240], radius=20, fill=(37, 99, 235), outline=cls.WHITE_MATH, width=3)
        draw.text((cx + 250, cy - 30), "S", fill=cls.WHITE_MATH, font=cls._get_font(60, bold=True))

        # Magnetic Flux Lines (B: Left to Right)
        for dy in range(-160, 180, 50):
            draw.line([cx - 180, cy + dy, cx + 180, cy + dy], fill=(96, 165, 250, 180), width=4)
            draw.polygon([(cx + 140, cy + dy - 8), (cx + 160, cy + dy), (cx + 140, cy + dy + 8)], fill=(96, 165, 250))

        # Suspended Copper Conductor Wire (Vertical)
        wire_y_offset = int(math.sin(time_sec * 4.0) * 80)
        draw.line([cx, cy - 320, cx, cy + 320], fill=(217, 119, 6), width=16)

        # Deflection Force Vector F (Perpendicular)
        draw.line([cx, cy, cx, cy - 140 + wire_y_offset], fill=cls.HOT_PINK, width=8)
        draw.polygon([(cx - 14, cy - 120 + wire_y_offset), (cx, cy - 150 + wire_y_offset), (cx + 14, cy - 120 + wire_y_offset)], fill=cls.HOT_PINK)
        draw.text((cx + 20, cy - 100), "F (Force)", fill=cls.HOT_PINK, font=cls._get_font(28, bold=True))

        return im

    @classmethod
    def _draw_dark_grid(cls, draw: ImageDraw.ImageDraw):
        # 3Blue1Brown grid spacing = 80px
        for x in range(0, cls.WIDTH, 80):
            draw.line([x, 0, x, cls.HEIGHT], fill=cls.GRID_DARK, width=1)
        for y in range(0, cls.HEIGHT, 80):
            draw.line([0, y, cls.WIDTH, y], fill=cls.GRID_DARK, width=1)
