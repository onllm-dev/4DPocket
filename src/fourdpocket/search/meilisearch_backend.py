"""Meilisearch search backend — optional upgrade from SQLite FTS5."""

import logging
import uuid

from fourdpocket.config import get_settings
from fourdpocket.models.item import KnowledgeItem

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        import meilisearch
        settings = get_settings()
        _client = meilisearch.Client(
            settings.search.meili_url,
            settings.search.meili_master_key or None,
        )
    return _client


def _get_index():
    client = _get_client()
    index = client.index("knowledge_items")
    return index


def init_meilisearch() -> None:
    """Initialize Meilisearch index with proper settings."""
    client = _get_client()
    try:
        client.create_index("knowledge_items", {"primaryKey": "id"})
    except Exception:
        pass  # Index may already exist

    index = _get_index()
    index.update_filterable_attributes([
        "user_id", "item_type", "source_platform", "is_favorite", "is_archived",
    ])
    index.update_sortable_attributes(["created_at", "title"])
    index.update_searchable_attributes(["title", "description", "content"])
    logger.info("Meilisearch index configured")


def index_item(item: KnowledgeItem) -> None:
    """Add or update an item in the Meilisearch index."""
    index = _get_index()
    doc = {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "title": item.title or "",
        "description": item.description or "",
        "content": (item.content or "")[:50000],
        "item_type": item.item_type.value if item.item_type else "",
        "source_platform": item.source_platform.value if item.source_platform else "",
        "is_favorite": item.is_favorite,
        "is_archived": item.is_archived,
        "created_at": item.created_at.isoformat() if item.created_at else "",
    }
    index.add_documents([doc])


def delete_item(item_id: uuid.UUID) -> None:
    """Remove an item from the index."""
    index = _get_index()
    index.delete_document(str(item_id))


def search(
    query: str,
    user_id: uuid.UUID,
    item_type: str | None = None,
    source_platform: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Search with Meilisearch."""
    index = _get_index()

    filters = [f'user_id = "{str(user_id)}"']
    if item_type:
        filters.append(f'item_type = "{item_type}"')
    if source_platform:
        filters.append(f'source_platform = "{source_platform}"')

    filter_str = " AND ".join(filters)

    result = index.search(
        query,
        {
            "filter": filter_str,
            "limit": limit,
            "offset": offset,
            "attributesToHighlight": ["title", "content"],
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
        },
    )

    return [
        {
            "item_id": hit["id"],
            "rank": idx,
            "title_snippet": hit.get("_formatted", {}).get("title", hit.get("title", "")),
            "content_snippet": hit.get("_formatted", {}).get("content", "")[:200],
        }
        for idx, hit in enumerate(result.get("hits", []))
    ]
