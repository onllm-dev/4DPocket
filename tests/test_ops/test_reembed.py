"""Tests for embed reindex operation.

Regression tests for: dry-run reports counts without mutating,
--user filter scopes to one user, dimension mismatch path.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def reembed_db(engine):
    """Create users and items in an in-memory DB for reembed tests."""
    from sqlmodel import Session

    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.models.item_chunk import ItemChunk
    from fourdpocket.models.user import User

    with Session(engine) as db:
        user1 = User(
            email="alice@example.com",
            username="alice",
            password_hash="$2b$12$fakehash",
            display_name="Alice",
        )
        user2 = User(
            email="bob@example.com",
            username="bob",
            password_hash="$2b$12$fakehash",
            display_name="Bob",
        )
        db.add(user1)
        db.add(user2)
        db.commit()
        db.refresh(user1)
        db.refresh(user2)

        item1 = KnowledgeItem(user_id=user1.id, title="Alice item")
        item2 = KnowledgeItem(user_id=user2.id, title="Bob item")
        db.add(item1)
        db.add(item2)
        db.commit()
        db.refresh(item1)
        db.refresh(item2)

        chunk1 = ItemChunk(
            item_id=item1.id,
            user_id=user1.id,
            text="Alice chunk text",
            chunk_order=0,
            embedding_model="OldModel",
        )
        chunk2 = ItemChunk(
            item_id=item2.id,
            user_id=user2.id,
            text="Bob chunk text",
            chunk_order=0,
            embedding_model="OldModel",
        )
        db.add(chunk1)
        db.add(chunk2)
        db.commit()

        return {
            "engine": engine,
            "user1": user1,
            "user2": user2,
            "item1": item1,
            "item2": item2,
        }


# ─── Dry run: no mutations ────────────────────────────────────────────────────


class TestReembedDryRun:
    def test_dry_run_returns_counts_without_mutating(self, reembed_db, monkeypatch):
        """--dry-run should report item count but not enqueue or clear embeddings."""
        from fourdpocket.ops import reembed as reembed_mod

        enqueued = []

        monkeypatch.setattr(
            "fourdpocket.ops.reembed._enqueue_embedding",
            lambda item_id, user_id: enqueued.append(item_id),
        )
        monkeypatch.setattr(
            "fourdpocket.ops.reembed._clear_embeddings_for_user",
            lambda user_id, vector_backend, db: (_ for _ in ()).throw(
                AssertionError("Should not clear embeddings in dry-run")
            ),
        )

        result = reembed_mod.run_reembed(
            engine=reembed_db["engine"],
            user_email=None,
            dry_run=True,
            vector_backend="chroma",
        )

        assert enqueued == [], "dry-run must not enqueue tasks"
        assert result["total_items"] == 2
        assert result["dry_run"] is True

    def test_dry_run_user_filter(self, reembed_db, monkeypatch):
        """--dry-run with --user EMAIL only counts that user's items."""
        from fourdpocket.ops import reembed as reembed_mod

        monkeypatch.setattr(
            "fourdpocket.ops.reembed._enqueue_embedding",
            lambda item_id, user_id: None,
        )
        monkeypatch.setattr(
            "fourdpocket.ops.reembed._clear_embeddings_for_user",
            lambda user_id, vector_backend, db: None,
        )

        result = reembed_mod.run_reembed(
            engine=reembed_db["engine"],
            user_email="alice@example.com",
            dry_run=True,
            vector_backend="chroma",
        )

        assert result["total_items"] == 1


# ─── Live run: enqueues and clears ────────────────────────────────────────────


class TestReembedLiveRun:
    def test_live_run_enqueues_all_items(self, reembed_db, monkeypatch):
        """Live run enqueues embedding tasks for all affected items."""
        from fourdpocket.ops import reembed as reembed_mod

        enqueued = []
        cleared = []

        monkeypatch.setattr(
            "fourdpocket.ops.reembed._enqueue_embedding",
            lambda item_id, user_id: enqueued.append(str(item_id)),
        )
        monkeypatch.setattr(
            "fourdpocket.ops.reembed._clear_embeddings_for_user",
            lambda user_id, vector_backend, db: cleared.append(str(user_id)),
        )

        result = reembed_mod.run_reembed(
            engine=reembed_db["engine"],
            user_email=None,
            dry_run=False,
            vector_backend="chroma",
        )

        assert result["total_items"] == 2
        assert len(enqueued) == 2
        assert len(cleared) == 2  # one clear per user

    def test_live_run_user_filter_only_clears_that_user(self, reembed_db, monkeypatch):
        """Live run with --user EMAIL only clears and re-enqueues for that user."""
        from fourdpocket.ops import reembed as reembed_mod

        enqueued = []
        cleared = []

        monkeypatch.setattr(
            "fourdpocket.ops.reembed._enqueue_embedding",
            lambda item_id, user_id: enqueued.append(str(item_id)),
        )
        monkeypatch.setattr(
            "fourdpocket.ops.reembed._clear_embeddings_for_user",
            lambda user_id, vector_backend, db: cleared.append(str(user_id)),
        )

        result = reembed_mod.run_reembed(
            engine=reembed_db["engine"],
            user_email="bob@example.com",
            dry_run=False,
            vector_backend="chroma",
        )

        assert result["total_items"] == 1
        assert len(enqueued) == 1
        assert len(cleared) == 1


# ─── User not found ───────────────────────────────────────────────────────────


class TestReembedUserNotFound:
    def test_exits_when_user_not_found(self, reembed_db):
        """run_reembed raises SystemExit when --user EMAIL doesn't match any user."""
        from fourdpocket.ops import reembed as reembed_mod

        with pytest.raises(SystemExit) as exc:
            reembed_mod.run_reembed(
                engine=reembed_db["engine"],
                user_email="nobody@example.com",
                dry_run=True,
                vector_backend="chroma",
            )
        assert exc.value.code != 0
