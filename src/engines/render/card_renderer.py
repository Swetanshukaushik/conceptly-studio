import os
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from src.models.schemas import ActScript, ReelScript

class CardRenderer:
    """
    Procedural Motion Card Renderer:
    Generates pixel-perfect 1080x1920 Full HD dark-mode visual cards
    strictly respecting CONTRACT.md UI Safe Zones:
    - Top 120px: Reserved for native nav
    - Safe Content Zone: Y = 180px to Y = 1350px
    - Subtitle Anchor: Y = 1350px to Y = 1450px (clear background)
    - Bottom 320px: Reserved for native player controls & Quiz CTA
    """

    WIDTH = 1080
    HEIGHT = 1920

    # Colors
    BG_TOP = (9, 13, 22)        # Deep slate black #090D16
    BG_BOTTOM = (15, 23, 42)    # Dark slate navy #0F172A
    CARD_BG = (17, 24, 39)      # Charcoal card #111827
    CARD_BORDER = (30, 41, 59)  # Subtle stroke #1E293B
    TEXT_WHITE = (248, 250, 252)
    TEXT_MUTED = (148, 163, 184)
    ACCENT_AMBER = (245, 158, 11)   # #F59E0B
    ACCENT_COBALT = (37, 99, 235)   # #2563EB
    ACCENT_EMERALD = (16, 185, 129) # #10B981

    @classmethod
    def _create_base_canvas(cls) -> Image.Image:
        """Creates vertical gradient canvas."""
        canvas = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), cls.BG_TOP)
        draw = ImageDraw.Draw(canvas)
        
        # Vertical gradient simulation
        steps = 100
        step_height = cls.HEIGHT // steps
        for i in range(steps):
            ratio = i / float(steps)
            r = int(cls.BG_TOP[0] * (1 - ratio) + cls.BG_BOTTOM[0] * ratio)
            g = int(cls.BG_TOP[1] * (1 - ratio) + cls.BG_BOTTOM[1] * ratio)
            b = int(cls.BG_TOP[2] * (1 - ratio) + cls.BG_BOTTOM[2] * ratio)
            draw.rectangle(
                [(0, i * step_height), (cls.WIDTH, (i + 1) * step_height)],
                fill=(r, g, b)
            )
        return canvas

    @classmethod
    def _get_font(cls, size: int, bold: bool = False) -> ImageFont.ImageFont:
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

    @classmethod
    def render_act_card(
        cls,
        act: ActScript,
        topic_title: str,
        subject: str,
        class_level: Optional[int],
        output_image_path: str
    ) -> str:
        """Renders a single 1080x1920 frame for a screenplay act."""
        os.makedirs(os.path.dirname(os.path.abspath(output_image_path)), exist_ok=True)
        img = cls._create_base_canvas()
        draw = ImageDraw.Draw(img)

        # 1. Breadcrumb pill at Y = 160px (Safe zone start)
        pill_text = f"{subject.upper()} • CLASS {class_level}" if class_level else subject.upper()
        font_pill = cls._get_font(26, bold=True)
        draw.rounded_rectangle(
            [(80, 150), (440, 205)],
            radius=20,
            fill=(30, 41, 59, 120),
            outline=cls.CARD_BORDER,
            width=2
        )
        draw.text((105, 163), pill_text, fill=cls.ACCENT_AMBER, font=font_pill)

        # 2. Act Indicator Badge at Y = 230px
        font_act = cls._get_font(34, bold=True)
        act_color = cls.ACCENT_AMBER if act.act_number == 1 else (cls.ACCENT_COBALT if act.act_number in [2, 3] else cls.ACCENT_EMERALD)
        draw.text((80, 230), f"ACT {act.act_number}: {act.title.upper()}", fill=act_color, font=font_act)

        # 3. Main Center Card Canvas (Y = 300px to Y = 1280px)
        card_rect = [(80, 300), (cls.WIDTH - 80, 1280)]
        draw.rounded_rectangle(card_rect, radius=32, fill=cls.CARD_BG, outline=cls.CARD_BORDER, width=3)

        # Topic Title inside Card
        font_title = cls._get_font(42, bold=True)
        draw.text((120, 340), topic_title, fill=cls.TEXT_WHITE, font=font_title)
        draw.line([(120, 410), (cls.WIDTH - 120, 410)], fill=cls.CARD_BORDER, width=2)

        # Content based on Card Type
        font_body = cls._get_font(36)
        font_emphasis = cls._get_font(52, bold=True)

        if act.card_type == "HOOK_CARD":
            # Big Paradox Hook Callout
            draw.rounded_rectangle([(120, 460), (cls.WIDTH - 120, 840)], radius=24, fill=(30, 41, 59), outline=cls.ACCENT_AMBER, width=2)
            draw.text((160, 490), "THE PARADOX", fill=cls.ACCENT_AMBER, font=cls._get_font(28, bold=True))
            
            # Multi-line word wrap for hook
            lines = cls._wrap_text(act.spoken_text, max_chars=32)
            y_offset = 550
            for line in lines[:5]:
                draw.text((160, y_offset), line, fill=cls.TEXT_WHITE, font=font_emphasis)
                y_offset += 65

            # Visual cues note
            draw.text((120, 920), "VISUAL DIRECTION", fill=cls.TEXT_MUTED, font=cls._get_font(24, bold=True))
            cue_lines = cls._wrap_text(act.visual_direction, max_chars=48)
            y_offset = 960
            for line in cue_lines[:3]:
                draw.text((120, y_offset), line, fill=cls.TEXT_MUTED, font=font_body)
                y_offset += 45

        elif act.card_type == "ANALOGY_DIAGRAM":
            # Dual Action-Reaction Comparison Boxes
            box1 = [(120, 460), (cls.WIDTH - 120, 680)]
            draw.rounded_rectangle(box1, radius=20, fill=(30, 41, 59), outline=cls.ACCENT_COBALT, width=2)
            draw.text((160, 490), "BODY A  ===>  ACTION FORCE (F1)", fill=cls.ACCENT_COBALT, font=cls._get_font(28, bold=True))
            draw.text((160, 545), "You push the brick wall with +100 N", fill=cls.TEXT_WHITE, font=font_body)

            # Center Opposing Arrows
            draw.text((cls.WIDTH // 2 - 40, 715), "⚡ EQUAL & OPPOSITE ⚡", fill=cls.ACCENT_AMBER, font=cls._get_font(28, bold=True))

            box2 = [(120, 780), (cls.WIDTH - 120, 1000)]
            draw.rounded_rectangle(box2, radius=20, fill=(30, 41, 59), outline=cls.ACCENT_EMERALD, width=2)
            draw.text((160, 810), "BODY B  <===  REACTION FORCE (F2)", fill=cls.ACCENT_EMERALD, font=cls._get_font(28, bold=True))
            draw.text((160, 865), "The wall pushes your hand with -100 N", fill=cls.TEXT_WHITE, font=font_body)

            draw.text((160, 1060), "Key: Forces act on DIFFERENT bodies!", fill=cls.ACCENT_AMBER, font=cls._get_font(32, bold=True))

        elif act.card_type == "COMPARISON_BOX":
            # Real World Rocket / Technology Application
            draw.rounded_rectangle([(120, 460), (cls.WIDTH - 120, 960)], radius=24, fill=(30, 41, 59), outline=cls.ACCENT_COBALT, width=2)
            draw.text((160, 490), "REAL WORLD APPLICATION", fill=cls.ACCENT_COBALT, font=cls._get_font(28, bold=True))
            draw.text((160, 550), "Rocket Acceleration in Space", fill=cls.TEXT_WHITE, font=font_emphasis)
            
            draw.text((160, 650), "1. Engine expels exhaust gas DOWNWARD", fill=cls.TEXT_WHITE, font=font_body)
            draw.text((160, 730), "2. Escaping mass exerts force UPWARD", fill=cls.TEXT_WHITE, font=font_body)
            draw.text((160, 810), "3. Result: Rocket accelerates into orbit!", fill=cls.ACCENT_EMERALD, font=font_body)

        else: # FORMULA_SPOTLIGHT / Summary Card
            draw.rounded_rectangle([(120, 460), (cls.WIDTH - 120, 900)], radius=24, fill=(30, 41, 59), outline=cls.ACCENT_EMERALD, width=3)
            draw.text((160, 500), "CORE FORMULA & PRINCIPLE", fill=cls.ACCENT_EMERALD, font=cls._get_font(28, bold=True))
            draw.text((160, 570), "F_action = - F_reaction", fill=cls.ACCENT_AMBER, font=cls._get_font(58, bold=True))
            
            draw.text((160, 680), "• Forces always occur in matched pairs", fill=cls.TEXT_WHITE, font=font_body)
            draw.text((160, 740), "• Cannot cancel out: act on different objects", fill=cls.TEXT_WHITE, font=font_body)
            draw.text((160, 800), "• Requires 2 interacting bodies to exist", fill=cls.TEXT_WHITE, font=font_body)

        # 4. Burned-in Subtitle Safe Zone Box at Y = 1360px - 1490px
        sub_box = [(60, 1360), (cls.WIDTH - 60, 1490)]
        draw.rounded_rectangle(sub_box, radius=20, fill=(15, 23, 42), outline=cls.ACCENT_AMBER, width=2)
        font_sub = cls._get_font(34, bold=True)
        sub_lines = cls._wrap_text(act.spoken_text, max_chars=42)
        y_sub = 1380
        for line in sub_lines[:2]:
            bbox = draw.textbbox((0, 0), line, font=font_sub)
            text_w = bbox[2] - bbox[0]
            x_sub = (cls.WIDTH - text_w) // 2
            draw.text((x_sub, y_sub), line, fill=cls.TEXT_WHITE, font=font_sub)
            y_sub += 48

        # Save generated frame
        img.save(output_image_path, "PNG")
        return output_image_path

    @classmethod
    def _wrap_text(cls, text: str, max_chars: int = 35) -> List[str]:
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
    def render_reel_frames(cls, script: ReelScript, subject: str, class_level: Optional[int], output_dir: str) -> List[str]:
        """Renders frames for all 4 acts."""
        os.makedirs(output_dir, exist_ok=True)
        frame_paths = []
        for act in script.acts:
            path = os.path.join(output_dir, f"frame_act_{act.act_number}.png")
            cls.render_act_card(act, script.topic_title, subject, class_level, path)
            frame_paths.append(path)
        return frame_paths
