"""Models package - import all models for Alembic discovery."""

from fourdpocket.models.api_token import ApiToken, ApiTokenCollection
from fourdpocket.models.base import (
    ApiTokenRole,
    ItemType,
    ReadingStatus,
    ShareMode,
    SourcePlatform,
    UserRole,
)
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.collection_note import CollectionNote
from fourdpocket.models.comment import Comment
from fourdpocket.models.embedding import Embedding
from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation, RelationEvidence
from fourdpocket.models.feed import KnowledgeFeed
from fourdpocket.models.feed_entry import FeedEntry
from fourdpocket.models.highlight import Highlight
from fourdpocket.models.instance_settings import InstanceSettings
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.item_link import ItemLink
from fourdpocket.models.llm_cache import LLMCache
from fourdpocket.models.note import Note
from fourdpocket.models.note_tag import NoteTag
from fourdpocket.models.rate_limit import RateLimitEntry
from fourdpocket.models.rss_feed import RSSFeed
from fourdpocket.models.rule import Rule
from fourdpocket.models.saved_filter import SavedFilter
from fourdpocket.models.share import Share, ShareRecipient
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.models.user import User

__all__ = [
    "ApiToken",
    "ApiTokenCollection",
    "ApiTokenRole",
    "Collection",
    "CollectionItem",
    "CollectionNote",
    "Comment",
    "Embedding",
    "EnrichmentStage",
    "Entity",
    "EntityAlias",
    "EntityRelation",
    "ItemEntity",
    "RelationEvidence",
    "FeedEntry",
    "Highlight",
    "InstanceSettings",
    "ItemChunk",
    "ItemLink",
    "ItemTag",
    "ItemType",
    "KnowledgeFeed",
    "KnowledgeItem",
    "LLMCache",
    "Note",
    "NoteTag",
    "RateLimitEntry",
    "RSSFeed",
    "ReadingStatus",
    "Rule",
    "SavedFilter",
    "Share",
    "ShareMode",
    "ShareRecipient",
    "SourcePlatform",
    "Tag",
    "User",
    "UserRole",
]
