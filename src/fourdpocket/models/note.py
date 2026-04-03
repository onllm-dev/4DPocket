"""Note model and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import ReadingStatus, utc_now

try:
    from sqlalchemy import DateTime, Text
except ImportError:
    from sqlmodel import DateTime, Text


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    item_id: uuid.UUID | None = Field(default=None, foreign_key="knowledge_items.id", index=True)
    title: str | None = None
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    summary: str | None = None
    is_favorite: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    reading_status: ReadingStatus = Field(default=ReadingStatus.unread)
    reading_progress: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class NoteCreate(BaseModel):
    title: str | None = None
    content: str
    item_id: uuid.UUID | None = None
    tags: list[str] | None = None


class NoteRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    item_id: uuid.UUID | None
    title: str | None
    content: str | None
    summary: str | None
    is_favorite: bool
    is_archived: bool
    reading_status: ReadingStatus
    reading_progress: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None
    reading_status: ReadingStatus | None = None
    reading_progress: int | None = None
    tags: list[str] | None = None
