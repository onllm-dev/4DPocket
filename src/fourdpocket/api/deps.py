"""FastAPI dependency injection."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from fourdpocket.api.auth_utils import decode_access_token, hash_password, create_access_token
from fourdpocket.config import get_settings
from fourdpocket.db.session import get_session
from fourdpocket.models.user import User
from fourdpocket.models.base import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_db():
    yield from get_session()


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()

    # Single-user mode: auto-create admin if no users exist
    if settings.auth.mode == "single":
        user = db.exec(select(User).where(User.role == UserRole.admin)).first()
        if user is None:
            user = User(
                email="admin@localhost",
                password_hash=hash_password("admin"),
                display_name="Admin",
                role=UserRole.admin,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
