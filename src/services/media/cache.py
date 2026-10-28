"""Content-addressed cache for generated images: the same model and full prompt returns the saved image for free.
Only images the reviewer accepted are stored, so a cache hit never brings back a known-bad picture."""
import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple


class ImageCache:
    def __init__(self, root: str):
        self.root = root

    @staticmethod
    def key(model: str, prompt: str) -> str:
        return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()[:32]

    def _paths(self, key: str) -> Tuple[str, str]:
        return os.path.join(self.root, key + ".img"), os.path.join(self.root, key + ".json")

    def get(self, model: str, prompt: str) -> Optional[Dict[str, Any]]:
        img, meta = self._paths(self.key(model, prompt))
        if not (os.path.exists(img) and os.path.exists(meta)):
            return None
        try:
            with open(img, "rb") as f, open(meta, encoding="utf-8") as m:
                info = json.load(m)
                return {"data": f.read(), "mime": info.get("mime", "image/png"), "score": info.get("score")}
        except Exception:
            return None

    def put(self, model: str, prompt: str, data: bytes, mime: str, score: Optional[float]) -> None:
        try:
            os.makedirs(self.root, exist_ok=True)
            img, meta = self._paths(self.key(model, prompt))
            with open(img, "wb") as f:
                f.write(data)
            with open(meta, "w", encoding="utf-8") as m:
                json.dump({"mime": mime, "score": score}, m)
        except Exception:
            pass   # a cache that cannot be written only costs a later regeneration


def default_cache() -> Optional[ImageCache]:
    from src.core.config import settings
    from src.services.config_loader import load_json
    cfg = load_json("premium.json")["cache"]
    return ImageCache(os.path.join(settings.LOCAL_STORAGE_DIR, cfg["dir"])) if cfg.get("enabled") else None
