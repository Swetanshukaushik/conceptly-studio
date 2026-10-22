import os
import math
import random
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from src.core.config import settings
from src.models.schemas import SceneBeat, VisualModality, ReelGenerationTier

class VisualAssetFactory:
    """
    Visual Asset & Cinematic Scene Generator:
    Produces 1080x1920 (9:16) vertical imagery matching each scene beat:
    - Tier PREMIUM: OpenAI DALL-E 3 / Flux / SDXL photorealistic generation
    - Tier DEFAULT / Offline: Procedural Cinematic & Neon Vector Schematics
    """

    WIDTH = 1080
    HEIGHT = 1920

    @classmethod
    def render_scene_image(
        cls,
        scene: SceneBeat,
        output_image_path: str,
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)

        # 1. Attempt DALL-E 3 if API key available and requested
        if tier == ReelGenerationTier.PREMIUM and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                prompt_9_16 = f"{scene.visual_prompt}. Extremely high quality, detailed, vertical 9:16 composition, cinematic lighting, sharp focus, no text watermarks."
                
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt_9_16,
                    size="1024x1792",
                    quality="standard",
                    n=1
                )
                image_url = response.data[0].url
                
                # Download and resize to exact 1080x1920
                import httpx
                res = httpx.get(image_url, timeout=30.0)
                if res.status_code == 200:
                    with open(output_image_path, "wb") as f:
                        f.write(res.content)
                    with Image.open(output_image_path) as im:
                        resized = im.resize((cls.WIDTH, cls.HEIGHT), Image.LANCZOS)
                        resized.save(output_image_path, "PNG")
                    return output_image_path
            except Exception as e:
                print(f"⚠️ DALL-E 3 generation failed: {e}. Falling back to procedural cinematic visual...")

        # 2. Procedural Cinematic & Neon Schematic Generator
        return cls._render_procedural_cinematic(scene, output_image_path)

    @classmethod
    def _render_procedural_cinematic(cls, scene: SceneBeat, output_path: str) -> str:
        """
        Renders rich, domain-themed 1080x1920 visual frames with atmospheric
        lighting, glowing vector focal points, and cinematic vignettes.
        """
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (10, 15, 26))
        draw = ImageDraw.Draw(img)

        # Domain colors and background gradient
        is_history = scene.visual_modality == VisualModality.CINEMATIC_SCENE and any(w in scene.visual_prompt.lower() for w in ["bhagat", "history", "court", "assembly", "jail", "flag"])
        is_bio = scene.visual_modality == VisualModality.ANATOMICAL_3D or "chloroplast" in scene.visual_prompt.lower() or "leaf" in scene.visual_prompt.lower()

        if is_history:
            # Sepia / Warm Amber Historic Palette
            bg_start = (28, 20, 14)   # Deep mahogany sepia
            bg_end = (15, 10, 8)      # Dark charred umber
            accent_glow = (245, 158, 11) # Warm lantern amber
            hero_title = "HISTORIC CHRONICLE • 1929"
        elif is_bio:
            # Bioluminescent Emerald / Cyan Palette
            bg_start = (6, 32, 24)    # Deep chlorophyll emerald
            bg_end = (4, 18, 14)      # Dark forest cyan
            accent_glow = (16, 185, 129) # Luminous green
            hero_title = "CELLULAR MOLECULAR BIOLOGY"
        else:
            # Physics / Cosmic Navy & Cobalt Palette
            bg_start = (11, 18, 38)   # Deep space navy
            bg_end = (6, 10, 22)      # Void black
            accent_glow = (56, 189, 248) # Neon sky blue / cyan
            hero_title = "PHYSICAL FORCES & MECHANICS"

        # 1. Draw atmospheric vertical gradient
        steps = 120
        step_h = cls.HEIGHT // steps
        for i in range(steps):
            ratio = i / float(steps)
            r = int(bg_start[0] * (1 - ratio) + bg_end[0] * ratio)
            g = int(bg_start[1] * (1 - ratio) + bg_end[1] * ratio)
            b = int(bg_start[2] * (1 - ratio) + bg_end[2] * ratio)
            draw.rectangle([(0, i * step_h), (cls.WIDTH, (i + 1) * step_h)], fill=(r, g, b))

        # 2. Draw Subtle Radial Light Spotlight in upper-center (Y=600px)
        center_x, center_y = cls.WIDTH // 2, 650
        for radius in range(400, 50, -30):
            alpha_ratio = (400 - radius) / 400.0
            glow_r = int(bg_start[0] + (accent_glow[0] - bg_start[0]) * 0.25 * alpha_ratio)
            glow_g = int(bg_start[1] + (accent_glow[1] - bg_start[1]) * 0.25 * alpha_ratio)
            glow_b = int(bg_start[2] + (accent_glow[2] - bg_start[2]) * 0.25 * alpha_ratio)
            draw.ellipse(
                [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
                fill=(glow_r, glow_g, glow_b)
            )

        # 3. Draw Hero Center Artwork Canvas (Safe Content Zone Y=280 to Y=1280)
        font_badge = cls._get_font(26, bold=True)
        font_hero = cls._get_font(46, bold=True)
        font_body = cls._get_font(32)

        # Header Badge
        draw.rounded_rectangle([(80, 160), (460, 215)], radius=18, fill=(20, 28, 48), outline=accent_glow, width=2)
        draw.text((105, 173), hero_title, fill=accent_glow, font=font_badge)

        # Scene Counter
        draw.text((cls.WIDTH - 220, 173), f"SCENE {scene.scene_number:02d}", fill=(148, 163, 184), font=font_badge)

        # Visual Focal Box (Y = 280px to Y = 1260px)
        card_box = [(80, 260), (cls.WIDTH - 80, 1260)]
        draw.rounded_rectangle(card_box, radius=32, fill=(17, 24, 39, 230), outline=(40, 54, 80), width=3)

        # Draw Domain-Specific Graphical Centerpiece
        if is_history:
            # Historic Arch & Monument Silhouette
            draw.ellipse([(cls.WIDTH//2 - 220, 340), (cls.WIDTH//2 + 220, 780)], outline=accent_glow, width=3)
            draw.text((cls.WIDTH//2 - 140, 520), "🏛️ HISTORIC STILL", fill=accent_glow, font=font_hero)
            draw.text((140, 680), "Lahore Central Assembly • 1929", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_bio:
            # 3D Cellular Chloroplast / Molecule Rings
            for r in [180, 120, 60]:
                draw.ellipse([(cls.WIDTH//2 - r, 550 - r), (cls.WIDTH//2 + r, 550 + r)], outline=accent_glow, width=3)
            draw.text((cls.WIDTH//2 - 130, 530), "🌿 3D ORGANELLE", fill=accent_glow, font=font_hero)
            draw.text((140, 720), "Thylakoid Solar Stacks • Grana", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        else:
            # Neon Physics Force Vectors
            cx, cy = cls.WIDTH // 2, 540
            # Opposing vector arrows
            draw.line([(cx - 280, cy), (cx - 40, cy)], fill=(245, 158, 11), width=10) # Left Action
            draw.polygon([(cx - 300, cy), (cx - 270, cy - 18), (cx - 270, cy + 18)], fill=(245, 158, 11))
            draw.text((cx - 240, cy - 60), "F_action", fill=(245, 158, 11), font=cls._get_font(36, bold=True))

            draw.line([(cx + 40, cy), (cx + 280, cy)], fill=(56, 189, 248), width=10) # Right Reaction
            draw.polygon([(cx + 300, cy), (cx + 270, cy - 18), (cx + 270, cy + 18)], fill=(56, 189, 248))
            draw.text((cx + 120, cy - 60), "F_reaction", fill=(56, 189, 248), font=cls._get_font(36, bold=True))

            # Central Contact Surface
            draw.line([(cx, cy - 100), (cx, cy + 100)], fill=(255, 255, 255), width=4)
            draw.text((140, 720), "Action & Reaction on Different Bodies", fill=(248, 250, 252), font=cls._get_font(34, bold=True))

        # Scene Visual Prompt Description Overlay inside Card
        draw.rounded_rectangle([(120, 800), (cls.WIDTH - 120, 1200)], radius=20, fill=(13, 19, 33), outline=(30, 41, 59), width=2)
        draw.text((150, 825), "CINEMATIC VISUAL DIRECTION", fill=accent_glow, font=cls._get_font(24, bold=True))
        
        wrapped_prompt = cls._wrap_text(scene.visual_prompt, max_chars=40)
        y_text = 875
        for line in wrapped_prompt[:6]:
            draw.text((150, y_text), line, fill=(203, 213, 225), font=cls._get_font(28))
            y_text += 46

        # Camera Motion Badge (Bottom Right of card)
        motion_text = f"🎥 MOTION: {scene.camera_motion.value}"
        draw.text((cls.WIDTH - 360, 1215), motion_text, fill=(148, 163, 184), font=cls._get_font(22, bold=True))

        # 4. Burned-in Subtitle Safe Zone Box at Y = 1360px - 1490px
        sub_box = [(60, 1360), (cls.WIDTH - 60, 1490)]
        draw.rounded_rectangle(sub_box, radius=20, fill=(15, 23, 42), outline=accent_glow, width=2)
        font_sub = cls._get_font(34, bold=True)
        sub_lines = cls._wrap_text(scene.spoken_line, max_chars=42)
        y_sub = 1380
        for line in sub_lines[:2]:
            bbox = draw.textbbox((0, 0), line, font=font_sub)
            text_w = bbox[2] - bbox[0]
            x_sub = (cls.WIDTH - text_w) // 2
            draw.text((x_sub, y_sub), line, fill=(255, 255, 255), font=font_sub)
            y_sub += 48

        img.save(output_path, "PNG")
        return output_path

    @classmethod
    def _wrap_text(cls, text: str, max_chars: int = 40):
        words = text.split()
        lines = []
        cur_line = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + 1 > max_chars:
                lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
            else:
                cur_line.append(w)
                cur_len += len(w) + 1
        if cur_line:
            lines.append(" ".join(cur_line))
        return lines

    @classmethod
    def _get_font(cls, size: int, bold: bool = False):
        font_candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFPro.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()
