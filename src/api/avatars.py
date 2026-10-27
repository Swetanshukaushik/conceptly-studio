from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.auth import get_current_user
from src.models.entities import User
from src.models.schemas import CharacterAvatarRead, CreateCustomAvatarRequest
from src.services.avatar_catalog import AvatarCatalogService

router = APIRouter(prefix="/avatars", tags=["avatars"])

@router.get("", response_model=List[CharacterAvatarRead])
def list_character_avatars(current_user: User = Depends(get_current_user)):
    """List all available character personas (presets + user custom)."""
    return AvatarCatalogService.list_avatars()

@router.get("/resolve", response_model=CharacterAvatarRead)
def resolve_character_avatar(
    exam_type: str = Query("SCHOOL"),
    subject: str = Query("Physics"),
    tier: str = Query("TIER_3_STEM"),
    avatar_id: Optional[str] = Query("AUTO"),
    current_user: User = Depends(get_current_user)
):
    """Dynamically resolves the best-matching presenter avatar for a curriculum topic."""
    return AvatarCatalogService.resolve_avatar(
        exam_type=exam_type,
        subject=subject,
        tier=tier,
        avatar_id=avatar_id
    )

@router.get("/{avatar_id}", response_model=CharacterAvatarRead)
def get_character_avatar(avatar_id: str, current_user: User = Depends(get_current_user)):
    avatar = AvatarCatalogService.get_avatar(avatar_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Character avatar not found")
    return avatar

@router.post("", response_model=CharacterAvatarRead)
def create_custom_character_avatar(
    payload: CreateCustomAvatarRequest,
    current_user: User = Depends(get_current_user)
):
    """Registers a new custom teacher persona with visual prompt specifications."""
    if not payload.name or not payload.prompt:
        raise HTTPException(status_code=400, detail="Avatar name and visual prompt are required.")
    return AvatarCatalogService.create_custom_avatar(payload)
