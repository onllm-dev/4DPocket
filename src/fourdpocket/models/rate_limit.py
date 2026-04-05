"""Database-backed rate limiting model — works with SQLite and PostgreSQL."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class RateLimitEntry(SQLModel, table=True):
    __tablename__ = "rate_limits"
    __table_args__ = (
        UniqueConstraint("key", "action", name="uq_rate_limit_key_action"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(index=True)          # e.g. "login:192.168.1.1" or "register:10.0.0.1"
    action: str = Field(index=True)       # "login", "register", "public_token"
    attempts: int = Field(default=1)
    locked_until: datetime | None = Field(default=None)
    last_attempt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
