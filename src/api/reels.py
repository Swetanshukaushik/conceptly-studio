import os
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from src.core.config import settings
from src.database.session import get_db
from src.models.entities import User, ReelJob, JobStage, ReelArtifact
from src.models.schemas import (
    CreateReelRequest,
    ReelJobRead,
    Gate1ApprovalRequest,
    Gate2ApprovalRequest,
    Gate3PublishRequest,
    SceneRegenerateRequest,
    SceneBeat,
    ReelGenerationTier,
    JobStatus
)
from src.engines.visuals.visual_factory import VisualAssetFactory
from src.api.auth import get_current_user
from src.pipeline.orchestrator import PipelineOrchestrator
from src.services.llm_factory import LLMFactory

router = APIRouter(prefix="/reels", tags=["reels"])

def format_job_response(job: ReelJob) -> dict:
    script = None
    if job.script_data:
        try:
            script = json.loads(job.script_data)
        except Exception:
            script = None
            
    quiz = None
    if job.quiz_data:
        try:
            quiz = json.loads(job.quiz_data)
        except Exception:
            quiz = None

    return {
        "id": job.id,
        "user_id": job.user_id,
        "generation_tier": job.generation_tier,
        "exam_type": job.exam_type,
        "class_level": job.class_level,
        "subject": job.subject,
        "topic_title": job.topic_title,
        "topic_id": job.topic_id,
        "status": job.status,
        "script_data": script,
        "quiz_data": quiz,
        "video_url": job.video_url,
        "local_video_path": job.local_video_path,
        "duration_sec": job.duration_sec,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "stages": [
            {
                "id": s.id,
                "stage_name": s.stage_name,
                "status": s.status,
                "progress_percent": s.progress_percent,
                "log_message": s.log_message,
                "updated_at": s.updated_at
            }
            for s in job.stages
        ],
        "artifacts": [
            {
                "id": a.id,
                "artifact_type": a.artifact_type,
                "file_path": a.file_path,
                "cloud_url": a.cloud_url,
                "created_at": a.created_at
            }
            for a in job.artifacts
        ]
    }

@router.get("/system/config-status")
def get_system_config_status(current_user: User = Depends(get_current_user)):
    llm_ok = bool(LLMFactory.is_llm_configured() or settings.ALLOW_OFFLINE_DEV_FALLBACK)
    visual_ok = bool(settings.FAL_KEY or settings.OPENAI_API_KEY or settings.HF_TOKEN or settings.POLLEN_KEY)
    cinema_ok = bool(settings.FAL_KEY or settings.KLING_API_KEY or settings.RUNWAY_API_KEY or settings.LUMA_API_KEY)

    return {
        "llm_configured": llm_ok,
        "visual_configured": visual_ok,
        "video_configured": cinema_ok,
        "free_tier_active": True,
        "gemini_active": bool(settings.GEMINI_API_KEY),
        "openai_active": bool(settings.OPENAI_API_KEY),
        "anthropic_active": bool(settings.ANTHROPIC_API_KEY),
        "fal_active": bool(settings.FAL_KEY),
        "kling_active": bool(settings.KLING_API_KEY),
        "runway_active": bool(settings.RUNWAY_API_KEY),
        "hf_active": bool(settings.HF_TOKEN),
        "pollen_active": bool(settings.POLLEN_KEY),
        "tiers": {
            "TIER_1_FLASH": {
                "name": "Tier 1: Flash",
                "cost": "$0.00",
                "enabled": bool(llm_ok and visual_ok),
                "required_keys": ["GEMINI_API_KEY", "FAL_KEY | POLLEN_KEY | HF_TOKEN | OPENAI_API_KEY"],
                "missing_keys": [
                    *(["GEMINI_API_KEY"] if not llm_ok else []),
                    *(["FAL_KEY or POLLEN_KEY or HF_TOKEN"] if not visual_ok else [])
                ],
                "tooltip": "✓ Ready to Generate (Photos + Audio)" if (llm_ok and visual_ok) else "⚠️ Requires external visual key (FAL_KEY, POLLEN_KEY, or HF_TOKEN) in .env"
            },
            "TIER_2_AVATAR": {
                "name": "Tier 2: Avatar",
                "cost": "~$0.02",
                "enabled": bool(llm_ok),
                "required_keys": ["GEMINI_API_KEY"],
                "missing_keys": [] if llm_ok else ["GEMINI_API_KEY"],
                "tooltip": "✓ Ready to Generate (Built-in 2D character engine)" if llm_ok else "⚠️ Requires GEMINI_API_KEY in .env"
            },
            "TIER_3_STEM": {
                "name": "Tier 3: STEM",
                "cost": "$0.00",
                "enabled": bool(llm_ok),
                "required_keys": ["GEMINI_API_KEY"],
                "missing_keys": [] if llm_ok else ["GEMINI_API_KEY"],
                "tooltip": "✓ Ready to Generate (100% Free local 3Blue1Brown physics simulation)" if llm_ok else "⚠️ Requires GEMINI_API_KEY in .env"
            },
            "TIER_4_CINEMA": {
                "name": "Tier 4: Cinema",
                "cost": "~$0.20",
                "enabled": bool(llm_ok and cinema_ok),
                "required_keys": ["GEMINI_API_KEY", "FAL_KEY | KLING_API_KEY | RUNWAY_API_KEY"],
                "missing_keys": [
                    *(["GEMINI_API_KEY"] if not llm_ok else []),
                    *(["FAL_KEY or KLING_API_KEY or RUNWAY_API_KEY"] if not cinema_ok else [])
                ],
                "tooltip": "✓ Ready to Generate (Kling / Runway video diffusion)" if (llm_ok and cinema_ok) else "⚠️ Requires FAL_KEY, KLING_API_KEY, or RUNWAY_API_KEY in .env"
            },
            "TIER_5_KURZGESAGT": {
                "name": "Tier 5: Kurzgesagt",
                "cost": "~$0.30",
                "enabled": bool(llm_ok),
                "required_keys": ["GEMINI_API_KEY"],
                "missing_keys": [] if llm_ok else ["GEMINI_API_KEY"],
                "tooltip": "✓ Ready to Generate (Rigged duck mascot + vector physics sim)" if llm_ok else "⚠️ Requires GEMINI_API_KEY in .env"
            }
        },
        "active_provider": (
            "Google Gemini 2.5 Flash" if settings.GEMINI_API_KEY
            else "OpenAI GPT-4o" if settings.OPENAI_API_KEY
            else "Anthropic Claude 3.5" if settings.ANTHROPIC_API_KEY
            else "Offline Dev Fallback" if settings.ALLOW_OFFLINE_DEV_FALLBACK
            else "None (Missing GEMINI_API_KEY)"
        )
    }

@router.post("/create", response_model=ReelJobRead)
def create_reel_job(
    payload: CreateReelRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce active LLM configuration: prevent silent hardcoding
    if not LLMFactory.is_llm_configured() and not settings.ALLOW_OFFLINE_DEV_FALLBACK:
        raise HTTPException(
            status_code=400,
            detail="Missing LLM API Key: GEMINI_API_KEY is not configured in .env. A valid API key is required to dynamically generate blueprints, scripts, and quizzes without hardcoding."
        )

    # Tier Key Validation
    if payload.generation_tier in (ReelGenerationTier.TIER_4_CINEMA, ReelGenerationTier.PREMIUM):
        if not (settings.FAL_KEY or settings.KLING_API_KEY or settings.RUNWAY_API_KEY):
            raise HTTPException(
                status_code=400,
                detail="Tier 4 (CINEMA AI) requires FAL_KEY (recommended for Fal.ai Kling / LTX) or RUNWAY_API_KEY in .env."
            )
    elif payload.generation_tier in (ReelGenerationTier.TIER_1_FLASH, ReelGenerationTier.FREE):
        if not (settings.FAL_KEY or settings.OPENAI_API_KEY or settings.HF_TOKEN or settings.POLLEN_KEY):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tier 1 (FLASH) requires an external visual model. Please configure FAL_KEY, POLLEN_KEY, HF_TOKEN, or OPENAI_API_KEY in .env, "
                    "or select Tier 3 (STEM RIGOR) or Tier 5 (KURZGESAGT) for 100% animation with zero extra keys."
                )
            )

    job = ReelJob(
        user_id=current_user.id,
        generation_tier=payload.generation_tier.value,
        exam_type=payload.exam_type,
        class_level=payload.class_level,
        subject=payload.subject,
        topic_title=payload.topic_title,
        topic_id=payload.topic_id,
        status=JobStatus.PENDING.value
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Initialize initial pipeline stages
    initial_stages = [
        "CURRICULUM_DISCOVERY",
        "CONCEPT_EXTRACTION",
        "SCRIPTWRITING",
        "GATE_1_REVIEW",
        "QUIZ_GENERATION",
        "GATE_2_REVIEW",
        "VOICE_SYNTHESIS",
        "KINETIC_SUBTITLES",
        "VIDEO_COMPOSITING",
        "GATE_3_REVIEW",
        "PUBLISHING"
    ]
    for name in initial_stages:
        stage = JobStage(job_id=job.id, stage_name=name, status="PENDING")
        db.add(stage)
    db.commit()
    db.refresh(job)
    
    # Trigger Stage 1 Blueprint Generation in Background
    background_tasks.add_task(PipelineOrchestrator.run_stage1_blueprint, job.id)
    
    return format_job_response(job)

@router.get("", response_model=List[ReelJobRead])
def list_reel_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    jobs = db.query(ReelJob).order_by(ReelJob.created_at.desc()).all()
    return [format_job_response(j) for j in jobs]

@router.get("/{job_id}", response_model=ReelJobRead)
def get_reel_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return format_job_response(job)

@router.post("/{job_id}/scenes/{scene_number}/regenerate", response_model=SceneBeat)
def regenerate_scene_visual(
    job_id: str,
    scene_number: int,
    payload: SceneRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.script_data:
        raise HTTPException(status_code=400, detail="No script data exists for this job")
    
    script_dict = json.loads(job.script_data)
    storyboard = script_dict.get("storyboard")
    if not storyboard or "scenes" not in storyboard:
        raise HTTPException(status_code=400, detail="No storyboard scenes found in script")
    
    target_idx = None
    target_scene_dict = None
    for idx, s in enumerate(storyboard["scenes"]):
        if s.get("scene_number") == scene_number:
            target_idx = idx
            target_scene_dict = s
            break
            
    if target_scene_dict is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_number} not found")
        
    scene = SceneBeat.parse_obj(target_scene_dict)
    if payload.visual_prompt:
        scene.visual_prompt = payload.visual_prompt
    if payload.camera_motion:
        scene.camera_motion = payload.camera_motion
    if payload.visual_modality:
        scene.visual_modality = payload.visual_modality
        
    tier = ReelGenerationTier(job.generation_tier)
    job_output_dir = os.path.join(settings.LOCAL_STORAGE_DIR, "jobs", job_id)
    frames_dir = os.path.join(job_output_dir, "storyboard_frames")
    os.makedirs(frames_dir, exist_ok=True)
    img_path = os.path.join(frames_dir, f"scene_{scene.scene_number:02d}.png")
    
    VisualAssetFactory.render_scene_image(scene, img_path, tier=tier)
    scene.image_path = img_path
    scene.image_url = f"/media/jobs/{job_id}/storyboard_frames/scene_{scene.scene_number:02d}.png"
    
    storyboard["scenes"][target_idx] = scene.dict()
    job.script_data = json.dumps(script_dict)
    db.commit()
    return scene

@router.post("/{job_id}/gate1/approve", response_model=ReelJobRead)
def approve_gate1_script(
    job_id: str,
    payload: Gate1ApprovalRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.script_data = json.dumps(payload.script_data.dict())
    job.status = JobStatus.GATE_1_APPROVED.value
    db.commit()
    db.refresh(job)
    
    # Trigger Stage 2 Quiz Generation in Background based on approved script
    background_tasks.add_task(PipelineOrchestrator.run_stage2_quiz, job.id)
    
    return format_job_response(job)

@router.post("/{job_id}/gate2/approve", response_model=ReelJobRead)
def approve_gate2_quiz(
    job_id: str,
    payload: Gate2ApprovalRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.quiz_data = json.dumps(payload.quiz_data.dict())
    job.status = JobStatus.GATE_2_APPROVED.value
    PipelineOrchestrator._update_stage(db, job_id, "GATE_2_REVIEW", "COMPLETED", 100, "Quiz approved by creator.")
    db.commit()
    db.refresh(job)
    
    # Trigger Stage 3 Video Synthesis in Background
    background_tasks.add_task(PipelineOrchestrator.run_stage3_video_synthesis, job.id)
    
    return format_job_response(job)

@router.post("/{job_id}/gate3/publish", response_model=ReelJobRead)
def publish_gate3_reel(
    job_id: str,
    payload: Gate3PublishRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if payload.publish_to_conceptly:
        from src.agents.publisher_agent import publisher_agent
        publisher_agent.publish_reel(job)
        PipelineOrchestrator._update_stage(db, job_id, "PUBLISHING", "COMPLETED", 100, "Successfully synced with Conceptly Core API.")
    
    PipelineOrchestrator._update_stage(db, job_id, "GATE_3_REVIEW", "COMPLETED", 100, "Approved and published by creator.")
    job.status = JobStatus.PUBLISHED.value
    db.commit()
    db.refresh(job)
    
    return format_job_response(job)
