"""Vision QA for a rendered frame: asks a vision model whether the beat really shows what the narration says."""
import json
import re
from typing import Any, Dict

from src.core.config import settings
from src.services.media.usage import check_budget
from src.services.config_loader import load_json


def judge_frame(image_path: str, beat: int, narration: str, intent: str, layout_note: str) -> Dict[str, Any]:
    """Returns {"score": int, "issues": [str]}. Raises on provider errors so callers decide what to do."""
    check_budget('judge_frame')   # refused when the reel's budget is used up
    cfg = load_json("qa.json")
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Vision QA needs GEMINI_API_KEY (or set qa.json enabled=false).")
    from src.services.media.usage import genai_module
    genai = genai_module()
    from PIL import Image
    genai.configure(api_key=settings.GEMINI_API_KEY)
    profile = load_json("llm_models.json")["gemini"][cfg["vision_profile"]]
    prompt = (cfg["prompt"].replace("{beat}", str(beat)).replace("{narration}", narration)
              .replace("{intent}", intent or "").replace("{layout_note}", layout_note or ""))
    last: Exception = RuntimeError("no model")
    with Image.open(image_path) as im:
        im = im.convert("RGB"); im.thumbnail((cfg["image_max_px"], cfg["image_max_px"]))
        for name in profile["models"]:
            try:
                model = genai.GenerativeModel(model_name=name, generation_config={**profile["generation"], "response_mime_type": "application/json"})
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", model.generate_content([prompt, im]).text.strip())
                data = json.loads(text)
                return {"score": int(data.get("score", 0)), "issues": [str(i) for i in data.get("issues", [])]}
            except Exception as e:
                last = e
    raise last


def judge_frames(items: list, layout_note: str) -> Dict[int, Dict[str, Any]]:
    """One request for many frames. items: [{beat, path, narration, intent}]. Returns {beat: {"score", "issues"}}."""
    check_budget('judge_frames')   # refused when the reel's budget is used up
    cfg = load_json("qa.json")
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Vision QA needs GEMINI_API_KEY (or set qa.json enabled=false).")
    from src.services.media.usage import genai_module
    genai = genai_module()
    from PIL import Image
    genai.configure(api_key=settings.GEMINI_API_KEY)
    profile = load_json("llm_models.json")["gemini"][cfg["vision_profile"]]
    header = "\n".join(f"- Frame {i + 1} = beat {it['beat']}. Narration: \"{it['narration']}\". Meant to show: \"{it.get('intent') or ''}\"" for i, it in enumerate(items))
    prompt = cfg["batch_prompt"].replace("{count}", str(len(items))).replace("{frames}", header).replace("{layout_note}", layout_note or "")
    parts: list = [prompt]
    for i, it in enumerate(items):
        with Image.open(it["path"]) as im:
            im = im.convert("RGB"); im.thumbnail((cfg["image_max_px"], cfg["image_max_px"]))
            parts += [f"Frame {i + 1} (beat {it['beat']}):", im.copy()]
    last: Exception = RuntimeError("no model")
    for name in profile["models"]:
        try:
            model = genai.GenerativeModel(model_name=name, generation_config={**profile["generation"], "response_mime_type": "application/json"})
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", model.generate_content(parts).text.strip())
            data = json.loads(text)
            out = {int(b["beat"]): {"score": int(b.get("score", 0)), "issues": [str(x) for x in b.get("issues", [])]} for b in data.get("beats", [])}
            missing = [it["beat"] for it in items if it["beat"] not in out]
            if missing:
                raise ValueError(f"judge returned no verdict for beats {missing}")
            return out
        except Exception as e:
            last = e
    raise last
