import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from src.database.session import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    jobs = relationship("ReelJob", back_populates="user", cascade="all, delete-orphan")

class ReelJob(Base):
    __tablename__ = "reel_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    generation_tier = Column(String(20), default="DEFAULT")  # "DEFAULT" | "PREMIUM"
    
    # Curriculum Taxonomy
    exam_type = Column(String(50), default="SCHOOL")
    class_level = Column(Integer, nullable=True)
    subject = Column(String(100), nullable=False)
    topic_title = Column(String(255), nullable=False)
    topic_id = Column(String(100), nullable=True)  # Conceptly Core UUID
    
    # Pipeline Status & Gating
    # Statuses: PENDING -> GATE_1_READY -> GATE_1_APPROVED -> GATE_2_READY -> GATE_2_APPROVED -> PROCESSING -> GATE_3_READY -> PUBLISHED | FAILED
    status = Column(String(50), default="PENDING", index=True)
    
    # Stage Checkpoint Payloads (JSON strings)
    script_data = Column(Text, nullable=True)
    quiz_data = Column(Text, nullable=True)
    
    # Media Artifacts
    video_url = Column(String(500), nullable=True)
    local_video_path = Column(String(500), nullable=True)
    duration_sec = Column(Integer, default=45)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="jobs")
    stages = relationship("JobStage", back_populates="job", cascade="all, delete-orphan", order_by="JobStage.created_at")
    artifacts = relationship("ReelArtifact", back_populates="job", cascade="all, delete-orphan")

class JobStage(Base):
    __tablename__ = "job_stages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("reel_jobs.id"), nullable=False)
    stage_name = Column(String(100), nullable=False)
    status = Column(String(50), default="PENDING")  # "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED"
    progress_percent = Column(Integer, default=0)
    log_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    job = relationship("ReelJob", back_populates="stages")

class ReelArtifact(Base):
    __tablename__ = "reel_artifacts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("reel_jobs.id"), nullable=False)
    artifact_type = Column(String(50), nullable=False)  # "SCRIPT_JSON", "QUIZ_JSON", "AUDIO_MP3", "SUBTITLE_ASS", "VIDEO_MP4"
    file_path = Column(String(500), nullable=False)
    cloud_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("ReelJob", back_populates="artifacts")
