import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Conceptly Studio"
    VERSION: str = "3.1.0"
    API_V1_STR: str = "/api"
    
    # Server & CORS
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "*"]
    
    # Authentication & Security
    SECRET_KEY: str = Field(default="conceptly-super-secret-jwt-key-2026-production", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ADMIN_EMAIL: str = Field(default="admin@conceptly.app", env="ADMIN_EMAIL")
    ADMIN_PASSWORD: str = Field(default="admin123456", env="ADMIN_PASSWORD")
    
    # Database
    DATABASE_URL: str = Field(default="sqlite:///./conceptly_studio.db", env="DATABASE_URL")
    
    # Media Storage
    STORAGE_PROVIDER: str = Field(default="local", env="STORAGE_PROVIDER")  # "local", "r2", "s3"
    LOCAL_STORAGE_DIR: str = Field(default="./output", env="LOCAL_STORAGE_DIR")
    R2_ACCOUNT_ID: Optional[str] = Field(default=None, env="R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME: str = Field(default="conceptly-reels", env="R2_BUCKET_NAME")
    R2_PUBLIC_URL: str = Field(default="https://media.conceptly.app", env="R2_PUBLIC_URL")
    
    # Conceptly Core Integration
    CONCEPTLY_API_BASE_URL: str = Field(default="https://conceptly-api.onrender.com/v1", env="CONCEPTLY_API_BASE_URL")
    CONCEPTLY_API_KEY: Optional[str] = Field(default=None, env="CONCEPTLY_API_KEY")
    
    # LLM Providers (Dual-Tier: Default & Premium)
    GEMINI_API_KEY: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    
    # Voice / TTS Providers
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None, env="ELEVENLABS_API_KEY")
    DEFAULT_EDGE_TTS_VOICE: str = "en-IN-NeerjaNeural"
    DEFAULT_ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel

    # Tier 2 & Tier 3 AI Video Generation Providers (2026 Generative Video)
    FAL_KEY: Optional[str] = Field(default=None, env="FAL_KEY")
    KLING_API_KEY: Optional[str] = Field(default=None, env="KLING_API_KEY")
    RUNWAY_API_KEY: Optional[str] = Field(default=None, env="RUNWAY_API_KEY")
    LUMA_API_KEY: Optional[str] = Field(default=None, env="LUMA_API_KEY")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
