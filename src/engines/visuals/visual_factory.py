import os
import math
import random
import urllib.request
import urllib.parse
import json
from typing import Optional, List
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

        # 1. External Visual Tool: Fal.ai FLUX.1 Schnell (Fastest 9:16 vertical graphics)
        if settings.FAL_KEY:
            try:
                import httpx
                headers = {
                    "Authorization": f"Key {settings.FAL_KEY}",
                    "Content-Type": "application/json"
                }
                endpoint = "https://fal.run/fal-ai/flux/schnell"
                payload = {
                    "prompt": f"{scene.visual_prompt}, high resolution, 9:16 vertical aspect ratio, clear focal point, vibrant colors, cinematic lighting, sharp focus, no text watermarks",
                    "image_size": {"width": 1080, "height": 1920},
                    "num_inference_steps": 4,
                    "enable_safety_checker": False
                }
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(endpoint, headers=headers, json=payload)
                    if resp.status_code == 200:
                        img_data = resp.json()
                        images = img_data.get("images", [])
                        if images and "url" in images[0]:
                            img_url = images[0]["url"]
                            img_res = client.get(img_url)
                            with open(output_image_path, "wb") as f_out:
                                f_out.write(img_res.content)
                            return output_image_path
                    else:
                        print(f"⚠️ Fal.ai FLUX image error ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                print(f"⚠️ Fal.ai FLUX generation failed: {e}")

        # 2. External Visual Tool: OpenAI DALL-E 3
        if settings.OPENAI_API_KEY:
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
                print(f"⚠️ DALL-E 3 generation failed: {e}")

        # 3. External Visual Tool: Hugging Face Serverless FLUX.1 Schnell
        if settings.HF_TOKEN:
            try:
                import httpx
                import io
                hf_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
                hf_headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
                hf_payload = {"inputs": f"{scene.visual_prompt}, vibrant educational illustration, 9:16 vertical aspect ratio, clear focal point, cinematic lighting, sharp focus, no text watermarks"}
                with httpx.Client(timeout=45.0) as client:
                    hf_res = client.post(hf_url, headers=hf_headers, json=hf_payload)
                    if hf_res.status_code == 200 and len(hf_res.content) > 5000:
                        with Image.open(io.BytesIO(hf_res.content)) as im:
                            im = im.convert("RGB")
                            if im.size != (cls.WIDTH, cls.HEIGHT):
                                im = im.resize((cls.WIDTH, cls.HEIGHT), Image.LANCZOS)
                            im.save(output_image_path, "PNG")
                        print(f"🎨 External FLUX image generated via Hugging Face: {output_image_path}")
                        return output_image_path
            except Exception as e:
                print(f"⚠️ Hugging Face FLUX generation failed: {e}")

        # 4. Free External Visual Tool: Pollinations.ai FLUX.1 (Supports POLLEN_KEY or keyless)
        try:
            import httpx
            import urllib.parse
            import io
            
            clean_prompt = scene.visual_prompt.strip()
            enhanced_prompt = f"{clean_prompt}, clean educational graphic illustration, Kurzgesagt vibrant scientific art style, flat vector aesthetic, high contrast, crisp details, 9:16 vertical composition, no text watermarks, 4k"
            encoded_prompt = urllib.parse.quote(enhanced_prompt)
            seed = getattr(scene, "scene_number", 1) * 137 + 42
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=576&height=1024&model=flux&nologo=true&seed={seed}"
            headers = {}
            if settings.POLLEN_KEY:
                headers["Authorization"] = f"Bearer {settings.POLLEN_KEY}"
            
            with httpx.Client(timeout=50.0) as client:
                res = client.get(url, headers=headers, follow_redirects=True)
                if res.status_code == 200 and len(res.content) > 5000:
                    with Image.open(io.BytesIO(res.content)) as im:
                        im = im.convert("RGB")
                        if im.size != (cls.WIDTH, cls.HEIGHT):
                            im = im.resize((cls.WIDTH, cls.HEIGHT), Image.LANCZOS)
                        im.save(output_image_path, "PNG")
                    print(f"🎨 External FLUX image generated via Pollinations: {output_image_path}")
                    return output_image_path
                else:
                    print(f"⚠️ Pollinations FLUX status ({res.status_code}): {res.text[:200]}")
        except Exception as e:
            print(f"⚠️ Pollinations FLUX generation error: {e}")

        # STRICTLY NO FALLBACK: If external tools are not configured or failed, throw explicit error
        raise RuntimeError(
            "Missing External Visual Generation Tool: Generating authentic, prompt-accurate graphics "
            "for arbitrary curriculum topics requires an external visual model. "
            "Please configure FAL_KEY (recommended for Fal.ai FLUX & Kling), OPENAI_API_KEY, HF_TOKEN, or POLLEN_KEY in your .env file. "
            "Internal geometric fallbacks have been permanently disabled per your strict requirement."
        )

    _ARCHIVE_URL_CACHE: dict = {}

    @classmethod
    def _extract_candidate_queries(cls, scene: SceneBeat) -> List[str]:
        """
        Dynamically derives 2 to 4 concise search keywords from the scene's prompt
        and spoken line to query Wikimedia Commons for ANY topic in the world.
        """
        import re
        queries: List[str] = []
        prompt = scene.visual_prompt.lower()
        
        # Strip AI prompt boilerplate
        cleaned = re.sub(
            r"(?i)\b(photorealistic|vertical 9:16|cinematic lighting|sharp focus|macro close-up|hyper-detailed|"
            r"dark background|no text watermarks|8k resolution|unreal engine|volumetric light|high-contrast|illustration|"
            r"ultra realistic|studio lighting|dramatic lighting|shot on 35mm|close up|view of|diagram of|render of|"
            r"detailed|extreme close-up|cross section|vector diagram|white background)\b",
            "",
            prompt
        )
        cleaned = re.sub(r"[,\.\(\)\"\:\-\_\/\#]", " ", cleaned)
        words = [w.strip() for w in cleaned.split() if len(w.strip()) > 3]

        # Candidate 1: First 2 substantive words (e.g. "triangular prism", "mrna vaccine")
        if len(words) >= 2:
            queries.append(f"{words[0]} {words[1]}")
        # Candidate 2: First 3 substantive words (e.g. "prism dispersion spectrum", "bastille storming 1789")
        if len(words) >= 3:
            queries.append(f"{words[0]} {words[1]} {words[2]}")
        # Candidate 3: Secondary focus words
        if len(words) >= 4:
            queries.append(f"{words[1]} {words[2]}")

        # Extract substantive terms from spoken line as well
        spoken_cleaned = re.sub(r"[,\.\(\)\"\:\-\_\?\!]", " ", scene.spoken_line.lower())
        stop_words = {
            "does", "what", "when", "where", "which", "actually", "inside", "looking",
            "right", "there", "about", "their", "these", "those", "because", "every",
            "first", "second", "third", "think", "never", "always", "would", "could", "should"
        }
        s_words = [w.strip() for w in spoken_cleaned.split() if len(w.strip()) > 3 and w not in stop_words]
        if len(s_words) >= 2:
            queries.append(f"{s_words[0]} {s_words[1]}")
        if len(s_words) >= 3:
            queries.append(f"{s_words[0]} {s_words[1]} {s_words[2]}")

        # De-duplicate while preserving prioritization
        return list(dict.fromkeys(queries))

    @classmethod
    def _resolve_archive_visual(cls, scene: SceneBeat, output_path: str) -> bool:
        """
        Dynamically queries Wikimedia Commons / Wikipedia for authentic public-domain
        scientific diagrams, medical illustrations, museum archives, and historical photography
        for ANY of millions of topics in the world, then composites into a 9:16 vertical cinema frame.
        """
        candidates = cls._extract_candidate_queries(scene)
        if not candidates:
            return False

        headers = {'User-Agent': 'ConceptlyStudio/1.0 (contact@conceptly.app)'}
        found_img_url: Optional[str] = None

        for query in candidates:
            if query in cls._ARCHIVE_URL_CACHE:
                found_img_url = cls._ARCHIVE_URL_CACHE[query]
                break

            try:
                # Use iiurlwidth=1280 to automatically render SVGs and large files into high-res PNG thumbnails
                url = (
                    f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
                    f"&gsrsearch={urllib.parse.quote(query)}&gsrnamespace=6&gsrlimit=3"
                    f"&prop=imageinfo&iiprop=url&iiurlwidth=1280&format=json"
                )
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=3.0) as r:
                    data = json.loads(r.read())
                    pages = data.get("query", {}).get("pages", {})
                    for pid, page in pages.items():
                        infos = page.get("imageinfo", [])
                        if infos:
                            thumb = infos[0].get("thumburl") or infos[0].get("url")
                            if thumb:
                                clean_u = thumb.split("?")[0]
                                if clean_u.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                                    found_img_url = thumb
                                    cls._ARCHIVE_URL_CACHE[query] = found_img_url
                                    break
                if found_img_url:
                    break
            except Exception:
                continue

        if not found_img_url:
            return False

        temp_raw = output_path + ".temp"
        try:
            req_img = urllib.request.Request(found_img_url, headers=headers)
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

        prompt_lower = scene.visual_prompt.lower()
        spoken_lower = scene.spoken_line.lower()
        full_text = f"{prompt_lower} {spoken_lower}"

        is_history = scene.visual_modality == VisualModality.CINEMATIC_SCENE and any(
            w in full_text for w in ["bhagat", "history", "court", "assembly", "jail", "flag", "revolution", "freedom", "war"]
        )
        is_optics = any(w in full_text for w in ["prism", "light", "refraction", "reflection", "spectrum", "dispersion", "lens", "wavelength", "rainbow", "optics"])
        is_bio = any(w in full_text for w in ["chloroplast", "photosynthesis", "cell", "dna", "mitosis", "organ", "plant", "heart", "gene"])
        is_chemistry = any(w in full_text for w in ["reaction", "molecule", "atom", "magnesium", "acid", "bond", "electron", "compound", "oxide", "element"])
        is_electricity = any(w in full_text for w in ["ohm", "resistance", "current", "voltage", "circuit", "amperes", "resistor"])
        is_magnetism = any(w in full_text for w in ["magnet", "lorentz", "magnetic field", "f=ilb", "tesla", "solenoid"])
        is_rocket = any(w in full_text for w in ["rocket", "exhaust", "propulsion", "thrust"])

        if is_history:
            bg_start = (28, 20, 14)
            bg_end = (15, 10, 8)
            accent_glow = (245, 158, 11)
            hero_title = "HISTORICAL ARCHIVE & CHRONICLE"
        elif is_optics:
            bg_start = (10, 18, 32)
            bg_end = (6, 12, 22)
            accent_glow = (56, 189, 248)
            hero_title = "OPTICS & WAVE DISPERSION"
        elif is_bio:
            bg_start = (6, 32, 24)
            bg_end = (4, 18, 14)
            accent_glow = (16, 185, 129)
            hero_title = "CELLULAR MOLECULAR BIOLOGY"
        elif is_chemistry:
            bg_start = (30, 20, 12)
            bg_end = (18, 10, 6)
            accent_glow = (251, 146, 60)
            hero_title = "CHEMICAL MOLECULAR DYNAMICS"
        elif is_electricity:
            bg_start = (26, 24, 10)
            bg_end = (16, 14, 6)
            accent_glow = (234, 179, 8)
            hero_title = "ELECTRICITY & CIRCUIT LAWS"
        elif is_magnetism:
            bg_start = (8, 24, 34)
            bg_end = (4, 14, 22)
            accent_glow = (0, 240, 255)
            hero_title = "ELECTROMAGNETIC FORCES"
        elif is_rocket:
            bg_start = (26, 12, 12)
            bg_end = (16, 8, 8)
            accent_glow = (239, 68, 68)
            hero_title = "NEWTONIAN PROPULSION"
        else:
            bg_start = (18, 14, 30)
            bg_end = (10, 8, 18)
            accent_glow = (168, 85, 247)
            hero_title = "CONCEPTUAL SCIENTIFIC PRINCIPLE"

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
        draw.rounded_rectangle([(80, 160), (520, 215)], radius=18, fill=(20, 28, 48), outline=accent_glow, width=2)
        draw.text((105, 173), hero_title, fill=accent_glow, font=font_badge)
        draw.text((cls.WIDTH - 220, 173), f"SCENE {scene.scene_number:02d}", fill=(148, 163, 184), font=font_badge)

        # Hero Center Graphic Canvas
        card_box = [(80, 260), (cls.WIDTH - 80, 1260)]
        draw.rounded_rectangle(card_box, radius=32, fill=(17, 24, 39, 230), outline=(40, 54, 80), width=3)

        cx, cy = cls.WIDTH // 2, 620

        if is_history:
            draw.ellipse([(cx - 240, 360), (cx + 240, 840)], outline=accent_glow, width=4)
            words = [w for w in scene.spoken_line.split() if len(w) > 2]
            title_text = " ".join(words[:5]) if words else "Historical Chronicle"
            draw.text((cx - 190, 560), "HISTORIC CHRONICLE", fill=accent_glow, font=font_hero)
            draw.text((120, 940), f"{title_text}...", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_optics:
            # Triangular Glass Prism & Rainbow Spectrum
            apex = (cx - 40, cy - 200)
            p_left = (cx - 260, cy + 180)
            p_right = (cx + 180, cy + 180)
            draw.polygon([apex, p_left, p_right], fill=(22, 36, 58), outline=accent_glow, width=4)

            # Incident White Light Ray
            src_x, src_y = 120, cy - 40
            hit_x, hit_y = cx - 150, cy - 10
            draw.line([(src_x, src_y), (hit_x, hit_y)], fill=(255, 255, 255), width=8)
            draw.text((120, cy - 90), "White Light", fill=(255, 255, 255), font=cls._get_font(26, bold=True))

            # 7 Rainbow Rays Emerging
            spectrum_cols = [
                ("Red", (255, 59, 48), -50),
                ("Orange", (255, 149, 0), -25),
                ("Yellow", (255, 204, 0), 0),
                ("Green", (52, 199, 89), 25),
                ("Blue", (0, 199, 255), 50),
                ("Violet", (175, 82, 222), 75)
            ]
            scr_x = cls.WIDTH - 140
            for c_name, c_rgb, dev in spectrum_cols:
                ex_x = cx + 80
                ex_y = cy - 10 + dev // 3
                draw.line([(hit_x, hit_y), (ex_x, ex_y)], fill=c_rgb, width=3)
                draw.line([(ex_x, ex_y), (scr_x, cy + dev * 3)], fill=c_rgb, width=5)

            # Screen
            draw.rounded_rectangle([(scr_x - 6, cy - 180), (scr_x + 16, cy + 250)], radius=6, fill=(240, 245, 255))
            draw.text((120, 940), "Prism Dispersion: Red Bends Least, Violet Most", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_bio:
            for r in [200, 140, 80]:
                draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=accent_glow, width=3)
            draw.text((cx - 170, cy - 20), "CELLULAR NANO-ENGINE", fill=accent_glow, font=font_hero)
            draw.text((120, 940), "Biochemical Energy Synthesis & Thylakoids", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_chemistry:
            for r in [180, 120, 60]:
                draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(80, 60, 40), width=2)
            draw.ellipse([(cx - 30, cy - 30), (cx + 30, cy + 30)], fill=accent_glow)
            draw.text((cx - 180, cy - 30), "MOLECULAR REACTION", fill=accent_glow, font=font_hero)
            draw.text((120, 940), "Oxidation & Synthesis: Energy Redistribution", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_electricity:
            draw.rectangle([(cx - 240, cy - 100), (cx + 240, cy + 100)], outline=accent_glow, width=4)
            draw.text((cx - 160, cy - 30), "CIRCUIT: V = I · R", fill=accent_glow, font=font_hero)
            draw.text((120, 940), "Ohm's Law: Current Proportional to Voltage", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_magnetism:
            draw.rectangle([(cx - 280, cy - 120), (cx - 120, cy + 120)], fill=(220, 38, 38), outline=(255, 255, 255), width=2)
            draw.text((cx - 220, cy - 25), "N", fill=(255, 255, 255), font=font_hero)
            draw.rectangle([(cx + 120, cy - 120), (cx + 280, cy + 120)], fill=(37, 99, 235), outline=(255, 255, 255), width=2)
            draw.text((cx + 180, cy - 25), "S", fill=(255, 255, 255), font=font_hero)
            draw.line([(cx - 120, cy), (cx + 120, cy)], fill=(0, 240, 255), width=6)
            draw.text((120, 940), "Magnetic Force: F = I · L · B", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        elif is_rocket:
            draw.line([(cx - 280, cy), (cx - 40, cy)], fill=(245, 158, 11), width=10)
            draw.polygon([(cx - 300, cy), (cx - 270, cy - 18), (cx - 270, cy + 18)], fill=(245, 158, 11))
            draw.text((cx - 240, cy - 60), "F_action", fill=(245, 158, 11), font=cls._get_font(36, bold=True))
            draw.line([(cx + 40, cy), (cx + 280, cy)], fill=(56, 189, 248), width=10)
            draw.polygon([(cx + 300, cy), (cx + 270, cy - 18), (cx + 270, cy + 18)], fill=(56, 189, 248))
            draw.text((cx + 120, cy - 60), "F_reaction", fill=(56, 189, 248), font=cls._get_font(36, bold=True))
            draw.line([(cx, cy - 100), (cx, cy + 100)], fill=(255, 255, 255), width=4)
            draw.text((120, 940), "Newton 3: Action-Reaction on Different Bodies", fill=(248, 250, 252), font=cls._get_font(34, bold=True))
        else:
            # Universal Conceptual Schematic
            for i in range(8):
                rad = 140 + i * 20
                draw.ellipse([(cx - rad, cy - rad), (cx + rad, cy + rad)], outline=(40, 32, 60), width=1)
            draw.ellipse([(cx - 100, cy - 100), (cx + 100, cy + 100)], fill=(24, 18, 42), outline=accent_glow, width=3)
            words = [w for w in scene.spoken_line.split() if len(w) > 3]
            summary_snippet = " ".join(words[:6]) if words else "Core Fundamental Principle"
            draw.text((cx - 170, cy - 25), "CORE PRINCIPLE", fill=accent_glow, font=font_hero)
            draw.text((120, 940), f"{summary_snippet}...", fill=(248, 250, 252), font=cls._get_font(34, bold=True))

        # Subtitles are dynamically burned in by ASS Compositor with word-level chronometry
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
