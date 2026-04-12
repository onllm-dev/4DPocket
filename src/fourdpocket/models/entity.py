"""Entity models for knowledge graph — Entity, EntityAlias, ItemEntity."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel, UniqueConstraint

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import JSON, DateTime, Text
except ImportError:
    from sqlmodel import JSON, DateTime, Text


class Entity(SQLModel, table=True):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "canonical_name", name="uq_entity_user_type_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    canonical_name: str = Field(index=True)
    entity_type: str = Field(index=True)  # person|org|concept|tool|product|event|location|other
    description: str | None = Field(default=None)
    item_count: int = Field(default=0)
    # LLM-authored structured synthesis of the entity across all mentions.
    # Stored as JSON text (portable across SQLite + Postgres via JSON column).
    synthesis: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    synthesis_generated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    synthesis_item_count: int = Field(default=0)
    synthesis_confidence: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class EntityAlias(SQLModel, table=True):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "alias", name="uq_alias_entity_alias"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    entity_id: uuid.UUID = Field(foreign_key="entities.id", index=True)
    alias: str = Field(index=True)
    source: str = Field(default="extraction")  # extraction|user|merge


class ItemEntity(SQLModel, table=True):
    __tablename__ = "item_entities"

    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", primary_key=True)
    entity_id: uuid.UUID = Field(foreign_key="entities.id", primary_key=True, index=True)
    chunk_id: uuid.UUID | None = Field(default=None, foreign_key="item_chunks.id")
    salience: float = Field(default=0.5)
    context: str | None = Field(default=None)
