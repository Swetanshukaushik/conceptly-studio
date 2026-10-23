import os
import time
import base64
from typing import Optional
from src.core.config import settings
from src.models.schemas import SceneBeat

class CinemaDiffusionEngine:
    """
    Tier 4: CINEMA AI (Generative AI Video Diffusion)
    Submits prompts and base frames to top-tier AI video diffusion models:
    - Primary: Fal.ai Kling 1.5 Standard Image-to-Video / LTX-Video
    - Alternative: Runway Gen-3 Alpha
    - Alternative: Luma Dream Machine Ray 2
    """

    WIDTH = 1080
    HEIGHT = 1920

    @classmethod
    def render_cinema_clip(
        cls,
        scene: SceneBeat,
        image_path: str,
        output_clip_path: str,
        duration: float = 3.5
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)

        # 1. Fal.ai Kling 1.5 / LTX Video Diffusion
        if settings.FAL_KEY:
            clip = cls._generate_fal_clip(scene, image_path, output_clip_path, duration)
            if clip: return clip

        # 2. Runway Gen-3 Alpha
        if settings.RUNWAY_API_KEY:
            clip = cls._generate_runway_clip(scene, image_path, output_clip_path, duration)
            if clip: return clip

        # 3. Luma Ray 2
        if settings.LUMA_API_KEY:
            clip = cls._generate_luma_clip(scene, image_path, output_clip_path, duration)
            if clip: return clip

        raise RuntimeError(
            "Missing Cinematic Video AI Key: Tier 4 (CINEMA AI) requires FAL_KEY, RUNWAY_API_KEY, or LUMA_API_KEY in .env."
        )

    @classmethod
    def _generate_fal_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        if not settings.FAL_KEY:
            return None
        try:
            import httpx
            with open(image_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
            image_data_uri = f"data:image/png;base64,{b64_img}"

            headers = {
                "Authorization": f"Key {settings.FAL_KEY}",
                "Content-Type": "application/json"
            }
            endpoint = "https://queue.fal.run/fal-ai/kling-video/v1/standard/image-to-video"
            payload = {
                "prompt": f"{scene.visual_prompt}. Cinematic 9:16 vertical video, photorealistic, 4k, smooth camera motion.",
                "image_url": image_data_uri,
                "duration": "5",
                "aspect_ratio": "9:16"
            }

            with httpx.Client(timeout=30.0) as client:
                res = client.post(endpoint, headers=headers, json=payload)
                if res.status_code not in (200, 201):
                    return None
                data = res.json()
                status_url = data.get("status_url")
                response_url = data.get("response_url")

                start_time = time.time()
                while time.time() - start_time < 90:
                    time.sleep(4.0)
                    poll_res = client.get(status_url, headers=headers)
                    if poll_res.status_code == 200:
                        status = poll_res.json().get("status")
                        if status == "COMPLETED":
                            result_res = client.get(response_url, headers=headers)
                            if result_res.status_code == 200:
                                video_url = result_res.json().get("video", {}).get("url")
                                if video_url:
                                    video_res = client.get(video_url)
                                    with open(output_path, "wb") as f_out:
                                        f_out.write(video_res.content)
                                    return output_path
                        elif status in ("FAILED", "CANCELLED"):
                            break
            return None
        except Exception as e:
            print(f"⚠️ Fal.ai video error: {e}")
            return None

    @classmethod
    def _generate_runway_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        if not settings.RUNWAY_API_KEY:
            return None
        try:
            import httpx
            with open(image_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
            image_uri = f"data:image/png;base64,{b64_img}"

            headers = {
                "Authorization": f"Bearer {settings.RUNWAY_API_KEY}",
                "X-Runway-Version": "2024-09-13",
                "Content-Type": "application/json"
            }
            payload = {
                "promptImage": image_uri,
                "model": "gen3a_turbo",
                "promptText": f"{scene.visual_prompt}. Extremely high production value, vertical 9:16.",
                "duration": 5,
                "ratio": "9:16"
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post("https://api.dev.runwayml.com/v1/image_to_video", headers=headers, json=payload)
                if res.status_code not in (200, 201):
                    return None
                task_id = res.json().get("id")
                start_time = time.time()
                while time.time() - start_time < 90:
                    time.sleep(4.0)
                    poll_res = client.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
                    if poll_res.status_code == 200:
                        poll_data = poll_res.json()
                        if poll_data.get("status") == "SUCCEEDED":
                            video_url = poll_data.get("output", [])[0]
                            video_res = client.get(video_url)
                            with open(output_path, "wb") as f_out:
                                f_out.write(video_res.content)
                            return output_path
                        elif poll_data.get("status") in ("FAILED", "CANCELLED"):
                            break
            return None
        except Exception as e:
            print(f"⚠️ Runway error: {e}")
            return None

    @classmethod
    def _generate_luma_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        if not settings.LUMA_API_KEY:
            return None
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {settings.LUMA_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "prompt": scene.visual_prompt,
                "aspect_ratio": "9:16"
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post("https://api.lumalabs.ai/dream-machine/v1/generations", headers=headers, json=payload)
                if res.status_code not in (200, 201):
                    return None
                gen_id = res.json().get("id")
                start_time = time.time()
                while time.time() - start_time < 90:
                    time.sleep(4.0)
                    poll_res = client.get(f"https://api.lumalabs.ai/dream-machine/v1/generations/{gen_id}", headers=headers)
                    if poll_res.status_code == 200:
                        data = poll_res.json()
                        if data.get("state") == "completed":
                            video_url = data.get("assets", {}).get("video")
                            if video_url:
                                video_res = client.get(video_url)
                                with open(output_path, "wb") as f_out:
                                    f_out.write(video_res.content)
                                return output_path
                        elif data.get("state") == "failed":
                            break
            return None
        except Exception as e:
            print(f"⚠️ Luma error: {e}")
            return None
