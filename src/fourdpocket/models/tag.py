"""Tag model, ItemTag junction, and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str = Field(index=True)
    slug: str = Field(index=True)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="tags.id")
    ai_generated: bool = Field(default=False)
    color: str | None = None
    description: str | None = None
    usage_count: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ItemTag(SQLModel, table=True):
    __tablename__ = "item_tags"

    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", primary_key=True)
    tag_id: uuid.UUID = Field(foreign_key="tags.id", primary_key=True)
    confidence: float | None = None


class TagCreate(BaseModel):
    name: str
    color: str | None = None
    parent_id: uuid.UUID | None = None

    model_config = {"extra": "forbid"}


class TagRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    ai_generated: bool
    color: str | None
    description: str | None
    usage_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    parent_id: uuid.UUID | None = None
    description: str | None = None
