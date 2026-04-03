"""Saved search filter model."""

import uuid
from datetime import datetime, timezone

from sqlmodel import JSON, Column, Field, SQLModel


class SavedFilter(SQLModel, table=True):
    __tablename__ = "saved_filters"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    name: str
    query: str  # Search query text
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))  # {source_platform, item_type, tags, etc.}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
