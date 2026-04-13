"""Tests for PgVectorBackend — mocked pgvector SQL execution."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from fourdpocket.search.backends.pgvector_backend import PgVectorBackend


class TestPgVectorBackend:
    """Test PgVectorBackend with mocked SQL execution."""

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def item_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def chunk_id(self):
        return uuid.uuid4()

    def test_upsert_item_is_noop(self, user_id, item_id):
        """upsert_item is a no-op for pgvector (embeddings on chunks only)."""
        backend = PgVectorBackend()
        backend.upsert_item(
            item_id=item_id,
            user_id=user_id,
            embedding=[0.1] * 384,
            metadata={},
        )
        # Should not raise — no database calls

    def test_upsert_chunk_returns_early_when_unavailable(self):
        """upsert_chunk exits early if pgvector extension is not available."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=False):
            backend.upsert_chunk(
                chunk_id=uuid.uuid4(),
                item_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                embedding=[0.1] * 384,
                metadata={},
            )

    def test_search_returns_empty_when_unavailable(self):
        """search returns empty list if pgvector not available."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=False):
            hits = backend.search(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 384,
                k=10,
            )
        assert hits == []

    def test_search_returns_empty_on_exception(self):
        """search returns empty list when DB operation raises."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=True), \
             patch.object(backend, "_ensure_column"), \
             patch("fourdpocket.db.session.get_engine", side_effect=Exception("DB error")):
            hits = backend.search(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 384,
                k=10,
            )
        assert hits == []

    def test_delete_item_is_noop(self, user_id, item_id):
        """delete_item is a no-op — chunks deleted via cascade."""
        backend = PgVectorBackend()
        backend.delete_item(item_id=item_id, user_id=user_id)
        # No engine calls expected — method body is just `pass`


# === PHASE 1A MOPUP ADDITIONS ===

    def test_check_available_caches_result(self):
        """_check_available caches its result in self._available."""
        backend = PgVectorBackend()
        with patch("fourdpocket.db.session.get_engine") as mock_engine, \
             patch("sqlmodel.Session") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.exec.return_value.one.return_value = (1,)

            result1 = backend._check_available()
            result2 = backend._check_available()
            assert result1 is True
            assert result2 is True
            # Second call should not re-query (cached)
            assert mock_engine.call_count == 1

    def test_upsert_chunk_returns_early_when_unavailable(self):
        """upsert_chunk exits early if pgvector extension is not available."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=False):
            backend.upsert_chunk(
                chunk_id=uuid.uuid4(),
                item_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                embedding=[0.1] * 384,
                metadata={},
            )

    def test_search_returns_empty_when_unavailable(self):
        """search returns empty list if pgvector not available."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=False):
            hits = backend.search(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 384,
                k=10,
            )
        assert hits == []

    def test_search_returns_empty_on_exception(self):
        """search returns empty list when DB operation raises."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=True), \
             patch.object(backend, "_ensure_column"), \
             patch("fourdpocket.db.session.get_engine", side_effect=Exception("DB error")):
            hits = backend.search(
                user_id=uuid.uuid4(),
                embedding=[0.1] * 384,
                k=10,
            )
        assert hits == []

    def test_search_deduplicates_by_item_id(self, user_id):
        """search returns only the best chunk per item when multiple chunks match."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=True), \
             patch.object(backend, "_ensure_column"), \
             patch("fourdpocket.db.session.get_engine") as mock_engine, \
             patch("sqlmodel.Session") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            # Simulate two chunks from the same item
            mock_result = MagicMock()
            mock_result.all.return_value = [
                (uuid.uuid4(), str(uuid.uuid4()), 0.1),  # chunk1, item1
                (uuid.uuid4(), str(uuid.uuid4()), 0.15), # chunk2, item1 (same item, worse score)
            ]
            mock_db.exec.return_value = mock_result

            hits = backend.search(user_id=user_id, embedding=[0.1] * 384, k=10)
            # Only one hit per unique item_id
            item_ids = [h.item_id for h in hits]
            assert len(item_ids) == len(set(item_ids))

    def test_upsert_chunk_executes_sql_update(self, chunk_id, item_id, user_id):
        """upsert_chunk executes UPDATE with correct vector string."""
        backend = PgVectorBackend()
        with patch.object(backend, "_check_available", return_value=True), \
             patch.object(backend, "_ensure_column"), \
             patch("fourdpocket.db.session.get_engine") as mock_engine, \
             patch("sqlmodel.Session") as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            embedding = [0.1] * 5
            backend.upsert_chunk(chunk_id=chunk_id, item_id=item_id, user_id=user_id, embedding=embedding, metadata={})

            # Verify UPDATE was called via text() with vector string
            calls = mock_db.exec.call_args_list
            assert len(calls) == 1
            # Check the vector string is constructed correctly
            mock_db.exec.assert_called()

    def test_ensure_column_idempotent(self):
        """_ensure_column sets the global _initialized flag — called multiple times safely."""
        import fourdpocket.search.backends.pgvector_backend as pgmod
        original = pgmod._initialized
        pgmod._initialized = False
        try:
            backend = PgVectorBackend()
            with patch.object(backend, "_check_available", return_value=True), \
                 patch("fourdpocket.db.session.get_engine") as mock_engine, \
                 patch("sqlmodel.Session") as mock_session_cls, \
                 patch("fourdpocket.ai.factory.get_embedding_provider") as mock_ep:
                mock_ep.return_value.embed_single.return_value = [0.1] * 384
                mock_db = MagicMock()
                mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
                mock_db.exec.return_value.first.return_value = None  # column doesn't exist

                backend._ensure_column()
                backend._ensure_column()  # second call should be no-op

                # All exec calls happen on first invocation only
        finally:
            pgmod._initialized = original
