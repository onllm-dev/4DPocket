"""KnowledgeItem model and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import ItemType, ReadingStatus, SourcePlatform, utc_now

try:
    from sqlalchemy import JSON, DateTime, Text
except ImportError:
    from sqlmodel import JSON, DateTime, Text


class KnowledgeItem(SQLModel, table=True):
    __tablename__ = "knowledge_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    item_type: ItemType = Field(default=ItemType.url)
    source_platform: SourcePlatform = Field(default=SourcePlatform.generic)
    url: str | None = None
    title: str | None = None
    description: str | None = None
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    raw_content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    summary: str | None = None
    screenshot_path: str | None = None
    favicon_url: str | None = None
    archive_path: str | None = None
    media: list = Field(default_factory=list, sa_column=Column(JSON))
    item_metadata: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    is_favorite: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    reading_progress: int = Field(default=0)
    reading_status: ReadingStatus = Field(default=ReadingStatus.unread)
    read_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ItemCreate(BaseModel):
    url: str | None = None
    title: str | None = None
    description: str | None = None
    content: str | None = None
    item_type: ItemType = ItemType.url
    source_platform: SourcePlatform = SourcePlatform.generic


class ItemRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    item_type: ItemType
    source_platform: SourcePlatform
    url: str | None
    title: str | None
    description: str | None
    content: str | None
    raw_content: str | None
    summary: str | None
    screenshot_path: str | None
    favicon_url: str | None
    archive_path: str | None
    media: list
    item_metadata: dict
    is_favorite: bool
    is_archived: bool
    reading_progress: int
    reading_status: ReadingStatus
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    content: str | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None
    reading_progress: int | None = None
    reading_status: ReadingStatus | None = None
