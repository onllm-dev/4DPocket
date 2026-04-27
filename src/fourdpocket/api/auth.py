"""Authentication endpoints."""

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy import delete as sql_delete
from sqlalchemy import text
from sqlmodel import Session, func, select

from fourdpocket.api.auth_utils import create_access_token, hash_password, verify_password
from fourdpocket.api.deps import (
    get_current_user,
    get_db,
    get_or_create_settings,
    require_jwt_session,
)
from fourdpocket.api.rate_limit import check_rate_limit, record_attempt, reset_rate_limit
from fourdpocket.auth.email import send_email
from fourdpocket.auth.tokens import generate_token, hash_token, is_expired
from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.base import UserRole
from fourdpocket.models.email_verification import EmailVerificationToken
from fourdpocket.models.password_reset import PasswordResetToken
from fourdpocket.models.user import User, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/auth", tags=["Auth"])

# Constant-time padding: always run a password verification even when the user
# does not exist, preventing timing side-channels that reveal registered emails.
_DUMMY_HASH: str = hash_password("dummy-constant-time-padding-xT9qZ")
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATIONS = [5, 10, 20, 40, 80]  # Minutes for consecutive failures

_RESET_TOKEN_TTL_MINUTES = 15
_VERIFY_TOKEN_TTL_HOURS = 24


def _send_password_reset_email(user: User, raw_token: str) -> None:
    from fourdpocket.config import get_settings
    public_url = get_settings().server.public_url.rstrip("/")
    link = f"{public_url}/reset-password?token={raw_token}"
    send_email(
        to=user.email,
        subject="Reset your 4dpocket password",
        body_text=f"Click the link below to reset your password (expires in {_RESET_TOKEN_TTL_MINUTES} minutes):\n\n{link}\n\nIf you did not request a reset, ignore this email.",
    )


def _send_verification_email(user: User, raw_token: str) -> None:
    from fourdpocket.config import get_settings
    public_url = get_settings().server.public_url.rstrip("/")
    link = f"{public_url}/api/v1/auth/email/verify?token={raw_token}"
    send_email(
        to=user.email,
        subject="Verify your 4dpocket email address",
        body_text=f"Click the link below to verify your email address:\n\n{link}\n\nThis link expires in {_VERIFY_TOKEN_TTL_HOURS} hours.",
    )


def _create_verification_token(db: Session, user_id) -> str:
    """Invalidate old tokens, create a new one, persist hash. Returns raw token."""
    # Delete any prior unused tokens for this user
    db.exec(
        sql_delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at == None,  # noqa: E711
        )
    )
    raw, token_hash = generate_token()
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_VERIFY_TOKEN_TTL_HOURS),
    )
    db.add(token)
    db.flush()
    return raw


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

    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(db, key=client_ip, action="register", max_attempts=10, window_seconds=3600, lockout_minutes=60)
    record_attempt(db, key=client_ip, action="register")

    # Check max users
    if settings.max_users is not None:
        user_count = db.exec(select(func.count()).select_from(User)).one()
        if user_count >= settings.max_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Maximum number of users reached",
            )

    # Check if email or username already exists (generic message prevents enumeration)
    existing = db.exec(select(User).where(User.email == user_data.email)).first()
    existing_username = db.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    if existing or existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists",
        )

    # First user becomes admin. Use an atomic conditional UPDATE on the
    # instance_settings singleton to claim the slot — race-free on both
    # SQLite (writes are serialized) and PostgreSQL (row-level lock on the
    # UPDATE). Exactly one concurrent registration can flip the flag from
    # False → True; every other caller gets rowcount=0 and becomes a regular
    # user. We rely on rowcount, not a separate read, so there is no TOCTOU.
    # Commit the claim immediately so the write lock is released before we do
    # further work — prevents SQLITE_BUSY for concurrent registrations that
    # would otherwise queue behind the User insert below.
    result = db.execute(
        text(
            "UPDATE instance_settings SET admin_bootstrapped = :t "
            "WHERE id = 1 AND admin_bootstrapped = :f"
        ),
        {"t": True, "f": False},
    )
    role = UserRole.admin if result.rowcount == 1 else UserRole.user
    db.commit()

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

    # Send verification email (best-effort — never block registration on failure)
    try:
        raw = _create_verification_token(db, user.id)
        db.commit()
        _send_verification_email(user, raw)
    except Exception:
        pass

    return user


@router.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    identifier = form_data.username  # Can be email or username

    # Resolve user by email or username
    user = db.exec(
        select(User).where((User.email == identifier) | (User.username == identifier))
    ).first()

    # Use canonical email as rate-limit key (prevents bypass via alternating identifiers)
    rate_key = user.email if user else identifier

    # Check lockout status (DB-backed, shared across workers)
    check_rate_limit(
        db, key=rate_key, action="login",
        max_attempts=MAX_FAILED_ATTEMPTS, window_seconds=3600,
        escalating_lockout=LOCKOUT_DURATIONS,
    )

    if not user:
        # Always verify against a dummy hash to prevent timing attacks that
        # reveal whether an email/username is registered.
        verify_password(form_data.password, _DUMMY_HASH)

    if not user or not verify_password(form_data.password, user.password_hash):
        # Record failed attempt in DB
        record_attempt(db, key=rate_key, action="login")
        db.commit()

        # Re-check if we just hit the limit
        try:
            check_rate_limit(
                db, key=rate_key, action="login",
                max_attempts=MAX_FAILED_ATTEMPTS, window_seconds=3600,
                escalating_lockout=LOCKOUT_DURATIONS,
            )
        except HTTPException:
            raise
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed attempts on success (using canonical key)
    reset_rate_limit(db, key=rate_key, action="login")

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


ALLOWED_PROFILE_FIELDS = {"display_name", "avatar_url", "bio", "username", "email"}


@router.patch("/me", response_model=UserRead)
def update_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_jwt_session),
):
    update_data = {
        k: v
        for k, v in data.model_dump(exclude_unset=True).items()
        if k in ALLOWED_PROFILE_FIELDS
    }
    # Enforce uniqueness for identity-critical fields.
    new_username = update_data.get("username")
    if new_username and new_username != current_user.username:
        clash = db.exec(
            select(User).where(User.username == new_username, User.id != current_user.id)
        ).first()
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
    new_email = update_data.get("email")
    if new_email and new_email != current_user.email:
        clash = db.exec(
            select(User).where(User.email == new_email, User.id != current_user.id)
        ).first()
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already taken",
            )
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


class DeleteMeRequest(BaseModel):
    current_password: str


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    data: DeleteMeRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_jwt_session),
):
    """Self-service account deletion. Requires current password for confirmation.
    Cascades through owned items, tokens, etc. Clears the auth cookie."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password is incorrect",
        )
    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    response.delete_cookie(key="4dp_token")
    try:
        from fourdpocket.storage.local import LocalStorage
        LocalStorage().delete_user_dir(user_id)
    except Exception:
        pass
    return None


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
    _: None = Depends(require_jwt_session),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(data.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    db.add(current_user)
    # Invalidate all existing PATs so stolen tokens cannot be reused after a
    # password change (session invalidation on credential rotation).
    db.exec(sql_delete(ApiToken).where(ApiToken.user_id == current_user.id))
    db.commit()


# ── Password reset ────────────────────────────────────────────────────────────

class PasswordResetRequest(BaseModel):
    email_or_username: str


class PasswordResetConfirm(BaseModel):
    token: str
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


@router.post("/password-reset/request")
def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request a password reset link. Always returns 200 to avoid leaking whether an account exists."""
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(db, key=client_ip, action="password_reset", max_attempts=3, window_seconds=3600, lockout_minutes=60)
    record_attempt(db, key=client_ip, action="password_reset")
    db.commit()

    identifier = data.email_or_username
    user = db.exec(
        select(User).where((User.email == identifier) | (User.username == identifier))
    ).first()

    if user:
        raw, token_hash = generate_token()
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=_RESET_TOKEN_TTL_MINUTES),
        )
        db.add(token)
        db.commit()
        _send_password_reset_email(user, raw)

    return {"sent": True}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Consume a password-reset token and update the user's password."""
    token_hash = hash_token(data.token)
    record = db.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()

    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unknown reset token")
    if record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has already been used")
    if is_expired(record):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    # Update password and bump password_changed_at so existing JWTs are invalidated
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    record.used_at = datetime.now(timezone.utc)
    db.add(user)
    db.add(record)
    # Invalidate PATs as well (credential rotation)
    db.exec(sql_delete(ApiToken).where(ApiToken.user_id == user.id))
    db.commit()
    return None


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/email/resend", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification_email(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a new verification token and (re-)send the verification email."""
    # Rate-limit per user (not per IP) to prevent spam via account takeover
    check_rate_limit(db, key=str(current_user.id), action="email_resend", max_attempts=2, window_seconds=60, lockout_minutes=5)
    record_attempt(db, key=str(current_user.id), action="email_resend")

    if current_user.email_verified:
        return None  # Already verified — silently succeed

    raw = _create_verification_token(db, current_user.id)
    db.commit()
    _send_verification_email(current_user, raw)
    return None


@router.get("/email/verify")
def verify_email(token: str, request: Request, db: Session = Depends(get_db)):
    """Verify an email address using the token from the verification email."""
    token_hash = hash_token(token)
    record = db.exec(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    ).first()

    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unknown verification token")
    if record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token has already been used")
    if is_expired(record):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token has expired")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    record.used_at = datetime.now(timezone.utc)
    db.add(user)
    db.add(record)
    db.commit()

    # Respond with JSON or redirect based on Accept header
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        from fourdpocket.config import get_settings
        public_url = get_settings().server.public_url.rstrip("/")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{public_url}/verified", status_code=302)

    return {"verified": True}
