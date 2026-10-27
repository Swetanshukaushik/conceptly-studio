from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class ReelGenerationTier(str, Enum):
    TIER_1_FLASH = "TIER_1_FLASH"           # Tier 1 ($0.00): 2.5D Ken Burns Photo Slideshow with Audio
    TIER_2_AVATAR = "TIER_2_AVATAR"         # Tier 2 (~$0.02): Dynamic Lip-Synced Character Teacher Avatar
    TIER_3_STEM = "TIER_3_STEM"             # Tier 3 ($0.00): 3Blue1Brown Manim Exact Physics & Math Vector Engine
    TIER_4_CINEMA = "TIER_4_CINEMA"         # Tier 4 (~$0.20): Fal.ai Kling / Runway Generative AI Cinema Video
    TIER_5_KURZGESAGT = "TIER_5_KURZGESAGT" # Tier 5 (~$0.30): Rigged Vector Character + Embedded Physics Sim + Studio FX
    
    # Backward compatibility aliases
    FREE = "FREE"
    PREMIUM = "PREMIUM"
    ULTRA = "ULTRA"
    DEFAULT = "DEFAULT"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    GATE_1_READY = "GATE_1_READY"         # Script ready for creator review
    GATE_1_APPROVED = "GATE_1_APPROVED"
    GATE_2_READY = "GATE_2_READY"         # Quiz ready for creator review
    GATE_2_APPROVED = "GATE_2_APPROVED"
    PROCESSING = "PROCESSING"             # TTS + Compositor running
    GATE_3_READY = "GATE_3_READY"         # Final reel rendered; awaiting publish decision
    PUBLISHED = "PUBLISHED"               # Synced to Conceptly Core
    FAILED = "FAILED"

# ================= Auth Schemas =================
class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    sub: Optional[str] = None

class UserRead(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ================= Script & Storyboard Schemas =================
class VisualModality(str, Enum):
    CINEMATIC_SCENE = "CINEMATIC_SCENE"       # History, Storytelling, UPSC, Real-world cinema
    SCIENTIFIC_DIAGRAM = "SCIENTIFIC_DIAGRAM" # Physics vectors, circuits, molecular bonds
    ANATOMICAL_3D = "ANATOMICAL_3D"           # Biology organs, cellular chloroplasts, DNA
    DATA_INFOGRAPHIC = "DATA_INFOGRAPHIC"     # Economics, timelines, formula spotlights

class CameraMotion(str, Enum):
    ZOOM_IN = "ZOOM_IN"       # Slow dramatic push-in (1.0x -> 1.15x)
    PAN_RIGHT = "PAN_RIGHT"   # Smooth horizontal drift
    PAN_LEFT = "PAN_LEFT"
    PULL_BACK = "PULL_BACK"   # Reveals wider context

class HudOverlay(BaseModel):
    formula: Optional[str] = None       # e.g. "L = I · ω" or "ΔU = Q - W"
    label: Optional[str] = None         # e.g. "CONSERVATION OF ANGULAR MOMENTUM"
    units: Optional[str] = None         # e.g. "kg · m² / s"
    concept_tag: Optional[str] = None   # e.g. "CLASS 11 PHYSICS"

class SceneBeat(BaseModel):
    scene_number: int
    act_number: int
    start_sec: float
    end_sec: float
    spoken_line: str
    visual_modality: VisualModality = VisualModality.CINEMATIC_SCENE
    shot_type: str = "GEN"  # "GEN" (photorealistic background visual) or "OVERLAY" (formula / diagram spotlight)
    visual_prompt: str = Field(..., description="Photorealistic prompt for 9:16 vertical render (NO text/words)")
    hud_overlay: Optional[HudOverlay] = None
    style_bible: Optional[str] = None
    camera_motion: CameraMotion = CameraMotion.ZOOM_IN
    sound_effect: str = "WHOOSH"  # "BASS_BOOM", "WHOOSH", "SPARK_CHIME", "NONE"
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    video_clip_path: Optional[str] = None
    video_clip_url: Optional[str] = None
    scene3d: Optional[Dict[str, Any]] = None  # Free tier: declarative 3D scene plan (see models/scene3d.py)

class Storyboard(BaseModel):
    topic_title: str
    total_scenes: int
    style_bible: Optional[str] = "Cinematic 35mm vertical photography, volumetric lighting, dark atmospheric studio, 9:16 portrait, photorealistic, clean plate, zero text watermarks, no letters"
    layout: Optional[str] = None  # Free tier: layout preset name (config/layouts)
    header: Optional[List[str]] = None  # Free tier: headline lines for header layouts
    qa: Optional[List[str]] = None  # Free tier: unresolved layout / vision QA findings after the auto-retry
    route: Optional[Dict[str, Any]] = None  # Concept Router decision (domain pack, method, kits); see services/concept_router.py
    scenes: List[SceneBeat]

class ActScript(BaseModel):
    act_number: int = Field(..., description="1 (Hook), 2 (Intuition), 3 (Application), 4 (Takeaway/CTA)")
    title: str
    start_sec: float
    end_sec: float
    spoken_text: str
    visual_direction: str
    card_type: str = "CONCEPT_CARD"  # "HOOK_CARD", "ANALOGY_DIAGRAM", "COMPARISON_BOX", "FORMULA_SPOTLIGHT"

class ReelScript(BaseModel):
    title: str
    topic_title: str
    hook: str
    key_takeaway: str
    summary_notes: List[str]
    interview_pitch: Optional[str] = None
    acts: List[ActScript]
    total_word_count: int
    estimated_duration_sec: int = 45
    storyboard: Optional[Storyboard] = None
    script_generator: Optional[str] = "AUTO"
    tts_vocal_direction: Optional[str] = None
    math_claims: Optional[List[Dict[str, Any]]] = None  # checkable statements the writer listed (see services/math_verifier.py)
    math_verification: Optional[Dict[str, Any]] = None  # {status, attempts, notes}: result of the deterministic check

# ================= Quiz Schemas (Matching CONTRACT.md) =================
class QuizOption(BaseModel):
    id: str  # "a", "b", "c", "d"
    text: str

class QuizQuestion(BaseModel):
    id: str  # "q1", "q2"
    text: str
    options: List[QuizOption]
    correctOptionId: str
    explanation: str

class QuizPayload(BaseModel):
    topicId: Optional[str] = None
    topicTitle: str
    questions: List[QuizQuestion]

# ================= Stage 0: Domain & Pedagogical Intelligence Dossier =================
class DomainPedagogyDossier(BaseModel):
    canonical_topic: str
    domain_field: str
    exam_track: str
    target_class_level: str
    core_misconception: str
    root_flaw: str
    counter_intuitive_hook: str
    curiosity_gap: str
    must_include_concept: str
    strictly_excluded_topics: List[str] = Field(default_factory=list)
    concrete_visual_metaphor: str
    visual_transformation_beat: str
    atomic_takeaway: str
    marking_scheme_keywords: List[str] = Field(default_factory=list)
    diagnostic_question: Optional[str] = None
    correct_answer: Optional[str] = None
    distractor_misconception_answer: Optional[str] = None
    avatar_delivery_tone: Optional[str] = None
    # Dynamic AI Persona Decision & Character Store
    chosen_character_name: Optional[str] = None
    character_type: Optional[str] = "HISTORICAL_OR_STEM" # "HISTORICAL", "STEM_PIONEER", "STUDENT_PEER", "PHENOMENA_ONLY"
    character_visual_brief_3d: Optional[str] = None
    character_voice_persona: Optional[str] = None
    provider_used: str = "OpenAI-ChatGPT (GPT-4o)"

# ================= Character Avatar Schemas =================
class CharacterAvatarRead(BaseModel):
    id: str
    name: str
    title: str
    exam_track: str
    subject: str
    style_badge: str
    avatar_icon: str = "🎭"
    accent_color: str = "from-blue-600 to-indigo-600"
    voice_id: str
    voice_rate: str = "+0%"
    voice_pitch: str = "+0Hz"
    prompt: str
    neutral_prompt: str
    is_builtin: bool = True
    preview_url: Optional[str] = None

class CreateCustomAvatarRequest(BaseModel):
    name: str
    title: str
    exam_track: str = "ALL"
    subject: str = "Science"
    style_badge: str = "PIXAR_CYBERPUNK"
    prompt: str
    voice_id: Optional[str] = "en-US-ChristopherNeural"
    voice_rate: Optional[str] = "+0%"
    voice_pitch: Optional[str] = "+0Hz"

# ================= Reel Job Ingestion Schemas =================
class CreateReelRequest(BaseModel):
    topic_title: str
    exam_type: str = "SCHOOL"  # "SCHOOL", "IIT_JEE", "NEET", "UPSC"
    class_level: Optional[Union[int, str]] = 9
    subject: str = "Physics"
    topic_id: Optional[str] = None
    generation_tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    script_generator: Optional[str] = "AUTO"  # "AUTO", "GEMINI", "OPENAI"
    voice_id: Optional[str] = None
    custom_prompt: Optional[str] = None
    avatar_id: Optional[str] = "AUTO"  # Persona selection or AUTO-match by curriculum
    direct_synthesis: Optional[bool] = True  # When True, directly synthesizes final video without intermediate HITL pauses

class SceneRegenerateRequest(BaseModel):
    visual_prompt: Optional[str] = None
    camera_motion: Optional[CameraMotion] = None
    visual_modality: Optional[VisualModality] = None

class Gate1ApprovalRequest(BaseModel):
    script_data: ReelScript

class Gate2ApprovalRequest(BaseModel):
    quiz_data: QuizPayload

class Gate3PublishRequest(BaseModel):
    publish_to_conceptly: bool = True

# ================= Response Schemas =================
class JobStageRead(BaseModel):
    id: str
    stage_name: str
    status: str
    progress_percent: int
    log_message: Optional[str] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ReelArtifactRead(BaseModel):
    id: str
    artifact_type: str
    file_path: str
    cloud_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ReelJobRead(BaseModel):
    id: str
    user_id: Optional[str] = None
    generation_tier: str
    script_generator: Optional[str] = "AUTO"
    exam_type: str
    class_level: Optional[Union[int, str]] = None
    subject: str
    topic_title: str
    topic_id: Optional[str] = None
    status: str
    script_data: Optional[Dict[str, Any]] = None
    quiz_data: Optional[Dict[str, Any]] = None
    avatar: Optional[Dict[str, Any]] = None
    domain_dossier: Optional[Dict[str, Any]] = None
    video_url: Optional[str] = None
    local_video_path: Optional[str] = None
    duration_sec: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    stages: List[JobStageRead] = []
    artifacts: List[ReelArtifactRead] = []
    
    class Config:
        from_attributes = True
