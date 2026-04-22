"""SQLite FTS5 full-text search backend with fuzzy fallback."""

import hashlib
import logging
import re
import time
import uuid
from collections import OrderedDict

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

CHUNKS_FTS_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    item_id UNINDEXED,
    user_id UNINDEXED,
    title,
    url,
    text,
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

# ─── Query Cache ───────────────────────────────────────────────
_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX = 500


class _TTLCache:
    """Simple LRU cache with TTL expiration."""

    def __init__(self, maxsize: int = _CACHE_MAX, ttl: int = _CACHE_TTL):
        self._cache: OrderedDict[str, tuple[float, list]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> list | None:
        if key in self._cache:
            ts, value = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                self._cache.move_to_end(key)
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: list) -> None:
        if key in self._cache:
            del self._cache[key]
        self._cache[key] = (time.monotonic(), value)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate_user(self, user_id: str) -> None:
        """Remove all cached entries for a user."""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{user_id}:")]
        for k in keys_to_remove:
            del self._cache[k]


_search_cache = _TTLCache()


def _cache_key(user_id: str, query: str, **kwargs) -> str:
    raw = f"{user_id}:{query}:{sorted(kwargs.items())}"
    return f"{user_id}:{hashlib.md5(raw.encode()).hexdigest()}"


# ─── FTS Initialization ───────────────────────────────────────

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
    from sqlmodel import select as _select

    from fourdpocket.models.item import KnowledgeItem as _KI

    items = db.exec(_select(_KI)).all()
    for item in items:
        index_item(db, item)
    logger.info("Re-indexed %d items in FTS5", len(items))
    return len(items)


def init_notes_fts(db: Session) -> None:
    """Create notes FTS5 virtual table if it doesn't exist."""
    db.exec(text(NOTES_FTS_CREATE))
    db.commit()


# ─── Query Building ───────────────────────────────────────────

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


def _build_url_fts_query(query: str) -> str | None:
    """Build a URL-optimized FTS query: match domain parts and path segments."""
    # Strip protocol
    url_text = re.sub(r'^https?://(www\.)?', '', query.strip().rstrip('/'))
    # Split on URL separators
    parts = re.split(r'[/\-_.?&=#+]', url_text)
    tokens = [p for p in parts if len(p) >= 2]
    if not tokens:
        return None
    return " ".join(f'"{t}"*' for t in tokens)


def _is_url_query(query: str) -> bool:
    """Detect if the query looks like a URL."""
    q = query.strip().lower()
    return (
        q.startswith("http://") or q.startswith("https://")
        or q.startswith("www.")
        or "." in q and "/" in q
        or re.match(r'^[\w-]+\.(com|org|net|io|dev|co|app|ai|edu|gov)', q) is not None
    )


# ─── Indexing ─────────────────────────────────────────────────

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
    # Invalidate cache for this user
    _search_cache.invalidate_user(str(item.user_id))


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
    _search_cache.invalidate_user(str(note.user_id))


def delete_item(db: Session, item_id: uuid.UUID) -> None:
    """Remove an item from FTS5 index."""
    db.exec(
        text("DELETE FROM items_fts WHERE item_id = :item_id"),
        params={"item_id": str(item_id)},
    )
    db.commit()


# ─── Search ───────────────────────────────────────────────────

def search(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    item_type: str | None = None,
    source_platform: str | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    tags: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Search items using FTS5 with user scoping, filter pushdown, and fuzzy fallback."""
    if not query.strip():
        return []

    # Check cache
    cache_k = _cache_key(
        str(user_id), query,
        item_type=item_type, source_platform=source_platform,
        is_favorite=is_favorite, is_archived=is_archived,
        tags=tags, after=after, before=before,
        limit=limit, offset=offset,
    )
    cached = _search_cache.get(cache_k)
    if cached is not None:
        return cached

    # URL-aware query building
    if _is_url_query(query):
        fts_query = _build_url_fts_query(query)
    else:
        fts_query = _build_fts_query(query)

    if not fts_query:
        return []

    results = _fts_search(
        db, fts_query, user_id, item_type, source_platform,
        is_favorite, is_archived, tags, after, before,
        limit, offset,
    )

    # Fuzzy fallback: if FTS5 returns no results, try LIKE-based fuzzy matching
    if not results and offset == 0:
        results = _fuzzy_search(
            db, query, user_id, item_type, source_platform,
            is_favorite, is_archived, tags, after, before,
            limit,
        )

    _search_cache.set(cache_k, results)
    return results


def _fts_search(
    db: Session,
    fts_query: str,
    user_id: uuid.UUID,
    item_type: str | None,
    source_platform: str | None,
    is_favorite: bool | None,
    is_archived: bool | None,
    tags: list[str] | None,
    after: str | None,
    before: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    """Core FTS5 search with filter pushdown via JOIN to knowledge_items."""
    where_fts = ["fts.user_id = :user_id"]
    where_items: list[str] = []
    params: dict = {"user_id": str(user_id), "limit": limit, "offset": offset}
    joins: list[str] = []

    if item_type:
        where_fts.append("fts.item_type = :item_type")
        params["item_type"] = item_type
    if source_platform:
        where_fts.append("fts.source_platform = :source_platform")
        params["source_platform"] = source_platform

    # Filters that need JOIN to knowledge_items
    needs_join = bool(is_favorite is not None or is_archived is not None or after or before)

    if needs_join:
        joins.append("JOIN knowledge_items ki ON ki.id = fts.item_id")

    if is_favorite is not None:
        where_items.append("ki.is_favorite = :is_favorite")
        params["is_favorite"] = is_favorite
    if is_archived is not None:
        where_items.append("ki.is_archived = :is_archived")
        params["is_archived"] = is_archived
    if after:
        where_items.append("ki.created_at >= :after_date")
        params["after_date"] = after
    if before:
        where_items.append("ki.created_at <= :before_date")
        params["before_date"] = before

    # Tag filter: join through item_tags → tags
    if tags:
        joins.append(
            "JOIN item_tags it ON it.item_id = fts.item_id"
            " JOIN tags t ON t.id = it.tag_id"
        )
        tag_placeholders = ", ".join(f":tag_{i}" for i in range(len(tags)))
        where_items.append(f"LOWER(t.slug) IN ({tag_placeholders})")
        for i, tag_slug in enumerate(tags):
            params[f"tag_{i}"] = tag_slug.lower().strip()

    fts_where = " AND ".join(where_fts)
    item_where = (" AND " + " AND ".join(where_items)) if where_items else ""
    join_sql = " ".join(joins)

    sql = f"""
        SELECT fts.item_id, fts.rank,
               snippet(items_fts, 2, '<mark>', '</mark>', '...', 32) as title_snippet,
               snippet(items_fts, 5, '<mark>', '</mark>', '...', 64) as content_snippet
        FROM items_fts fts
        {join_sql}
        WHERE items_fts MATCH :query AND {fts_where}{item_where}
        ORDER BY fts.rank
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


def _fuzzy_search(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    item_type: str | None,
    source_platform: str | None,
    is_favorite: bool | None,
    is_archived: bool | None,
    tags: list[str] | None,
    after: str | None,
    before: str | None,
    limit: int,
) -> list[dict]:
    """Fuzzy fallback using LIKE with trigram-style matching for typo tolerance."""
    tokens = query.strip().split()
    if not tokens:
        return []

    where_clauses = ["ki.user_id = :user_id"]
    params: dict = {"user_id": str(user_id), "limit": limit}

    # Build fuzzy LIKE conditions: each token matches title, url, or description
    like_parts = []
    for i, token in enumerate(tokens[:5]):  # Cap at 5 tokens
        param_key = f"tok_{i}"
        params[param_key] = f"%{token.lower()}%"
        like_parts.append(
            f"(LOWER(ki.title) LIKE :{param_key}"
            f" OR LOWER(ki.url) LIKE :{param_key}"
            f" OR LOWER(ki.description) LIKE :{param_key})"
        )
    where_clauses.extend(like_parts)

    if item_type:
        where_clauses.append("ki.item_type = :item_type")
        params["item_type"] = item_type
    if source_platform:
        where_clauses.append("ki.source_platform = :source_platform")
        params["source_platform"] = source_platform
    if is_favorite is not None:
        where_clauses.append("ki.is_favorite = :is_favorite")
        params["is_favorite"] = is_favorite
    if is_archived is not None:
        where_clauses.append("ki.is_archived = :is_archived")
        params["is_archived"] = is_archived
    if after:
        where_clauses.append("ki.created_at >= :after_date")
        params["after_date"] = after
    if before:
        where_clauses.append("ki.created_at <= :before_date")
        params["before_date"] = before

    joins = ""
    if tags:
        joins = "JOIN item_tags it ON it.item_id = ki.id JOIN tags t ON t.id = it.tag_id"
        tag_placeholders = ", ".join(f":tag_{i}" for i in range(len(tags)))
        where_clauses.append(f"LOWER(t.slug) IN ({tag_placeholders})")
        for i, tag_slug in enumerate(tags):
            params[f"tag_{i}"] = tag_slug.lower().strip()

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT CAST(ki.id AS TEXT) as item_id,
               0.0 as rank,
               NULL as title_snippet,
               NULL as content_snippet
        FROM knowledge_items ki
        {joins}
        WHERE {where_sql}
        ORDER BY ki.created_at DESC
        LIMIT :limit
    """

    try:
        result = db.exec(text(sql), params=params)
        return [
            {"item_id": row[0], "rank": row[1], "title_snippet": row[2], "content_snippet": row[3]}
            for row in result.all()
        ]
    except Exception as e:
        logger.warning("Fuzzy search failed: %s", e)
        return []


# ─── Notes Search ─────────────────────────────────────────────

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


# ─── Chunk-Level FTS ─────────────────────────────────────────

def init_chunks_fts(db: Session) -> None:
    """Create chunks_fts virtual table if it doesn't exist."""
    db.exec(text(CHUNKS_FTS_CREATE))
    db.commit()


def index_chunks(
    db: Session,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    chunks: list,
    title: str | None = None,
    url: str | None = None,
) -> None:
    """Index item chunks into chunks_fts. Replaces any existing entries for the item."""
    # Remove existing chunk entries for this item
    delete_chunks(db, item_id)

    for chunk in chunks:
        # chunk can be an ItemChunk model or a Chunk dataclass
        chunk_id = str(getattr(chunk, "id", "") or getattr(chunk, "content_hash", ""))
        chunk_text_val = getattr(chunk, "text", "")
        chunk_order = getattr(chunk, "chunk_order", 0)

        db.exec(
            text(
                "INSERT INTO chunks_fts (chunk_id, item_id, user_id, title, url, text) "
                "VALUES (:chunk_id, :item_id, :user_id, :title, :url, :text)"
            ),
            params={
                "chunk_id": chunk_id,
                "item_id": str(item_id),
                "user_id": str(user_id),
                "title": (title or "") if chunk_order == 0 else "",
                "url": (url or "") if chunk_order == 0 else "",
                "text": chunk_text_val[:50000],
            },
        )
    db.commit()
    _search_cache.invalidate_user(str(user_id))


def delete_chunks(db: Session, item_id: uuid.UUID) -> None:
    """Remove all chunk FTS entries for an item."""
    # Look up user_id for cache invalidation before deleting
    result = db.exec(
        text("SELECT DISTINCT user_id FROM chunks_fts WHERE item_id = :item_id"),
        params={"item_id": str(item_id)},
    )
    user_ids = [row[0] for row in result.all()]

    db.exec(
        text("DELETE FROM chunks_fts WHERE item_id = :item_id"),
        params={"item_id": str(item_id)},
    )
    db.commit()

    for uid in user_ids:
        _search_cache.invalidate_user(uid)


def search_chunks(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    item_type: str | None = None,
    source_platform: str | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    tags: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Search chunks via FTS5, roll up to items (best chunk per item).

    Returns the same dict shape as search(): {item_id, rank, title_snippet, content_snippet}
    """
    if not query.strip():
        return []

    # Check cache
    cache_k = _cache_key(
        str(user_id), f"chunk:{query}",
        item_type=item_type, source_platform=source_platform,
        is_favorite=is_favorite, is_archived=is_archived,
        tags=tags, after=after, before=before,
        limit=limit, offset=offset,
    )
    cached = _search_cache.get(cache_k)
    if cached is not None:
        return cached

    if _is_url_query(query):
        fts_query = _build_url_fts_query(query)
    else:
        fts_query = _build_fts_query(query)

    if not fts_query:
        return []

    # Build filter JOINs
    where_fts = ["cfts.user_id = :user_id"]
    where_items: list[str] = []
    params: dict = {"user_id": str(user_id), "query": fts_query}
    joins: list[str] = []

    # Filters that require JOIN to knowledge_items
    needs_join = bool(
        item_type or source_platform or is_favorite is not None
        or is_archived is not None or after or before or tags
    )

    if needs_join:
        joins.append("JOIN knowledge_items ki ON ki.id = cfts.item_id")

    if item_type:
        where_items.append("ki.item_type = :item_type")
        params["item_type"] = item_type
    if source_platform:
        where_items.append("ki.source_platform = :source_platform")
        params["source_platform"] = source_platform
    if is_favorite is not None:
        where_items.append("ki.is_favorite = :is_favorite")
        params["is_favorite"] = is_favorite
    if is_archived is not None:
        where_items.append("ki.is_archived = :is_archived")
        params["is_archived"] = is_archived
    if after:
        where_items.append("ki.created_at >= :after_date")
        params["after_date"] = after
    if before:
        where_items.append("ki.created_at <= :before_date")
        params["before_date"] = before

    if tags:
        joins.append(
            "JOIN item_tags it ON it.item_id = cfts.item_id"
            " JOIN tags t ON t.id = it.tag_id"
        )
        tag_placeholders = ", ".join(f":tag_{i}" for i in range(len(tags)))
        where_items.append(f"LOWER(t.slug) IN ({tag_placeholders})")
        for i, tag_slug in enumerate(tags):
            params[f"tag_{i}"] = tag_slug.lower().strip()

    fts_where = " AND ".join(where_fts)
    item_where = (" AND " + " AND ".join(where_items)) if where_items else ""
    join_sql = " ".join(joins)

    # Two-step approach: snippet() can't be used with GROUP BY, so we first
    # find matching chunks, then pick the best per item in Python.
    sql = f"""
        SELECT cfts.item_id, cfts.rank, cfts.chunk_id,
               snippet(chunks_fts, 3, '<mark>', '</mark>', '...', 32) as title_snippet,
               snippet(chunks_fts, 5, '<mark>', '</mark>', '...', 64) as content_snippet
        FROM chunks_fts cfts
        {join_sql}
        WHERE chunks_fts MATCH :query AND {fts_where}{item_where}
        ORDER BY cfts.rank
        LIMIT :raw_limit
    """
    # Fetch enough rows to cover the offset+limit after rollup deduplication.
    params["raw_limit"] = (offset + limit) * 5

    try:
        result = db.exec(text(sql), params=params)
        rows = result.all()
    except Exception as e:
        logger.warning("Chunk FTS5 search failed: %s", e)
        return []

    # Roll up: keep the best-scoring chunk per item
    seen_items: dict[str, dict] = {}
    for row in rows:
        iid = row[0]
        if iid not in seen_items:
            seen_items[iid] = {
                "item_id": iid,
                "rank": row[1],
                "title_snippet": row[3],
                "content_snippet": row[4],
            }

    results = list(seen_items.values())[offset:offset + limit]

    _search_cache.set(cache_k, results)
    return results
