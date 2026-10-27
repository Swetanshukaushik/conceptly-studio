"""Python side of the studio3d renderer (studio3d/render.mjs): assembles a timeline spec from the
storyboard + speech timestamps and runs the headless 3D renderer."""
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from src.services.config_loader import load_json

STUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), "studio3d")


class Studio3DError(RuntimeError):
    pass


class Studio3DEngine:
    @staticmethod
    def _node() -> str:
        node = os.environ.get("NODE_BIN") or shutil.which("node")
        if not node:
            raise Studio3DError("Node.js not found. Install Node 20+ or set NODE_BIN.")
        if not os.path.isdir(os.path.join(STUDIO_DIR, "node_modules")):
            raise Studio3DError("studio3d dependencies missing. Run: cd studio3d && npm install")
        return node

    @classmethod
    def build_spec(
        cls,
        storyboard: Any,
        look: str,
        word_timestamps: Optional[List[Any]] = None,
        fps: Optional[int] = None,
    ) -> Dict[str, Any]:
        cfg = load_json("render.json")
        scenes: List[Dict[str, Any]] = []
        for sc in storyboard.scenes:
            plan = getattr(sc, "scene3d", None)
            if not plan:
                raise Studio3DError(f"Scene {sc.scene_number} has no 3D plan; the Free tier cannot render it.")
            d = dict(plan)
            d.pop("beat", None)
            d.pop("intent", None)
            d.update({"id": f"beat_{sc.scene_number}", "beat": sc.scene_number, "start": float(sc.start_sec), "end": float(sc.end_sec)})
            scenes.append(d)
        captions = [{"w": w.word, "t0": float(w.start_sec), "t1": float(w.end_sec)} for w in (word_timestamps or [])]
        spec = {
            "version": 1, "look": look, "fps": fps or cfg["canvas"]["fps"],
            "duration": scenes[-1]["end"], "scenes": scenes, "captions": captions,
        }
        narrator = cls.narrator_spec(getattr(storyboard, "route", None))
        if narrator:
            spec["narrator"] = narrator
        if getattr(storyboard, "layout", None):
            spec["layout"] = storyboard.layout
        if getattr(storyboard, "header", None):
            spec["header"] = storyboard.header
        return spec

    @staticmethod
    def narrator_spec(route: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Settings for the on-screen narrator character, from the routed pack's persona (config/characters, config/narrator.json)."""
        cfg = load_json("narrator.json")
        persona = (route or {}).get("persona") or {}
        if not cfg.get("enabled") or persona.get("status") != "ready" or not persona.get("archetype"):
            return None
        from src.services.config_loader import CONFIG_DIR
        for name in [persona["archetype"], persona.get("fallback")]:
            if not name:
                continue
            try:
                char = load_json("characters", f"{name}.json")
            except FileNotFoundError:
                continue
            base = {k: v for k, v in cfg.items() if k != "enabled"}
            if char.get("kind") == "photo":
                if not os.path.exists(os.path.join(CONFIG_DIR, char["image"].replace("/config/", "", 1))):
                    continue   # photo missing on this machine: fall back to the rig character
                return {**base, "name": char["name"], "kind": "photo", "photo": char}
            return {**base, "name": char["name"], "kind": "rig", "params": char["params"]}
        return None

    @classmethod
    def _run(cls, args: List[str], timeout: int) -> Dict[str, Any]:
        cmd = [cls._node(), os.path.join(STUDIO_DIR, "render.mjs")] + args
        env = dict(os.environ)
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, env=env)
        lines = [l for l in res.stdout.strip().splitlines() if l.startswith("{")]
        if not lines:
            raise Studio3DError(f"studio3d produced no result (exit {res.returncode}): {res.stderr[-1500:]}")
        result = json.loads(lines[-1])
        if not result.get("ok") and "problems" not in result:
            raise Studio3DError(f"studio3d failed: {result.get('error', '')[-1500:]}\n{res.stderr[-800:]}")
        return result

    @classmethod
    def _with_spec(cls, spec: Dict[str, Any], fn):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "spec.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(spec, f)
            return fn(path)

    @classmethod
    def lint(cls, spec: Dict[str, Any], assets_dir: Optional[str] = None) -> List[str]:
        def run(path):
            args = ["--spec", path, "--lint"]
            if assets_dir:
                args += ["--assets", assets_dir]
            return cls._run(args, timeout=180)
        return cls._with_spec(spec, run).get("problems", [])

    @classmethod
    def render_stills(cls, spec: Dict[str, Any], times: List[float], out_dir: str, assets_dir: Optional[str] = None) -> List[str]:
        def run(path):
            args = ["--spec", path, "--stills", ",".join(f"{t:.3f}" for t in times), "--outdir", out_dir]
            if assets_dir:
                args += ["--assets", assets_dir]
            return cls._run(args, timeout=300)
        return cls._with_spec(spec, run)["files"]

    @classmethod
    def render_reel(cls, spec: Dict[str, Any], output_mp4: str, audio_path: Optional[str] = None, assets_dir: Optional[str] = None) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)

        def run(path):
            args = ["--spec", path, "--out", output_mp4]
            if audio_path:
                args += ["--audio", audio_path]
            if assets_dir:
                args += ["--assets", assets_dir]
            return cls._run(args, timeout=int(max(600, spec["duration"] * 20)))
        result = cls._with_spec(spec, run)
        if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < 10_000:
            raise Studio3DError("studio3d reported success but produced no video")
        return result
