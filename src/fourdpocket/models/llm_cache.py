"""LLM response cache model — avoids redundant LLM calls for identical inputs."""

import uuid
from datetime import datetime

from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class LLMCache(SQLModel, table=True):
    __tablename__ = "llm_cache"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    content_hash: str = Field(index=True)
    cache_type: str = Field(index=True)  # "extraction", "summary", "tagging", "keywords"
    response: str  # JSON string of the cached response
    model_name: str = ""  # Which model produced this response
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
