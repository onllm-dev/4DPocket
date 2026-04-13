"""Tests for SearchIndexer — delegates to sqlite or meilisearch backend."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.indexer import SearchIndexer


@pytest.fixture
def indexer_user(db: Session):
    user = User(
        email="indexeruser@example.com",
        username="indexeruser",
        password_hash="$2b$12$fakehash",
        display_name="Indexer Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestSearchIndexer:
    """Test SearchIndexer facade delegates to correct backend."""

    def test_index_item_sqlite_backend(self, db: Session, indexer_user):
        """With 'sqlite' backend, index_item delegates to sqlite_fts.index_item."""
        with patch("fourdpocket.search.indexer.get_settings") as mock_settings:
            mock_settings.return_value.search.backend = "sqlite"

            indexer = SearchIndexer(db)
            item = KnowledgeItem(
                user_id=indexer_user.id,
                title="SQLite Backend Item",
                content="Content for indexing test",
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            indexer.index_item(item)

            # Verify by searching — should be findable
            from fourdpocket.search.sqlite_fts import search
            results = search(db, "SQLite Backend", indexer_user.id)
            assert len(results) >= 1

    def test_delete_item_sqlite_backend(self, db: Session, indexer_user):
        """With 'sqlite' backend, delete_item delegates to sqlite_fts.delete_item."""
        with patch("fourdpocket.search.indexer.get_settings") as mock_settings:
            mock_settings.return_value.search.backend = "sqlite"

            indexer = SearchIndexer(db)
            item = KnowledgeItem(
                user_id=indexer_user.id,
                title="To Be Deleted",
                content="This item will be deleted",
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            from fourdpocket.search.sqlite_fts import index_item
            index_item(db, item)

            indexer.delete_item(item.id)

            from fourdpocket.search.sqlite_fts import search
            results = search(db, "To Be Deleted", indexer_user.id)
            assert all(r["item_id"] != str(item.id) for r in results)

    def test_search_sqlite_backend(self, db: Session, indexer_user):
        """With 'sqlite' backend, search delegates to sqlite_fts.search."""
        with patch("fourdpocket.search.indexer.get_settings") as mock_settings:
            mock_settings.return_value.search.backend = "sqlite"

            item = KnowledgeItem(
                user_id=indexer_user.id,
                title="Search Indexer Test",
                content="Unique content for search indexer testing",
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            from fourdpocket.search.sqlite_fts import index_item
            index_item(db, item)

            indexer = SearchIndexer(db)
            results = indexer.search(
                query="Unique content",
                user_id=indexer_user.id,
                limit=20,
                offset=0,
            )

            assert len(results) >= 1

    def test_search_with_filters(self, db: Session, indexer_user):
        """SearchIndexer passes all filter arguments to the underlying backend."""
        with patch("fourdpocket.search.indexer.get_settings") as mock_settings:
            mock_settings.return_value.search.backend = "sqlite"

            indexer = SearchIndexer(db)

            results = indexer.search(
                query="anything",
                user_id=indexer_user.id,
                item_type="article",
                source_platform="youtube",
                is_favorite=True,
                tags=["python"],
                limit=10,
                offset=0,
            )

            assert isinstance(results, list)

    @patch("fourdpocket.search.indexer.get_settings")
    def test_search_meilisearch_backend(self, mock_settings, db: Session, indexer_user):
        """With 'meilisearch' backend, search delegates to meilisearch_backend.search."""
        mock_settings.return_value.search.backend = "meilisearch"

        with patch("fourdpocket.search.meilisearch_backend.search") as mock_search:
            mock_search.return_value = [
                {"item_id": "item-1", "rank": 0.5, "title_snippet": "Result"}
            ]

            indexer = SearchIndexer(db)
            results = indexer.search(
                query="test query",
                user_id=indexer_user.id,
                limit=20,
                offset=0,
            )

            mock_search.assert_called_once()
            assert len(results) == 1
            assert results[0]["item_id"] == "item-1"

    @patch("fourdpocket.search.indexer.get_settings")
    def test_index_item_meilisearch_backend(self, mock_settings, db: Session, indexer_user):
        """With 'meilisearch' backend, index_item delegates to meilisearch_backend."""
        mock_settings.return_value.search.backend = "meilisearch"

        with patch("fourdpocket.search.meilisearch_backend.index_item") as mock_index:
            mock_index.return_value = None

            indexer = SearchIndexer(db)
            item = MagicMock()
            item.id = uuid.uuid4()
            indexer.index_item(item)

            mock_index.assert_called_once_with(item)

    @patch("fourdpocket.search.indexer.get_settings")
    def test_delete_item_meilisearch_backend(self, mock_settings, db: Session):
        """With 'meilisearch' backend, delete_item delegates to meilisearch_backend."""
        mock_settings.return_value.search.backend = "meilisearch"

        with patch("fourdpocket.search.meilisearch_backend.delete_item") as mock_delete:
            mock_delete.return_value = None

            indexer = SearchIndexer(MagicMock())
            item_id = uuid.uuid4()
            indexer.delete_item(item_id)

            mock_delete.assert_called_once_with(item_id)

    @patch("fourdpocket.search.indexer.get_settings")
    def test_unknown_backend_returns_empty(self, mock_settings, db: Session, indexer_user):
        """Unknown backend returns empty list for search."""
        mock_settings.return_value.search.backend = "unknown_backend"

        indexer = SearchIndexer(db)
        results = indexer.search(
            query="test",
            user_id=indexer_user.id,
            limit=20,
            offset=0,
        )

        assert results == []
