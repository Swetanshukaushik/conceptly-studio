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

@router.post("/create", response_model=ReelJobRead)
def create_reel_job(
    payload: CreateReelRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
