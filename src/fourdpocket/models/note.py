"""Note model and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import Text
except ImportError:
    from sqlmodel import Text


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    item_id: uuid.UUID | None = Field(default=None, foreign_key="knowledge_items.id", index=True)
    title: str | None = None
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NoteCreate(BaseModel):
    title: str | None = None
    content: str
    item_id: uuid.UUID | None = None


class NoteRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    item_id: uuid.UUID | None
    title: str | None
    content: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
