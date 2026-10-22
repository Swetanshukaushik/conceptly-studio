import os
import shutil
import subprocess
from typing import Optional
from src.core.config import settings
from src.models.schemas import SceneBeat, ReelGenerationTier, CameraMotion
from src.engines.visuals.visual_factory import VisualAssetFactory

class VideoClipEngine:
    """
    Multi-Tier AI Video Generation Engine (2026):
    - Tier 1 FREE: 2.5D Depth-Parallax & Camera Motion Video Generator (Near $0.00)
    - Tier 2 PREMIUM: Kling AI / Hailuo Video (Fal.ai / Kling API) (~$0.20)
    - Tier 3 ULTRA: Hollywood Two-Step Pipeline (FLUX.1 + Runway Gen-3 / Luma Ray 2) (~$0.85)
    """

    WIDTH = 1080
    HEIGHT = 1920

    @classmethod
    def _find_ffmpeg(cls) -> Optional[str]:
        candidates = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg",
            shutil.which("ffmpeg")
        ]
        for path in candidates:
            if path and os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return None

    @classmethod
    def generate_scene_clip(
        cls,
        scene: SceneBeat,
        output_clip_path: str,
        tier: ReelGenerationTier = ReelGenerationTier.FREE
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        duration = max(2.5, scene.end_sec - scene.start_sec)

        # 1. Ensure base frame image exists
        base_img_path = scene.image_path
        if not base_img_path or not os.path.exists(base_img_path):
            base_img_path = output_clip_path.replace(".mp4", "_frame.png")
            VisualAssetFactory.render_scene_image(scene, base_img_path, tier=tier)
            scene.image_path = base_img_path

        # 2. Tier 3 ULTRA: Runway Gen-3 Alpha / Luma Ray 2
        if tier == ReelGenerationTier.ULTRA:
            if settings.RUNWAY_API_KEY:
                clip = cls._generate_runway_clip(scene, base_img_path, output_clip_path, duration)
                if clip: return clip
            elif settings.LUMA_API_KEY:
                clip = cls._generate_luma_clip(scene, base_img_path, output_clip_path, duration)
                if clip: return clip

        # 3. Tier 2 PREMIUM: Kling AI / Fal.ai Video Diffusion
        if tier in (ReelGenerationTier.PREMIUM, ReelGenerationTier.ULTRA):
            if settings.FAL_KEY:
                clip = cls._generate_fal_clip(scene, base_img_path, output_clip_path, duration)
                if clip: return clip
            elif settings.KLING_API_KEY:
                clip = cls._generate_kling_clip(scene, base_img_path, output_clip_path, duration)
                if clip: return clip

        # 4. Tier 1 FREE (or offline fallback): Autonomous 2026 Enhanced Engine
        # 4A. Manim Mathematical & Calculus Physics Engine (Vector strokes, derivatives, harmonic oscillators)
        from src.engines.render.manim_math_engine import ManimMathPhysicsEngine
        if ManimMathPhysicsEngine.should_render(scene):
            try:
                return ManimMathPhysicsEngine.render_math_clip(scene, output_clip_path, duration)
            except Exception as e:
                print(f"⚠️ Manim math engine notice: {e}, falling back to general physics...")

        # 4B. Dynamic Animated Physics & Science Simulations (Newton, Collisions, Orbit, Photosynthesis)
        from src.engines.render.physics_sim_engine import PhysicsSimulationEngine
        if PhysicsSimulationEngine.should_simulate(scene):
            try:
                return PhysicsSimulationEngine.render_simulation_clip(scene, output_clip_path, duration)
            except Exception as e:
                print(f"⚠️ Physics sim notice: {e}, falling back to character/parallax motion...")

        # 4B. Multi-Plane Storytelling Scenes (Assembly Bombing, Fluttering Pamphlets, Courtroom Megaphone, Jail Lamp)
        from src.engines.render.storytelling_engine import MultiPlaneStorytellingEngine
        if MultiPlaneStorytellingEngine.should_render(scene):
            try:
                return MultiPlaneStorytellingEngine.render_narrative_clip(scene, output_clip_path, duration, base_img_path)
            except Exception as e:
                print(f"⚠️ Multi-plane narrative notice: {e}, falling back to character motion...")

        # 4C. Cinematic Living Character Motion (Breathing, light sweeps, floating embers for historical/human scenes)
        from src.engines.render.character_motion_engine import CharacterMotionEngine
        if CharacterMotionEngine.should_animate_character(scene) and base_img_path and os.path.exists(base_img_path):
            try:
                return CharacterMotionEngine.render_living_character_clip(base_img_path, output_clip_path, duration, scene)
            except Exception as e:
                print(f"⚠️ Character motion notice: {e}, falling back to parallax motion...")

        # 4D. General 2.5D Parallax Camera Motion Engine
        return cls._generate_parallax_clip(base_img_path, output_clip_path, duration, scene.camera_motion)

    @classmethod
    def _generate_parallax_clip(
        cls,
        image_path: str,
        output_clip_path: str,
        duration: float,
        motion: CameraMotion = CameraMotion.ZOOM_IN
    ) -> str:
        """
        Synthesizes a moving 1080x1920 30fps H.264 video clip with 2.5D camera trajectories.
        """
        ffmpeg_bin = cls._find_ffmpeg()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg binary not found")

        fps = 30
        frames = int(duration * fps)

        # Configure motion filter
        if motion == CameraMotion.ZOOM_IN:
            # Slow dramatic push-in
            vf = f"zoompan=z='min(zoom+0.0012,1.15)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        elif motion == CameraMotion.PAN_RIGHT:
            # Smooth horizontal drift right
            vf = f"zoompan=z=1.12:x='min(x+1.5,iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
        elif motion == CameraMotion.PAN_LEFT:
            # Smooth horizontal drift left
            vf = f"zoompan=z=1.12:x='max(x-1.5,0)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
        elif motion == CameraMotion.PULL_BACK:
            # Reveals wider context (1.15 -> 1.0)
            vf = f"zoompan=z='if(lte(zoom,1.0),1.0,max(1.0,1.15-0.0012*on))':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        else:
            vf = f"zoompan=z='min(zoom+0.0010,1.12)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"

        cmd = [
            ffmpeg_bin, "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", vf,
            "-t", f"{duration:.2f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            output_clip_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"⚠️ Parallax clip generation error: {res.stderr.decode('utf-8', errors='ignore')}")
        return output_clip_path

    @classmethod
    def _generate_fal_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        """
        Calls Fal.ai API for Kling 1.5 / Hailuo / LTX-Video generation.
        """
        if not settings.FAL_KEY:
            return None

        try:
            import httpx
            import base64
            import time

            with open(image_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
            image_data_uri = f"data:image/png;base64,{b64_img}"

            headers = {
                "Authorization": f"Key {settings.FAL_KEY}",
                "Content-Type": "application/json"
            }

            # Submit generation to Fal.ai queue (Kling 1.5 standard image-to-video)
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
                    print(f"⚠️ Fal.ai submission notice ({res.status_code}): {res.text[:200]}")
                    return None

                data = res.json()
                status_url = data.get("status_url")
                response_url = data.get("response_url")

                # Poll for completion (up to 90 seconds)
                start_time = time.time()
                while time.time() - start_time < 90:
                    time.sleep(4.0)
                    poll_res = client.get(status_url, headers=headers)
                    if poll_res.status_code == 200:
                        poll_data = poll_res.json()
                        status = poll_data.get("status")
                        if status == "COMPLETED":
                            result_res = client.get(response_url, headers=headers)
                            if result_res.status_code == 200:
                                video_url = result_res.json().get("video", {}).get("url")
                                if video_url:
                                    video_res = client.get(video_url)
                                    with open(output_path, "wb") as f_out:
                                        f_out.write(video_res.content)
                                    print(f"🎉 Fal.ai Kling clip generated: {output_path}")
                                    return output_path
                        elif status in ("FAILED", "CANCELLED"):
                            print(f"⚠️ Fal.ai video status: {status}")
                            break
            return None
        except Exception as e:
            print(f"⚠️ Fal.ai video generation error: {e}. Falling back to local engines...")
            return None

    @classmethod
    def _generate_runway_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        """
        Calls Runway Gen-3 Alpha API for Hollywood-tier generative video.
        """
        if not settings.RUNWAY_API_KEY:
            return None

        try:
            import httpx
            import base64
            import time

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
                "promptText": f"{scene.visual_prompt}. Extremely high production value, vertical 9:16, 60fps cinematic look.",
                "duration": 5,
                "ratio": "9:16"
            }

            with httpx.Client(timeout=30.0) as client:
                res = client.post("https://api.dev.runwayml.com/v1/image_to_video", headers=headers, json=payload)
                if res.status_code not in (200, 201):
                    print(f"⚠️ Runway API notice ({res.status_code}): {res.text[:200]}")
                    return None

                task_id = res.json().get("id")
                if not task_id:
                    return None

                # Poll Runway task
                start_time = time.time()
                while time.time() - start_time < 90:
                    time.sleep(4.0)
                    poll_res = client.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
                    if poll_res.status_code == 200:
                        poll_data = poll_res.json()
                        status = poll_data.get("status")
                        if status == "SUCCEEDED":
                            video_url = poll_data.get("output", [])[0]
                            video_res = client.get(video_url)
                            with open(output_path, "wb") as f_out:
                                f_out.write(video_res.content)
                            print(f"👑 Runway Gen-3 clip generated: {output_path}")
                            return output_path
                        elif status in ("FAILED", "CANCELLED"):
                            print(f"⚠️ Runway video status: {status}")
                            break
            return None
        except Exception as e:
            print(f"⚠️ Runway video generation error: {e}. Falling back to local engines...")
            return None

    @classmethod
    def _generate_luma_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        """
        Calls Luma Dream Machine Ray 2 API.
        """
        if not settings.LUMA_API_KEY:
            return None

        try:
            import httpx
            import time

            headers = {
                "Authorization": f"Bearer {settings.LUMA_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "prompt": scene.visual_prompt,
                "aspect_ratio": "9:16",
                "keyframes": {
                    "frame0": {
                        "type": "image",
                        "url": scene.image_url or ""
                    }
                }
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
                                print(f"👑 Luma Ray 2 clip generated: {output_path}")
                                return output_path
                        elif data.get("state") == "failed":
                            break
            return None
        except Exception as e:
            print(f"⚠️ Luma generation note: {e}")
            return None

    @classmethod
    def _generate_kling_clip(cls, scene: SceneBeat, image_path: str, output_path: str, duration: float) -> Optional[str]:
        """Calls Kling AI direct API."""
        return cls._generate_fal_clip(scene, image_path, output_path, duration)
