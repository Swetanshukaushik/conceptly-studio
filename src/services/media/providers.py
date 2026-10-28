"""Media providers behind one interface. The gateway is the only place that spends: it estimates, reserves against the
ledger, calls the provider and records the real cost. Prices and model names come from config/providers.json.
"""
import base64
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.services.config_loader import load_json
from src.services.media.ledger import SpendLedger


class ProviderError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status, self.retryable = status, retryable


@dataclass
class ImageRequest:
    prompt: str
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    label: str = ""


@dataclass
class ImageResult:
    data: bytes
    mime: str
    model: str
    cost_usd: float
    meta: Dict[str, Any] = field(default_factory=dict)


def image_config() -> Dict[str, Any]:
    return load_json("providers.json")["image"]


def model_price(model: str) -> float:
    models = image_config()["models"]
    if model not in models:
        raise ProviderError(f"Unknown image model '{model}'; add it to config/providers.json")
    return float(models[model]["price_usd"])


class ImageProvider:
    name = "base"

    def estimate(self, req: ImageRequest) -> float:
        return model_price(req.model or image_config()["default_model"])

    def generate(self, req: ImageRequest) -> ImageResult:
        raise NotImplementedError


def _png(width: int = 9, height: int = 16, rgb=(120, 120, 120)) -> bytes:
    """A valid solid-colour PNG, enough for offline tests."""
    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class FakeImageProvider(ImageProvider):
    """Deterministic offline provider. `fail_on` lists 1-based call numbers that raise; `price` overrides the config price."""
    name = "fake"

    def __init__(self, price: Optional[float] = None, fail_on: Optional[List[int]] = None):
        self.price, self.fail_on, self.calls = price, set(fail_on or []), []

    def estimate(self, req: ImageRequest) -> float:
        return self.price if self.price is not None else super().estimate(req)

    def generate(self, req: ImageRequest) -> ImageResult:
        self.calls.append(req)
        if len(self.calls) in self.fail_on:
            raise ProviderError("fake provider failure", status=500, retryable=True)
        shade = sum(req.prompt.encode()) % 200 + 30
        return ImageResult(_png(rgb=(shade, shade, shade)), "image/png", req.model or image_config()["default_model"], self.estimate(req))


class GeminiImageProvider(ImageProvider):
    """Gemini image models over REST. Cost is the configured flat price per image (the API returns tokens, not dollars)."""
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, transport=None):
        if api_key is None:
            from src.core.config import settings
            api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is not set")
        self.api_key, self.transport = api_key, transport

    def generate(self, req: ImageRequest) -> ImageResult:
        cfg = image_config()
        model = req.model or cfg["default_model"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"contents": [{"parts": [{"text": req.prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": req.aspect_ratio or cfg["aspect_ratio"]}}}
        headers = {"x-goog-api-key": self.api_key}
        try:
            if self.transport:
                status, payload = self.transport(url, body, headers)
            else:
                import httpx
                from src.services.media.usage import check_live
                check_live("Gemini image")
                r = httpx.post(url, json=body, headers=headers, timeout=cfg["timeout_seconds"])
                status, payload = r.status_code, (r.json() if r.content else {})
        except Exception as exc:
            raise ProviderError(f"image request failed: {type(exc).__name__}", retryable=True)
        if status != 200:
            message = ((payload or {}).get("error") or {}).get("message", "")[:160]
            raise ProviderError(f"{model} returned {status}: {message}", status=status, retryable=status >= 500)
        cand = ((payload or {}).get("candidates") or [{}])[0]
        for part in (cand.get("content") or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline:
                return ImageResult(base64.b64decode(inline["data"]), inline.get("mimeType") or inline.get("mime_type") or "image/png",
                                   model, model_price(model), {"finish": cand.get("finishReason"), "usage": payload.get("usageMetadata")})
        raise ProviderError(f"{model} returned no image (finish: {cand.get('finishReason')})")


@dataclass
class ClipRequest:
    image: bytes
    image_mime: str
    prompt: str
    model: Optional[str] = None
    label: str = ""


@dataclass
class ClipResult:
    data: bytes
    mime: str
    model: str
    seconds: float
    cost_usd: float
    meta: Dict[str, Any] = field(default_factory=dict)


def video_config() -> Dict[str, Any]:
    return load_json("providers.json")["video"]


def clip_price_per_second(model: str) -> float:
    models = video_config()["models"]
    if model not in models:
        raise ProviderError(f"Unknown video model '{model}'; add it to config/providers.json")
    return float(models[model]["price_per_second_usd"])


def probe_seconds(data: bytes) -> Optional[float]:
    """Length of an mp4 in seconds (ffprobe), or None when it cannot be read."""
    import os, shutil, subprocess, tempfile
    probe = shutil.which("ffprobe") or next((p for p in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe") if os.path.exists(p)), None)
    if not probe:
        return None
    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
        f.write(data); f.flush()
        try:
            out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", f.name], capture_output=True, text=True, timeout=30).stdout.strip()
            return float(out)
        except Exception:
            return None


class ClipProvider:
    name = "base"

    def estimate(self, req: ClipRequest) -> float:
        cfg = load_json("premium.json")["clips"]
        return clip_price_per_second(req.model or video_config()["default_model"]) * float(cfg["reserve_seconds"])

    def generate(self, req: ClipRequest) -> ClipResult:
        raise NotImplementedError


class FakeClipProvider(ClipProvider):
    """Offline provider that returns a real, tiny mp4 (ffmpeg test pattern) so frame extraction can be tested. `fail_on` lists 1-based call numbers that raise."""
    name = "fake"

    def __init__(self, seconds: float = 3.0, fail_on: Optional[List[int]] = None, status: int = 500):
        self.seconds, self.fail_on, self.status, self.calls = seconds, set(fail_on or []), status, []

    def generate(self, req: ClipRequest) -> ClipResult:
        import os, shutil, subprocess, tempfile
        self.calls.append(req)
        if len(self.calls) in self.fail_on:
            raise ProviderError("fake clip failure", status=self.status, retryable=self.status >= 500)
        ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "c.mp4")
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=72x128:rate=12:duration={self.seconds}", "-pix_fmt", "yuv420p", out], check=True, timeout=60)
            data = open(out, "rb").read()
        model = req.model or video_config()["default_model"]
        return ClipResult(data, "video/mp4", model, self.seconds, clip_price_per_second(model) * self.seconds)


class GeminiClipProvider(ClipProvider):
    """Image-to-video with Gemini Omni over the Interactions API (REST). Cost is the measured length of the returned video times the configured price per second."""
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, transport=None):
        if api_key is None:
            from src.core.config import settings
            api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is not set")
        self.api_key, self.transport = api_key, transport

    def generate(self, req: ClipRequest) -> ClipResult:
        cfg = video_config(); model = req.model or cfg["default_model"]
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        body = {"model": model,
                "input": [{"type": "image", "data": base64.b64encode(req.image).decode(), "mime_type": req.image_mime}, {"type": "text", "text": req.prompt}],
                "response_format": {"type": "video", "aspect_ratio": cfg["aspect_ratio"], "resolution": cfg["resolution"]}}
        headers = {"x-goog-api-key": self.api_key}
        try:
            if self.transport:
                status, payload = self.transport(url, body, headers)
            else:
                import httpx
                from src.services.media.usage import check_live
                check_live("Gemini video")
                r = httpx.post(url, json=body, headers=headers, timeout=cfg["timeout_seconds"])
                status, payload = r.status_code, (r.json() if r.content else {})
        except Exception as exc:
            raise ProviderError(f"video request failed: {type(exc).__name__}", retryable=True)
        if status != 200:
            message = ((payload or {}).get("error") or {}).get("message", "")[:160]
            raise ProviderError(f"{model} returned {status}: {message}", status=status, retryable=status >= 500)
        for step in (payload or {}).get("steps") or []:
            for item in step.get("content") or []:
                if item.get("type") == "video" and item.get("data"):
                    data = base64.b64decode(item["data"])
                    secs = probe_seconds(data)
                    est_secs = float(load_json("premium.json")["clips"]["reserve_seconds"])
                    return ClipResult(data, item.get("mime_type") or "video/mp4", model, secs or est_secs, clip_price_per_second(model) * (secs or est_secs),
                                      {"length_measured": secs is not None})
        raise ProviderError(f"{model} returned no video")


class MediaGateway:
    """Spend-guarded entry point for generation. Never call a provider directly from the pipeline."""

    def __init__(self, ledger: SpendLedger, image_provider: ImageProvider, clip_provider: Optional[ClipProvider] = None):
        self.ledger, self.image_provider, self.clip_provider = ledger, image_provider, clip_provider

    def generate_image(self, req: ImageRequest) -> ImageResult:
        req.model = req.model or image_config()["default_model"]
        estimate = self.image_provider.estimate(req)
        token = self.ledger.reserve("image", req.model, estimate, req.label)   # raises BudgetExceeded before any call
        try:
            result = self.image_provider.generate(req)
        except ProviderError as exc:
            self.ledger.release(token, str(exc))
            raise
        except Exception as exc:
            self.ledger.release(token, f"{type(exc).__name__}: {exc}")
            raise ProviderError(f"unexpected provider error: {type(exc).__name__}")
        self.ledger.commit(token, result.cost_usd, bytes=len(result.data))
        return result

    def default_model(self) -> str:
        return image_config()["default_model"]

    def hero_model(self) -> str:
        return image_config()["hero_model"]

    def generate_clip(self, req: ClipRequest) -> ClipResult:
        """Image-to-video. Reserves the estimated cost first (raises BudgetExceeded before any call), records the measured cost."""
        if self.clip_provider is None:
            raise ProviderError("no clip provider configured for this tier")
        req.model = req.model or video_config()["default_model"]
        token = self.ledger.reserve("video", req.model, self.clip_provider.estimate(req), req.label)
        try:
            result = self.clip_provider.generate(req)
        except ProviderError as exc:
            self.ledger.release(token, str(exc))
            raise
        except Exception as exc:
            self.ledger.release(token, f"{type(exc).__name__}: {exc}")
            raise ProviderError(f"unexpected provider error: {type(exc).__name__}")
        self.ledger.commit(token, result.cost_usd, bytes=len(result.data), seconds=round(result.seconds, 2))
        return result


def new_gateway(tier_cap_usd: Optional[float] = None, image_provider: Optional[ImageProvider] = None, clip_provider: Optional[ClipProvider] = None, clips: bool = False) -> MediaGateway:
    """Gateway on the active job's ledger when there is one (so images and text add up in one report), else a fresh one."""
    from src.services.media.usage import current_ledger
    cfg = load_json("providers.json")["ledger"]
    cap = tier_cap_usd if tier_cap_usd is not None else cfg["cap_usd_default"]
    return MediaGateway(current_ledger() or SpendLedger(cap, cfg.get("safety_margin", 1.0)), image_provider or GeminiImageProvider(),
                        clip_provider or (GeminiClipProvider() if clips else None))
