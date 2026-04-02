"""Embedding model for vector storage metadata."""

import uuid

from sqlmodel import Column, Field, SQLModel

try:
    from sqlalchemy import LargeBinary, Text
except ImportError:
    from sqlmodel import LargeBinary, Text


class Embedding(SQLModel, table=True):
    __tablename__ = "embeddings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", index=True)
    item_type: str = Field(default="knowledge_item")
    vector: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))
    model: str = Field(default="all-MiniLM-L6-v2")
    content_hash: str | None = None
