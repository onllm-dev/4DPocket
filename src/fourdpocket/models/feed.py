"""KnowledgeFeed model."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlmodel import JSON


class KnowledgeFeed(SQLModel, table=True):
    __tablename__ = "knowledge_feeds"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subscriber_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    publisher_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    filter_config: dict = Field(default_factory=dict, sa_column=Column("filter", JSON, default="{}"))
    created_at: datetime = Field(default_factory=utc_now)
