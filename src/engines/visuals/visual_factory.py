import os
import math
import random
import urllib.request
import urllib.parse
import json
from typing import Optional, List, Any, Dict
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.core.config import settings
from src.models.schemas import SceneBeat, VisualModality, ReelGenerationTier

class VisualAssetFactory:
    """
    Visual Asset & Cinematic Scene Generator:
    Produces 1080x1920 (9:16) vertical imagery matching each scene beat:
    - 100% Dynamic Neural Generation (Fal.ai FLUX.1 / DALL-E 3 / Hugging Face FLUX.1 / Pollinations FLUX.1)
    - Dynamic Living World & 3D Presenter Avatar Compositor
    - Dynamic Public Domain Scientific Archive Resolver (Wikimedia Commons)
    Zero hardcoded keyword dispatchers or deterministic procedural fallback simulations.
    """

    WIDTH = 1080
    HEIGHT = 1920

    @classmethod
    def render_scene_image(
        cls,
        scene: SceneBeat,
        output_image_path: str,
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT,
        avatar: Optional[Any] = None
    ) -> str:
        """
        Synthesizes the complete visual frame using strict layer separation:
        1. Layer 1 (GEN): Clean, photorealistic neural base visual plate conditioned on the reel's style bible.
        2. Layer 2 (OVERLAY): High-precision, deterministic frosted-glass scientific HUD card (when hud_overlay is defined).
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)

        # 1. Base Visual Plate Generation
        generated = cls._generate_base_visual_plate(scene, output_image_path, tier=tier, avatar=avatar)
        if not generated or not os.path.exists(output_image_path):
            raise RuntimeError(f"Visual asset generation failed for scene {scene.scene_number}: All dynamic neural image providers failed. Please check network connectivity.")

        # 2. Layer 2: Deterministic Scientific HUD Card Compositing
        hud = getattr(scene, "hud_overlay", None)
        if hud:
            cls._apply_hud_overlay(output_image_path, hud)

        return output_image_path

    @classmethod
    def _apply_hud_overlay(cls, image_path: str, hud: Any) -> None:
        """
        Renders a razor-sharp mathematical frosted-glass HUD card onto the upper-third
        of the image. Strictly decouples mathematical accuracy from the AI diffusion model.
        """
        if not hud:
            return

        formula = getattr(hud, "formula", None) or (hud.get("formula") if isinstance(hud, dict) else None)
        label = getattr(hud, "label", None) or (hud.get("label") if isinstance(hud, dict) else None)
        units = getattr(hud, "units", None) or (hud.get("units") if isinstance(hud, dict) else None)
        concept_tag = getattr(hud, "concept_tag", None) or (hud.get("concept_tag") if isinstance(hud, dict) else None)

        if not formula and not label:
            return

        try:
            with Image.open(image_path) as base_img:
                canvas = base_img.convert("RGBA")
                overlay_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay_layer)

                W, H = cls.WIDTH, cls.HEIGHT
                card_w = 940
                card_h = 220 if (units and formula) else 175
                card_x = (W - card_w) // 2
                card_y = 230  # Safely below status bar (0-160px) and well above subtitles (1360-1490px)

                # Frosted glass card body: Deep midnight obsidian with alpha
                draw.rounded_rectangle(
                    [(card_x, card_y), (card_x + card_w, card_y + card_h)],
                    radius=28,
                    fill=(10, 15, 29, 215),
                    outline=(6, 182, 212, 240),  # Glowing cyan accent border
                    width=3
                )

                # Top Category Pill
                tag_text = (concept_tag or label or "SCIENTIFIC CORE").upper()
                font_tag = cls._get_font(22, bold=True)
                draw.text((card_x + 36, card_y + 24), f"⚡ {tag_text}", fill=(6, 182, 212), font=font_tag)

                # Main Hero Formula
                if formula:
                    font_formula = cls._get_font(42, bold=True)
                    draw.text((card_x + 36, card_y + 66), formula, fill=(248, 250, 252), font=font_formula)

                # Units / Context Description
                sub_label = units or label or ""
                if sub_label and sub_label != tag_text:
                    font_sub = cls._get_font(22, bold=False)
                    draw.text((card_x + 36, card_y + (142 if formula else 75)), f"SI Unit / Rule: {sub_label}", fill=(148, 163, 184), font=font_sub)

                final_im = Image.alpha_composite(canvas, overlay_layer).convert("RGB")
                final_im.save(image_path, "PNG")
                print(f"📐 Mathematical HUD card composited onto {image_path}: {formula or label}")
        except Exception as e:
            print(f"⚠️ HUD overlay composition note: {e}")

    @classmethod
    def _generate_base_visual_plate(
        cls,
        scene: SceneBeat,
        output_image_path: str,
        tier: ReelGenerationTier = ReelGenerationTier.DEFAULT,
        avatar: Optional[Any] = None
    ) -> Optional[str]:
        # Style Bible & Negative Prompting (Guarantees visual continuity and zero text hallucination)
        style_bible = getattr(scene, "style_bible", None) or "Cinematic 35mm vertical photography, volumetric lighting, dark atmospheric studio, 9:16 portrait, photorealistic, clean plate, zero text watermarks, no letters"
        negative_rules = "Strictly clean background plate, no text, no words, no letters, no labels, no watermark, no logos, no typography, no equations."

        # 0. Character Avatar Scene Compositing (when scene features the teacher in their 3D world)
        prompt_text = (scene.visual_prompt or "").lower()
        avatar_name = (getattr(avatar, "name", "") or (avatar.get("name", "") if isinstance(avatar, dict) else "")).lower()
        if avatar and (getattr(scene, "scene_number", 1) in (1, 3) or (avatar_name and avatar_name in prompt_text)):
            avatar_id = getattr(avatar, "id", None) or (avatar.get("id") if isinstance(avatar, dict) else None)
            if avatar_id:
                char_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "character_store", avatar_id)
                avatar_img_path = os.path.join(char_dir, "avatar_3d.png")
                world_img_path = os.path.join(char_dir, "world_scene_3d.png")
                if os.path.exists(avatar_img_path):
                    try:
                        base_canvas = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (10, 15, 26))
                        if os.path.exists(world_img_path):
                            with Image.open(world_img_path) as w_img:
                                base_canvas = w_img.convert("RGB").resize((cls.WIDTH, cls.HEIGHT), Image.LANCZOS)
                        with Image.open(avatar_img_path) as a_img:
                            a_rgba = a_img.convert("RGBA")
                            a_w = int(cls.WIDTH * 0.90)
                            a_h = int(a_rgba.height * (a_w / float(a_rgba.width)))
                            a_resized = a_rgba.resize((a_w, a_h), Image.LANCZOS)
                            paste_x = (cls.WIDTH - a_w) // 2
                            paste_y = max(180, cls.HEIGHT - a_h - 220)
                            base_canvas.paste(a_resized, (paste_x, paste_y), a_resized)
                        base_canvas.save(output_image_path, "PNG")
                        print(f"🎭 Composed 3D Character Avatar frame: {output_image_path}")
                        return output_image_path
                    except Exception as e_av:
                        print(f"⚠️ Avatar compositing note: {e_av}")

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
                    "prompt": f"{scene.visual_prompt}. Aesthetic Style: {style_bible}. {negative_rules}",
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
                prompt_9_16 = f"{scene.visual_prompt}. Style Bible: {style_bible}. {negative_rules}"
                
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
                hf_payload = {"inputs": f"{scene.visual_prompt}. Aesthetic Style: {style_bible}. {negative_rules}"}
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

        # 4. Neural Diffusion Visual Tool: Pollinations.ai FLUX.1 (Zero cost, high-res 3D CGI)
        try:
            import httpx
            import urllib.parse
            import io
            
            clean_prompt = scene.visual_prompt.strip()
            enhanced_prompt = f"{clean_prompt}. Aesthetic Style: {style_bible}. {negative_rules}"
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
                    print(f"🎨 Dynamic FLUX image generated via Pollinations: {output_image_path}")
                    return output_image_path
                else:
                    print(f"⚠️ Pollinations FLUX status ({res.status_code}): {res.text[:200]}")
        except Exception as e:
            print(f"⚠️ Pollinations FLUX generation error: {e}")

        # 5. Dynamic Public Domain & Scientific Archive Media Resolver (Wikimedia Commons)
        try:
            if cls._resolve_archive_visual(scene, output_image_path):
                print(f"🏛️ Authentic scientific archive image resolved: {output_image_path}")
                return output_image_path
        except Exception as e:
            print(f"⚠️ Archive media resolver failed: {e}")

        return None

    _ARCHIVE_URL_CACHE: dict = {}
    _USED_ARCHIVE_URLS: set = set()

    @classmethod
    def reset_job_session(cls):
        """Clears per-job used URLs so every scene gets a fresh, unique visual."""
        cls._USED_ARCHIVE_URLS.clear()

    @classmethod
    def _extract_candidate_queries(cls, scene: SceneBeat) -> List[str]:
        """
        Dynamically derives concise, scene-specific search keywords from the scene's prompt
        and spoken line to query Wikimedia Commons for ANY topic in the world.
        Zero hardcoded keyword dispatchers or pre-programmed topic switches.
        """
        import re
        queries: List[str] = []
        prompt = scene.visual_prompt
        spoken = scene.spoken_line

        # 1. Extract proper nouns, capitalized scientific laws, and quoted terms dynamically
        scientific_terms = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", spoken)
        for term in scientific_terms:
            t_clean = term.strip().lower()
            if len(t_clean) > 4 and t_clean not in ["conceptly studio", "scene beat"]:
                queries.append(t_clean)

        # 2. Strip AI prompt boilerplate, rendering buzzwords, mascot names, and visual fluff
        cleaned = re.sub(
            r"(?i)\b(photorealistic|vertical 9:16|cinematic lighting|sharp focus|macro close-up|hyper-detailed|"
            r"dark background|no text watermarks|8k resolution|unreal engine|volumetric light|high-contrast|illustration|"
            r"ultra realistic|studio lighting|dramatic lighting|shot on 35mm|close up|view of|diagram of|render of|"
            r"detailed|extreme close-up|cross section|vector diagram|white background|bright neon|glowing neon|"
            r"kurzgesagt|studio|signature|cartoon|scientist|duck|mascot|quarks|dr quarks|einstein|kalam|franklin|arya|"
            r"pointing|enthusiastically|smiling|wearing|standing|holding|glowing|bright|neon|vibrant|cosmic|space|"
            r"3d avatar|avatar|pixar|cyberpunk|tech-noir|octane render|turnaround|isolated|flat vector|style)\b",
            " ",
            prompt.lower()
        )
        cleaned = re.sub(r"[,\.\(\)\"\:\-\_\/\#]", " ", cleaned)
        words = [w.strip() for w in cleaned.split() if len(w.strip()) > 3]

        if len(words) >= 2:
            queries.append(f"{words[0]} {words[1]}")
        if len(words) >= 3:
            queries.append(f"{words[0]} {words[1]} {words[2]}")
        if len(words) >= 4:
            queries.append(f"{words[1]} {words[2]}")

        # 3. Substantive spoken terms
        spoken_cleaned = re.sub(r"[,\.\(\)\"\:\-\_\?\!]", " ", spoken.lower())
        stop_words = {
            "does", "what", "when", "where", "which", "actually", "inside", "looking",
            "right", "there", "about", "their", "these", "those", "because", "every",
            "first", "second", "third", "think", "never", "always", "would", "could", "should",
            "just", "make", "once", "this", "exact", "like"
        }
        s_words = [w.strip() for w in spoken_cleaned.split() if len(w.strip()) > 3 and w not in stop_words]
        if len(s_words) >= 2:
            queries.append(f"{s_words[0]} {s_words[1]}")
        if len(s_words) >= 3:
            queries.append(f"{s_words[0]} {s_words[1]} {s_words[2]}")

        return list(dict.fromkeys(queries))

    @classmethod
    def _resolve_archive_visual(cls, scene: SceneBeat, output_path: str) -> bool:
        """
        Dynamically queries Wikimedia Commons / Wikipedia for authentic public-domain
        scientific diagrams, medical illustrations, museum archives, and historical photography
        for ANY of millions of topics in the world, then composites into a 9:16 vertical cinema frame.
        Strictly enforces de-duplication: no two scenes in the same reel can ever use the same image.
        """
        candidates = cls._extract_candidate_queries(scene)
        if not candidates:
            return False

        headers = {'User-Agent': 'ConceptlyStudio/1.0 (contact@conceptly.app)'}
        found_img_url: Optional[str] = None

        for query in candidates:
            if query in cls._ARCHIVE_URL_CACHE:
                cached_url = cls._ARCHIVE_URL_CACHE[query]
                if cached_url not in cls._USED_ARCHIVE_URLS:
                    found_img_url = cached_url
                    cls._USED_ARCHIVE_URLS.add(cached_url)
                    break

            try:
                # Use iiurlwidth=1280 to automatically render SVGs and large files into high-res PNG thumbnails
                url = (
                    f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
                    f"&gsrsearch={urllib.parse.quote(query)}&gsrnamespace=6&gsrlimit=8"
                    f"&prop=imageinfo&iiprop=url&iiurlwidth=1280&format=json"
                )
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=4.0) as r:
                    data = json.loads(r.read())
                    pages = data.get("query", {}).get("pages", {})
                    for pid, page in pages.items():
                        title = page.get("title", "")
                        # Filter out PDF document titles which only render book cover pages
                        if title.lower().endswith(".pdf"):
                            continue
                        infos = page.get("imageinfo", [])
                        if infos:
                            thumb = infos[0].get("thumburl") or infos[0].get("url")
                            if thumb:
                                clean_u = thumb.split("?")[0]
                                if clean_u.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                                    if thumb in cls._USED_ARCHIVE_URLS:
                                        continue  # Never repeat an image across scenes
                                    found_img_url = thumb
                                    cls._USED_ARCHIVE_URLS.add(thumb)
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
                # Preserve light background for transparent PNG/SVG diagrams to prevent black-on-black silhouette
                if raw_im.mode in ("RGBA", "LA") or (raw_im.mode == "P" and "transparency" in raw_im.info):
                    alpha_im = raw_im.convert("RGBA")
                    # Clean high-contrast white base for technical diagrams
                    white_base = Image.new("RGB", alpha_im.size, (250, 250, 252))
                    white_base.paste(alpha_im, mask=alpha_im.split()[3])
                    im = white_base
                else:
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
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFPro.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()
