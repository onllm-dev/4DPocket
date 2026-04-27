"""PAT audit event model — records every meaningful PAT action."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime, String
except ImportError:
    from sqlmodel import DateTime, String


class PatEvent(SQLModel, table=True):
    __tablename__ = "pat_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    pat_id: uuid.UUID = Field(foreign_key="api_tokens.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    # action: "mcp_tool_call" | "rest_call" | "mint" | "revoke"
    action: str
    resource: str | None = None  # tool name OR endpoint path OR item_id
    ip: str | None = None
    user_agent: str | None = Field(
        default=None,
        sa_column=Column("user_agent", String(512), nullable=True),
    )
    status_code: int | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
