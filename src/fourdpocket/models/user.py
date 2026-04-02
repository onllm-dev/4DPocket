"""User model and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr
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
    password_hash: str
    display_name: str | None = None
    avatar_url: str | None = None
    role: UserRole = Field(default=UserRole.user)
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON, default="{}"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserCreate(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
