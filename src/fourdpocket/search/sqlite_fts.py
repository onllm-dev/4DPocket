"""SQLite FTS5 full-text search backend."""

import logging
import uuid

from sqlalchemy import text
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem

logger = logging.getLogger(__name__)

# FTS5 virtual table DDL
FTS_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    item_id UNINDEXED,
    user_id UNINDEXED,
    title,
    description,
    content,
    source_platform UNINDEXED,
    item_type UNINDEXED,
    tokenize='porter unicode61'
);
"""


def init_fts(db: Session) -> None:
    """Create FTS5 virtual table if it doesn't exist."""
    db.exec(text(FTS_CREATE))
    db.commit()


def index_item(db: Session, item: KnowledgeItem) -> None:
    """Index a knowledge item in FTS5."""
    # Remove existing entry if any
    db.exec(
        text("DELETE FROM items_fts WHERE item_id = :item_id"),
        params={"item_id": str(item.id)},
    )

    db.exec(
        text(
            "INSERT INTO items_fts (item_id, user_id, title, description, content, "
            "source_platform, item_type) VALUES (:item_id, :user_id, :title, "
            ":description, :content, :source_platform, :item_type)"
        ),
        params={
            "item_id": str(item.id),
            "user_id": str(item.user_id),
            "title": item.title or "",
            "description": item.description or "",
            "content": (item.content or "")[:50000],  # cap content size
            "source_platform": item.source_platform.value if item.source_platform else "",
            "item_type": item.item_type.value if item.item_type else "",
        },
    )
    db.commit()


def delete_item(db: Session, item_id: uuid.UUID) -> None:
    """Remove an item from FTS5 index."""
    db.exec(
        text("DELETE FROM items_fts WHERE item_id = :item_id"),
        params={"item_id": str(item_id)},
    )
    db.commit()


def search(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    item_type: str | None = None,
    source_platform: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Search items using FTS5 with user scoping."""
    if not query.strip():
        return []

    # Escape FTS5 special characters
    safe_query = query.replace('"', '""')

    where_clauses = ["user_id = :user_id"]
    params: dict = {"user_id": str(user_id), "limit": limit, "offset": offset}

    if item_type:
        where_clauses.append("item_type = :item_type")
        params["item_type"] = item_type
    if source_platform:
        where_clauses.append("source_platform = :source_platform")
        params["source_platform"] = source_platform

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT item_id, rank, snippet(items_fts, 2, '<mark>', '</mark>', '...', 32) as title_snippet,
               snippet(items_fts, 4, '<mark>', '</mark>', '...', 64) as content_snippet
        FROM items_fts
        WHERE items_fts MATCH :query AND {where_sql}
        ORDER BY rank
        LIMIT :limit OFFSET :offset
    """

    try:
        result = db.exec(text(sql), params={"query": f'"{safe_query}"', **params})
        rows = result.all()
    except Exception as e:
        logger.warning("FTS5 search failed: %s", e)
        return []

    return [
        {
            "item_id": row[0],
            "rank": row[1],
            "title_snippet": row[2],
            "content_snippet": row[3],
        }
        for row in rows
    ]
