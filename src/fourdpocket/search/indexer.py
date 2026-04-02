"""Search indexer facade — delegates to configured backend."""

import logging
import uuid

from sqlmodel import Session

from fourdpocket.config import get_settings
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.search import sqlite_fts

logger = logging.getLogger(__name__)


class SearchIndexer:
    """Facade for search indexing — delegates to SQLite FTS5 or Meilisearch."""

    def __init__(self, db: Session):
        self._db = db
        self._backend = get_settings().search.backend

    def init(self) -> None:
        """Initialize search backend (create tables/indexes)."""
        if self._backend == "sqlite":
            sqlite_fts.init_fts(self._db)
        elif self._backend == "meilisearch":
            pass  # Meilisearch initialization handled separately

    def index_item(self, item: KnowledgeItem) -> None:
        """Index a knowledge item."""
        if self._backend == "sqlite":
            sqlite_fts.index_item(self._db, item)
        elif self._backend == "meilisearch":
            from fourdpocket.search.meilisearch_backend import index_item as meili_index

            meili_index(item)

    def delete_item(self, item_id: uuid.UUID) -> None:
        """Remove an item from the search index."""
        if self._backend == "sqlite":
            sqlite_fts.delete_item(self._db, item_id)
        elif self._backend == "meilisearch":
            from fourdpocket.search.meilisearch_backend import delete_item as meili_delete

            meili_delete(item_id)

    def search(
        self,
        query: str,
        user_id: uuid.UUID,
        item_type: str | None = None,
        source_platform: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """Search items."""
        if self._backend == "sqlite":
            return sqlite_fts.search(
                self._db, query, user_id, item_type, source_platform, limit, offset
            )
        elif self._backend == "meilisearch":
            from fourdpocket.search.meilisearch_backend import search as meili_search

            return meili_search(query, user_id, item_type, source_platform, limit, offset)
        return []
