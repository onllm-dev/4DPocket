"""Authentication endpoints."""

import re
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlmodel import Session, func, select

from fourdpocket.api.auth_utils import create_access_token, hash_password, verify_password
from fourdpocket.api.deps import get_current_user, get_db, get_or_create_settings
from fourdpocket.models.base import UserRole
from fourdpocket.models.user import User, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory rate limiting for failed login attempts.
# NOTE: For production multi-instance deployments, replace with a Redis- or
# database-backed store so limits survive restarts and are shared across nodes.
_MAX_TRACKED_KEYS = 10000
_failed_login_attempts: dict[str, dict] = defaultdict(lambda: {"count": 0, "locked_until": 0.0})

# Constant-time padding: always run a password verification even when the user
# does not exist, preventing timing side-channels that reveal registered emails.
_DUMMY_HASH: str = hash_password("dummy-constant-time-padding-xT9qZ")
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATIONS = [5, 10, 20, 40, 80]  # Minutes for consecutive failures

# In-memory rate limiting for registration attempts (10 per hour per IP)
_register_attempts: dict[str, list[float]] = {}


def _evict_stale_login_entries() -> None:
    """Evict stale entries from rate limit dicts to prevent unbounded memory growth."""
    now = time.time()
    if len(_failed_login_attempts) > _MAX_TRACKED_KEYS:
        stale = [k for k, v in _failed_login_attempts.items()
                 if v["count"] == 0 and v["locked_until"] < now]
        for k in stale:
            del _failed_login_attempts[k]
    if len(_register_attempts) > _MAX_TRACKED_KEYS:
        stale = [k for k, v in _register_attempts.items()
                 if all(now - t > 3600 for t in v)]
        for k in stale:
            del _register_attempts[k]


def _check_register_rate_limit(client_ip: str) -> None:
    _evict_stale_login_entries()
    now = time.time()
    attempts = [t for t in _register_attempts.get(client_ip, []) if now - t < 3600]
    if len(attempts) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Try again later.",
        )
    attempts.append(now)
    _register_attempts[client_ip] = attempts


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Check instance registration settings BEFORE rate limiting to prevent
    # attackers from exhausting the rate limit when registration is disabled.
    settings = get_or_create_settings(db)
    if not settings.registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled",
        )

    _check_register_rate_limit(request.client.host if request.client else "unknown")

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
    identifier = form_data.username  # Can be email or username
    now = time.time()

    # Resolve user by email or username
    user = db.exec(
        select(User).where((User.email == identifier) | (User.username == identifier))
    ).first()

    # Use canonical email as rate-limit key (prevents bypass via alternating identifiers)
    rate_key = user.email if user else identifier

    # Check lockout status
    attempts = _failed_login_attempts[rate_key]
    if attempts["locked_until"] > now:
        remaining = int(attempts["locked_until"] - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Account locked due to too many failed attempts. "
                f"Try again in {remaining} seconds."
            ),
        )

    if not user:
        # Always verify against a dummy hash to prevent timing attacks that
        # reveal whether an email/username is registered.
        verify_password(form_data.password, _DUMMY_HASH)

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

    # Reset failed attempts on success (using canonical key)
    _failed_login_attempts[rate_key] = {"count": 0, "locked_until": 0.0}

    access_token = create_access_token(user.id)

    # Set httpOnly cookie for XSS protection (supplements Bearer token)
    from fourdpocket.config import get_settings
    cookie_settings = get_settings()
    is_secure = cookie_settings.server.secure_cookies
    response.set_cookie(
        key="4dp_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
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
