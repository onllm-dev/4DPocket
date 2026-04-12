"""ItemChunk model — stores content chunks for paragraph-level retrieval."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel, UniqueConstraint

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime, Text
except ImportError:
    from sqlmodel import DateTime, Text


class ItemChunk(SQLModel, table=True):
    __tablename__ = "item_chunks"
    __table_args__ = (UniqueConstraint("item_id", "chunk_order", name="uq_chunk_item_order"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    chunk_order: int = Field(default=0)
    text: str = Field(sa_column=Column(Text, nullable=False))
    token_count: int = Field(default=0)
    char_start: int = Field(default=0)
    char_end: int = Field(default=0)
    content_hash: str = Field(default="")
    embedding_model: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
