"""CollectionNote junction table for collection-note associations."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class CollectionNote(SQLModel, table=True):
    __tablename__ = "collection_notes"

    collection_id: uuid.UUID = Field(foreign_key="collections.id", primary_key=True)
    note_id: uuid.UUID = Field(foreign_key="notes.id", primary_key=True)
    position: int = Field(default=0)
    added_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
