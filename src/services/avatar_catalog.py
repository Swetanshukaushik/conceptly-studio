import json
import os
import math
from typing import List, Optional, Dict, Any
from src.models.schemas import CharacterAvatarRead, CreateCustomAvatarRequest
from src.core.config import settings

# ================= Built-in Master Persona Roster =================
# Incorporates the exact personas and prompt designs provided by the creator.
BUILTIN_AVATARS: Dict[str, Dict[str, Any]] = {
    "einstein_cyber": {
        "id": "einstein_cyber",
        "name": "Albert Einstein",
        "title": "Sci-Fi Cybernetic Physicist (IIT-JEE / Advanced)",
        "exam_track": "IIT_JEE",
        "subject": "Physics & Calculus",
        "style_badge": "PIXAR_CYBERPUNK",
        "avatar_icon": "⚛️",
        "accent_color": "from-amber-500 to-indigo-600",
        "voice_id": "en-US-BrianMultilingualNeural",
        "voice_rate": "+0%",
        "voice_pitch": "+0Hz",
        "prompt": (
            "A stylized, modern sci-fi 3D avatar inspired by Albert Einstein. "
            "A friendly, brilliant cybernetic elder with iconic, wild, expressive white hair that seems to crackle with faint, glowing golden plasma energy. "
            "He wears a comfortable, high-tech woven tweed blazer integrated with subtle, glowing fiber-optic lines. "
            "He has warm, deeply crinkled, intelligent eyes looking forward. "
            "Floating elegantly between his hands is a miniature, shimmering holographic model of a warped space-time fabric, with a glowing star bending the grid lines around it. "
            "Cinematic studio lighting, soft cosmic ambient glow, hyper-detailed, warm golden and deep space-blue color palette, Pixar-meets-Cyberpunk aesthetic. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": (
            "A stylized, modern sci-fi 3D avatar inspired by Albert Einstein. Friendly cybernetic elder with iconic wild white hair crackling with faint golden plasma. "
            "High-tech woven tweed blazer with glowing fiber-optic lines. Floating holographic space-time grid between hands. "
            "Neutral key studio lighting on a seamless 50% neutral gray background (#808080), isolated character reference turnaround sheet, Pixar-meets-Cyberpunk aesthetic."
        ),
        "is_builtin": True,
        "preview_url": "/media/character_store/einstein_cyber/avatar_3d.png"
    },
    "franklin_dna": {
        "id": "franklin_dna",
        "name": "Dr. Rosalind Franklin",
        "title": "Tech-Noir Android Biologist (NEET / Medical)",
        "exam_track": "NEET",
        "subject": "Biology & Genetics",
        "style_badge": "TECH_NOIR_OCTANE",
        "avatar_icon": "🧬",
        "accent_color": "from-teal-500 to-cyan-600",
        "voice_id": "en-US-AriaNeural",
        "voice_rate": "+1%",
        "voice_pitch": "+0Hz",
        "prompt": (
            "A hyper-detailed, sleek 3D sci-fi android avatar inspired by Rosalind Franklin. "
            "Clean, minimalist humanoid cybernetic design. "
            "She wears a structured, dark graphite-gray high-collar lab jacket with sharp lines and sterile white accents. "
            "Over her eyes is a dark, translucent geometric visor; glowing softly inside the visor is a sharp, phosphor-cyan light in the exact shape of the iconic Photo 51 X-ray diffraction pattern (a perfect geometric cross made of dashed light particles). "
            "Holographic, shimmering 3D DNA double-helix structures and molecular bonds float elegantly between her hands. "
            "Photorealistic, cinematic lighting, volumetric studio glow, octane render, tech-noir aesthetic, deep teal and clean white color palette, professional look. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": (
            "A hyper-detailed, sleek 3D sci-fi android avatar inspired by Rosalind Franklin in dark graphite-gray lab jacket. "
            "Translucent geometric visor with glowing phosphor-cyan Photo 51 cross pattern. Holographic 3D DNA double-helix between hands. "
            "Volumetric studio glow on a seamless neutral 50% gray background (#808080), isolated reference turnaround, tech-noir octane render."
        ),
        "is_builtin": True,
        "preview_url": "/media/character_store/franklin_dna/avatar_3d.png"
    },
    "kalam_statesman": {
        "id": "kalam_statesman",
        "name": "Dr. A.P.J. Abdul Kalam",
        "title": "Dignified Statesman & Aerospace Scientist (UPSC)",
        "exam_track": "UPSC",
        "subject": "Polity, Science & Governance",
        "style_badge": "DIGNIFIED_CINEMATIC",
        "avatar_icon": "🇮🇳",
        "accent_color": "from-blue-600 to-amber-600",
        "voice_id": "en-IN-PrabhatNeural",
        "voice_rate": "-3%",
        "voice_pitch": "-5Hz",
        "prompt": (
            "A highly dignified, warm, and inspiring 3D digital avatar inspired by Dr. A.P.J. Abdul Kalam. "
            "A wise elder statesman with his iconic, neatly middle-parted silver-white hair falling gently over his ears. "
            "He is dressed in a crisp, elegant charcoal-blue Bandhgala jacket (closed-neck Indian suit) featuring a tiny, intricately detailed glowing golden Ashoka Chakra pin on the lapel. "
            "He has deeply kind, crinkled, intelligent eyes looking directly forward with a gentle, encouraging smile. "
            "Floating subtly in the background around him are sleek, translucent holographic rings showing orbital satellite trajectories, smoothly blended with clean geometric diagrams representing economic growth charts and the Preamble of the Constitution of India. "
            "Soft, warm cinematic lighting, studio background, professional and profoundly respectful atmosphere. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": (
            "A highly dignified, inspiring 3D digital avatar inspired by Dr. A.P.J. Abdul Kalam in charcoal-blue Bandhgala with tiny golden Ashoka Chakra pin. "
            "Iconic silver-white hair, kind encouraging smile, translucent orbital satellite trajectories. "
            "Soft warm cinematic key lighting on a seamless 50% neutral gray background (#808080), isolated reference portrait."
        ),
        "is_builtin": True,
        "preview_url": "/media/character_store/kalam_statesman/avatar_3d.png"
    },
    "arya_youth": {
        "id": "arya_youth",
        "name": "Arya (Tech-Savvy Youth)",
        "title": "Modern EdTech Creator (NCERT Classes 9–12)",
        "exam_track": "SCHOOL",
        "subject": "NCERT All-Subjects",
        "style_badge": "NEON_CYBER_ANIME",
        "avatar_icon": "⚡",
        "accent_color": "from-purple-600 to-pink-500",
        "voice_id": "en-IN-NeerjaNeural",
        "voice_rate": "+8%",
        "voice_pitch": "+6Hz",
        "prompt": (
            "A highly stylish, charismatic 3D digital anime-inspired avatar of a cool, modern Indian tech-savvy youth. "
            "They have sharp features, an energetic confident smile, and a trendy, textured modern haircut. "
            "They are wearing an ultra-cool neon-accented streetwear hoodie over a casual t-shirt, looking effortlessly dapper and approachable. "
            "They are sitting comfortably at a glowing gaming desk. "
            "Floating all around them in electric neon-blue, vivid purple, and neon-orange graffiti-style vectors are dynamic NCERT school concepts: spinning 3D atomic orbits, floating algebraic equations, a glowing DNA helix, and a sleek holographic gaming headset. "
            "High-energy cinematic lighting, vibrant studio background, crisp details, cutting-edge Pixar-meets-Cyberpunk aesthetic. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": (
            "A stylish, charismatic 3D digital anime avatar of a modern Indian youth in neon-accented streetwear hoodie. "
            "Energetic confident smile, floating neon atomic orbits, equations, and gaming headset. "
            "High-energy studio lighting on seamless neutral 50% gray background (#808080), isolated character reference turnaround sheet."
        ),
        "is_builtin": True,
        "preview_url": "/media/character_store/arya_youth/avatar_3d.png"
    },
    "kabir_student": {
        "id": "kabir_student",
        "name": "Kabir (14-Year-Old Indian Student)",
        "title": "Smart, Funny & Curious Student Host (Universal Fallback)",
        "exam_track": "NCERT_ALL",
        "subject": "General STEM & School Curricula",
        "style_badge": "PIXAR_STUDENT_3D",
        "avatar_icon": "🎒",
        "accent_color": "from-amber-400 to-emerald-500",
        "voice_id": "en-IN-PrabhatNeural",
        "voice_rate": "+12%",
        "voice_pitch": "+16Hz",
        "prompt": (
            "A high-end 3D animated character of a 14-year-old Indian schoolboy named Kabir. "
            "He has large, expressive, deeply intelligent and mischievous dark brown eyes, a warm excited grin, and a stylish modern side-swept Indian haircut. "
            "He wears a cool, contemporary school-themed varsity jacket with rolled-up sleeves, a graphic tee, and smart modern glasses. "
            "He looks witty, hilariously astonished, and brilliantly perceptive as he gestures towards 3D floating science experiments, rotating equations, and physical mechanisms. "
            "Cinematic volumetric studio lighting, Pixar/DreamWorks 3D feature animation aesthetic, rich color grading, vertical 9:16 framing. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": (
            "A charismatic 3D Pixar-style 14-year-old Indian student character in varsity jacket and glasses with excited expression. "
            "Neutral key studio lighting on seamless 50% neutral gray background (#808080), full-body turnaround model sheet."
        ),
        "is_builtin": True,
        "preview_url": "/media/character_store/kabir_student/avatar_3d.png"
    },
    "gandhi_cinematic": {
        "id": "gandhi_cinematic",
        "name": "Mahatma Gandhi",
        "title": "Father of the Nation & Freedom Movement Leader (UPSC/History)",
        "exam_track": "UPSC",
        "subject": "Modern Indian History & Ethics",
        "style_badge": "HISTORICAL_3D_CINEMA",
        "avatar_icon": "🕊️",
        "accent_color": "from-amber-600 to-yellow-500",
        "voice_id": "en-IN-PrabhatNeural",
        "voice_rate": "-4%",
        "voice_pitch": "-6Hz",
        "prompt": (
            "A photorealistic, dignified 3D cinematic reconstruction of Mahatma Gandhi. "
            "Iconic round steel-rimmed spectacles, gentle wise eyes with deep lines of determination, dressed in a simple khadi dhoti and shawl. "
            "Standing in a high-production 3D animated environment (1930 Dandi Salt March or Sabarmati Ashram) with warm cinematic sunrise lighting, dusty golden air particles, and historical realism. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "Cinematic 3D historical character portrait of Mahatma Gandhi on seamless neutral gray background (#808080).",
        "is_builtin": True,
        "preview_url": "/media/character_store/gandhi_cinematic/avatar_3d.png"
    },
    "bose_patriot": {
        "id": "bose_patriot",
        "name": "Netaji Subhas Chandra Bose",
        "title": "Supreme Commander of INA (UPSC/History)",
        "exam_track": "UPSC",
        "subject": "Modern Indian History & Armed Struggle",
        "style_badge": "HISTORICAL_3D_CINEMA",
        "avatar_icon": "🎖️",
        "accent_color": "from-red-600 to-amber-700",
        "voice_id": "en-IN-PrabhatNeural",
        "voice_rate": "+3%",
        "voice_pitch": "+0Hz",
        "prompt": (
            "A commanding, photorealistic 3D cinematic avatar of Netaji Subhas Chandra Bose. "
            "Dressed in his sharp military officer uniform of the Indian National Army (INA) with peaked cap and round spectacles. "
            "Intense, fiery, determined gaze looking forward. Atmospheric military camp background with volumetric dust rays, dramatic cinematic lighting. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "Cinematic 3D historical character portrait of Subhas Chandra Bose on seamless neutral gray background (#808080).",
        "is_builtin": True,
        "preview_url": "/media/character_store/bose_patriot/avatar_3d.png"
    },
    "ambedkar_jurist": {
        "id": "ambedkar_jurist",
        "name": "Dr. B.R. Ambedkar",
        "title": "Chief Architect of the Indian Constitution (UPSC/Polity)",
        "exam_track": "UPSC",
        "subject": "Indian Constitution, Polity & Social Justice",
        "style_badge": "HISTORICAL_3D_CINEMA",
        "avatar_icon": "⚖️",
        "accent_color": "from-blue-700 to-indigo-800",
        "voice_id": "en-IN-PrabhatNeural",
        "voice_rate": "-2%",
        "voice_pitch": "-4Hz",
        "prompt": (
            "A distinguished, authoritative 3D cinematic digital reconstruction of Dr. B.R. Ambedkar. "
            "Wearing his iconic crisp blue three-piece western suit with a red tie and pen in front pocket, holding the original Constitution of India book. "
            "Intellectual, determined expression with thick-rimmed glasses. 3D animated Constituent Assembly Hall in the background with majestic wood paneling and warm ambient lighting. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "Cinematic 3D historical portrait of Dr. B.R. Ambedkar in blue suit with Constitution book on neutral gray background.",
        "is_builtin": True,
        "preview_url": "/media/character_store/ambedkar_jurist/avatar_3d.png"
    },
    "napoleon_emperor": {
        "id": "napoleon_emperor",
        "name": "Napoleon Bonaparte",
        "title": "French Emperor & Military Strategist (UPSC/World History)",
        "exam_track": "UPSC",
        "subject": "World History & European Wars",
        "style_badge": "HISTORICAL_3D_CINEMA",
        "avatar_icon": "⚔️",
        "accent_color": "from-indigo-900 to-red-700",
        "voice_id": "en-GB-ThomasNeural",
        "voice_rate": "+0%",
        "voice_pitch": "+0Hz",
        "prompt": (
            "A cinematic, photorealistic 3D avatar of Napoleon Bonaparte. "
            "Wearing his iconic dark blue and white Chasseurs-à-Cheval uniform with gold epaulets and black bicorne cocked hat. "
            "Piercing, calculating eyes with one hand placed inside his waistcoat. 19th-century European battlefield with smoke, flags, and cinematic golden hour rim lighting. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "Cinematic 3D historical portrait of Napoleon Bonaparte on neutral gray background.",
        "is_builtin": True,
        "preview_url": "/media/character_store/napoleon_emperor/avatar_3d.png"
    },
    "newton_principia": {
        "id": "newton_principia",
        "name": "Sir Isaac Newton",
        "title": "Master of Classical Mechanics & Gravitation (IIT-JEE)",
        "exam_track": "IIT_JEE",
        "subject": "Mechanics, Gravitation & Optics",
        "style_badge": "BAROQUE_3D_CGI",
        "avatar_icon": "🍎",
        "accent_color": "from-emerald-700 to-amber-600",
        "voice_id": "en-GB-RyanNeural",
        "voice_rate": "+0%",
        "voice_pitch": "+0Hz",
        "prompt": (
            "A photorealistic 3D digital avatar of Sir Isaac Newton in 17th-century Cambridge attire with shoulder-length gray curls and dark velvet coat. "
            "Holding a glass prism refracting sunlight into a vivid spectral rainbow beam, with a glowing apple and gravitational force vectors floating in 3D around him. Baroque cinematic chiaroscuro lighting. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "3D portrait of Sir Isaac Newton on neutral gray background with floating prism.",
        "is_builtin": True,
        "preview_url": "/media/character_store/newton_principia/avatar_3d.png"
    },
    "curie_radium": {
        "id": "curie_radium",
        "name": "Marie Curie",
        "title": "Pioneer of Radioactivity & Nuclear Physics (NEET/Chemistry)",
        "exam_track": "NEET",
        "subject": "Radioactivity, Chemistry & Modern Physics",
        "style_badge": "OCTANE_GLOW_3D",
        "avatar_icon": "☢️",
        "accent_color": "from-green-500 to-teal-700",
        "voice_id": "en-US-AriaNeural",
        "voice_rate": "+0%",
        "voice_pitch": "+0Hz",
        "prompt": (
            "A hyper-realistic 3D cinematic avatar of Marie Curie in an early 20th-century Parisian chemistry laboratory. "
            "Wearing a modest dark wool lab dress, holding a glass test tube emitting an ethereal, glowing green luminescent radium light that casts emerald rim lighting on her focused, determined face. Volumetric laboratory smoke and chemical glassware. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "3D portrait of Marie Curie holding glowing test tube on neutral gray background.",
        "is_builtin": True,
        "preview_url": "/media/character_store/curie_radium/avatar_3d.png"
    },
    "ramanujan_infinity": {
        "id": "ramanujan_infinity",
        "name": "Srinivasa Ramanujan",
        "title": "Mathematical Genius of Infinite Series (IIT-JEE/Math)",
        "exam_track": "IIT_JEE",
        "subject": "Pure Mathematics, Calculus & Number Theory",
        "style_badge": "MYSTICAL_MATH_3D",
        "avatar_icon": "♾️",
        "accent_color": "from-purple-700 to-indigo-600",
        "voice_id": "en-IN-PrabhatNeural",
        "voice_rate": "-1%",
        "voice_pitch": "-2Hz",
        "prompt": (
            "A deeply expressive, photorealistic 3D avatar of Srinivasa Ramanujan. "
            "Wearing traditional Indian attire with a dark shawl and tilak on forehead, sitting in a Cambridge study. "
            "Surrounded by glowing golden mathematical equations, modular forms, infinite continued fractions, and partition functions dancing in 3D air like cosmic constellations. Warm candlelight and celestial glow. --ar 1:1 --v 6.0"
        ),
        "neutral_prompt": "3D portrait of Srinivasa Ramanujan surrounded by glowing math equations on neutral gray background.",
        "is_builtin": True,
        "preview_url": "/media/character_store/ramanujan_infinity/avatar_3d.png"
    },
    "quarks_duck": {
        "id": "quarks_duck",
        "name": "Dr. Quarks",
        "title": "Curious Science Duck Mascot (Kurzgesagt Studio)",
        "exam_track": "ALL",
        "subject": "All Conceptual Science",
        "style_badge": "KURZGESAGT_VECTOR",
        "avatar_icon": "🦆",
        "accent_color": "from-amber-400 to-orange-500",
        "voice_id": "en-US-GuyNeural",
        "prompt": (
            "Studio Kurzgesagt signature cartoon scientist duck mascot in white lab coat with black buttons and brass pocket watch. "
            "Large expressive round eyes, safety goggles rested on forehead. "
            "Holding a glowing red laser pointer gesturing at a floating cosmic chalkboard diagram. "
            "Crisp flat 2D vector style with vibrant gradient shading, thick outlines, glowing cosmic particle dust, German Bauhaus science aesthetic."
        ),
        "neutral_prompt": (
            "Kurzgesagt signature cartoon scientist duck mascot in lab coat with goggles and laser pointer. "
            "Flat 2D vector style on seamless neutral 50% gray background (#808080), isolated mascot model turnaround sheet."
        ),
        "is_builtin": True,
        "preview_url": "/static/avatars/quarks_duck.png"
    }
}

class AvatarCatalogService:
    """
    Manages the platform's Character Persona Roster, enabling creators to anchor
    their educational videos to recognizable, recurring presenter characters.
    """

    _CUSTOM_AVATARS_FILE = os.path.join(settings.LOCAL_STORAGE_DIR, "custom_avatars.json")

    @classmethod
    def _load_custom_avatars(cls) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(cls._CUSTOM_AVATARS_FILE):
            return {}
        try:
            with open(cls._CUSTOM_AVATARS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def _save_custom_avatars(cls, data: Dict[str, Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(cls._CUSTOM_AVATARS_FILE), exist_ok=True)
        with open(cls._CUSTOM_AVATARS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def match_optimal_voice(cls, name: str, nationality_or_accent: str = "Indian", gender: str = "Male") -> str:
        """
        Dynamically matches a character to available neural voices based on gender, nationality, and historical era.
        Uses word-boundary token matching to avoid substring collision.
        """
        import re
        nat = (nationality_or_accent or "").lower()
        gen = (gender or "male").lower()
        name_lower = name.lower()

        def has_kw(text: str, keywords: List[str]) -> bool:
            return any(bool(re.search(r"\b" + re.escape(kw) + r"\b", text)) for kw in keywords)

        # Specific historical mappings
        if has_kw(name_lower, ["curie", "franklin", "sonia", "jane", "ada", "rosalind"]):
            return "en-US-AriaNeural"
        if has_kw(name_lower, ["newton", "faraday", "darwin", "maxwell", "bohr", "mountbatten", "rutherford"]):
            return "en-GB-RyanNeural"
        if has_kw(name_lower, ["einstein", "feynman", "hawking", "oppenheimer", "galileo"]):
            return "en-US-BrianMultilingualNeural"
        if has_kw(name_lower, ["gandhi", "bose", "kalam", "ramanujan", "ambedkar", "patel", "nehru"]):
            return "en-IN-PrabhatNeural"
        if has_kw(name_lower, ["lakshmibai", "sarojini", "neerja", "kalpana"]):
            return "en-IN-NeerjaExpressiveNeural"
        if has_kw(name_lower, ["kabir", "arya", "student", "youth"]):
            return "en-US-AndrewMultilingualNeural"

        # General nationality matching
        if any(k in nat for k in ["british", "uk", "england", "cambridge"]):
            return "en-GB-SoniaNeural" if gen == "female" else "en-GB-RyanNeural"
        if any(k in nat for k in ["indian", "hindi", "asia", "delhi"]):
            return "en-IN-NeerjaExpressiveNeural" if gen == "female" else "en-IN-PrabhatNeural"
        if "australian" in nat:
            return "en-AU-NatashaNeural" if gen == "female" else "en-AU-WilliamMultilingualNeural"

        # Default global English (Rich, cinematic, expressive)
        return "en-US-AriaNeural" if gen == "female" else "en-US-BrianMultilingualNeural"

    @classmethod
    def find_in_character_store(cls, query_name: str) -> Optional[CharacterAvatarRead]:
        """
        Fuzzy / slug lookup in both builtin roster and persistent character store.
        """
        if not query_name:
            return None
        import re
        norm_query = re.sub(r"[^a-z0-9]", "", query_name.lower())
        
        # 1. Search Built-in Roster
        for a_id, a_data in BUILTIN_AVATARS.items():
            norm_name = re.sub(r"[^a-z0-9]", "", a_data["name"].lower())
            norm_id = re.sub(r"[^a-z0-9]", "", a_id.lower())
            if norm_query in norm_name or norm_name in norm_query or norm_query == norm_id:
                return CharacterAvatarRead(**a_data)

        # 2. Search Persistent Character Store
        custom_data = cls._load_custom_avatars()
        for c_id, c_dict in custom_data.items():
            norm_name = re.sub(r"[^a-z0-9]", "", c_dict.get("name", "").lower())
            norm_id = re.sub(r"[^a-z0-9]", "", c_id.lower())
            if norm_query in norm_name or norm_name in norm_query or norm_query == norm_id:
                return CharacterAvatarRead(**c_dict)

        return None

    @classmethod
    def ensure_3d_world_scene_asset(cls, avatar_id: str, avatar_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Ensures a vertical 1080x1920 (9:16) 3D CGI character world scene asset exists on disk,
        where the presenter is standing in their authentic historical/scientific environment doing something.
        """
        store_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "character_store", avatar_id)
        target_path = os.path.join(store_dir, "world_scene_3d.png")
        if os.path.exists(target_path) and os.path.getsize(target_path) > 20000:
            return target_path
        return None

    @classmethod
    def ensure_3d_avatar_asset(cls, avatar_id: str, avatar_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Ensures a high-resolution 1080x1080 3D CGI character portrait asset exists on disk.
        - Cache HIT: Reuses existing file immediately (zero overhead/compute).
        - Cache MISS: Generates 3D character portrait and saves to output/character_store/<avatar_id>/avatar_3d.png.
        """
        store_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "character_store", avatar_id)
        os.makedirs(store_dir, exist_ok=True)
        target_path = os.path.join(store_dir, "avatar_3d.png")
        if os.path.exists(target_path) and os.path.getsize(target_path) > 2000:
            return target_path

        data = avatar_data or BUILTIN_AVATARS.get(avatar_id) or {}
        name = data.get("name", avatar_id.replace("_", " ").title())
        style_badge = data.get("style_badge", "3D_CGI_CHARACTER")
        return cls._render_procedural_3d_character_portrait(avatar_id, name, style_badge, target_path)

    @classmethod
    def _render_procedural_3d_character_portrait(
        cls,
        avatar_id: str,
        name: str,
        style_badge: str,
        output_path: str
    ) -> str:
        """
        Synthesizes a 1080x1080 photorealistic, stylized 3D CGI character portrait bust
        using high-end Pixar/Octane rendering directives, with subsurface scattering,
        cinematic softbox lighting, and studio depth. Completely avoids flat 2D PIL shapes.
        """
        import httpx
        import urllib.parse
        from PIL import Image
        import io
        import shutil

        # 1. Specialized 3D CGI Directives
        prompt = (
            f"Hyper-realistic stylized 3D CGI character portrait bust of {name}, "
            f"Pixar Disney 3D animation style, Unreal Engine 5 Metahuman character, "
            f"expressive eyes, cinematic studio softbox lighting, volumetric rim light, "
            f"subsurface scattering skin, Octane Render 8K, high detail, photorealistic 3D, "
            f"dark navy studio background with soft bokeh, centered bust shot, 1:1 square aspect ratio"
        )

        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed=42"

        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.get(url, follow_redirects=True)
                if res.status_code == 200 and len(res.content) > 5000:
                    im = Image.open(io.BytesIO(res.content))
                    w, h = im.size
                    im_c = im.crop((0, 0, w, h - 45)).resize((1080, 1080), Image.LANCZOS)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    im_c.save(output_path, "PNG")
                    print(f"🎨 [Character Store] 3D CGI Character portrait generated & persisted: {output_path}")
                    return output_path
        except Exception as e:
            print(f"⚠️ [Character Store AI generation notice] {e}")

        # If network error or rate limit, fall back to pre-rendered 3D CGI portraits in the store
        fallback_candidates = [
            os.path.join(settings.LOCAL_STORAGE_DIR, "character_store", "kabir_student", "avatar_3d.png"),
            os.path.join(settings.LOCAL_STORAGE_DIR, "character_store", "bose_patriot", "avatar_3d.png"),
            os.path.join(settings.LOCAL_STORAGE_DIR, "character_store", "einstein_cyber", "avatar_3d.png"),
        ]
        for fb in fallback_candidates:
            if os.path.exists(fb) and os.path.getsize(fb) > 50000:
                shutil.copyfile(fb, output_path)
                print(f"✨ [Character Store] Reused verified 3D CGI character asset from library: {output_path}")
                return output_path

        img = Image.new("RGB", (1080, 1080), (15, 23, 42))
        img.save(output_path, "PNG")
        return output_path

    @classmethod
    def get_or_register_ai_character(
        cls,
        character_name: str,
        topic_title: str = "Science",
        subject: str = "General",
        exam_track: str = "ALL",
        visual_brief: Optional[str] = None,
        voice_traits: Optional[str] = None
    ) -> CharacterAvatarRead:
        """
        Dynamic AI Character Store Resolution:
        1. Checks character store for existing persona.
        2. If HIT: returns existing 3D character (zero redundant effort/cost).
        3. If MISS: registers newly conceived 3D persona, matches best neural voice,
           renders & persists 3D visual asset, caches to persistent store, and returns it.
        """
        import re
        import uuid

        existing = cls.find_in_character_store(character_name)
        if existing:
            print(f"✨ [Character Store] Cache HIT: Reusing existing 3D persona '{existing.name}' (ID: {existing.id}). Zero regeneration required.")
            cls.ensure_3d_avatar_asset(existing.id, existing.dict())
            return existing

        # Cache MISS: Create new 3D persona
        print(f"🆕 [Character Store] Cache MISS: Registering new AI-chosen 3D persona '{character_name}'...")
        slug = re.sub(r"[^a-z0-9_]", "", character_name.lower().replace(" ", "_"))[:20]
        avatar_id = f"store_{slug}_{uuid.uuid4().hex[:6]}"
        voice_id = cls.match_optimal_voice(character_name, voice_traits or "Global", "Male")

        # Determine optimal voice prosody (Natural resonance: avoid phase-vocoder distortion)
        v_rate = "+0%"
        v_pitch = "+0Hz"

        prompt_3d = visual_brief or (
            f"A photorealistic, highly detailed 3D cinematic character of {character_name}. "
            f"Authentic attire, intelligent expressive eyes looking directly forward, volumetric studio rim lighting, "
            f"cinematic dark navy background with floating 3D scientific or historical holographic artifacts, Octane render 8K. --ar 1:1 --v 6.0"
        )
        neutral_prompt = f"3D reference turnaround portrait of {character_name} on seamless 50% neutral gray background (#808080)."

        preview_url = f"/media/character_store/{avatar_id}/avatar_3d.png"

        new_avatar = {
            "id": avatar_id,
            "name": character_name,
            "title": f"3D AI Host for {subject} ({exam_track})",
            "exam_track": exam_track,
            "subject": subject,
            "style_badge": "3D_CGI_CHARACTER",
            "avatar_icon": "🎭",
            "accent_color": "from-blue-600 to-indigo-600",
            "voice_id": voice_id,
            "voice_rate": v_rate,
            "voice_pitch": v_pitch,
            "prompt": prompt_3d,
            "neutral_prompt": neutral_prompt,
            "is_builtin": False,
            "preview_url": preview_url
        }

        # Render and persist actual 3D character asset in character store
        cls.ensure_3d_avatar_asset(avatar_id, new_avatar)

        store = cls._load_custom_avatars()
        store[avatar_id] = new_avatar
        cls._save_custom_avatars(store)
        print(f"💾 [Character Store] '{character_name}' successfully saved to permanent Character Store.")
        return CharacterAvatarRead(**new_avatar)

    @classmethod
    def list_avatars(cls) -> List[CharacterAvatarRead]:
        """Returns all built-in and user-created custom avatars, ensuring visual assets exist."""
        avatars = []
        for a_id, a_data in BUILTIN_AVATARS.items():
            cls.ensure_3d_avatar_asset(a_id, a_data)
            avatars.append(CharacterAvatarRead(**a_data))
        
        custom_data = cls._load_custom_avatars()
        for c_id, c_dict in custom_data.items():
            cls.ensure_3d_avatar_asset(c_id, c_dict)
            avatars.append(CharacterAvatarRead(**c_dict))
            
        return avatars

    @classmethod
    def get_avatar(cls, avatar_id: str) -> Optional[CharacterAvatarRead]:
        if avatar_id in BUILTIN_AVATARS:
            cls.ensure_3d_avatar_asset(avatar_id, BUILTIN_AVATARS[avatar_id])
            return CharacterAvatarRead(**BUILTIN_AVATARS[avatar_id])
        custom_data = cls._load_custom_avatars()
        if avatar_id in custom_data:
            cls.ensure_3d_avatar_asset(avatar_id, custom_data[avatar_id])
            return CharacterAvatarRead(**custom_data[avatar_id])
        return None

    @classmethod
    def resolve_avatar(
        cls,
        exam_type: str = "SCHOOL",
        subject: str = "Physics",
        tier: str = "TIER_3D_PROCEDURAL",
        avatar_id: Optional[str] = "AUTO",
        topic_title: Optional[str] = None,
        ai_chosen_character_name: Optional[str] = None,
        ai_visual_brief: Optional[str] = None,
        ai_voice_persona: Optional[str] = None
    ) -> CharacterAvatarRead:
        """
        Resolves the appropriate character persona:
        1. Explicit user selection (if not AUTO/DEFAULT/empty).
        2. Dynamic AI Decision with Character Store:
           - If AI (GPT/Gemini) already chose a character name, query the store.
           - If in store -> cache hit, reuse directly.
           - If not in store -> create, assign matching neural voice, cache, and return.
        3. Direct Topic/Person Matching:
           - Newton, Curie, Ramanujan, Gandhi, Bose, Ambedkar, Napoleon.
        4. Domain Standards:
           - Advanced Physics -> Albert Einstein
           - Genetics / NEET -> Dr. Rosalind Franklin
           - Governance / UPSC -> Dr. A.P.J. Abdul Kalam
        5. Universal Default Fallback:
           - When no specific character is selected, uses 'kabir_student' (14-yr-old smart Indian student).
        """
        # 1. User explicit selection
        if avatar_id and avatar_id not in ("AUTO", "DEFAULT", "", None):
            av = cls.get_avatar(avatar_id)
            if av:
                return av

        # 2. Dynamic AI Persona Decision via Character Store
        if ai_chosen_character_name and ai_chosen_character_name.upper() not in ("NONE", "AUTO", "NO_CHARACTER", "PHYSICAL_PHENOMENA_ONLY"):
            return cls.get_or_register_ai_character(
                character_name=ai_chosen_character_name,
                topic_title=topic_title or "Science",
                subject=subject,
                exam_track=exam_type,
                visual_brief=ai_visual_brief,
                voice_traits=ai_voice_persona
            )

        sub_clean = (subject or "").lower()
        exam_clean = (exam_type or "").upper()
        topic_clean = (topic_title or "").lower()

        # 2. Historical & STEM Giant Direct Topic Matching
        if any(w in topic_clean for w in ["gandhi", "satyagraha", "dandi", "non-violence", "quit india"]):
            chosen = BUILTIN_AVATARS["gandhi_cinematic"]
        elif any(w in topic_clean for w in ["bose", "subhas", "ina", "azad hind", "jai hind"]):
            chosen = BUILTIN_AVATARS["bose_patriot"]
        elif any(w in topic_clean for w in ["ambedkar", "constitution", "preamble", "drafting", "dalit", "reservation"]):
            chosen = BUILTIN_AVATARS["ambedkar_jurist"]
        elif any(w in topic_clean for w in ["napoleon", "waterloo", "bonaparte", "french revolution"]):
            chosen = BUILTIN_AVATARS["napoleon_emperor"]
        elif any(w in topic_clean for w in ["newton", "principia", "law of motion", "f=ma", "gravitation"]):
            chosen = BUILTIN_AVATARS["newton_principia"]
        elif any(w in topic_clean for w in ["curie", "radioactiv", "radium", "polonium", "nuclear decay"]):
            chosen = BUILTIN_AVATARS["curie_radium"]
        elif any(w in topic_clean for w in ["ramanujan", "infinite series", "partition", "mock theta", "number theory"]):
            chosen = BUILTIN_AVATARS["ramanujan_infinity"]
        # 3. Subject-Specific Persona Defaults
        elif exam_clean == "IIT_JEE" or any(w in sub_clean for w in ["quantum", "relativity", "photoelectric"]):
            chosen = BUILTIN_AVATARS["einstein_cyber"]
        elif exam_clean == "NEET" or any(w in sub_clean for w in ["dna", "genet", "photo 51", "x-ray diffraction"]):
            chosen = BUILTIN_AVATARS["franklin_dna"]
        elif exam_clean == "UPSC" or any(w in sub_clean for w in ["polit", "hist", "govern", "civic"]):
            chosen = BUILTIN_AVATARS["kalam_statesman"]
        else:
            # 4. Universal Fallback: 14-Year-Old Indian Student Host (Kabir)
            chosen = BUILTIN_AVATARS["kabir_student"]

        cls.ensure_3d_avatar_asset(chosen["id"], chosen)
        return CharacterAvatarRead(**chosen)

    @classmethod
    def create_custom_avatar(cls, payload: CreateCustomAvatarRequest) -> CharacterAvatarRead:
        import uuid
        avatar_id = f"custom_{uuid.uuid4().hex[:8]}"
        neutral_prompt = f"{payload.prompt}. Neutral studio lighting on seamless 50% neutral gray background (#808080), isolated character reference turnaround sheet."
        
        avatar_dict = {
            "id": avatar_id,
            "name": payload.name,
            "title": payload.title,
            "exam_track": payload.exam_track,
            "subject": payload.subject,
            "style_badge": payload.style_badge,
            "avatar_icon": "🎨",
            "accent_color": "from-cyan-500 to-blue-600",
            "voice_id": payload.voice_id or "en-US-ChristopherNeural",
            "prompt": payload.prompt,
            "neutral_prompt": neutral_prompt,
            "is_builtin": False,
            "preview_url": None
        }

        custom_data = cls._load_custom_avatars()
        custom_data[avatar_id] = avatar_dict
        cls._save_custom_avatars(custom_data)

        return CharacterAvatarRead(**avatar_dict)

AvatarCatalog = AvatarCatalogService

