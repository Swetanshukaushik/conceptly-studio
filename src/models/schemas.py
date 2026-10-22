from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class ReelGenerationTier(str, Enum):
    FREE = "FREE"           # Tier 1 (Cost: ~$0.00 / reel): Gemini Flash + EdgeTTS + 2.5D Parallax Video Clips
    PREMIUM = "PREMIUM"     # Tier 2 (Cost: ~$0.20 / reel): Kling AI / Hailuo AI Video Clips + Visual Story
    ULTRA = "ULTRA"         # Tier 3 (Cost: ~$0.85 / reel): FLUX.1 + Runway Gen-3 / Luma Ray 2 + ElevenLabs
    DEFAULT = "DEFAULT"     # Backward compatibility alias

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

class SceneBeat(BaseModel):
    scene_number: int
    act_number: int
    start_sec: float
    end_sec: float
    spoken_line: str
    visual_modality: VisualModality = VisualModality.CINEMATIC_SCENE
    visual_prompt: str = Field(..., description="Photorealistic or diagrammatic prompt for 9:16 vertical render")
    camera_motion: CameraMotion = CameraMotion.ZOOM_IN
    sound_effect: str = "WHOOSH"  # "BASS_BOOM", "WHOOSH", "SPARK_CHIME", "NONE"
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    video_clip_path: Optional[str] = None
    video_clip_url: Optional[str] = None

class Storyboard(BaseModel):
    topic_title: str
    total_scenes: int
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

# ================= Reel Job Ingestion Schemas =================
class CreateReelRequest(BaseModel):
    topic_title: str
    exam_type: str = "SCHOOL"  # "SCHOOL", "IIT_JEE", "NEET", "UPSC"
    class_level: Optional[int] = 9
    subject: str = "Physics"
    topic_id: Optional[str] = None
    generation_tier: ReelGenerationTier = ReelGenerationTier.DEFAULT
    voice_id: Optional[str] = None
    custom_prompt: Optional[str] = None

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
    exam_type: str
    class_level: Optional[int] = None
    subject: str
    topic_title: str
    topic_id: Optional[str] = None
    status: str
    script_data: Optional[Dict[str, Any]] = None
    quiz_data: Optional[Dict[str, Any]] = None
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
