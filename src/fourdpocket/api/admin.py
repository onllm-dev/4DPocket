"""Admin management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_db, get_or_create_settings, require_admin
from fourdpocket.models.base import UserRole
from fourdpocket.models.user import User, UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    users = db.exec(select(User).offset(offset).limit(limit)).all()
    return users


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    display_name: str | None = None


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and data.role and data.role != UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(user)
    db.commit()


# ─── AI Settings (admin-controlled) ─────────────────────────────

AI_CONFIG_KEYS = {
    "chat_provider", "ollama_url", "ollama_model",
    "groq_api_key", "nvidia_api_key",
    "custom_base_url", "custom_api_key", "custom_model", "custom_api_type",
    "embedding_provider", "embedding_model",
    "auto_tag", "auto_summarize",
    "tag_confidence_threshold", "tag_suggestion_threshold",
    "sync_enrichment",
}


def _mask_key(value: str) -> str:
    """Mask API keys for display: show first 4 and last 4 chars."""
    if not value or len(value) < 12:
        return "***" if value else ""
    return f"{value[:4]}...{value[-4:]}"


@router.get("/ai-settings")
def get_ai_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Get resolved AI configuration (env defaults + admin overrides)."""
    from fourdpocket.ai.factory import get_resolved_ai_config

    config = get_resolved_ai_config()
    # Mask sensitive keys in response
    masked = {**config}
    for key in ("groq_api_key", "nvidia_api_key", "custom_api_key"):
        if key in masked and masked[key]:
            masked[key] = _mask_key(masked[key])
    return masked


class AISettingsUpdate(BaseModel):
    chat_provider: str | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    groq_api_key: str | None = None
    nvidia_api_key: str | None = None
    custom_base_url: str | None = None
    custom_api_key: str | None = None
    custom_model: str | None = None
    custom_api_type: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    auto_tag: bool | None = None
    auto_summarize: bool | None = None
    tag_confidence_threshold: float | None = None
    tag_suggestion_threshold: float | None = None
    sync_enrichment: bool | None = None


@router.patch("/ai-settings")
def update_ai_settings(
    data: AISettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update AI settings (stored in InstanceSettings.extra['ai_config']).

    Admin panel settings take precedence over .env values.
    """
    settings = get_or_create_settings(db)
    extra = dict(settings.extra) if settings.extra else {}
    ai_config = extra.get("ai_config", {})

    update_dict = data.model_dump(exclude_unset=True)
    # Only accept known AI config keys
    for key, value in update_dict.items():
        if key in AI_CONFIG_KEYS:
            # Don't overwrite key with masked value
            if key.endswith("_key") and value and "..." in value:
                continue
            ai_config[key] = value

    extra["ai_config"] = ai_config
    settings.extra = extra
    db.add(settings)
    db.commit()
    db.refresh(settings)

    # Return resolved config with masked keys
    from fourdpocket.ai.factory import get_resolved_ai_config

    config = get_resolved_ai_config()
    masked = {**config}
    for key in ("groq_api_key", "nvidia_api_key", "custom_api_key"):
        if key in masked and masked[key]:
            masked[key] = _mask_key(masked[key])
    return masked


# ─── Instance Settings ──────────────────────────────────────────

class InstanceSettingsRead(BaseModel):
    instance_name: str
    registration_enabled: bool
    registration_mode: str
    default_user_role: str
    max_users: int | None
    model_config = {"from_attributes": True}


class InstanceSettingsUpdate(BaseModel):
    instance_name: str | None = None
    registration_enabled: bool | None = None
    registration_mode: str | None = None
    default_user_role: str | None = None
    max_users: int | None = None


@router.get("/settings", response_model=InstanceSettingsRead)
def get_instance_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return get_or_create_settings(db)


@router.patch("/settings", response_model=InstanceSettingsRead)
def update_instance_settings(
    data: InstanceSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    settings = get_or_create_settings(db)
    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
