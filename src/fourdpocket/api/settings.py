"""User settings endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


class UserSettingsSchema(BaseModel):
    auto_tag: bool = True
    auto_summarize: bool = True
    tag_confidence_threshold: float = 0.7
    media_download: bool = True
    default_share_mode: str = "private"
    theme: str = "system"
    view_mode: str = "grid"


@router.get("", response_model=UserSettingsSchema)
def get_user_settings(
    current_user: User = Depends(get_current_user),
):
    defaults = UserSettingsSchema()
    stored = current_user.settings or {}
    merged = {**defaults.model_dump(), **stored}
    return UserSettingsSchema(**merged)


@router.patch("", response_model=UserSettingsSchema)
def update_user_settings(
    data: UserSettingsSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_settings = current_user.settings or {}
    updated = {**current_settings, **data.model_dump(exclude_unset=True)}
    current_user.settings = updated
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserSettingsSchema(**updated)
