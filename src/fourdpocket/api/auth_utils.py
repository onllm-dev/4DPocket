"""Authentication utilities - password hashing and JWT tokens."""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from fourdpocket.config import get_settings


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.auth.token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "iss": "4dpocket",
    }
    return jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.auth.secret_key, algorithms=[settings.auth.algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
