"""Collection model, CollectionItem junction, and schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import ShareMode, utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class Collection(SQLModel, table=True):
    __tablename__ = "collections"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str
    description: str | None = None
    icon: str | None = None
    is_public: bool = Field(default=False)
    is_smart: bool = Field(default=False)
    smart_query: str | None = None
    share_mode: ShareMode = Field(default=ShareMode.private)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class CollectionItem(SQLModel, table=True):
    __tablename__ = "collection_items"

    collection_id: uuid.UUID = Field(foreign_key="collections.id", primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", primary_key=True)
    position: int = Field(default=0)
    added_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None
    icon: str | None = None

    model_config = {"extra": "forbid"}


class CollectionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    icon: str | None
    is_public: bool
    is_smart: bool
    share_mode: ShareMode
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    is_public: bool | None = None
