"""UserQuota model — per-user resource limits."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class UserQuota(SQLModel, table=True):
    __tablename__ = "user_quotas"

    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        primary_key=True,
    )
    items_max: int | None = None  # null = unlimited
    storage_bytes_max: int | None = None
    daily_api_calls_max: int | None = None
    daily_api_calls_used: int = Field(default=0)
    daily_window_start: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    # Denormalized counters — trusted on writes, recomputable by admin
    items_used: int = Field(default=0)
    storage_bytes_used: int = Field(default=0)
