"""API token (PAT) models for MCP and programmatic access."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import ApiTokenRole, utc_now

try:
    from sqlalchemy import JSON, DateTime
except ImportError:
    from sqlmodel import JSON, DateTime


class ApiToken(SQLModel, table=True):
    __tablename__ = "api_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str
    token_prefix: str = Field(unique=True, index=True)
    token_hash: str = Field(index=True)
    role: ApiTokenRole = Field(default=ApiTokenRole.viewer)
    all_collections: bool = Field(default=True)
    include_uncollected: bool = Field(default=True)
    allow_deletion: bool = Field(default=False)
    admin_scope: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ApiTokenCollection(SQLModel, table=True):
    __tablename__ = "api_token_collections"

    token_id: uuid.UUID = Field(foreign_key="api_tokens.id", primary_key=True)
    collection_id: uuid.UUID = Field(foreign_key="collections.id", primary_key=True)
