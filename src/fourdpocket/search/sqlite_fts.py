"""SQLite FTS5 full-text search backend."""

import logging
import re
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
    url,
    description,
    content,
    source_platform UNINDEXED,
    item_type UNINDEXED,
    tokenize='porter unicode61'
);
"""

NOTES_FTS_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    note_id UNINDEXED,
    user_id UNINDEXED,
    title,
    content,
    tokenize='porter unicode61'
);
"""


def init_fts(db: Session) -> bool:
    """Create FTS5 virtual table if it doesn't exist. Returns True if table was recreated."""
    recreated = False
    # Check if url column exists in the FTS table; if not, drop and recreate
    try:
        db.exec(text("SELECT url FROM items_fts LIMIT 0"))
    except Exception:
        # Schema changed - drop and recreate
        db.exec(text("DROP TABLE IF EXISTS items_fts"))
        db.commit()
        recreated = True
    db.exec(text(FTS_CREATE))
    db.commit()
    return recreated


def reindex_all_items(db: Session) -> int:
    """Re-index all knowledge items in FTS5. Returns count indexed."""
    from fourdpocket.models.item import KnowledgeItem as _KI
    from sqlmodel import select as _select

    items = db.exec(_select(_KI)).all()
    for item in items:
        index_item(db, item)
    logger.info("Re-indexed %d items in FTS5", len(items))
    return len(items)


def init_notes_fts(db: Session) -> None:
    """Create notes FTS5 virtual table if it doesn't exist."""
    db.exec(text(NOTES_FTS_CREATE))
    db.commit()


def _build_fts_query(query: str) -> str | None:
    """Sanitize query and build FTS5 token query with prefix matching."""
    safe_query = re.sub(r'[*+\-"^{}()\[\]:.]', ' ', query)
    safe_query = re.sub(r'\b(AND|OR|NOT|NEAR)\b', '', safe_query, flags=re.IGNORECASE)
    safe_query = ' '.join(safe_query.split())
    tokens = safe_query.split()
    if not tokens:
        return None
    # Each token gets prefix matching (word*), joined with implicit AND
    return " ".join(f'"{t}"*' for t in tokens)


def index_item(db: Session, item: KnowledgeItem) -> None:
    """Index a knowledge item in FTS5."""
    # Remove existing entry if any
    db.exec(
        text("DELETE FROM items_fts WHERE item_id = :item_id"),
        params={"item_id": str(item.id)},
    )

    db.exec(
        text(
            "INSERT INTO items_fts (item_id, user_id, title, url, description, content, "
            "source_platform, item_type) VALUES (:item_id, :user_id, :title, :url, "
            ":description, :content, :source_platform, :item_type)"
        ),
        params={
            "item_id": str(item.id),
            "user_id": str(item.user_id),
            "title": item.title or "",
            "url": item.url or "",
            "description": item.description or "",
            "content": (item.content or "")[:50000],  # cap content size
            "source_platform": item.source_platform.value if item.source_platform else "",
            "item_type": item.item_type.value if item.item_type else "",
        },
    )
    db.commit()


def index_note(db: Session, note) -> None:
    """Index a note in FTS5."""
    db.exec(
        text("DELETE FROM notes_fts WHERE note_id = :note_id"),
        params={"note_id": str(note.id)},
    )
    # Strip HTML tags for indexing
    content = re.sub(r'<[^>]+>', ' ', note.content or '')
    db.exec(
        text(
            "INSERT INTO notes_fts (note_id, user_id, title, content) "
            "VALUES (:note_id, :user_id, :title, :content)"
        ),
        params={
            "note_id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title or "",
            "content": content[:50000],
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

    fts_query = _build_fts_query(query)
    if not fts_query:
        return []

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
        SELECT item_id, rank,
               snippet(items_fts, 2, '<mark>', '</mark>', '...', 32) as title_snippet,
               snippet(items_fts, 5, '<mark>', '</mark>', '...', 64) as content_snippet
        FROM items_fts
        WHERE items_fts MATCH :query AND {where_sql}
        ORDER BY rank
        LIMIT :limit OFFSET :offset
    """

    try:
        result = db.exec(text(sql), params={"query": fts_query, **params})
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


def search_notes(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Search notes using FTS5."""
    if not query.strip():
        return []

    fts_query = _build_fts_query(query)
    if not fts_query:
        return []

    sql = """
        SELECT note_id, rank,
               snippet(notes_fts, 2, '<mark>', '</mark>', '...', 32) as title_snippet,
               snippet(notes_fts, 3, '<mark>', '</mark>', '...', 64) as content_snippet
        FROM notes_fts
        WHERE notes_fts MATCH :query AND user_id = :user_id
        ORDER BY rank
        LIMIT :limit OFFSET :offset
    """
    try:
        result = db.exec(text(sql), params={
            "query": fts_query, "user_id": str(user_id),
            "limit": limit, "offset": offset,
        })
        return [
            {"note_id": r[0], "rank": r[1], "title_snippet": r[2], "content_snippet": r[3]}
            for r in result.all()
        ]
    except Exception as e:
        logger.warning("Notes FTS5 search failed: %s", e)
        return []
