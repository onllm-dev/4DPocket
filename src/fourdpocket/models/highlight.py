"""Highlight and annotation models."""

import uuid
from datetime import datetime

from sqlmodel import JSON, Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class Highlight(SQLModel, table=True):
    __tablename__ = "highlights"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", index=True)
    text: str  # The highlighted text
    note: str | None = None  # Annotation note
    color: str = Field(default="yellow")  # yellow, green, blue, red, purple
    position: dict | None = Field(default=None, sa_column=Column(JSON))  # Page position info
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
