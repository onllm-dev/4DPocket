"""LLM response cache model — avoids redundant LLM calls for identical inputs."""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class LLMCache(SQLModel, table=True):
    __tablename__ = "llm_cache"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    content_hash: str = Field(index=True)
    cache_type: str = Field(index=True)  # "extraction", "summary", "tagging", "keywords"
    response: str  # JSON string of the cached response
    model_name: str = ""  # Which model produced this response
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
