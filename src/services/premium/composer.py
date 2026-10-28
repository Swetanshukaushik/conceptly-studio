"""Turns a shot and its still into a studio3d scene: a full-frame image plane, a camera move over it (expressions of the
scene progress p, so it stays correct after narration timing changes), a slow dust layer in front for depth, and the overlays."""
import math
from typing import Any, Dict, List, Optional

from src.services.premium import style

TAN = math.tan(math.radians(20))   # fov 40


def _mix(a: float, b: float) -> Any:
    return round(a, 4) if abs(a - b) < 1e-6 else f"mix({a:.4f},{b:.4f},smooth(0,1,p))"


def camera_for(motion: str) -> Dict[str, Any]:
    cfg = style.cfg(); m = cfg["motions"].get(motion) or cfg["motions"]["push_in"]; plane_h = cfg["plane"]["height"]
    dist = lambda frac: frac * plane_h / (2 * TAN)   # camera distance that shows `frac` of the plane height
    d0, d1 = dist(m["d"][0]), dist(m["d"][1])
    return {"position": [_mix(m["x"][0], m["x"][1]), _mix(m["y"][0], m["y"][1]), _mix(d0, d1)],
            "target": [_mix(m["x"][0], m["x"][1]), _mix(m["y"][0], m["y"][1]), 0], "fov": 40}


def compose_scene(shot: Any, still: Dict[str, Any], beat: Dict[str, Any]) -> Dict[str, Any]:
    cfg = style.cfg(); H = cfg["plane"]["height"]
    aspect = still.get("aspect") or cfg["plane"]["aspect"]
    W = H * cfg["plane"]["aspect"]
    objects: List[Dict[str, Any]] = []; overlays: List[Dict[str, Any]] = []
    if still.get("src"):
        # contain-fit is done by the renderer; a 9:16 still fills the plane, an archive photo (landscape) is shown full width
        size = [W, H] if abs(aspect - cfg["plane"]["aspect"]) < 0.08 else ([W, W / aspect] if aspect > cfg["plane"]["aspect"] else [H * aspect, H])
        objects.append({"id": "still", "type": "image", "src": still["src"], "aspect": aspect, "size": size, "dim": 1.0, "position": [0, 0, 0],
                        "appear": {"at": 0, "duration": 0.5, "style": "fade"}})
    else:
        objects.append({"id": "glow_bg", "type": "glow", "color": "primary", "size": 14, "intensity": 0.6, "position": [0, 0, -1]})
    if cfg["dust"]["enabled"]:
        n = int(cfg["dust"]["count"])
        objects.append({"id": "dust", "type": "particles", "count": n, "radius": 0.016, "color": "accent",
                        "x": "sin(i*12.9898)*2.6+sin(t*0.3+i)*0.25", "y": "sin(i*78.233)*4.6+cos(t*0.25+i*2)*0.3", "z": "1.5+sin(i*37.719)*0.6"})
    for i, pin in enumerate(shot.pins[:3]):
        pid = f"pin{i + 1}"
        objects.append({"id": pid, "type": "glow", "color": "accent", "size": 0.35, "intensity": 0.8,
                        "position": [round((pin.x - 0.5) * size_w(objects, W), 3), round((0.5 - pin.y) * size_h(objects, H), 3), 0.05],
                        "appear": {"at": 0.8 + 0.5 * i, "duration": 0.4, "style": "fade"}})
        overlays.append({"kind": "tag", "target": pid, "text": pin.text, "style": "pin", "side": "right" if pin.x < 0.55 else "left", "at": 0.8 + 0.5 * i})
    if shot.title:
        overlays.append({"kind": "title", "text": shot.title, "anchor": "upper", "at": 0.3, "until": max(2.0, min(4.5, beat["seconds"] - 0.3))})
    if shot.pop_word:
        overlays.append({"kind": "pop", "word": shot.pop_word})
    return {"beat": beat["beat"], "intent": shot.prompt[:140], "staging": f"{shot.shot_type} still, camera {shot.motion.replace('_', ' ')}",
            "params": {}, "camera": camera_for(shot.motion), "objects": objects, "overlays": overlays, "floor": False}


def size_w(objects: List[Dict[str, Any]], default: float) -> float:
    img = next((o for o in objects if o.get("id") == "still"), None)
    return img["size"][0] if img else default


def size_h(objects: List[Dict[str, Any]], default: float) -> float:
    img = next((o for o in objects if o.get("id") == "still"), None)
    return img["size"][1] if img else default
