import os
import math
import random
import subprocess
import shutil
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from src.models.schemas import SceneBeat, VisualModality, CameraMotion

class KurzgesagtAnimationEngine:
    """
    Tier 1 Universal Kurzgesagt-Style Vector Motion Engine:
    Produces smooth, vibrant, 30fps Full HD (1080x1920 9:16) vector animations
    resembling the iconic Kurzgesagt ("In a Nutshell") science animation style.

    Core Animation Archetypes:
    1. BIOLOGY_CELLULAR_MEMBRANE: Undulating lipid bilayer, cytoplasm, nanoparticle/virus docking & entry.
    2. BIOLOGY_MOLECULAR_SYNTHESIS: Ribosome nanomachine sliding on mRNA ribbon, assembling amino acids.
    3. BIOLOGY_IMMUNE_RESPONSE: Y-shaped antibody nanobots swarming and locking onto spike antigens.
    4. OPTICS_WAVE_DISPERSION: Incident white light ray striking glass prism, refracting, and fanning into rainbow waves.
    5. ELECTROMAGNETISM_LORENTZ: Red North / Blue South poles, magnetic flux lines, electron drift, surging F=ILB vector.
    6. ATOMIC_CHEMICAL_REACTION: 3D tilted atomic electron orbitals, covalent bond snapping with energy shockwaves.
    7. SPACE_NEWTON_PROPULSION: Vector spacecraft with high-velocity exhaust particle plume and Newton 3 reaction force.
    8. DATA_SYSTEMS_NETWORK: Constellation of pulsing network nodes, animated data flows, real-time plotting curve.
    9. UNIVERSAL_CONCEPT_CORE: Gyroscopic multi-ring concept engine with orbital semantic nodes and particle halos.
    """

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    # Kurzgesagt Signature Palette
    BG_DARK = (11, 15, 27)          # Obsidian Slate
    BG_MID = (18, 24, 43)           # Deep Space Indigo
    CYAN = (0, 245, 212)            # Phosphor Cyan
    PINK = (247, 37, 133)           # Hot Magenta
    AMBER = (255, 183, 3)           # Solar Gold
    EMERALD = (16, 185, 129)        # Bio Emerald
    COBALT = (58, 134, 255)         # Vector Blue
    CORAL = (251, 133, 0)           # Reaction Orange
    PURPLE = (181, 131, 241)        # Electric Lavender
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
    def detect_archetype(cls, scene: SceneBeat) -> str:
        """Dynamically identifies the Kurzgesagt visual archetype from prompt and spoken text."""
        text = f"{scene.visual_prompt} {scene.spoken_line}".lower()

        # 1. Immune Defense & Antibodies
        if any(w in text for w in ["antibody", "antibodies", "immune", "immunity", "antigen", "t-cell", "b-cell", "lock onto", "pathogen", "virus"]):
            return "BIOLOGY_IMMUNE_RESPONSE"

        # 2. Molecular Translation / Synthesis
        if any(w in text for w in ["ribosome", "mrna", "translation", "protein", "synthesize", "amino acid", "codon", "polypeptide", "transcription", "recipe card", "genetic code"]):
            return "BIOLOGY_MOLECULAR_SYNTHESIS"

        # 3. Cellular Membrane & Nanoparticles
        if any(w in text for w in ["cell", "membrane", "cytoplasm", "nanoparticle", "lipid", "nucleus", "entry", "vesicle", "organelle", "endocytosis"]):
            return "BIOLOGY_CELLULAR_MEMBRANE"

        # 4. Optics & Wave Dispersion
        if any(w in text for w in ["prism", "light", "dispersion", "refraction", "spectrum", "rainbow", "wavelength", "snell", "cauchy", "optic", "colors"]):
            return "OPTICS_WAVE_DISPERSION"

        # 5. Electromagnetism & Lorentz Force
        if any(w in text for w in ["magnet", "magnetic", "lorentz", "f=ilb", "f=i*l*b", "fleming", "conductor", "induction", "flux", "tesla"]):
            return "ELECTROMAGNETISM_LORENTZ"

        # 6. Atomic & Chemical Reactions
        if any(w in text for w in ["atom", "atomic", "electron", "orbital", "chemical", "bond", "reaction", "molecule", "molecular", "compound", "oxide"]):
            return "ATOMIC_CHEMICAL_REACTION"

        # 7. Space Propulsion & Newton Mechanics
        if any(w in text for w in ["rocket", "exhaust", "propulsion", "thrust", "recoil", "action-reaction", "orbit", "gravity", "momentum"]):
            return "SPACE_NEWTON_PROPULSION"

        # 8. Data Networks & Systems
        if any(w in text for w in ["network", "system", "data", "economic", "market", "currency", "graph", "trend", "algorithm", "flow"]):
            return "DATA_SYSTEMS_NETWORK"

        # 9. Universal Fallback
        return "UNIVERSAL_CONCEPT_CORE"

    @classmethod
    def render_scene_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        duration: float = 3.5
    ) -> str:
        """
        Renders a 30fps Full HD (1080x1920) moving Kurzgesagt vector animation clip
        piped directly into FFmpeg stdin.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found for Kurzgesagt animation engine")

        archetype = cls.detect_archetype(scene)
        total_frames = max(30, int(duration * cls.FPS))

        # Map archetype to frame renderer
        render_map = {
            "BIOLOGY_CELLULAR_MEMBRANE": cls._render_frame_cellular_membrane,
            "BIOLOGY_MOLECULAR_SYNTHESIS": cls._render_frame_molecular_synthesis,
            "BIOLOGY_IMMUNE_RESPONSE": cls._render_frame_immune_response,
            "OPTICS_WAVE_DISPERSION": cls._render_frame_optics_dispersion,
            "ELECTROMAGNETISM_LORENTZ": cls._render_frame_electromagnetism_lorentz,
            "ATOMIC_CHEMICAL_REACTION": cls._render_frame_atomic_reaction,
            "SPACE_NEWTON_PROPULSION": cls._render_frame_newton_propulsion,
            "DATA_SYSTEMS_NETWORK": cls._render_frame_data_network,
            "UNIVERSAL_CONCEPT_CORE": cls._render_frame_universal_core,
        }
        render_func = render_map.get(archetype, cls._render_frame_universal_core)

        # Initialize shared procedural state
        state: Dict[str, Any] = {
            "particles": [
                {
                    "x": random.uniform(50, cls.WIDTH - 50),
                    "y": random.uniform(200, cls.HEIGHT - 400),
                    "vx": random.uniform(-0.8, 0.8),
                    "vy": random.uniform(-0.8, 0.8),
                    "radius": random.uniform(2.5, 6.0),
                    "color": random.choice([cls.CYAN, cls.PURPLE, cls.AMBER, cls.EMERALD]),
                    "phase": random.uniform(0, math.pi * 2)
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
                frame_img = render_func(frame_idx, total_frames, progress, state, scene)
                proc.stdin.write(frame_img.tobytes())
            proc.stdin.close()
            proc.wait(timeout=60)
        except Exception as e:
            proc.kill()
            raise RuntimeError(f"Kurzgesagt animation render error: {e}")

        return output_clip_path

    @classmethod
    def render_scene_keyframe(cls, scene: SceneBeat, output_image_path: str) -> str:
        """
        Renders a single high-definition hero keyframe (progress=0.45) for the Gate 1 Storyboard preview.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)
        archetype = cls.detect_archetype(scene)

        render_map = {
            "BIOLOGY_CELLULAR_MEMBRANE": cls._render_frame_cellular_membrane,
            "BIOLOGY_MOLECULAR_SYNTHESIS": cls._render_frame_molecular_synthesis,
            "BIOLOGY_IMMUNE_RESPONSE": cls._render_frame_immune_response,
            "OPTICS_WAVE_DISPERSION": cls._render_frame_optics_dispersion,
            "ELECTROMAGNETISM_LORENTZ": cls._render_frame_electromagnetism_lorentz,
            "ATOMIC_CHEMICAL_REACTION": cls._render_frame_atomic_reaction,
            "SPACE_NEWTON_PROPULSION": cls._render_frame_newton_propulsion,
            "DATA_SYSTEMS_NETWORK": cls._render_frame_data_network,
            "UNIVERSAL_CONCEPT_CORE": cls._render_frame_universal_core,
        }
        render_func = render_map.get(archetype, cls._render_frame_universal_core)

        state: Dict[str, Any] = {
            "particles": [
                {
                    "x": random.uniform(50, cls.WIDTH - 50),
                    "y": random.uniform(200, cls.HEIGHT - 400),
                    "vx": random.uniform(-0.8, 0.8),
                    "vy": random.uniform(-0.8, 0.8),
                    "radius": random.uniform(2.5, 6.0),
                    "color": random.choice([cls.CYAN, cls.PURPLE, cls.AMBER, cls.EMERALD]),
                    "phase": random.uniform(0, math.pi * 2)
                }
                for _ in range(35)
            ]
        }

        img = render_func(45, 90, 0.50, state, scene)
        img.save(output_image_path, "PNG")
        return output_image_path

    # ================= HELPER UTILITIES: KURZGESAGT VECTOR ART =================

    @classmethod
    def _create_base_canvas(cls, bg_top: Tuple[int, int, int], bg_bot: Tuple[int, int, int]) -> Image.Image:
        """Renders smooth vertical multi-stop gradient background."""
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), bg_top)
        draw = ImageDraw.Draw(img)
        steps = 100
        step_h = cls.HEIGHT // steps
        for i in range(steps):
            ratio = i / float(steps)
            r = int(bg_top[0] * (1 - ratio) + bg_bot[0] * ratio)
            g = int(bg_top[1] * (1 - ratio) + bg_bot[1] * ratio)
            b = int(bg_top[2] * (1 - ratio) + bg_bot[2] * ratio)
            draw.rectangle([(0, i * step_h), (cls.WIDTH, (i + 1) * step_h)], fill=(r, g, b))
        return img

    @classmethod
    def _draw_cel_sphere(
        cls,
        draw: ImageDraw.Draw,
        cx: float, cy: float, radius: float,
        color: Tuple[int, int, int],
        outline: Optional[Tuple[int, int, int]] = None
    ):
        """Draws a signature Kurzgesagt 2.5D cel-shaded sphere with shadow and specular highlight."""
        r_base, g_base, b_base = color
        shadow_col = (int(r_base * 0.65), int(g_base * 0.65), int(b_base * 0.65))
        light_col = (min(255, int(r_base + 55)), min(255, int(g_base + 55)), min(255, int(b_base + 55)))

        # Base sphere
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], fill=color, outline=outline, width=2 if outline else 0)

        # Shadow crescent (lower-right)
        shadow_r = radius * 0.88
        draw.ellipse([(cx - shadow_r + radius * 0.18, cy - shadow_r + radius * 0.18), (cx + shadow_r + radius * 0.18, cy + shadow_r + radius * 0.18)], fill=shadow_col)

        # Main inner highlight
        inner_r = radius * 0.78
        draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], fill=color)

        # Specular glint (upper-left)
        glint_r = radius * 0.28
        draw.ellipse([(cx - radius * 0.45, cy - radius * 0.45), (cx - radius * 0.45 + glint_r * 2, cy - radius * 0.45 + glint_r * 2)], fill=light_col)

    @classmethod
    def _draw_hud_badge(
        cls,
        draw: ImageDraw.Draw,
        scene: SceneBeat,
        badge_text: str,
        accent_color: Tuple[int, int, int]
    ):
        """Draws the signature top Kurzgesagt pill badge and safe area header."""
        font_badge = cls._get_font(26, bold=True)
        draw.rounded_rectangle([(80, 150), (620, 215)], radius=22, fill=(18, 26, 44, 230), outline=accent_color, width=2)
        draw.text((110, 168), badge_text, fill=accent_color, font=font_badge)
        draw.text((cls.WIDTH - 240, 168), f"SCENE {scene.scene_number:02d}", fill=(148, 163, 184), font=font_badge)

    @classmethod
    def _draw_ambient_particles(cls, draw: ImageDraw.Draw, state: Dict[str, Any], frame_idx: int):
        """Animates 35 floating ambient vector motes with subtle sinusoidal drift."""
        for p in state.get("particles", []):
            x = p["x"] + math.sin(frame_idx * 0.04 + p["phase"]) * 14
            y = p["y"] + math.cos(frame_idx * 0.03 + p["phase"]) * 12
            r = p["radius"]
            draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=p["color"])

    # ================= 1. ARCHETYPE: BIOLOGY CELLULAR MEMBRANE =================
    @classmethod
    def _render_frame_cellular_membrane(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((8, 28, 26), (4, 16, 18))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        # 1. Background Cell Nucleus (Protected Vault)
        nuc_cx, nuc_cy = cls.WIDTH // 2, 1150
        nuc_r = 380 + 8 * math.sin(frame_idx * 0.08)
        draw.ellipse([(nuc_cx - nuc_r, nuc_cy - nuc_r), (nuc_cx + nuc_r, nuc_cy + nuc_r)], fill=(6, 42, 38), outline=(20, 80, 70), width=4)

        # Rotating DNA Double Helix inside nucleus
        for step in range(16):
            t_step = step / 16.0
            dna_y = nuc_cy - 160 + step * 20
            phase = frame_idx * 0.12 + t_step * math.pi * 3
            x_strand1 = nuc_cx + math.sin(phase) * 120
            x_strand2 = nuc_cx - math.sin(phase) * 120
            draw.line([(x_strand1, dna_y), (x_strand2, dna_y)], fill=(34, 197, 94), width=3)
            cls._draw_cel_sphere(draw, x_strand1, dna_y, 9, cls.CYAN)
            cls._draw_cel_sphere(draw, x_strand2, dna_y, 9, cls.PINK)

        # 2. Undulating Lipid Bilayer Membrane (Cell Boundary)
        mem_y_base = 560
        bilayer_pts_top = []
        bilayer_pts_bot = []
        for x in range(0, cls.WIDTH + 30, 25):
            undulation = math.sin(x * 0.012 + frame_idx * 0.15) * 16
            bilayer_pts_top.append((x, mem_y_base + undulation))
            bilayer_pts_bot.append((x, mem_y_base + 36 + undulation))

        for pt in bilayer_pts_top:
            cls._draw_cel_sphere(draw, pt[0], pt[1], 11, cls.EMERALD)
        for pt in bilayer_pts_bot:
            cls._draw_cel_sphere(draw, pt[0], pt[1], 11, (16, 140, 110))

        # 3. Lipid Nanoparticle / Delivery Carrier Descending & Releasing Payload
        np_start_y = 180
        np_target_y = 510
        # Smooth ease-in-out descent
        ease_p = 0.5 - 0.5 * math.cos(min(1.0, progress * 1.6) * math.pi)
        np_y = np_start_y + (np_target_y - np_start_y) * ease_p
        np_x = cls.WIDTH // 2

        # Nanoparticle outer lipid shell
        np_radius = 65
        cls._draw_cel_sphere(draw, np_x, np_y, np_radius, cls.AMBER, outline=(255, 255, 255))

        # Glowing mRNA Ribbon inside releasing into cytoplasm
        if progress > 0.40:
            release_p = (progress - 0.40) / 0.60
            for i in range(18):
                t_ribbon = i / 18.0
                rx = np_x + math.sin(t_ribbon * 4 + frame_idx * 0.2) * 45
                ry = np_y + 40 + t_ribbon * (280 * release_p)
                col = cls.PINK if i % 2 == 0 else cls.CYAN
                cls._draw_cel_sphere(draw, rx, ry, 7, col)

        cls._draw_hud_badge(draw, scene, "🧬 CELLULAR MEMBRANE & ENTRY", cls.EMERALD)
        return img

    # ================= 2. ARCHETYPE: BIOLOGY MOLECULAR SYNTHESIS =================
    @classmethod
    def _render_frame_molecular_synthesis(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((15, 14, 34), (8, 7, 20))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 680

        # 1. Moving mRNA Ribbon Tape (sliding smoothly right to left)
        tape_speed = frame_idx * 6.5
        tape_y = cy + 15
        for x_base in range(-100, cls.WIDTH + 200, 32):
            cur_x = x_base - int(tape_speed % 32)
            wave_offset = math.sin(cur_x * 0.015 + frame_idx * 0.1) * 12
            draw.line([(cur_x, tape_y + wave_offset - 10), (cur_x + 28, tape_y + wave_offset - 10)], fill=(70, 60, 110), width=6)
            # Codon beads
            col_codon = cls.CYAN if (x_base // 32) % 3 == 0 else (cls.AMBER if (x_base // 32) % 3 == 1 else cls.PINK)
            draw.rectangle([(cur_x + 6, tape_y + wave_offset - 20), (cur_x + 22, tape_y + wave_offset)], fill=col_codon)

        # 2. Massive Two-Subunit Molecular Ribosome Machine
        breathe = math.sin(frame_idx * 0.25) * 8
        # Large Subunit (Top)
        cls._draw_cel_sphere(draw, cx, cy - 80 + breathe * 0.5, 150, (124, 58, 237), outline=(167, 139, 250))
        # Small Subunit (Bottom)
        cls._draw_cel_sphere(draw, cx, cy + 90 - breathe * 0.5, 120, (91, 33, 182), outline=(139, 92, 246))

        # 3. Assembled Polypeptide Chain Emerging & Folding (Amino acid beads)
        num_assembled = int(progress * 22) + 4
        chain_pts = []
        for i in range(num_assembled):
            fold_angle = i * 0.45 + frame_idx * 0.05
            dist = 90 + i * 18
            bx = cx + math.cos(fold_angle) * (dist * 0.6)
            by = (cy - 180) - i * 14 + math.sin(fold_angle) * 16
            chain_pts.append((bx, by))
            aa_col = [cls.AMBER, cls.EMERALD, cls.PINK, cls.CYAN][i % 4]
            cls._draw_cel_sphere(draw, bx, by, 11, aa_col, outline=(255, 255, 255))

        # Connect chain with bonds
        for i in range(len(chain_pts) - 1):
            draw.line([chain_pts[i], chain_pts[i + 1]], fill=(255, 255, 255), width=3)

        # Synthesis Spark Burst at exit tunnel
        if frame_idx % 6 < 4:
            for _ in range(6):
                sp_x = cx + random.uniform(-25, 25)
                sp_y = cy - 180 + random.uniform(-25, 25)
                draw.ellipse([(sp_x - 3, sp_y - 3), (sp_x + 3, sp_y + 3)], fill=cls.AMBER)

        cls._draw_hud_badge(draw, scene, "🔬 RIBOSOME MOLECULAR FACTORY", cls.PURPLE)
        return img

    # ================= 3. ARCHETYPE: BIOLOGY IMMUNE RESPONSE =================
    @classmethod
    def _render_frame_immune_response(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((24, 10, 18), (12, 6, 10))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 650

        # 1. Central Foreign Antigen / Virus Body
        virus_r = 140 + math.sin(frame_idx * 0.15) * 6
        # Shift color from aggressive red to neutralized teal upon binding
        neutralize_ratio = min(1.0, progress * 1.5)
        vr = int(239 * (1 - neutralize_ratio) + 16 * neutralize_ratio)
        vg = int(68 * (1 - neutralize_ratio) + 185 * neutralize_ratio)
        vb = int(68 * (1 - neutralize_ratio) + 129 * neutralize_ratio)
        virus_color = (vr, vg, vb)

        # Corona of Spike Proteins
        num_spikes = 12
        spike_tips = []
        for s in range(num_spikes):
            angle = s * (2 * math.pi / num_spikes) + frame_idx * 0.02
            tip_dist = virus_r + 55
            tx = cx + math.cos(angle) * tip_dist
            ty = cy + math.sin(angle) * tip_dist
            base_x = cx + math.cos(angle) * virus_r
            base_y = cy + math.sin(angle) * virus_r
            draw.line([(base_x, base_y), (tx, ty)], fill=virus_color, width=8)
            cls._draw_cel_sphere(draw, tx, ty, 14, cls.PINK if neutralize_ratio < 0.6 else cls.CYAN)
            spike_tips.append((tx, ty, angle))

        cls._draw_cel_sphere(draw, cx, cy, virus_r, virus_color, outline=(255, 255, 255))

        # 2. Swarm of Y-Shaped Kurzgesagt Antibodies Locking In
        for idx, (tx, ty, ang) in enumerate(spike_tips[:8]):
            # Antibodies fly in from perimeter toward spike tips
            flight_p = min(1.0, progress * 1.8 + idx * 0.05)
            ab_dist = 420 * (1.0 - flight_p)
            ab_x = tx + math.cos(ang) * ab_dist
            ab_y = ty + math.sin(ang) * ab_dist

            # Draw Y-shaped antibody nanobot
            ab_len = 36
            stem_x = ab_x + math.cos(ang) * ab_len
            stem_y = ab_y + math.sin(ang) * ab_len
            draw.line([(ab_x, ab_y), (stem_x, stem_y)], fill=cls.CYAN, width=6)
            # Two Fab grasping arms
            arm1_x = ab_x + math.cos(ang + 0.6) * 24
            arm1_y = ab_y + math.sin(ang + 0.6) * 24
            arm2_x = ab_x + math.cos(ang - 0.6) * 24
            arm2_y = ab_y + math.sin(ang - 0.6) * 24
            draw.line([(ab_x, ab_y), (arm1_x, arm1_y)], fill=cls.CYAN, width=6)
            draw.line([(ab_x, ab_y), (arm2_x, arm2_y)], fill=cls.CYAN, width=6)

            cls._draw_cel_sphere(draw, arm1_x, arm1_y, 5, cls.AMBER)
            cls._draw_cel_sphere(draw, arm2_x, arm2_y, 5, cls.AMBER)

        # 3. Expanding Neutralization Rings
        if progress > 0.5:
            ring_r = int((progress - 0.5) * 500)
            draw.ellipse([(cx - ring_r, cy - ring_r), (cx + ring_r, cy + ring_r)], outline=cls.CYAN, width=3)

        cls._draw_hud_badge(draw, scene, "🛡️ ANTIBODY LOCK & NEUTRALIZATION", cls.PINK)
        return img

    # ================= 4. ARCHETYPE: OPTICS WAVE DISPERSION =================
    @classmethod
    def _render_frame_optics_dispersion(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((10, 16, 32), (6, 10, 20))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 620

        # 1. Glass Triangular Prism
        apex = (cx - 40, cy - 220)
        p_left = (cx - 260, cy + 200)
        p_right = (cx + 200, cy + 200)
        draw.polygon([apex, p_left, p_right], fill=(20, 34, 58), outline=cls.CYAN, width=4)

        # 2. Incident White Light Ray (traveling toward prism)
        src_x, src_y = 60, cy - 60
        hit_x, hit_y = cx - 150, cy - 10

        beam_travel = min(1.0, progress * 2.2)
        cur_beam_x = src_x + (hit_x - src_x) * beam_travel
        cur_beam_y = src_y + (hit_y - src_y) * beam_travel
        draw.line([(src_x, src_y), (cur_beam_x, cur_beam_y)], fill=(255, 255, 255), width=8)

        # Refraction flash at impact
        if beam_travel >= 1.0:
            cls._draw_cel_sphere(draw, hit_x, hit_y, 14, cls.WHITE)

            # 3. Seven Rainbow Wave Streams Emergence
            spectrum = [
                ("Red", (255, 59, 48), -60, 0.08),
                ("Orange", (255, 149, 0), -35, 0.10),
                ("Yellow", (255, 204, 0), -10, 0.12),
                ("Green", (52, 199, 89), 15, 0.14),
                ("Cyan", (0, 245, 212), 40, 0.16),
                ("Blue", (58, 134, 255), 65, 0.18),
                ("Violet", (175, 82, 222), 90, 0.20)
            ]

            scr_x = cls.WIDTH - 120
            exit_x = cx + 90
            exit_y = cy + 10

            # Internal beam through glass
            draw.line([(hit_x, hit_y), (exit_x, exit_y)], fill=(220, 235, 255), width=5)

            # Exiting sinusoidal spectral waves
            fan_progress = min(1.0, (progress - 0.35) / 0.65) if progress > 0.35 else 0.0
            for name, rgb, dev, freq in spectrum:
                target_y = cy + dev * 2.6
                cur_scr_x = exit_x + (scr_x - exit_x) * fan_progress
                cur_scr_y = exit_y + (target_y - exit_y) * fan_progress

                # Sinusoidal wave ripple
                prev_pt = (exit_x, exit_y)
                steps = 25
                for s in range(1, steps + 1):
                    t = s / float(steps)
                    wx = exit_x + (cur_scr_x - exit_x) * t
                    wy = exit_y + (cur_scr_y - exit_y) * t + math.sin(wx * freq - frame_idx * 0.35) * 8
                    draw.line([prev_pt, (wx, wy)], fill=rgb, width=4)
                    prev_pt = (wx, wy)

            # Projection screen
            draw.rounded_rectangle([(scr_x - 8, cy - 200), (scr_x + 18, cy + 280)], radius=8, fill=(245, 248, 255), outline=cls.CYAN, width=2)

        cls._draw_hud_badge(draw, scene, "🌈 OPTICAL CAUCHY DISPERSION", cls.CYAN)
        return img

    # ================= 5. ARCHETYPE: ELECTROMAGNETISM LORENTZ =================
    @classmethod
    def _render_frame_electromagnetism_lorentz(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((10, 16, 28), (6, 10, 18))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 650

        # 1. Magnetic Pole Pieces: Red North (Left) and Blue South (Right)
        # North Pole
        draw.rounded_rectangle([(cx - 360, cy - 140), (cx - 180, cy + 140)], radius=16, fill=(220, 38, 38), outline=(255, 255, 255), width=3)
        draw.text((cx - 290, cy - 35), "N", fill=(255, 255, 255), font=cls._get_font(60, bold=True))

        # South Pole
        draw.rounded_rectangle([(cx + 180, cy - 140), (cx + 360, cy + 140)], radius=16, fill=(37, 99, 235), outline=(255, 255, 255), width=3)
        draw.text((cx + 250, cy - 35), "S", fill=(255, 255, 255), font=cls._get_font(60, bold=True))

        # 2. Magnetic Flux Lines B streaming smoothly from N to S
        flux_offset = (frame_idx * 4) % 40
        for y_off in [-80, -40, 0, 40, 80]:
            draw.line([(cx - 180, cy + y_off), (cx + 180, cy + y_off)], fill=(0, 240, 255, 140), width=2)
            # Directional flux chevrons
            ch_x = cx - 140 + flux_offset
            while ch_x < cx + 160:
                draw.polygon([(ch_x, cy + y_off - 6), (ch_x + 10, cy + y_off), (ch_x, cy + y_off + 6)], fill=cls.CYAN)
                ch_x += 60

        # 3. Suspended Conductor Wire Kicking Sideways (F = I L B)
        kick_p = min(1.0, progress * 1.6)
        displacement_y = -85 * (1.0 - math.cos(kick_p * math.pi * 0.5))
        wire_y = cy + displacement_y

        draw.line([(cx - 140, wire_y), (cx + 140, wire_y)], fill=(245, 158, 11), width=16)

        # Golden electrons streaming through wire (Current I)
        for i in range(8):
            ex = cx - 120 + ((frame_idx * 8 + i * 35) % 240)
            cls._draw_cel_sphere(draw, ex, wire_y, 6, cls.AMBER)

        # Surging Force Vector Arrow F
        if progress > 0.2:
            arrow_len = min(160, int((progress - 0.2) * 220))
            draw.line([(cx, wire_y), (cx, wire_y - arrow_len)], fill=cls.EMERALD, width=10)
            draw.polygon([(cx - 20, wire_y - arrow_len), (cx + 20, wire_y - arrow_len), (cx, wire_y - arrow_len - 30)], fill=cls.EMERALD)
            draw.text((cx + 30, wire_y - arrow_len - 15), "F = I · L · B", fill=cls.EMERALD, font=cls._get_font(34, bold=True))

        cls._draw_hud_badge(draw, scene, "⚡ LORENTZ DEFLECTION FORCE", cls.CYAN)
        return img

    # ================= 6. ARCHETYPE: ATOMIC CHEMICAL REACTION =================
    @classmethod
    def _render_frame_atomic_reaction(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((18, 12, 28), (8, 6, 14))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 650

        # Central Nucleus
        cls._draw_cel_sphere(draw, cx, cy, 38, cls.CORAL, outline=(255, 255, 255))

        # 3 Tilted 3D Electron Orbital Rings
        orbital_radii = [(220, 75, 0.4), (200, 70, -0.6), (240, 80, 1.2)]
        for r_major, r_minor, tilt in orbital_radii:
            # Draw ellipse rotated
            num_pts = 60
            pts = []
            for i in range(num_pts):
                theta = i * (2 * math.pi / num_pts)
                x_el = r_major * math.cos(theta)
                y_el = r_minor * math.sin(theta)
                # Rotate by tilt
                rot_x = cx + x_el * math.cos(tilt) - y_el * math.sin(tilt)
                rot_y = cy + x_el * math.sin(tilt) + y_el * math.cos(tilt)
                pts.append((rot_x, rot_y))
            for i in range(len(pts) - 1):
                draw.line([pts[i], pts[i + 1]], fill=(140, 100, 200, 120), width=2)

            # Orbiting Electron
            e_theta = frame_idx * 0.15 + tilt * 2
            ex_local = r_major * math.cos(e_theta)
            ey_local = r_minor * math.sin(e_theta)
            ex = cx + ex_local * math.cos(tilt) - ey_local * math.sin(tilt)
            ey = cy + ex_local * math.sin(tilt) + ey_local * math.cos(tilt)
            cls._draw_cel_sphere(draw, ex, ey, 9, cls.CYAN)

        # Covalent Bond Snap Flash
        if progress > 0.45:
            shock_r = int((progress - 0.45) * 380)
            draw.ellipse([(cx - shock_r, cy - shock_r), (cx + shock_r, cy + shock_r)], outline=cls.AMBER, width=3)

        cls._draw_hud_badge(draw, scene, "⚛️ ATOMIC ORBITAL & BONDING", cls.PURPLE)
        return img

    # ================= 7. ARCHETYPE: SPACE NEWTON PROPULSION =================
    @classmethod
    def _render_frame_newton_propulsion(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((8, 10, 22), (4, 6, 12))
        draw = ImageDraw.Draw(img)

        # Parallax Starfield
        for p in state.get("particles", []):
            star_y = (p["y"] + frame_idx * 6) % (cls.HEIGHT - 300) + 100
            draw.ellipse([(p["x"] - 2, star_y - 2), (p["x"] + 2, star_y + 2)], fill=(255, 255, 255))

        cx, cy = cls.WIDTH // 2, 600

        # High-Velocity Exhaust Plume (Newton Action)
        for i in range(35):
            angle = random.uniform(math.pi * 0.35, math.pi * 0.65)
            speed = random.uniform(12, 35)
            dist = (frame_idx * 4 + i * 15) % 260
            px = cx + math.cos(angle) * (dist * 0.4)
            py = cy + 120 + dist
            p_rad = random.uniform(6, 16)
            col = random.choice([cls.CORAL, cls.AMBER, cls.WHITE])
            draw.ellipse([(px - p_rad, py - p_rad), (px + p_rad, py + p_rad)], fill=col)

        # Sleek Vector Spacecraft Body
        # Nose cone & fuselage
        nose = (cx, cy - 140)
        wing_l = (cx - 75, cy + 110)
        wing_r = (cx + 75, cy + 110)
        draw.polygon([nose, wing_l, (cx, cy + 80), wing_r], fill=(240, 245, 255), outline=cls.COBALT, width=4)
        cls._draw_cel_sphere(draw, cx, cy - 20, 24, cls.CYAN)

        # Newton 3 Force Arrows
        draw.line([(cx, cy + 130), (cx, cy + 290)], fill=cls.AMBER, width=8)
        draw.polygon([(cx - 16, cy + 290), (cx + 16, cy + 290), (cx, cy + 320)], fill=cls.AMBER)
        draw.text((cx + 25, cy + 220), "F_action (Exhaust)", fill=cls.AMBER, font=cls._get_font(26, bold=True))

        draw.line([(cx, cy - 150), (cx, cy - 280)], fill=cls.CYAN, width=8)
        draw.polygon([(cx - 16, cy - 280), (cx + 16, cy - 280), (cx, cy - 310)], fill=cls.CYAN)
        draw.text((cx + 25, cy - 250), "F_reaction (Thrust)", fill=cls.CYAN, font=cls._get_font(26, bold=True))

        cls._draw_hud_badge(draw, scene, "🚀 NEWTONIAN ACTION-REACTION", cls.AMBER)
        return img

    # ================= 8. ARCHETYPE: DATA SYSTEMS NETWORK =================
    @classmethod
    def _render_frame_data_network(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((12, 18, 30), (6, 10, 18))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 650

        # Network Nodes & Dynamic Splines
        nodes = [
            (cx - 240, cy - 160),
            (cx, cy - 220),
            (cx + 240, cy - 160),
            (cx - 180, cy + 140),
            (cx + 180, cy + 140),
            (cx, cy)
        ]

        # Draw connecting conduits
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                draw.line([nodes[i], nodes[j]], fill=(30, 48, 76), width=3)
                # Pulsing data packet
                t_packet = ((frame_idx * 0.05 + i * 0.2 + j * 0.3) % 1.0)
                px = nodes[i][0] + (nodes[j][0] - nodes[i][0]) * t_packet
                py = nodes[i][1] + (nodes[j][1] - nodes[i][1]) * t_packet
                cls._draw_cel_sphere(draw, px, py, 5, cls.CYAN)

        for nx, ny in nodes:
            cls._draw_cel_sphere(draw, nx, ny, 28, cls.COBALT, outline=(255, 255, 255))

        # Real-time curve graph below
        graph_box = [(120, cy + 240), (cls.WIDTH - 120, cy + 480)]
        draw.rounded_rectangle(graph_box, radius=18, fill=(18, 26, 44), outline=(40, 56, 84), width=2)
        curve_pts = []
        num_steps = int(progress * 30) + 2
        for s in range(num_steps):
            gx = 140 + s * 26
            gy = cy + 440 - math.sin(s * 0.2) * 120 - s * 3
            curve_pts.append((gx, gy))

        if len(curve_pts) > 1:
            for s in range(len(curve_pts) - 1):
                draw.line([curve_pts[s], curve_pts[s + 1]], fill=cls.CYAN, width=5)
            last_pt = curve_pts[-1]
            cls._draw_cel_sphere(draw, last_pt[0], last_pt[1], 8, cls.AMBER)

        cls._draw_hud_badge(draw, scene, "📈 SYSTEMS & NETWORK DYNAMICS", cls.COBALT)
        return img

    # ================= 9. ARCHETYPE: UNIVERSAL CONCEPT CORE =================
    @classmethod
    def _render_frame_universal_core(
        cls, frame_idx: int, total_frames: int, progress: float, state: Dict[str, Any], scene: SceneBeat
    ) -> Image.Image:
        img = cls._create_base_canvas((14, 16, 32), (8, 10, 20))
        draw = ImageDraw.Draw(img)
        cls._draw_ambient_particles(draw, state, frame_idx)

        cx, cy = cls.WIDTH // 2, 650

        # Concentric Gyroscopic Rings rotating at different speeds
        for i, rad in enumerate([180, 260, 340]):
            angle = frame_idx * (0.04 - i * 0.01)
            draw.ellipse([(cx - rad, cy - rad * 0.4), (cx + rad, cy + rad * 0.4)], outline=(45, 60, 95), width=2)
            # Orbiting node
            nx = cx + rad * math.cos(angle)
            ny = cy + rad * 0.4 * math.sin(angle)
            cls._draw_cel_sphere(draw, nx, ny, 12, [cls.CYAN, cls.AMBER, cls.PINK][i])

        # Core Glowing Sphere
        core_r = 90 + math.sin(frame_idx * 0.15) * 6
        cls._draw_cel_sphere(draw, cx, cy, core_r, (79, 70, 229), outline=(255, 255, 255))
        draw.text((cx - 45, cy - 18), "CORE", fill=(255, 255, 255), font=cls._get_font(32, bold=True))

        # Dynamic keyword labels from spoken line
        words = [w for w in scene.spoken_line.split() if len(w) > 3]
        if words:
            summary = " • ".join(words[:4]).upper()
            draw.rounded_rectangle([(cx - 240, cy + 320), (cx + 240, cy + 380)], radius=16, fill=(18, 26, 44), outline=cls.CYAN, width=2)
            draw.text((cx - 210, cy + 338), summary, fill=cls.CYAN, font=cls._get_font(22, bold=True))

        cls._draw_hud_badge(draw, scene, "💡 FUNDAMENTAL MECHANISM", cls.PURPLE)
        return img
