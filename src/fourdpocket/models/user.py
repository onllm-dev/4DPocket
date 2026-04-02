"""User model and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import UserRole, utc_now

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlmodel import JSON


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
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON, default="{}"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    display_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
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
