import os
import math
import random
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from src.models.schemas import SceneBeat, VisualModality

class PhysicsSimulationEngine:
    """
    Tier 1 FREE Dynamic Physics & Scientific Simulation Video Generator:
    Produces smooth 1080x1920 (9:16 vertical) 30fps Full HD animated physics videos
    with zero paid GPU API costs ($0.00 / reel).
    
    Simulations Supported:
    1. Rocket Propulsion & Action-Reaction (Newton's 3rd Law)
    2. Elastic & Inelastic Collisions (Conservation of Momentum)
    3. Gravitational Orbital Mechanics & Centripetal Acceleration
    4. Wave Motion, Optics & Snell's Law Refraction
    5. Cellular Biology & Chloroplast Photosynthesis Reaction
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
    def _get_font(cls, size: int) -> ImageFont.ImageFont:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @classmethod
    def should_simulate(cls, scene: SceneBeat) -> bool:
        """Determines if the scene beat represents a physical or scientific simulation with a dedicated procedural model."""
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()
        
        # 1. Optics & Prism Dispersion
        if any(w in text for w in ["prism", "dispersion", "refraction", "spectrum", "rainbow", "snell", "white light", "optics", "wavelength"]):
            return True

        # 2. Magnetism & Lorentz Force
        if any(w in text for w in ["magnet", "lorentz", "magnetic", "f=ilb", "f=i*l*b", "fleming", "conductor", "tesla", "solenoid"]):
            return True

        # 3. Rocket Propulsion & Action-Reaction (Newton's 3rd Law)
        if any(w in text for w in ["rocket", "exhaust", "propulsion", "thrust", "recoil"]) and not any(w in text for w in ["history", "bio", "cell", "prism", "light"]):
            return True

        # 4. Elastic & Inelastic Collisions / Momentum
        if any(w in text for w in ["collision", "momentum", "impact", "elastic impact"]):
            return True

        # 5. Gravitational Orbital Mechanics
        if any(w in text for w in ["orbital mechanics", "gravitation", "satellite orbit", "planetary gravity", "centripetal orbit"]):
            return True

        # 6. Cellular Biology & Photosynthesis
        if any(w in text for w in ["chloroplast", "photosynthesis", "thylakoid", "calvin cycle"]):
            return True

        return False

    @classmethod
    def render_simulation_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        duration: float = 3.5
    ) -> str:
        """
        Renders a dynamic 30fps MP4 physics simulation video clip piped directly to FFmpeg.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        total_frames = max(30, int(duration * cls.FPS))
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()

        # Route strictly to appropriate physical model
        if any(w in text for w in ["prism", "dispersion", "refraction", "spectrum", "rainbow", "snell", "white light", "optics", "wavelength"]):
            sim_func = cls._render_frame_prism_optics
        elif any(w in text for w in ["magnet", "lorentz", "magnetic", "f=ilb", "f=i*l*b", "fleming", "conductor", "tesla"]):
            sim_func = cls._render_frame_magnetism_force
        elif any(w in text for w in ["rocket", "exhaust", "propulsion", "thrust", "newton"]):
            sim_func = cls._render_frame_rocket_propulsion
        elif any(w in text for w in ["collision", "momentum", "impact", "elastic"]):
            sim_func = cls._render_frame_collision
        elif any(w in text for w in ["orbit", "gravity", "gravitation", "satellite", "planetary"]):
            sim_func = cls._render_frame_orbit
        elif any(w in text for w in ["chloroplast", "photosynthesis", "plant", "cell", "thylakoid"]):
            sim_func = cls._render_frame_photosynthesis
        else:
            sim_func = cls._render_frame_generic_schematic

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

        # Shared simulation state (particles, trajectory history, etc.)
        sim_state: Dict[str, Any] = {
            "particles": [],
            "stars": [{"x": random.randint(0, cls.WIDTH), "y": random.randint(0, cls.HEIGHT), "s": random.randint(1, 3)} for _ in range(80)],
            "seed": random.randint(1000, 9999)
        }

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for frame_idx in range(total_frames):
                progress = frame_idx / float(total_frames)
                img = sim_func(frame_idx, total_frames, progress, sim_state, scene)
                proc.stdin.write(img.tobytes())
            proc.stdin.close()
            proc.wait(timeout=60)
        except Exception as e:
            proc.kill()
            raise RuntimeError(f"Physics simulation render error: {e}")

        return output_clip_path

    # ================= 1. ROCKET PROPULSION & NEWTON'S 3RD LAW =================
    @classmethod
    def _render_frame_rocket_propulsion(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (11, 15, 25))
        draw = ImageDraw.Draw(img)

        # 1. Background Space Grid & Moving Stars (sensation of upward acceleration)
        speed = 8 + int(progress * 28)
        for star in state["stars"]:
            star["y"] = (star["y"] + speed) % cls.HEIGHT
            alpha = 150 + int(70 * math.sin(frame_idx * 0.1 + star["x"]))
            draw.ellipse([star["x"], star["y"], star["x"] + star["s"], star["y"] + star["s"]], fill=(alpha, alpha, 255))

        # Vertical altitude guide lines
        grid_offset = (frame_idx * speed * 2) % 300
        for y in range(-300 + grid_offset, cls.HEIGHT + 300, 300):
            draw.line([(140, y), (940, y)], fill=(25, 38, 60), width=1)
            draw.text((150, y + 8), f"+{(1500 - y // 2)}m", fill=(50, 75, 110), font=cls._get_font(18))

        # 2. Rocket Kinematics & Position
        # Rocket ascends slightly while camera tracks (oscillates smoothly)
        rocket_cx = cls.WIDTH // 2
        rocket_cy = int(720 - math.sin(progress * math.pi) * 60)
        nozzle_y = rocket_cy + 190

        # 3. Dynamic Exhaust Particle Emitter (Newton's Action Force)
        # Emit 18-25 new exhaust particles every frame
        for _ in range(22):
            vx = random.uniform(-4.5, 4.5)
            vy = random.uniform(18.0, 34.0)
            state["particles"].append({
                "x": rocket_cx + random.uniform(-16, 16),
                "y": nozzle_y + random.uniform(0, 10),
                "vx": vx,
                "vy": vy,
                "radius": random.uniform(8.0, 18.0),
                "life": 1.0,
                "decay": random.uniform(0.035, 0.065)
            })

        # Update and render exhaust particles
        alive_particles = []
        for p in state["particles"]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vx"] *= 0.96
            p["radius"] += 0.8  # Expands as it cools in vacuum
            p["life"] -= p["decay"]
            if p["life"] > 0 and p["y"] < cls.HEIGHT:
                alive_particles.append(p)
                life = p["life"]
                r = int(p["radius"])
                # Color gradient: White-hot -> Yellow -> Flame Orange -> Crimson -> Smoke grey
                if life > 0.8:
                    color = (255, 255, 255)
                elif life > 0.6:
                    color = (255, 230, 80)
                elif life > 0.35:
                    color = (255, 120, 20)
                elif life > 0.15:
                    color = (210, 40, 30)
                else:
                    color = (80, 85, 100)
                draw.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=color)
        state["particles"] = alive_particles

        # 4. Rocket Fuselage Graphic (Sleek Modern 9:16 Aerospace Craft)
        # Rocket Body
        body_w, body_h = 70, 260
        rx1, ry1 = rocket_cx - body_w // 2, rocket_cy - body_h // 2
        rx2, ry2 = rocket_cx + body_w // 2, rocket_cy + body_h // 2

        # Aerodynamic Cone
        draw.polygon([(rocket_cx, ry1 - 85), (rx1, ry1), (rx2, ry1)], fill=(240, 245, 255))
        # Nose cone tip glow
        draw.ellipse([rocket_cx - 6, ry1 - 88, rocket_cx + 6, ry1 - 76], fill=(0, 240, 255))

        # Main Body Cylinder
        draw.rectangle([rx1, ry1, rx2, ry2], fill=(220, 230, 245))
        # Body accent stripes & flag
        draw.rectangle([rx1, ry1 + 40, rx2, ry1 + 55], fill=(30, 58, 138))
        draw.rectangle([rx1, ry1 + 140, rx2, ry1 + 148], fill=(239, 68, 68))

        # Side Fins
        draw.polygon([(rx1, ry2 - 60), (rx1 - 45, ry2 + 20), (rx1, ry2)], fill=(180, 195, 215))
        draw.polygon([(rx2, ry2 - 60), (rx2 + 45, ry2 + 20), (rx2, ry2)], fill=(180, 195, 215))

        # Rocket Engine Bell Nozzle
        draw.polygon([(rx1 + 10, ry2), (rx2 - 10, ry2), (rx2 + 8, nozzle_y), (rx1 - 8, nozzle_y)], fill=(75, 85, 99))
        # Super-heated nozzle core
        draw.ellipse([rocket_cx - 24, nozzle_y - 6, rocket_cx + 24, nozzle_y + 12], fill=(255, 240, 150))

        # 5. DYNAMIC PHYSICS FORCE VECTORS (Newton's 3rd Law)
        # Vector A: REACTION THRUST (Upward, Cyan Neon, pulsating)
        pulse = 1.0 + 0.08 * math.sin(frame_idx * 0.4)
        v_thrust_len = int(220 * pulse)
        cls._draw_glowing_vector(
            draw,
            start=(rocket_cx, rocket_cy - 40),
            end=(rocket_cx, rocket_cy - 40 - v_thrust_len),
            color=(0, 240, 255),
            label="F_reaction = +THRUST (Rocket Accelerates UP)",
            label_side="right"
        )

        # Vector B: ACTION EXHAUST (Downward, Amber Flame, pulsating)
        v_exhaust_len = int(250 * pulse)
        cls._draw_glowing_vector(
            draw,
            start=(rocket_cx, nozzle_y + 20),
            end=(rocket_cx, nozzle_y + 20 + v_exhaust_len),
            color=(255, 184, 0),
            label="F_action = -EXHAUST (Gas Expelled DOWN)",
            label_side="right"
        )

        # 6. Educational HUD Badges (Top & Bottom Safe Zones Respected)
        # Top Header Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 215], radius=16, fill=(18, 24, 38, 230), outline=(0, 240, 255), width=2)
        font_badge = cls._get_font(26)
        draw.text((150, 162), "⚡ DYNAMIC PHYSICS SIMULATION: NEWTON'S 3RD LAW", fill=(0, 240, 255), font=font_badge)

        # Telemetry Box (Left)
        draw.rounded_rectangle([80, 240, 380, 360], radius=12, fill=(15, 23, 42, 210), outline=(59, 130, 246), width=1)
        font_sub = cls._get_font(20)
        altitude = 12400 + int(progress * 42000)
        mach = 2.4 + progress * 5.2
        draw.text((100, 255), f"ALTITUDE: {altitude:,} m", fill=(240, 240, 250), font=font_sub)
        draw.text((100, 288), f"VELOCITY: Mach {mach:.1f}", fill=(56, 189, 248), font=font_sub)
        draw.text((100, 321), "EXHAUST VELOCITY: 2,800 m/s", fill=(251, 191, 36), font=cls._get_font(18))

        # Mathematical Law Card (Bottom HUD above subtitles zone)
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 23, 42, 240), outline=(234, 179, 8), width=2)
        font_eq = cls._get_font(30)
        draw.text((115, 1365), "LAW: F_action = - F_reaction", fill=(255, 255, 255), font=font_eq)
        draw.text((115, 1412), "Mass of gas expelled downwards creates equal upward momentum.", fill=(156, 163, 175), font=cls._get_font(20))

        return img

    # ================= 2. CONSERVATION OF MOMENTUM & COLLISION =================
    @classmethod
    def _render_frame_collision(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (15, 20, 35))
        draw = ImageDraw.Draw(img)

        # Center line runway
        track_y = 850
        draw.line([(60, track_y), (cls.WIDTH - 60, track_y)], fill=(50, 65, 95), width=3)
        # Coordinate ticks
        for x in range(100, cls.WIDTH - 80, 80):
            draw.line([(x, track_y - 12), (x, track_y + 12)], fill=(70, 85, 120), width=2)

        # Collision physics timing
        impact_t = 0.45
        m1, m2 = 3.0, 1.5  # Mass 1 (Heavy) & Mass 2 (Light)
        v1_init, v2_init = 6.0, -7.0  # Initial velocities

        # Rebound velocities (Elastic collision formula)
        v1_final = ((m1 - m2) * v1_init + 2 * m2 * v2_init) / (m1 + m2)
        v2_final = ((m2 - m1) * v2_init + 2 * m1 * v1_init) / (m1 + m2)

        impact_x = cls.WIDTH // 2
        r1, r2 = 65, 45  # Radii

        if progress < impact_t:
            # Approaching
            sub_p = progress / impact_t
            x1 = int(140 + sub_p * (impact_x - r1 - 140))
            x2 = int((cls.WIDTH - 140) - sub_p * (cls.WIDTH - 140 - (impact_x + r2)))
            v1_cur, v2_cur = v1_init, v2_init
            deform = 0
            is_impact = False
        else:
            # Rebounding
            sub_p = (progress - impact_t) / (1.0 - impact_t)
            is_impact = (progress - impact_t) < 0.08
            deform = int(14 * math.exp(-(progress - impact_t) * 15))
            x1 = int((impact_x - r1) + sub_p * v1_final * 35)
            x2 = int((impact_x + r2) + sub_p * v2_final * 35)
            v1_cur, v2_cur = v1_final, v2_final

        # Impact Shockwave Ring & Sparks
        if progress >= impact_t:
            impact_age = (progress - impact_t) * 18
            shock_r = int(impact_age * 45)
            alpha_shock = max(0, int(255 - impact_age * 30))
            if shock_r > 0 and alpha_shock > 0:
                draw.ellipse([impact_x - shock_r, track_y - shock_r, impact_x + shock_r, track_y + shock_r], outline=(alpha_shock, alpha_shock, 255), width=4)

        # Draw Mass 1 (Cyan Body)
        draw.ellipse([x1 - r1 + deform, track_y - r1, x1 + r1 - deform, track_y + r1], fill=(6, 182, 212), outline=(255, 255, 255), width=3)
        draw.text((x1 - 25, track_y - 12), f"m₁={m1:.1f}kg", fill=(255, 255, 255), font=cls._get_font(20))

        # Draw Mass 2 (Orange Body)
        draw.ellipse([x2 - r2 + deform, track_y - r2, x2 + r2 - deform, track_y + r2], fill=(249, 115, 22), outline=(255, 255, 255), width=3)
        draw.text((x2 - 25, track_y - 12), f"m₂={m2:.1f}kg", fill=(255, 255, 255), font=cls._get_font(20))

        # Dynamic Velocity Vectors
        cls._draw_glowing_vector(draw, (x1, track_y - r1 - 30), (int(x1 + v1_cur * 22), track_y - r1 - 30), (34, 211, 238), f"v₁={v1_cur:+.1f} m/s", "top")
        cls._draw_glowing_vector(draw, (x2, track_y - r2 - 30), (int(x2 + v2_cur * 22), track_y - r2 - 30), (251, 146, 60), f"v₂={v2_cur:+.1f} m/s", "top")

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 215], radius=16, fill=(18, 24, 38, 230), outline=(6, 182, 212), width=2)
        draw.text((150, 162), "💥 CONSERVATION OF LINEAR MOMENTUM", fill=(6, 182, 212), font=cls._get_font(26))

        # Mathematical Formula Card
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 23, 42, 240), outline=(56, 189, 248), width=2)
        draw.text((115, 1365), "LAW: m₁v₁ + m₂v₂ = m₁v₁' + m₂v₂'", fill=(255, 255, 255), font=cls._get_font(30))
        p_total = m1 * v1_init + m2 * v2_init
        draw.text((115, 1412), f"Total Momentum p = {p_total:+.1f} kg·m/s (Conserved across impact)", fill=(156, 163, 175), font=cls._get_font(20))

        return img

    # ================= 3. ORBITAL MECHANICS & CENTRIPETAL GRAVITY =================
    @classmethod
    def _render_frame_orbit(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (8, 12, 22))
        draw = ImageDraw.Draw(img)

        center_x, center_y = cls.WIDTH // 2, 800
        orbit_rx, orbit_ry = 360, 220  # Elliptical orbit axes

        # Concentric Gravitational Field Lines
        for r_scale in [0.4, 0.7, 1.0, 1.35]:
            gx1, gy1 = center_x - int(orbit_rx * r_scale), center_y - int(orbit_ry * r_scale)
            gx2, gy2 = center_x + int(orbit_rx * r_scale), center_y + int(orbit_ry * r_scale)
            draw.ellipse([gx1, gy1, gx2, gy2], outline=(30, 45, 70), width=1)

        # Central Celestial Body (Earth / Massive Center)
        earth_r = 75
        # Atmosphere glow
        draw.ellipse([center_x - earth_r - 18, center_y - earth_r - 18, center_x + earth_r + 18, center_y + earth_r + 18], fill=(15, 55, 110))
        draw.ellipse([center_x - earth_r, center_y - earth_r, center_x + earth_r, center_y + earth_r], fill=(30, 100, 180), outline=(100, 200, 255), width=2)
        draw.text((center_x - 30, center_y - 12), "MASS M", fill=(240, 240, 255), font=cls._get_font(20))

        # Orbiting Satellite Position
        theta = progress * 2 * math.pi
        sat_x = int(center_x + orbit_rx * math.cos(theta))
        sat_y = int(center_y + orbit_ry * math.sin(theta))

        # Orbital Trail
        trail = state.setdefault("orbit_trail", [])
        trail.append((sat_x, sat_y))
        if len(trail) > 40: trail.pop(0)
        for i in range(1, len(trail)):
            alpha = int(255 * (i / len(trail)))
            draw.line([trail[i-1], trail[i]], fill=(alpha // 2, alpha, 255), width=3)

        # Satellite Craft
        draw.ellipse([sat_x - 16, sat_y - 16, sat_x + 16, sat_y + 16], fill=(245, 245, 255), outline=(0, 240, 255), width=2)
        draw.rectangle([sat_x - 36, sat_y - 4, sat_x - 18, sat_y + 4], fill=(59, 130, 246)) # Solar panel L
        draw.rectangle([sat_x + 18, sat_y - 4, sat_x + 36, sat_y + 4], fill=(59, 130, 246)) # Solar panel R

        # Velocity Vector v (Tangent to orbit)
        tangent_dx = -orbit_rx * math.sin(theta)
        tangent_dy = orbit_ry * math.cos(theta)
        t_mag = math.sqrt(tangent_dx**2 + tangent_dy**2) + 1e-5
        v_arrow_len = 120
        v_end_x = int(sat_x + (tangent_dx / t_mag) * v_arrow_len)
        v_end_y = int(sat_y + (tangent_dy / t_mag) * v_arrow_len)
        cls._draw_glowing_vector(draw, (sat_x, sat_y), (v_end_x, v_end_y), (16, 185, 129), "v_tangent", "top")

        # Centripetal Gravitational Vector F_g (Points directly to center M)
        rad_dx = center_x - sat_x
        rad_dy = center_y - sat_y
        r_mag = math.sqrt(rad_dx**2 + rad_dy**2) + 1e-5
        fg_arrow_len = 130
        fg_end_x = int(sat_x + (rad_dx / r_mag) * fg_arrow_len)
        fg_end_y = int(sat_y + (rad_dy / r_mag) * fg_arrow_len)
        cls._draw_glowing_vector(draw, (sat_x, sat_y), (fg_end_x, fg_end_y), (6, 182, 212), "F_gravity = G·(M·m)/r²", "bottom")

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 215], radius=16, fill=(18, 24, 38, 230), outline=(16, 185, 129), width=2)
        draw.text((150, 162), "🌌 ORBITAL MECHANICS & CENTRIPETAL ACCELERATION", fill=(16, 185, 129), font=cls._get_font(24))

        # Bottom Formula HUD
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 23, 42, 240), outline=(16, 185, 129), width=2)
        draw.text((115, 1365), "EQUILIBRIUM: F_gravity = m · v² / r", fill=(255, 255, 255), font=cls._get_font(30))
        draw.text((115, 1412), "Continuous free-fall: gravitational pull bends path into a stable closed orbit.", fill=(156, 163, 175), font=cls._get_font(19))

        return img

    # ================= 4. CELLULAR BIOLOGY / CHLOROPLAST REACTION =================
    @classmethod
    def _render_frame_photosynthesis(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (8, 24, 16))
        draw = ImageDraw.Draw(img)

        # Chloroplast Double Membrane Outline
        cx, cy = cls.WIDTH // 2, 780
        draw.ellipse([cx - 440, cy - 300, cx + 440, cy + 300], fill=(12, 45, 25), outline=(34, 197, 94), width=4)
        draw.ellipse([cx - 425, cy - 285, cx + 425, cy + 285], fill=(16, 55, 32), outline=(74, 222, 128), width=2)

        # Thylakoid Grana Stacks
        for stack_x in [cx - 240, cx - 80, cx + 80, cx + 240]:
            for disk_y in range(cy - 120, cy + 140, 45):
                draw.rounded_rectangle([stack_x - 60, disk_y - 15, stack_x + 60, disk_y + 15], radius=10, fill=(22, 101, 52), outline=(134, 239, 172), width=2)

        # Incoming Sunlight Photon Packets (h·ν)
        photon_y = int(280 + progress * 400)
        for px in [cx - 200, cx, cx + 200]:
            draw.line([(px, photon_y - 40), (px, photon_y + 20)], fill=(253, 224, 71), width=4)
            draw.ellipse([px - 10, photon_y + 12, px + 10, photon_y + 32], fill=(255, 255, 150))
            draw.text((px + 16, photon_y), "Photon (h·ν)", fill=(254, 240, 138), font=cls._get_font(18))

        # Splitting Water Molecule (H2O -> 2H+ + 1/2 O2 + 2e-)
        rx, ry = cx, cy + 20
        draw.rounded_rectangle([rx - 160, ry - 35, rx + 160, ry + 35], radius=14, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
        draw.text((rx - 140, ry - 14), "PHOTOSYSTEM II: 2 H₂O → O₂ + 4H⁺ + 4e⁻", fill=(125, 211, 252), font=cls._get_font(17))

        # Streaming Electrons (cyan particle stream)
        e_stream_x = int(cx - 140 + (progress * 6) % 1 * 280)
        draw.ellipse([e_stream_x - 8, ry - 50, e_stream_x + 8, ry - 34], fill=(0, 240, 255))
        draw.text((e_stream_x - 6, ry - 75), "e⁻", fill=(0, 240, 255), font=cls._get_font(20))

        # Top Badge
        draw.rounded_rectangle([120, 140, cls.WIDTH - 120, 215], radius=16, fill=(18, 38, 24, 230), outline=(34, 197, 94), width=2)
        draw.text((150, 162), "🌱 BIOLOGICAL MECHANISM: PHOTOSYNTHESIS (THYLAKOID)", fill=(74, 222, 128), font=cls._get_font(22))

        # Bottom Formula HUD
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1470], radius=18, fill=(15, 30, 20, 240), outline=(34, 197, 94), width=2)
        draw.text((115, 1365), "OVERALL: 6 CO₂ + 6 H₂O + Light → C₆H₁₂O₆ + 6 O₂", fill=(255, 255, 255), font=cls._get_font(26))
        draw.text((115, 1412), "Water molecules are photolyzed to release oxygen and generate ATP & NADPH.", fill=(187, 247, 208), font=cls._get_font(19))

        return img

    # ================= HELPER: GLOWING VECTOR ARROW =================
    @classmethod
    def _draw_glowing_vector(
        cls,
        draw: ImageDraw.Draw,
        start: Tuple[int, int],
        end: Tuple[int, int],
        color: Tuple[int, int, int],
        label: str,
        label_side: str = "right"
    ) -> None:
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        mag = math.sqrt(dx**2 + dy**2) + 1e-5
        ux, uy = dx / mag, dy / mag

        # Glow halo
        draw.line([start, end], fill=(color[0] // 3, color[1] // 3, color[2] // 3), width=9)
        # Core vector line
        draw.line([start, end], fill=color, width=4)

        # Arrowhead
        head_len = 22
        hx1 = ex - head_len * ux + head_len * 0.45 * uy
        hy1 = ey - head_len * uy - head_len * 0.45 * ux
        hx2 = ex - head_len * ux - head_len * 0.45 * uy
        hy2 = ey - head_len * uy + head_len * 0.45 * ux
        draw.polygon([(ex, ey), (int(hx1), int(hy1)), (int(hx2), int(hy2))], fill=color)

        # Label typography
        font = cls._get_font(20)
        lx, ly = (sx + ex) // 2, (sy + ey) // 2
        if label_side == "right":
            lx += 25
        elif label_side == "left":
            lx -= 200
        elif label_side == "top":
            ly -= 35
        else:
            ly += 25
        draw.text((lx, ly), label, fill=color, font=font)

    # ================= 6. MAGNETIC FORCE ON CONDUCTOR (F = I L B) & LORENTZ FORCE =================
    @classmethod
    def _render_frame_magnetism_force(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (10, 14, 26))
        draw = ImageDraw.Draw(img)

        # 1. Subtle Background Grid
        for y in range(100, cls.HEIGHT - 100, 120):
            draw.line([(60, y), (cls.WIDTH - 60, y)], fill=(18, 28, 48), width=1)
        for x in range(60, cls.WIDTH - 60, 120):
            draw.line([(x, 100), (x, cls.HEIGHT - 100)], fill=(18, 28, 48), width=1)

        # 2. Permanent Magnetic Poles (North - Left / South - Right)
        pole_y = 820
        pole_h = 420
        pole_w = 170

        # North Pole (Left) - Vibrant Crimson Red
        n_x1, n_y1 = 80, pole_y - pole_h // 2
        n_x2, n_y2 = 80 + pole_w, pole_y + pole_h // 2
        # Metallic Bevel
        draw.rectangle([n_x1 - 6, n_y1 - 6, n_x2 + 6, n_y2 + 6], fill=(40, 15, 20))
        draw.rectangle([n_x1, n_y1, n_x2, n_y2], fill=(225, 45, 55))
        # Highlight stripe
        draw.rectangle([n_x2 - 14, n_y1, n_x2, n_y2], fill=(255, 100, 110))
        font_pole = cls._get_font(90)
        draw.text((n_x1 + 45, pole_y - 55), "N", fill=(255, 255, 255), font=font_pole)
        draw.text((n_x1 + 25, pole_y + 130), "NORTH POLE", fill=(255, 200, 200), font=cls._get_font(18))

        # South Pole (Right) - Deep Electric Blue
        s_x1, s_y1 = cls.WIDTH - 80 - pole_w, pole_y - pole_h // 2
        s_x2, s_y2 = cls.WIDTH - 80, pole_y + pole_h // 2
        draw.rectangle([s_x1 - 6, s_y1 - 6, s_x2 + 6, s_y2 + 6], fill=(15, 25, 50))
        draw.rectangle([s_x1, s_y1, s_x2, s_y2], fill=(35, 110, 235))
        draw.rectangle([s_x1, s_y1, s_x1 + 14, s_y2], fill=(90, 160, 255))
        draw.text((s_x1 + 45, pole_y - 55), "S", fill=(255, 255, 255), font=font_pole)
        draw.text((s_x1 + 25, pole_y + 130), "SOUTH POLE", fill=(200, 220, 255), font=cls._get_font(18))

        # 3. Magnetic Field Lines (B-Field: North -> South)
        gap_start_x = n_x2
        gap_end_x = s_x1
        gap_width = gap_end_x - gap_start_x
        
        for idx, line_y in enumerate(range(pole_y - 160, pole_y + 180, 40)):
            # Glow halo line
            draw.line([(gap_start_x, line_y), (gap_end_x, line_y)], fill=(0, 60, 90), width=3)
            draw.line([(gap_start_x, line_y), (gap_end_x, line_y)], fill=(0, 220, 255), width=2)
            
            # Animated moving flux arrows
            arrow_offset = (frame_idx * 5 + idx * 75) % gap_width
            ax = gap_start_x + arrow_offset
            draw.polygon([(ax, line_y - 6), (ax + 12, line_y), (ax, line_y + 6)], fill=(0, 240, 255))

        draw.text((cls.WIDTH // 2 - 120, pole_y - 195), "MAGNETIC FLUX DENSITY  B →", fill=(0, 230, 255), font=cls._get_font(18))

        # 4. Conducting Copper Rod with Dynamic Deflection
        wire_center_x = cls.WIDTH // 2
        # Wire oscillates and swings upward/outward under Lorentz force
        deflection_amp = 85.0 * math.sin(progress * math.pi)
        deflected_y_offset = -int(deflection_amp)

        wire_top_y = pole_y - 320
        wire_bot_y = pole_y + 320
        wire_radius = 24

        # Wire leads / supports
        draw.line([(wire_center_x, 340), (wire_center_x, wire_top_y + deflected_y_offset)], fill=(120, 130, 150), width=4)
        draw.line([(wire_center_x, wire_bot_y + deflected_y_offset), (wire_center_x, 1300)], fill=(120, 130, 150), width=4)

        # Wire Rod with metallic gradient
        wy1 = wire_top_y + deflected_y_offset
        wy2 = wire_bot_y + deflected_y_offset
        draw.rectangle([wire_center_x - wire_radius, wy1, wire_center_x + wire_radius, wy2], fill=(210, 120, 50))
        # Specular copper highlight
        draw.rectangle([wire_center_x - 6, wy1, wire_center_x + 6, wy2], fill=(255, 195, 130))
        # End caps
        draw.ellipse([wire_center_x - wire_radius, wy1 - 10, wire_center_x + wire_radius, wy1 + 10], fill=(240, 150, 70))
        draw.ellipse([wire_center_x - wire_radius, wy2 - 10, wire_center_x + wire_radius, wy2 + 10], fill=(160, 80, 30))

        # 5. Electron Drift / Electric Current Particles (I)
        for i in range(16):
            p_y = wy1 + ((frame_idx * 7 + i * 40) % (wy2 - wy1))
            draw.ellipse([wire_center_x - 7, p_y - 7, wire_center_x + 7, p_y + 7], fill=(255, 230, 70))
            draw.line([(wire_center_x, p_y), (wire_center_x, p_y - 18)], fill=(255, 200, 40), width=3)

        # 6. DYNAMIC 3D VECTOR TRIAD (Fleming's Left-Hand Rule)
        core_node = (wire_center_x, (wy1 + wy2) // 2)

        # Vector 1: Magnetic Field B (Right, Cyan)
        b_len = 160
        cls._draw_glowing_vector(
            draw,
            start=core_node,
            end=(core_node[0] + b_len, core_node[1]),
            color=(0, 240, 255),
            label="B (1.20 Tesla →)",
            label_side="top"
        )

        # Vector 2: Current I (Upward, Gold)
        i_len = 170
        cls._draw_glowing_vector(
            draw,
            start=core_node,
            end=(core_node[0], core_node[1] - i_len),
            color=(255, 215, 0),
            label="I (4.50 A ↑)",
            label_side="left"
        )

        # Vector 3: Lorentz Force F = I L B (Deflecting Outward Resultant, Neon Lime/Green)
        f_pulse = 1.0 + 0.15 * math.sin(frame_idx * 0.3)
        f_len = int(220 * (0.6 + 0.4 * math.sin(progress * math.pi)) * f_pulse)
        cls._draw_glowing_vector(
            draw,
            start=core_node,
            end=(core_node[0] - int(f_len * 0.707), core_node[1] - int(f_len * 0.707)),
            color=(0, 255, 170),
            label="F_lorentz = 3.51 N [OUTWARD]",
            label_side="left"
        )

        # 7. Real-Time Telemetry & Parameter HUD
        # Top Header Pill
        draw.rounded_rectangle([100, 130, cls.WIDTH - 100, 210], radius=16, fill=(16, 24, 40, 230), outline=(0, 240, 255), width=2)
        font_badge = cls._get_font(24)
        draw.text((130, 155), "⚡ LORENTZ FORCE ENGINE: F = I · L · B · sin(θ)", fill=(0, 240, 255), font=font_badge)

        # Telemetry Card (Left Upper)
        draw.rounded_rectangle([80, 235, 430, 385], radius=14, fill=(14, 22, 38, 220), outline=(59, 130, 246), width=1)
        font_sub = cls._get_font(20)
        draw.text((105, 252), "CURRENT (I): 4.50 Amperes", fill=(255, 215, 0), font=font_sub)
        draw.text((105, 282), "FIELD (B): 1.20 Tesla (Uniform)", fill=(0, 230, 255), font=font_sub)
        draw.text((105, 312), "WIRE LENGTH (L): 0.65 Meters", fill=(240, 240, 250), font=font_sub)
        draw.text((105, 342), "ANGLE (θ): 90.0° [MAXIMUM FORCE]", fill=(0, 255, 170), font=font_sub)

        # Fleming's Rule Card (Right Upper)
        draw.rounded_rectangle([cls.WIDTH - 440, 235, cls.WIDTH - 80, 385], radius=14, fill=(14, 22, 38, 220), outline=(16, 185, 129), width=1)
        draw.text((cls.WIDTH - 420, 252), "FLEMING'S LEFT-HAND RULE", fill=(0, 255, 170), font=cls._get_font(18))
        draw.text((cls.WIDTH - 420, 282), "• THUMB: Force (F) [Deflection]", fill=(240, 240, 250), font=cls._get_font(16))
        draw.text((cls.WIDTH - 420, 312), "• FOREFINGER: Field (B) [N → S]", fill=(0, 230, 255), font=cls._get_font(16))
        draw.text((cls.WIDTH - 420, 342), "• MIDDLE FINGER: Current (I)", fill=(255, 215, 0), font=cls._get_font(16))

        # Bottom Formula Spotlight Card (Above Safe Zone for Subtitles)
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1475], radius=18, fill=(15, 23, 42, 240), outline=(234, 179, 8), width=2)
        font_eq = cls._get_font(30)
        draw.text((115, 1362), "F = (4.50 A) × (0.65 m) × (1.20 T) × sin(90°) = 3.51 N", fill=(255, 255, 255), font=font_eq)
        draw.text((115, 1414), "Sideways magnetic deflecting force drives Maglev trains & electric motors.", fill=(156, 163, 175), font=cls._get_font(20))

        return img

    # ================= 7. OPTICS: TRIANGULAR PRISM DISPERSION & SPECTRUM =================
    @classmethod
    def _render_frame_prism_optics(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (10, 14, 24))
        draw = ImageDraw.Draw(img)

        # 1. Optical Bench Dark Gradient Background
        for y in range(0, cls.HEIGHT, 4):
            ratio = y / float(cls.HEIGHT)
            r = int(8 + ratio * 8)
            g = int(12 + ratio * 10)
            b = int(22 + ratio * 18)
            draw.rectangle([(0, y), (cls.WIDTH, y + 4)], fill=(r, g, b))

        # Ambient optical laboratory bench grid (subtle)
        for gx in range(60, cls.WIDTH, 120):
            draw.line([(gx, 220), (gx, 1340)], fill=(20, 28, 45), width=1)
        for gy in range(220, 1340, 120):
            draw.line([(60, gy), (cls.WIDTH - 60, gy)], fill=(20, 28, 45), width=1)

        # Center of Optics Stage
        cx, cy = cls.WIDTH // 2, 720

        # 2. Triangular Glass Prism (Apex at top, equilateral geometry)
        apex = (cx, cy - 240)
        p_left = (cx - 260, cy + 200)
        p_right = (cx + 260, cy + 200)

        # Glass Body with Refraction Glow
        draw.polygon([apex, p_left, p_right], fill=(18, 32, 54, 220), outline=(56, 189, 248), width=4)
        # Glass Bevel & Internal Refraction Highlights
        draw.line([(apex[0], apex[1] + 25), (p_left[0] + 35, p_left[1] - 15)], fill=(125, 211, 252), width=2)
        draw.line([(apex[0], apex[1] + 25), (p_right[0] - 35, p_right[1] - 15)], fill=(56, 189, 248), width=1)
        draw.text((cx - 65, cy + 120), "GLASS (n ≈ 1.52)", fill=(148, 163, 184), font=cls._get_font(20))

        # 3. Incident White Light Ray (from Left to Left Face of Prism)
        src_x, src_y = 60, cy - 50
        hit_x = int(cx - 130)
        hit_y = int(cy - 20)

        # Draw intense incident white light beam with soft glow
        draw.line([(src_x, src_y), (hit_x, hit_y)], fill=(120, 180, 255), width=14)
        draw.line([(src_x, src_y), (hit_x, hit_y)], fill=(220, 240, 255), width=8)
        draw.line([(src_x, src_y), (hit_x, hit_y)], fill=(255, 255, 255), width=4)
        draw.text((80, cy - 90), "INCIDENT WHITE LIGHT (Polychromatic)", fill=(255, 255, 255), font=cls._get_font(20))

        # Dynamic photons moving along incident beam
        pulse_phase = (frame_idx * 0.12) % 1.0
        for p_offset in [0.1, 0.4, 0.7]:
            px = int(src_x + (hit_x - src_x) * ((pulse_phase + p_offset) % 1.0))
            py = int(src_y + (hit_y - src_y) * ((pulse_phase + p_offset) % 1.0))
            draw.ellipse([(px - 6, py - 6), (px + 6, py + 6)], fill=(255, 255, 255))

        # Interface Normal Line at Incidence
        draw.line([(hit_x - 35, hit_y - 70), (hit_x + 35, hit_y + 70)], fill=(100, 116, 139), width=2)
        draw.text((hit_x - 55, hit_y - 95), "Normal", fill=(148, 163, 184), font=cls._get_font(18))

        # 4. Seven Spectral Rainbow Color Bands (Red to Violet)
        # In real physics: Red (700nm, n=1.513) bends LEAST; Violet (400nm, n=1.532) bends MOST
        spectrum = [
            ("Red", "700 nm", (255, 59, 48), -75, 0),
            ("Orange", "620 nm", (255, 149, 0), -45, 1),
            ("Yellow", "580 nm", (255, 204, 0), -15, 2),
            ("Green", "530 nm", (52, 199, 89), 18, 3),
            ("Blue", "470 nm", (0, 199, 255), 52, 4),
            ("Indigo", "430 nm", (88, 86, 214), 85, 5),
            ("Violet", "400 nm", (175, 82, 222), 120, 6)
        ]

        screen_x = cls.WIDTH - 90

        for col_name, wl, rgb, dev_delta, idx in spectrum:
            exit_x = cx + 130
            exit_y = cy - 20 + int(idx * 7)

            # Ray INSIDE the prism (slight fanning inside glass)
            draw.line([(hit_x, hit_y), (exit_x, exit_y)], fill=rgb, width=3)

            # Emergent ray leaving right face to projection screen (wide fanning)
            target_y = cy + 20 + dev_delta * 2

            # Outer soft glow ray
            draw.line([(exit_x, exit_y), (screen_x, target_y)], fill=(rgb[0] // 3, rgb[1] // 3, rgb[2] // 3), width=10)
            # Core spectral ray
            draw.line([(exit_x, exit_y), (screen_x, target_y)], fill=rgb, width=4)

            # Photon wave packets traversing emerging ray
            ray_phase = (frame_idx * 0.15 + idx * 0.1) % 1.0
            rpx = int(exit_x + (screen_x - exit_x) * ray_phase)
            rpy = int(exit_y + (target_y - exit_y) * ray_phase)
            draw.ellipse([(rpx - 4, rpy - 4), (rpx + 4, rpy + 4)], fill=(255, 255, 255))

            # Spectral band on screen
            draw.line([(screen_x, target_y - 12), (screen_x, target_y + 12)], fill=rgb, width=10)

        # 5. Projection Screen (White frosted glass detector)
        draw.rounded_rectangle([(screen_x - 6, cy - 160), (screen_x + 18, cy + 300)], radius=8, fill=(240, 245, 255), outline=(148, 163, 184), width=2)
        draw.text((screen_x - 140, cy - 195), "DETECTOR SCREEN", fill=(203, 213, 225), font=cls._get_font(18))

        # Wavelength label callouts on right
        draw.text((screen_x - 130, cy - 130), "Red: 700nm (Least bent)", fill=(255, 99, 88), font=cls._get_font(16))
        draw.text((screen_x - 130, cy + 265), "Violet: 400nm (Most bent)", fill=(195, 122, 242), font=cls._get_font(16))

        # 6. Telemetry & Science HUD
        # Top Header Pill
        draw.rounded_rectangle([80, 130, cls.WIDTH - 80, 210], radius=16, fill=(16, 24, 40, 230), outline=(56, 189, 248), width=2)
        draw.text((110, 155), "🌈 OPTICS: DISPERSION OF WHITE LIGHT THROUGH PRISM", fill=(56, 189, 248), font=cls._get_font(24))

        # Telemetry Card (Left Upper)
        draw.rounded_rectangle([80, 235, 450, 405], radius=14, fill=(14, 22, 38, 220), outline=(56, 189, 248), width=1)
        font_sub = cls._get_font(18)
        draw.text((105, 252), "REFRACTIVE INDEX: n(λ) = A + B/λ²", fill=(255, 215, 0), font=font_sub)
        draw.text((105, 282), "CAUCHY RELATION: n(violet) > n(red)", fill=(125, 211, 252), font=font_sub)
        draw.text((105, 312), "SPEED IN GLASS: v = c / n(λ)", fill=(240, 240, 250), font=font_sub)
        draw.text((105, 342), "ANGLE OF DEVIATION: δ = (n - 1) · A", fill=(52, 199, 89), font=font_sub)
        draw.text((105, 372), "SPECTRUM: V - I - B - G - Y - O - R", fill=(175, 82, 222), font=font_sub)

        # Bottom Educational Keynote Card
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1475], radius=18, fill=(15, 23, 42, 240), outline=(56, 189, 248), width=2)
        font_eq = cls._get_font(26)
        draw.text((115, 1362), "White light contains all visible wavelengths.", fill=(255, 255, 255), font=font_eq)
        draw.text((115, 1412), "Different colors travel at different speeds in glass, causing them to bend at different angles.", fill=(186, 230, 253), font=cls._get_font(18))

        return img

    # ================= 8. DYNAMIC GENERAL CONCEPT SCHEMATIC =================
    @classmethod
    def _render_frame_generic_schematic(
        cls,
        frame_idx: int,
        total_frames: int,
        progress: float,
        state: Dict[str, Any],
        scene: SceneBeat
    ) -> Image.Image:
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (12, 18, 30))
        draw = ImageDraw.Draw(img)

        # Dark sleek background with grid
        for y in range(0, cls.HEIGHT, 8):
            r = int(10 + (y / cls.HEIGHT) * 10)
            g = int(14 + (y / cls.HEIGHT) * 14)
            b = int(24 + (y / cls.HEIGHT) * 22)
            draw.rectangle([(0, y), (cls.WIDTH, y + 8)], fill=(r, g, b))

        # Dynamic floating particle field
        cx, cy = cls.WIDTH // 2, 700
        for i in range(12):
            angle = (frame_idx * 0.05 + i * (2 * math.pi / 12)) % (2 * math.pi)
            rad = 220 + 40 * math.sin(frame_idx * 0.1 + i)
            px = int(cx + rad * math.cos(angle))
            py = int(cy + rad * math.sin(angle))
            draw.ellipse([(px - 8, py - 8), (px + 8, py + 8)], fill=(56, 189, 248))
            draw.line([(cx, cy), (px, py)], fill=(30, 48, 76), width=1)

        # Center core schematic node
        draw.ellipse([(cx - 120, cy - 120), (cx + 120, cy + 120)], fill=(20, 32, 54), outline=(56, 189, 248), width=3)
        draw.ellipse([(cx - 70, cy - 70), (cx + 70, cy + 70)], fill=(30, 48, 80), outline=(125, 211, 252), width=2)

        # Header Badge
        draw.rounded_rectangle([80, 140, cls.WIDTH - 80, 220], radius=16, fill=(16, 24, 40, 230), outline=(56, 189, 248), width=2)
        font_badge = cls._get_font(24)
        draw.text((110, 165), f"🔬 CONCEPT SCHEMATIC • SCENE {scene.scene_number:02d}", fill=(56, 189, 248), font=font_badge)

        # Core summary
        font_core = cls._get_font(24)
        words = scene.spoken_line.split()
        summary_txt = " ".join(words[:9]) + ("..." if len(words) > 9 else "")
        draw.text((cx - 180, cy + 180), summary_txt, fill=(240, 240, 250), font=font_core)

        # Bottom Safe Zone Card
        draw.rounded_rectangle([80, 1340, cls.WIDTH - 80, 1475], radius=18, fill=(15, 23, 42, 240), outline=(56, 189, 248), width=2)
        draw.text((115, 1370), "SCIENTIFIC MECHANISM IN MOTION", fill=(255, 255, 255), font=cls._get_font(26))
        draw.text((115, 1415), "Observable principles governing matter, energy, and physical transformation.", fill=(186, 230, 253), font=cls._get_font(18))

        return img
