"""RSS feed subscription model."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class RSSFeed(SQLModel, table=True):
    __tablename__ = "rss_feeds"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    url: str  # Feed URL
    title: str | None = None
    category: str | None = None  # Maps to a tag
    target_collection_id: uuid.UUID | None = Field(default=None, foreign_key="collections.id")
    poll_interval: int = Field(default=3600)  # seconds: 900, 3600, 21600, 86400
    is_active: bool = Field(default=True)
    last_fetched_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    format: str = Field(default="rss")  # rss, atom, json_feed
    mode: str = Field(default="auto")  # auto (add to collection), approval (hold for review)
    filters: str | None = None  # JSON string of keyword/tag filter rules
    last_entry_id: str | None = None  # To avoid re-fetching
    last_error: str | None = None  # Last fetch error message
    error_count: int = Field(default=0)  # Consecutive error count
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
