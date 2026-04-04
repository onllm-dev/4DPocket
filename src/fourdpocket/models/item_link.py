"""ItemLink model for multi-link topic node items."""

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator
from sqlmodel import Column, Field, SQLModel

from fourdpocket.models.base import utc_now

try:
    from sqlalchemy import DateTime
except ImportError:
    from sqlmodel import DateTime


class ItemLink(SQLModel, table=True):
    __tablename__ = "item_links"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="knowledge_items.id", index=True)
    url: str
    title: str | None = None
    domain: str | None = None
    position: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ItemLinkCreate(BaseModel):
    url: str
    title: str | None = None
    domain: str | None = None
    position: int = 0

    model_config = {"extra": "forbid"}

    @field_validator("url")
    @classmethod
    def reject_dangerous_schemes(cls, v: str) -> str:
        lowered = v.lower().strip()
        if any(lowered.startswith(s) for s in ("javascript:", "data:", "vbscript:")):
            raise ValueError("URL scheme not permitted")
        return v


class ItemLinkRead(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    url: str
    title: str | None
    domain: str | None
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}
