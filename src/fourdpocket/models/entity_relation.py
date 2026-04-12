"""Entity relation models for the concept graph."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel, UniqueConstraint

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class EntityRelation(SQLModel, table=True):
    __tablename__ = "entity_relations"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_relation_source_target"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)
    source_id: uuid.UUID = Field(foreign_key="entities.id", index=True)
    target_id: uuid.UUID = Field(foreign_key="entities.id", index=True)
    keywords: str | None = Field(default=None)
    description: str | None = Field(default=None)
    weight: float = Field(default=1.0)
    item_count: int = Field(default=1)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class RelationEvidence(SQLModel, table=True):
    __tablename__ = "relation_evidence"

    relation_id: uuid.UUID = Field(foreign_key="entity_relations.id", primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", primary_key=True)
    chunk_id: uuid.UUID | None = Field(default=None, foreign_key="item_chunks.id")
