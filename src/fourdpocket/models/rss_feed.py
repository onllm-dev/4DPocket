"""RSS feed subscription model."""

import uuid
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class RSSFeed(SQLModel, table=True):
    __tablename__ = "rss_feeds"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    url: str  # Feed URL
    title: str | None = None
    category: str | None = None  # Maps to a tag
    target_collection_id: str | None = Field(default=None, foreign_key="collections.id")
    poll_interval: int = Field(default=3600)  # seconds: 900, 3600, 21600, 86400
    is_active: bool = Field(default=True)
    last_fetched_at: datetime | None = None
    last_entry_id: str | None = None  # To avoid re-fetching
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
