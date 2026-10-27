"""Schema for the declarative 3D scene plan produced by the scene director and played back by studio3d.

Allowed object types and overlay kinds come from config/scene_vocabulary.json, the same file that is
rendered into the director prompt, so the manual, the validator and the schema cannot drift apart.
Numeric fields accept a number or an expression string; the renderer is the authority on per-type
fields and reports unknown things back as lint problems.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from src.services.config_loader import load_json

_VOCAB = load_json("scene_vocabulary.json")
ObjectType = Literal[tuple(_VOCAB["object_types"].keys())]  # type: ignore[valid-type]
OverlayKind = Literal[tuple(_VOCAB["overlay_kinds"].keys())]  # type: ignore[valid-type]
Anchor = Literal["top", "upper", "center", "lower"]
Num = Union[float, int, str]


class Object3D(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: ObjectType
    id: Optional[str] = None
    position: Optional[List[Num]] = None
    rotation: Optional[List[Num]] = None
    scale: Optional[Union[Num, List[Num]]] = None
    material: Optional[Union[str, Dict[str, Any]]] = None
    appear: Optional[Dict[str, Any]] = None
    vanish: Optional[Dict[str, Any]] = None
    children: Optional[List["Object3D"]] = None


class Overlay3D(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: OverlayKind
    at: Optional[Num] = 0
    until: Optional[float] = None
    anchor: Optional[Anchor] = None
    color: Optional[str] = None


class Camera3D(BaseModel):
    model_config = ConfigDict(extra="allow")
    position: List[Num]
    target: List[Num]
    fov: Optional[Num] = 40


class SceneDirection(BaseModel):
    """One 3D scene. Times are scene-local seconds; the renderer supplies start/end."""
    model_config = ConfigDict(extra="allow")
    beat: int = Field(..., description="Storyboard beat number this scene visualises")
    intent: str = Field(..., description="One sentence: what the viewer should understand from this scene")
    staging: str = Field(..., description="One or two sentences: what is where, what moves, how the camera travels. Write this BEFORE the objects.")
    params: Dict[str, Num] = Field(default_factory=dict)
    camera: Camera3D
    objects: List[Object3D]
    overlays: List[Overlay3D] = Field(default_factory=list)
    look: Optional[str] = None
    floor: Optional[Union[bool, Dict[str, Any]]] = None
    transition: Optional[Dict[str, Any]] = None


class ReelVisualPlan(BaseModel):
    """Whole-reel plan from the director: a look, a layout and one SceneDirection per beat."""
    model_config = ConfigDict(extra="allow")
    physics_plan: Optional[str] = Field(None, description="For physics topics, written BEFORE the scenes: for each beat, which physical quantity or law it shows and which tool implements it (sim block, mechanism prefab, graph prefab, field/wave expressions). A motion, force, energy, collision, rotation, oscillation or field topic must use the sim block.")
    look: str
    layout: str = Field("full", description="Layout name from the layouts list")
    header: Optional[List[str]] = Field(None, description="Headline lines for layouts that have a header block; follow the line count and length given in the layout list")
    scenes: List[SceneDirection]
