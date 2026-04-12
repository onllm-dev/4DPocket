"""Meilisearch keyword backend — wraps existing meilisearch_backend module."""

import logging
import uuid

from sqlmodel import Session

from fourdpocket.search.base import KeywordHit, SearchFilters

logger = logging.getLogger(__name__)


class MeilisearchKeywordBackend:
    def __init__(self):
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        from fourdpocket.search.meilisearch_backend import init_meilisearch

        init_meilisearch()
        self._initialized = True

    def init(self, db: Session) -> None:
        self._ensure_init()

    def index_item(self, db: Session, item: object) -> None:
        self._ensure_init()
        from fourdpocket.search.meilisearch_backend import index_item

        index_item(item)  # type: ignore[arg-type]

    def index_chunks(
        self,
        db: Session,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        chunks: list,
        title: str | None,
        url: str | None,
    ) -> None:
        """Index chunks as separate Meilisearch documents for chunk-level retrieval."""
        try:
            from fourdpocket.search.meilisearch_backend import _get_client

            client = _get_client()
            try:
                client.create_index("knowledge_chunks", {"primaryKey": "id"})
            except Exception:
                pass

            index = client.index("knowledge_chunks")
            docs = []
            for chunk in chunks:
                docs.append({
                    "id": str(chunk.id),
                    "item_id": str(item_id),
                    "user_id": str(user_id),
                    "title": title or "",
                    "url": url or "",
                    "text": chunk.text,
                    "chunk_order": chunk.chunk_order,
                })
            if docs:
                index.add_documents(docs)
        except Exception as e:
            logger.debug("Meilisearch chunk indexing failed: %s", e)

    def delete_item(self, db: Session, item_id: uuid.UUID) -> None:
        from fourdpocket.search.meilisearch_backend import delete_item

        delete_item(item_id)

        # Also delete chunks from chunk index
        try:
            from fourdpocket.search.meilisearch_backend import _get_client

            client = _get_client()
            index = client.index("knowledge_chunks")
            index.delete_documents(filter=f'item_id = "{str(item_id)}"')
        except Exception:
            pass

    def search(
        self,
        db: Session,
        query: str,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        offset: int,
    ) -> list[KeywordHit]:
        self._ensure_init()
        from fourdpocket.search.meilisearch_backend import _get_client

        client = _get_client()
        index = client.index("knowledge_items")

        # Build filter string with ALL filter fields
        filter_parts = [f'user_id = "{str(user_id)}"']
        if filters.item_type:
            filter_parts.append(f'item_type = "{filters.item_type}"')
        if filters.source_platform:
            filter_parts.append(f'source_platform = "{filters.source_platform}"')
        if filters.is_favorite is not None:
            filter_parts.append(
                f"is_favorite = {'true' if filters.is_favorite else 'false'}"
            )
        if filters.is_archived is not None:
            filter_parts.append(
                f"is_archived = {'true' if filters.is_archived else 'false'}"
            )

        filter_str = " AND ".join(filter_parts)

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

        hits = [
            KeywordHit(
                item_id=hit["id"],
                rank=idx,
                title_snippet=hit.get("_formatted", {}).get("title", hit.get("title", "")),
                content_snippet=hit.get("_formatted", {}).get("content", "")[:200],
            )
            for idx, hit in enumerate(result.get("hits", []))
        ]

        # Post-filter for tags, after, before (not natively supported by Meilisearch filterable attrs)
        if filters.tags or filters.after or filters.before:
            hits = self._post_filter(db, hits, user_id, filters)

        return hits

    def _post_filter(
        self,
        db: Session,
        hits: list[KeywordHit],
        user_id: uuid.UUID,
        filters: SearchFilters,
    ) -> list[KeywordHit]:
        """Apply filters that Meilisearch doesn't support natively as post-filters."""
        if not hits:
            return hits

        from sqlmodel import select

        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.tag import ItemTag, Tag

        item_ids = [uuid.UUID(h.item_id) for h in hits]
        items = db.exec(
            select(KnowledgeItem).where(KnowledgeItem.id.in_(item_ids))
        ).all()
        item_map = {str(i.id): i for i in items}

        # Build tag lookup if needed
        tag_items: set[str] = set()
        if filters.tags:
            tag_rows = db.exec(
                select(ItemTag.item_id)
                .join(Tag, Tag.id == ItemTag.tag_id)
                .where(
                    Tag.user_id == user_id,
                    Tag.slug.in_(filters.tags),
                    ItemTag.item_id.in_(item_ids),
                )
            ).all()
            tag_items = {str(r) for r in tag_rows}

        filtered = []
        for hit in hits:
            item = item_map.get(hit.item_id)
            if not item:
                continue

            if filters.tags and hit.item_id not in tag_items:
                continue
            if filters.after and item.created_at:
                if item.created_at.isoformat()[:len(filters.after)] < filters.after:
                    continue
            if filters.before and item.created_at:
                if item.created_at.isoformat()[:len(filters.before)] > filters.before:
                    continue

            filtered.append(hit)

        return filtered
