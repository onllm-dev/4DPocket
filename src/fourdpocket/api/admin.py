"""Admin management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select, func

from fourdpocket.api.deps import get_db, require_admin
from fourdpocket.models.user import User, UserRead
from fourdpocket.models.base import UserRole
from fourdpocket.models.instance_settings import InstanceSettings

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


def _get_or_create_settings(db: Session) -> InstanceSettings:
    settings = db.get(InstanceSettings, 1)
    if not settings:
        settings = InstanceSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/settings", response_model=InstanceSettingsRead)
def get_instance_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return _get_or_create_settings(db)


@router.patch("/settings", response_model=InstanceSettingsRead)
def update_instance_settings(
    data: InstanceSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    settings = _get_or_create_settings(db)
    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
