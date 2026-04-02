"""Automation rule model."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlmodel import JSON


class Rule(SQLModel, table=True):
    __tablename__ = "rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str
    condition: dict = Field(default_factory=dict, sa_column=Column(JSON, default="{}"))
    action: dict = Field(default_factory=dict, sa_column=Column(JSON, default="{}"))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
