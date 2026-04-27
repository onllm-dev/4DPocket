"""User model and schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import UserRole, utc_now

try:
    from sqlalchemy import JSON, DateTime
except ImportError:
    from sqlmodel import JSON, DateTime


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(index=True, unique=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    is_active: bool = Field(default=True)
    role: UserRole = Field(default=UserRole.user)
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    password_changed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    email_verified: bool = Field(default=False)
    email_verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: str | None = None

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        if "@" in v:
            raise ValueError("Username cannot contain '@' - use email field for email addresses")
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters")
        if len(v) > 30:
            raise ValueError("Username must be at most 30 characters")
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores, dots, and hyphens")
        return v

    @field_validator("password")
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


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    display_name: str | None
    avatar_url: str | None
    bio: str | None
    is_active: bool
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    username: str | None = None
    email: EmailStr | None = None

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if "@" in v:
            raise ValueError("Username cannot contain '@'")
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters")
        if len(v) > 30:
            raise ValueError("Username must be at most 30 characters")
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscores, dots, and hyphens")
        return v
