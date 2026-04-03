"""Saved search filter model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import JSON, Column, Field, SQLModel


class SavedFilter(SQLModel, table=True):
    __tablename__ = "saved_filters"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str
    query: str  # Search query text
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))  # {source_platform, item_type, tags, etc.}
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
