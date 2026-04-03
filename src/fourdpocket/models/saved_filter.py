"""Saved search filter model."""

import uuid
from datetime import datetime

from sqlmodel import JSON, Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class SavedFilter(SQLModel, table=True):
    __tablename__ = "saved_filters"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str
    query: str  # Search query text
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))  # {source_platform, item_type, tags, etc.}
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
