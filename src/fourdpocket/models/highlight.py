"""Highlight and annotation models."""

import uuid
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Column, JSON


class Highlight(SQLModel, table=True):
    __tablename__ = "highlights"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    item_id: str = Field(foreign_key="knowledge_items.id", index=True)
    text: str  # The highlighted text
    note: str | None = None  # Annotation note
    color: str = Field(default="yellow")  # yellow, green, blue, red, purple
    position: dict | None = Field(default=None, sa_column=Column(JSON))  # Page position info
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
