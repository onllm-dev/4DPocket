"""Share and ShareRecipient models."""

import enum
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from fourdpocket.models.base import utc_now


class ShareType(str, enum.Enum):
    item = "item"
    collection = "collection"
    tag = "tag"


class ShareRecipientRole(str, enum.Enum):
    viewer = "viewer"
    editor = "editor"


class Share(SQLModel, table=True):
    __tablename__ = "shares"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    share_type: ShareType
    item_id: uuid.UUID | None = Field(default=None, foreign_key="knowledge_items.id")
    collection_id: uuid.UUID | None = Field(default=None, foreign_key="collections.id")
    tag_id: uuid.UUID | None = Field(default=None, foreign_key="tags.id")
    public_token: str | None = Field(default=None, unique=True)
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ShareRecipient(SQLModel, table=True):
    __tablename__ = "share_recipients"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    share_id: uuid.UUID = Field(foreign_key="shares.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    role: ShareRecipientRole = Field(default=ShareRecipientRole.viewer)
    accepted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
