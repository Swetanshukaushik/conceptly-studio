"""Asks a vision model whether an image really shows what a scene needs. Gemini only for now."""
import json
import re
from typing import Any, Dict

from src.core.config import settings
from src.services.config_loader import load_json


def judge_image(image_path: str, narration: str, query: str) -> Dict[str, Any]:
    """Returns {"match": bool, "reason": str}. Raises on provider errors so callers can decide."""
    cfg = load_json("images.json")
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Image verification needs GEMINI_API_KEY (or set images.json verify_with_vision=false).")
    import google.generativeai as genai
    from PIL import Image
    genai.configure(api_key=settings.GEMINI_API_KEY)
    profile = load_json("llm_models.json")["gemini"][cfg["vision_profile"]]
    prompt = cfg["judge_prompt"].replace("{narration}", narration).replace("{query}", query)
    last: Exception = RuntimeError("no model")
    with Image.open(image_path) as im:
        im = im.convert("RGB"); im.thumbnail((1024, 1024))
        for name in profile["models"]:
            try:
                model = genai.GenerativeModel(model_name=name, generation_config={**profile["generation"], "response_mime_type": "application/json"})
                text = model.generate_content([prompt, im]).text.strip()
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
                data = json.loads(text)
                return {"match": bool(data.get("match")), "reason": str(data.get("reason", ""))}
            except Exception as e:
                last = e
    raise last


def ask_image(image_path: str, prompt: str) -> Dict[str, Any]:
    """Sends one image and a prompt that asks for JSON; returns the parsed object. Raises on provider errors."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Image review needs GEMINI_API_KEY.")
    import google.generativeai as genai
    from PIL import Image
    genai.configure(api_key=settings.GEMINI_API_KEY)
    cfg = load_json("images.json")
    profile = load_json("llm_models.json")["gemini"][cfg["vision_profile"]]
    last: Exception = RuntimeError("no model")
    with Image.open(image_path) as im:
        im = im.convert("RGB"); im.thumbnail((1600, 1600))
        for name in profile["models"]:
            try:
                model = genai.GenerativeModel(model_name=name, generation_config={**profile["generation"], "response_mime_type": "application/json"})
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", model.generate_content([prompt, im]).text.strip())
                return json.loads(text)
            except Exception as e:
                last = e
    raise last
