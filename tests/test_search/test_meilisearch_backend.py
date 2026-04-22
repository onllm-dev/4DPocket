"""Tests for MeilisearchKeywordBackend — mocked meilisearch.Client.

Patch path rationale: MeilisearchKeywordBackend (backends/meilisearch_backend.py)
lazily imports `_get_client` and `init_meilisearch` from the top-level module
`fourdpocket.search.meilisearch_backend` inside method bodies. Patching at
`fourdpocket.search.meilisearch_backend._get_client` is therefore correct — the
lazy import resolves the name at call time, not at module load time. If the
import is ever hoisted to the top of backends/meilisearch_backend.py, the patch
target must change to `fourdpocket.search.backends.meilisearch_backend._get_client`.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from fourdpocket.search.backends.meilisearch_backend import MeilisearchKeywordBackend
from fourdpocket.search.base import SearchFilters


class TestMeilisearchKeywordBackend:
    """Test MeilisearchKeywordBackend with mocked meilisearch.Client."""

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def item_id(self):
        return uuid.uuid4()

    @patch("fourdpocket.search.meilisearch_backend.init_meilisearch")
    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_index_item(self, mock_get_client, mock_init, db: Session, item_id):
        """index_item delegates to meilisearch_backend.index_item."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        # Create a minimal fake item
        class FakeItem:
            id = item_id
            user_id = uuid.uuid4()
            title = "Test Item"
            url = "https://example.com"
            description = "A description"
            content = "Content here"
            item_type = None
            source_platform = None
            is_favorite = False
            is_archived = False
            created_at = None

        backend.index_item(db, FakeItem())

        # init_meilisearch was called
        mock_init.assert_called()

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_returns_keyword_hits(self, mock_get_client, db: Session, user_id):
        """search returns KeywordHit list from Meilisearch response."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {
            "hits": [
                {
                    "id": "item-uuid-1",
                    "title": "Result Title",
                    "_formatted": {
                        "title": "<mark>Result</mark> Title",
                        "content": "matched content",
                    },
                },
                {
                    "id": "item-uuid-2",
                    "title": "Other Title",
                    "_formatted": {
                        "title": "Other Title",
                        "content": "",
                    },
                },
            ]
        }

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        results = backend.search(
            db=db,
            query="test query",
            user_id=user_id,
            filters=SearchFilters(),
            limit=20,
            offset=0,
        )

        assert len(results) == 2
        assert results[0].item_id == "item-uuid-1"
        assert results[0].title_snippet == "<mark>Result</mark> Title"
        assert results[0].content_snippet == "matched content"
        assert results[1].item_id == "item-uuid-2"

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_with_item_type_filter(self, mock_get_client, db: Session, user_id):
        """item_type filter is converted to Meilisearch filter expression."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(item_type="url"),
            limit=20,
            offset=0,
        )

        args, kwargs = mock_index.search.call_args
        # Options passed as positional second arg dict
        filter_str = args[1].get("filter", "") if len(args) > 1 else ""
        assert 'item_type = "url"' in filter_str
        assert f'user_id = "{str(user_id)}"' in filter_str

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_with_source_platform_filter(self, mock_get_client, db: Session, user_id):
        """source_platform filter is converted to Meilisearch filter."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(source_platform="youtube"),
            limit=20,
            offset=0,
        )

        args, kwargs = mock_index.search.call_args
        filter_str = args[1].get("filter", "") if len(args) > 1 else ""
        assert 'source_platform = "youtube"' in filter_str

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_with_is_favorite_filter(self, mock_get_client, db: Session, user_id):
        """is_favorite filter converts to boolean filter string."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(is_favorite=True),
            limit=20,
            offset=0,
        )

        args, kwargs = mock_index.search.call_args
        filter_str = args[1].get("filter", "") if len(args) > 1 else ""
        assert "is_favorite = true" in filter_str

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_handles_empty_response(self, mock_get_client, db: Session, user_id):
        """Empty hits list returns empty list."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        results = backend.search(
            db=db,
            query="nothing",
            user_id=user_id,
            filters=SearchFilters(),
            limit=20,
            offset=0,
        )

        assert results == []

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_delete_item(self, mock_get_client, db: Session, item_id):
        """delete_item calls meilisearch_backend.delete_item and chunk deletion."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.delete_item(db, item_id)

        # Chunk index deletion should be attempted
        mock_client.index.assert_any_call("knowledge_chunks")

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_index_chunks(self, mock_get_client, db: Session, user_id, item_id):
        """index_chunks creates chunk documents in knowledge_chunks index."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        class FakeChunk:
            id = uuid.uuid4()
            text = "Test chunk content"
            chunk_order = 0
            section_kind = None
            section_role = None
            author = None
            is_accepted_answer = False

        backend.index_chunks(
            db=db,
            item_id=item_id,
            user_id=user_id,
            chunks=[FakeChunk()],
            title="Test Item",
            url="https://example.com",
        )

        mock_client.create_index.assert_any_call("knowledge_chunks", {"primaryKey": "id"})
        mock_index.add_documents.assert_called()

    # === PHASE 1A MOPUP ADDITIONS ===

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_index_chunks_section_provenance(self, mock_get_client, db: Session, user_id, item_id):
        """index_chunks includes section_kind, section_role, author, is_accepted_answer when present."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        class FakeChunk:
            id = uuid.uuid4()
            text = "Answer text"
            chunk_order = 0
            section_kind = "answer"
            section_role = "accepted"
            author = "alice"
            is_accepted_answer = True

        backend.index_chunks(
            db=db,
            item_id=item_id,
            user_id=user_id,
            chunks=[FakeChunk()],
            title="Question Title",
            url="https://example.com/q",
        )

        # Verify add_documents was called with section provenance fields
        args, _ = mock_index.add_documents.call_args
        docs = args[0]
        assert len(docs) == 1
        assert docs[0]["section_kind"] == "answer"
        assert docs[0]["section_role"] == "accepted"
        assert docs[0]["author"] == "alice"
        assert docs[0]["is_accepted_answer"] is True

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_with_is_archived_filter(self, mock_get_client, db: Session, user_id):
        """is_archived filter is correctly included in Meilisearch filter expression."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(is_archived=True),
            limit=20,
            offset=0,
        )

        args, kwargs = mock_index.search.call_args
        filter_str = args[1].get("filter", "") if len(args) > 1 else ""
        assert "is_archived = true" in filter_str

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_with_multiple_filters_combined(self, mock_get_client, db: Session, user_id):
        """Multiple filters are combined with AND in Meilisearch filter string."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(item_type="url", source_platform="web", is_favorite=False),
            limit=20,
            offset=0,
        )

        args, kwargs = mock_index.search.call_args
        filter_str = args[1].get("filter", "") if len(args) > 1 else ""
        assert 'item_type = "url"' in filter_str
        assert 'source_platform = "web"' in filter_str
        assert "is_favorite = false" in filter_str
        # All joined by AND
        assert " AND " in filter_str

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_highlight_options(self, mock_get_client, db: Session, user_id):
        """Meilisearch search includes correct highlight options."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="highlight me",
            user_id=user_id,
            filters=SearchFilters(),
            limit=20,
            offset=0,
        )

        args, kwargs = mock_index.search.call_args
        opts = args[1] if len(args) > 1 else kwargs
        assert "attributesToHighlight" in opts
        assert "highlightPreTag" in opts
        assert "highlightPostTag" in opts

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_handles_missing_formatted(self, mock_get_client, db: Session, user_id):
        """search falls back to raw title when _formatted is absent."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {
            "hits": [
                {"id": "item-1", "title": "Plain Title"},
            ]
        }

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        results = backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(),
            limit=20,
            offset=0,
        )

        assert len(results) == 1
        assert results[0].title_snippet == "Plain Title"

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_search_respects_offset(self, mock_get_client, db: Session, user_id):
        """Meilisearch search is called with the correct offset."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index
        mock_index.search.return_value = {"hits": []}

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        backend.search(
            db=db,
            query="test",
            user_id=user_id,
            filters=SearchFilters(),
            limit=10,
            offset=20,
        )

        args, kwargs = mock_index.search.call_args
        opts = args[1] if len(args) > 1 else kwargs
        assert opts["offset"] == 20

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_delete_item_raises_on_client_error(self, mock_get_client, db: Session, item_id):
        """delete_item silently handles client errors without raising."""
        mock_client = MagicMock()
        mock_client.index.return_value.delete_documents.side_effect = Exception("Client error")
        mock_get_client.return_value = mock_client

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        # Should not raise
        backend.delete_item(db, item_id)

    @patch("fourdpocket.search.meilisearch_backend._get_client")
    def test_index_chunks_omits_null_provenance_fields(self, mock_get_client, db: Session, user_id, item_id):
        """index_chunks omits section fields from doc when chunk has no values."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_index = MagicMock()
        mock_client.index.return_value = mock_index

        backend = MeilisearchKeywordBackend()
        backend.init(db)

        class FakeChunk:
            id = uuid.uuid4()
            text = "Plain chunk"
            chunk_order = 0
            section_kind = None
            section_role = None
            author = None
            is_accepted_answer = False

        backend.index_chunks(
            db=db,
            item_id=item_id,
            user_id=user_id,
            chunks=[FakeChunk()],
            title="Title",
            url="https://example.com",
        )

        args, _ = mock_index.add_documents.call_args
        docs = args[0]
        assert "section_kind" not in docs[0]
        assert "section_role" not in docs[0]
        assert "author" not in docs[0]
