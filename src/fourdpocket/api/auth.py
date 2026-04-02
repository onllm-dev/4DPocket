"""Authentication endpoints."""

import re
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlmodel import Session, func, select

from fourdpocket.api.auth_utils import create_access_token, hash_password, verify_password
from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.base import UserRole
from fourdpocket.models.instance_settings import InstanceSettings
from fourdpocket.models.user import User, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory rate limiting for failed login attempts
# Note: For production, persist to database
_failed_login_attempts: dict[str, dict] = defaultdict(lambda: {"count": 0, "locked_until": 0.0})
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATIONS = [5, 10, 20, 40, 80]  # Minutes for consecutive failures


def _get_or_create_settings(db: Session) -> InstanceSettings:
    settings = db.get(InstanceSettings, 1)
    if not settings:
        settings = InstanceSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check instance registration settings
    settings = _get_or_create_settings(db)
    if not settings.registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled",
        )

    # Check max users
    if settings.max_users is not None:
        user_count = db.exec(select(func.count()).select_from(User)).one()
        if user_count >= settings.max_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Maximum number of users reached",
            )

    # Check if email already exists
    existing = db.exec(select(User).where(User.email == user_data.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check if username already exists
    existing_username = db.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    # First user becomes admin
    total_users = db.exec(select(func.count()).select_from(User)).one()
    role = UserRole.admin if total_users == 0 else UserRole.user

    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        display_name=user_data.display_name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form_data.username
    now = time.time()

    # Check lockout status
    attempts = _failed_login_attempts[email]
    if attempts["locked_until"] > now:
        remaining = int(attempts["locked_until"] - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Account locked due to too many failed attempts. "
                f"Try again in {remaining} seconds."
            ),
        )

    user = db.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        # Record failed attempt
        attempts["count"] += 1
        if attempts["count"] >= MAX_FAILED_ATTEMPTS:
            lockout_idx = min(attempts["count"] - MAX_FAILED_ATTEMPTS, len(LOCKOUT_DURATIONS) - 1)
            lockout_duration = LOCKOUT_DURATIONS[lockout_idx]
            attempts["locked_until"] = now + (lockout_duration * 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Account locked for {lockout_duration} minutes.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed attempts on success
    attempts["count"] = 0
    attempts["locked_until"] = 0.0

    access_token = create_access_token(user.id)

    # Set httpOnly cookie for XSS protection (supplements Bearer token)
    from fourdpocket.config import get_settings
    cookie_settings = get_settings()
    response.set_cookie(
        key="4dp_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=cookie_settings.auth.token_expire_minutes * 60,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie(key="4dp_token")
    return None


ALLOWED_PROFILE_FIELDS = {"display_name", "avatar_url", "bio"}


@router.patch("/me", response_model=UserRead)
def update_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = {
        k: v
        for k, v in data.model_dump(exclude_unset=True).items()
        if k in ALLOWED_PROFILE_FIELDS
    }
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(data.new_password)
    db.add(current_user)
    db.commit()
