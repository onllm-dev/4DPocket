"""SQLite FTS5 keyword backend — wraps existing sqlite_fts module."""

import uuid

from sqlmodel import Session

from fourdpocket.search.base import KeywordHit, SearchFilters


class SqliteFtsBackend:
    def init(self, db: Session) -> None:
        from fourdpocket.search.sqlite_fts import init_chunks_fts, init_fts, init_notes_fts

        init_fts(db)
        init_notes_fts(db)
        init_chunks_fts(db)

    def index_item(self, db: Session, item: object) -> None:
        from fourdpocket.search.sqlite_fts import index_item

        index_item(db, item)  # type: ignore[arg-type]

    def index_chunks(
        self,
        db: Session,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        chunks: list,
        title: str | None,
        url: str | None,
    ) -> None:
        from fourdpocket.search.sqlite_fts import index_chunks

        index_chunks(db, item_id, user_id, chunks, title, url)

    def delete_item(self, db: Session, item_id: uuid.UUID) -> None:
        from fourdpocket.search.sqlite_fts import delete_chunks, delete_item

        delete_item(db, item_id)
        delete_chunks(db, item_id)

    def search(
        self,
        db: Session,
        query: str,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        offset: int,
    ) -> list[KeywordHit]:
        from fourdpocket.search.sqlite_fts import search, search_chunks

        # Try chunk search first, fall back to item-level
        results = search_chunks(
            db, query, user_id,
            item_type=filters.item_type,
            source_platform=filters.source_platform,
            is_favorite=filters.is_favorite,
            is_archived=filters.is_archived,
            tags=filters.tags,
            after=filters.after,
            before=filters.before,
            limit=limit,
            offset=offset,
        )

        if not results:
            results = search(
                db, query, user_id,
                item_type=filters.item_type,
                source_platform=filters.source_platform,
                is_favorite=filters.is_favorite,
                is_archived=filters.is_archived,
                tags=filters.tags,
                after=filters.after,
                before=filters.before,
                limit=limit,
                offset=offset,
            )

        return [
            KeywordHit(
                item_id=r["item_id"],
                rank=r.get("rank", 0),
                title_snippet=r.get("title_snippet"),
                content_snippet=r.get("content_snippet"),
            )
            for r in results
        ]
