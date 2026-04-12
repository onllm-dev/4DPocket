"""EnrichmentStage model — tracks per-stage enrichment status for items."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class EnrichmentStage(SQLModel, table=True):
    __tablename__ = "enrichment_stages"

    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", primary_key=True)
    stage: str = Field(primary_key=True)
    status: str = Field(default="pending")
    attempts: int = Field(default=0)
    last_error: str | None = Field(default=None)
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
