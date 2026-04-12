"""FastAPI dependency injection."""

import logging
import secrets
import uuid

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from fourdpocket.api.auth_utils import decode_access_token, hash_password
from fourdpocket.config import get_settings
from fourdpocket.db.session import get_session
from fourdpocket.models.api_token import ApiToken
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


def _resolve_pat(db: Session, token: str) -> tuple[User, ApiToken] | None:
    """Attempt to resolve an ``fdp_pat_*`` token. Returns (user, pat) or None."""
    from fourdpocket.api.api_token_utils import looks_like_pat, resolve_token, touch_last_used

    if not looks_like_pat(token):
        return None

    pat = resolve_token(db, token)
    if pat is None:
        return None

    user = db.get(User, pat.user_id)
    if user is None or user.is_active is False:
        return None

    touch_last_used(db, pat)
    return user, pat


def _resolve_identity(
    request: Request,
    token: str | None,
    db: Session,
) -> tuple[User, ApiToken | None]:
    """Resolve an authenticated identity from either a PAT or a JWT.

    Returns ``(User, ApiToken | None)``. The PAT is cached on ``request.state``
    so PAT-aware dependencies can retrieve it without re-resolving.
    """
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
            return user, None

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Personal Access Token path — takes precedence when the prefix matches.
    pat_result = _resolve_pat(db, token)
    if pat_result is not None:
        user, pat = pat_result
        if user.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
            )
        request.state.pat = pat
        return user, pat

    # If the caller passed an ``fdp_pat_`` prefix but resolution failed, reject
    # outright — falling through to JWT would produce a confusing error.
    from fourdpocket.api.api_token_utils import looks_like_pat

    if looks_like_pat(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT path
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
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalidated by password change",
                )

    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    request.state.pat = None
    return user, None


def get_current_user(
    request: Request,
    token: str | None = Depends(_get_token_from_request),
    db: Session = Depends(get_db),
) -> User:
    user, _ = _resolve_identity(request, token, db)
    return user


def get_current_user_pat_aware(
    request: Request,
    token: str | None = Depends(_get_token_from_request),
    db: Session = Depends(get_db),
) -> tuple[User, ApiToken | None]:
    """Like ``get_current_user`` but returns the PAT too (``None`` for JWT auth)."""
    return _resolve_identity(request, token, db)


def get_current_pat(request: Request) -> ApiToken | None:
    """Return the PAT attached to the current request, if any.

    Relies on ``get_current_user`` (or a pat-aware variant) having run earlier
    in the dependency chain to populate ``request.state.pat``.
    """
    return getattr(request.state, "pat", None)


def require_pat_editor(pat: ApiToken | None = Depends(get_current_pat)) -> None:
    """Reject requests made with a viewer-role PAT."""
    from fourdpocket.api.api_token_utils import require_editor

    if pat is not None:
        require_editor(pat)


def require_pat_deletion(pat: ApiToken | None = Depends(get_current_pat)) -> None:
    """Reject requests made with a PAT that lacks ``allow_deletion``."""
    from fourdpocket.api.api_token_utils import require_deletion

    if pat is not None:
        require_deletion(pat)


def require_admin(
    current_user: User = Depends(get_current_user),
    pat: ApiToken | None = Depends(get_current_pat),
) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    # A PAT can only reach admin endpoints when admin_scope was explicitly opted in.
    if pat is not None and not pat.admin_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin operations require a token with admin_scope.",
        )
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
