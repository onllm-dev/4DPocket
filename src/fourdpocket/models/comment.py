"""Comment model."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import Text
except ImportError:
    from sqlmodel import Text


class Comment(SQLModel, table=True):
    __tablename__ = "comments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", index=True)
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)
