"""NoteTag junction table for note-tag associations."""

import uuid

from sqlmodel import Field, SQLModel


class NoteTag(SQLModel, table=True):
    __tablename__ = "note_tags"

    note_id: uuid.UUID = Field(foreign_key="notes.id", primary_key=True)
    tag_id: uuid.UUID = Field(foreign_key="tags.id", primary_key=True)
    confidence: float | None = None
