"""FastAPI dependency injection."""

import logging
import secrets
import uuid

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from fourdpocket.api.auth_utils import decode_access_token, hash_password
from fourdpocket.config import get_settings
from fourdpocket.db.session import get_session
from fourdpocket.models.base import UserRole
from fourdpocket.models.user import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _get_token_from_request(
    token: str | None = Depends(oauth2_scheme),
    cookie_token: str | None = Cookie(default=None, alias="4dp_token"),
) -> str | None:
    """Support token from either Bearer header or httpOnly cookie."""
    return token or cookie_token


def get_db():
    yield from get_session()


def get_current_user(
    token: str | None = Depends(_get_token_from_request),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()

    # Single-user mode: auto-create admin if no users exist
    if settings.auth.mode == "single":
        user = db.exec(select(User).where(User.role == UserRole.admin)).first()
        if user is None:
            _password = secrets.token_urlsafe(32)
            _email = f"admin-{secrets.token_hex(4)}@localhost"
            user = User(
                email=_email,
                username="admin",
                password_hash=hash_password(_password),
                display_name="Admin",
                role=UserRole.admin,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(
                "Single-user admin auto-created (email=%s). Auth is bypassed in single-user mode.",
                _email,
            )
        if token is None:
            return user

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Reject tokens issued before password change
    if user.password_changed_at:
        iat = payload.get("iat")
        if iat and isinstance(iat, (int, float)):
            from datetime import datetime, timezone
            token_issued = datetime.fromtimestamp(iat, tz=timezone.utc)
            pwd_changed = user.password_changed_at
            if pwd_changed.tzinfo is None:
                pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
            if token_issued < pwd_changed:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalidated by password change")

    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_or_create_settings(db: Session):  # -> InstanceSettings (lazy import)
    from fourdpocket.models.instance_settings import InstanceSettings

    settings = db.get(InstanceSettings, 1)
    if not settings:
        settings = InstanceSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
