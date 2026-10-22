import os
import math
import random
import urllib.request
import urllib.parse
import json
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.core.config import settings
from src.models.schemas import SceneBeat, VisualModality, ReelGenerationTier

class VisualAssetFactory:
    """
    Visual Asset & Cinematic Scene Generator:
    Produces 1080x1920 (9:16) vertical imagery matching each scene beat:
    - Priority 1: OpenAI DALL-E 3 (when tier is PREMIUM and OPENAI_API_KEY is set)
    - Priority 2: Authentic Public Domain & Historical Archive Media Resolver (Wikimedia / Wikipedia)
    - Priority 3: High-Yield Procedural Vector Schematics (zero debug text overlays)
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
                print(f"⚠️ DALL-E 3 generation failed: {e}. Falling back to authentic archive resolver...")

        # 2. Authentic Public Domain Archive Media Resolver (Real Historical / Scientific Imagery)
        if cls._resolve_archive_visual(scene, output_image_path):
            return output_image_path

        # 3. Clean Procedural Visual Schematic (No debug text boxes)
        return cls._render_procedural_cinematic(scene, output_image_path)

    @classmethod
    def _resolve_archive_visual(cls, scene: SceneBeat, output_path: str) -> bool:
        """
        Fetches authentic public-domain photographs, museum archives, and scientific diagrams
        from Wikimedia Commons / Wikipedia, then composites them into 9:16 vertical cinema stills.
        """
        prompt_lower = scene.visual_prompt.lower()
        queries = []

        if any(w in prompt_lower for w in ["bhagat", "assembly", "lahore", "delhi", "freedom", "martyr", "revolution"]):
            scene_queries = {
                1: ["Bhagat Singh 1929", "Bhagat Singh portrait felt hat"],
                2: ["Central Assembly Hall New Delhi", "Central Legislative Assembly Delhi"],
                3: ["Central Legislative Assembly bombing 1929", "The Tribune 1929 bombing"],
                4: ["Daily milap poster Lahore conspiracy case 1930", "Lahore conspiracy case poster"],
                5: ["Statues of Bhagat Singh Hussainiwala", "Bhagat Singh Rajguru Sukhdev Hussainiwala"],
                6: ["Delhi India Red Fort Facade", "Red Fort New Delhi"]
            }
            queries.extend(scene_queries.get(scene.scene_number, ["Bhagat Singh 1929"]))
            queries.append("Bhagat Singh")
        elif any(w in prompt_lower for w in ["chloroplast", "photosynthesis", "cell", "plant"]):
            queries.extend(["Chloroplast diagram", "Thylakoid ultrastructure", "Plant cell structure"])
        elif any(w in prompt_lower for w in ["rocket", "exhaust", "propulsion", "space"]):
            queries.extend(["Falcon 9 launch exhaust plume", "Rocket engine test combustion plume", "Space Shuttle launch"])
        else:
            # Extract meaningful nouns from visual prompt
            words = [w for w in scene.visual_prompt.split() if len(w) > 3 and w.lower() not in (
                "dramatic", "cinematic", "photorealistic", "vertical", "composition", "lighting", "shallow", "depth", "field"
            )]
            if words:
                queries.append(" ".join(words[:3]))

        headers = {'User-Agent': 'ConceptlyStudio/1.0 (contact@conceptly.app)'}
        img_url = None

        for q in queries:
            try:
                url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(q)}&gsrnamespace=6&gsrlimit=3&prop=imageinfo&iiprop=url&format=json"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=4.0) as r:
                    data = json.loads(r.read())
                    pages = data.get("query", {}).get("pages", {})
                    for pid, page in pages.items():
                        infos = page.get("imageinfo", [])
                        if infos and infos[0].get("url"):
                            clean_u = infos[0]["url"].split("?")[0]
                            if clean_u.lower().endswith((".jpg", ".jpeg", ".png")):
                                img_url = clean_u
                                break
                if img_url:
                    break
            except Exception:
                continue

        if not img_url:
            return False

        temp_raw = output_path + ".temp"
        try:
            req_img = urllib.request.Request(img_url, headers=headers)
            with urllib.request.urlopen(req_img, timeout=10.0) as resp, open(temp_raw, "wb") as f:
                f.write(resp.read())

            with Image.open(temp_raw) as raw_im:
                im = raw_im.convert("RGB")
            if os.path.exists(temp_raw):
                os.remove(temp_raw)

            cls._composite_real_photo_vertical(im, output_path, scene)
            return True
        except Exception as e:
            print(f"⚠️ Archive photo composition failed: {e}")
            if os.path.exists(temp_raw):
                try: os.remove(temp_raw)
                except Exception: pass
            return False

    @classmethod
    def _composite_real_photo_vertical(cls, im: Image.Image, output_path: str, scene: SceneBeat):
        """
        Composites an authentic photograph into a cinematic 1080x1920 vertical frame:
        - Layer 1: Blurred atmospheric ambient backdrop derived from the photograph itself
        - Layer 2: Hero sharp centerpiece, aspect-fit in the upper-mid viewing area
        - Layer 3: Warm golden ambient border and bottom subtitle vignette (ZERO prompt text)
        """
        W, H = cls.WIDTH, cls.HEIGHT
        canvas = Image.new("RGB", (W, H), (15, 10, 8))

        # 1. Atmospheric blurred backdrop
        bg = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(35))
        dark_overlay = Image.new("RGB", (W, H), (12, 8, 6))
        bg = Image.blend(bg, dark_overlay, 0.40)
        canvas.paste(bg, (0, 0))

        # 2. Hero Centerpiece (Aspect-fit inside 980x1120 area, centered at Y=640)
        max_w, max_h = 980, 1120
        aspect = im.width / float(im.height)
        if aspect > (max_w / float(max_h)):
            fg_w = max_w
            fg_h = int(fg_w / aspect)
        else:
            fg_h = max_h
            fg_w = int(fg_h * aspect)

        fg = im.resize((fg_w, fg_h), Image.LANCZOS)
        x = (W - fg_w) // 2
        y = 640 - (fg_h // 2)

        draw = ImageDraw.Draw(canvas)
        # Subtle ambient gold border around authentic historical photo
        draw.rounded_rectangle([(x - 6, y - 6), (x + fg_w + 6, y + fg_h + 6)], radius=20, outline=(245, 158, 11), width=4)
        canvas.paste(fg, (x, y))

        # 3. Bottom vignette gradient to guarantee subtitle legibility in safe zone
        for i in range(480):
            alpha = int(220 * (i / 480.0))
            y_pos = H - 480 + i
            draw.line([(0, y_pos), (W, y_pos)], fill=(12, 8, 6, alpha))

        # 4. Burned-in Subtitle Safe Zone Box at Y = 1360px - 1490px
        sub_box = [(60, 1360), (cls.WIDTH - 60, 1490)]
        draw.rounded_rectangle(sub_box, radius=20, fill=(15, 23, 42), outline=(245, 158, 11), width=2)
        font_sub = cls._get_font(34, bold=True)
        sub_lines = cls._wrap_text(scene.spoken_line, max_chars=42)
        y_sub = 1380
        for line in sub_lines[:2]:
            bbox = draw.textbbox((0, 0), line, font=font_sub)
            text_w = bbox[2] - bbox[0]
            x_sub = (cls.WIDTH - text_w) // 2
            draw.text((x_sub, y_sub), line, fill=(255, 255, 255), font=font_sub)
            y_sub += 48

        canvas.save(output_path, "PNG")

    @classmethod
    def _render_procedural_cinematic(cls, scene: SceneBeat, output_path: str) -> str:
        """
        Renders clean, domain-themed 1080x1920 graphical visual frames with atmospheric
        lighting and vector schematics (NEVER printing raw prompt debug text on screen).
        """
        img = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (10, 15, 26))
        draw = ImageDraw.Draw(img)

        is_history = scene.visual_modality == VisualModality.CINEMATIC_SCENE and any(
            w in scene.visual_prompt.lower() for w in ["bhagat", "history", "court", "assembly", "jail", "flag"]
        )
        is_bio = scene.visual_modality == VisualModality.ANATOMICAL_3D or "chloroplast" in scene.visual_prompt.lower()

        if is_history:
            bg_start = (28, 20, 14)
            bg_end = (15, 10, 8)
            accent_glow = (245, 158, 11)
            hero_title = "HISTORIC CHRONICLE • 1929"
        elif is_bio:
            bg_start = (6, 32, 24)
            bg_end = (4, 18, 14)
            accent_glow = (16, 185, 129)
            hero_title = "CELLULAR MOLECULAR BIOLOGY"
        else:
            bg_start = (11, 18, 38)
            bg_end = (6, 10, 22)
            accent_glow = (56, 189, 248)
            hero_title = "PHYSICAL FORCES & MECHANICS"

        # 1. Vertical background gradient
        steps = 120
        step_h = cls.HEIGHT // steps
        for i in range(steps):
            ratio = i / float(steps)
            r = int(bg_start[0] * (1 - ratio) + bg_end[0] * ratio)
            g = int(bg_start[1] * (1 - ratio) + bg_end[1] * ratio)
            b = int(bg_start[2] * (1 - ratio) + bg_end[2] * ratio)
            draw.rectangle([(0, i * step_h), (cls.WIDTH, (i + 1) * step_h)], fill=(r, g, b))

        # 2. Radial glow spotlight in center
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

        font_badge = cls._get_font(26, bold=True)
        font_hero = cls._get_font(44, bold=True)

        # Header Badge
        draw.rounded_rectangle([(80, 160), (480, 215)], radius=18, fill=(20, 28, 48), outline=accent_glow, width=2)
        draw.text((105, 173), hero_title, fill=accent_glow, font=font_badge)
        draw.text((cls.WIDTH - 220, 173), f"SCENE {scene.scene_number:02d}", fill=(148, 163, 184), font=font_badge)

        # Hero Center Graphic Canvas
        card_box = [(80, 260), (cls.WIDTH - 80, 1260)]
        draw.rounded_rectangle(card_box, radius=32, fill=(17, 24, 39, 230), outline=(40, 54, 80), width=3)

        if is_history:
            draw.ellipse([(cls.WIDTH//2 - 240, 360), (cls.WIDTH//2 + 240, 840)], outline=accent_glow, width=4)
            scene_titles = {
                1: ("HISTORIC CHRONICLE", "Delhi Central Assembly • 1929"),
                2: ("THE PAMPHLETS", "To Make the Deaf Hear"),
                3: ("THE TRIAL", "Colonial Dock as Megaphone"),
                4: ("JAIL WRITINGS", "Lahore Central Prison • 1930"),
                5: ("THE MARTYRS", "March 23, 1931 • Shaheed Diwas"),
                6: ("INQUILAB ZINDABAD", "Freedom Flame • Swaraj")
            }
            s_tag, s_sub = scene_titles.get(scene.scene_number, ("HISTORIC CHRONICLE", "Freedom Struggle 1929"))
            draw.text((cls.WIDTH//2 - 190, 560), s_tag, fill=accent_glow, font=font_hero)
            draw.text((120, 940), s_sub, fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_bio:
            for r in [200, 140, 80]:
                draw.ellipse([(cls.WIDTH//2 - r, 580 - r), (cls.WIDTH//2 + r, 580 + r)], outline=accent_glow, width=3)
            draw.text((cls.WIDTH//2 - 170, 560), "CHLOROPLAST", fill=accent_glow, font=font_hero)
            draw.text((120, 940), "Thylakoid Solar Stacks • Grana", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        else:
            cx, cy = cls.WIDTH // 2, 580
            draw.line([(cx - 280, cy), (cx - 40, cy)], fill=(245, 158, 11), width=10)
            draw.polygon([(cx - 300, cy), (cx - 270, cy - 18), (cx - 270, cy + 18)], fill=(245, 158, 11))
            draw.text((cx - 240, cy - 60), "F_action", fill=(245, 158, 11), font=cls._get_font(36, bold=True))

            draw.line([(cx + 40, cy), (cx + 280, cy)], fill=(56, 189, 248), width=10)
            draw.polygon([(cx + 300, cy), (cx + 270, cy - 18), (cx + 270, cy + 18)], fill=(56, 189, 248))
            draw.text((cx + 120, cy - 60), "F_reaction", fill=(56, 189, 248), font=cls._get_font(36, bold=True))

            draw.line([(cx, cy - 100), (cx, cy + 100)], fill=(255, 255, 255), width=4)
            draw.text((120, 940), "Action-Reaction on Different Bodies", fill=(248, 250, 252), font=cls._get_font(34, bold=True))

        # Burned-in Subtitle Safe Zone Box at Y = 1360px - 1490px
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
