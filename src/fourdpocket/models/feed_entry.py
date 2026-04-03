"""FeedEntry model for feed approval queue."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class FeedEntry(SQLModel, table=True):
    __tablename__ = "feed_entries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    feed_id: uuid.UUID = Field(foreign_key="rss_feeds.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    title: str | None = None
    url: str | None = None
    content_snippet: str | None = None
    status: str = Field(default="pending")  # pending, approved, rejected
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class FeedEntryRead(BaseModel):
    id: uuid.UUID
    feed_id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    url: str | None
    content_snippet: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
