"""Tests for enrichment_summary helpers."""

import uuid

import pytest
from sqlmodel import Session, select

from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.workers.enrichment_summary import (
    USER_VISIBLE_STAGES,
    batch_enrichment_summary,
    queue_stats,
    summarize_stages,
)

# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sum_user(db: Session):
    user = User(
        email="sumtest@example.com",
        username="sumuser",
        password_hash="$2b$12$fakehash",
        display_name="Summary Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sum_item(db: Session, sum_user):
    item = KnowledgeItem(
        user_id=sum_user.id,
        title="Summary Test Item",
        content="Content for summary testing.",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _stage(
    db: Session,
    item_id: uuid.UUID,
    stage: str,
    status: str,
    error: str | None = None,
):
    row = EnrichmentStage(
        item_id=item_id,
        stage=stage,
        status=status,
        last_error=error,
    )
    db.add(row)
    db.commit()
    return row


# ─── summarize_stages ────────────────────────────────────────────────────────

class TestSummarizeStages:
    """Cover lines 25-70."""

    def test_no_stages_returns_none(self, db: Session, sum_item):
        """Line 38-44: no stages → overall='none'."""
        result = summarize_stages([])
        assert result.overall == "none"
        assert result.stages == {}
        assert result.failed_stages == []
        assert result.last_error is None

    def test_all_done(self, db: Session, sum_item):
        """Line 60-61: all stages done/skipped → overall='done'."""
        for stage in USER_VISIBLE_STAGES:
            _stage(db, sum_item.id, stage, "done")
        result = summarize_stages(
            db.exec(
                select(EnrichmentStage).where(
                    EnrichmentStage.item_id == sum_item.id
                )
            ).all()
        )
        assert result.overall == "done"

    def test_any_failed_wins(self, db: Session, sum_item):
        """Lines 50-57: any failed stage → overall='failed', last_error set."""
        _stage(db, sum_item.id, "chunked", "done")
        _stage(db, sum_item.id, "embedded", "failed", error="Embedding timeout")
        _stage(db, sum_item.id, "tagged", "done")
        stages = db.exec(
            select(EnrichmentStage).where(EnrichmentStage.item_id == sum_item.id)
        ).all()
        result = summarize_stages(stages)
        assert result.overall == "failed"
        assert "embedded" in result.failed_stages
        assert result.last_error == "Embedding timeout"

    def test_any_pending_or_running(self, db: Session, sum_item):
        """Lines 58-59: pending/running → overall='processing'."""
        _stage(db, sum_item.id, "chunked", "done")
        _stage(db, sum_item.id, "embedded", "pending")
        stages = db.exec(
            select(EnrichmentStage).where(EnrichmentStage.item_id == sum_item.id)
        ).all()
        result = summarize_stages(stages)
        assert result.overall == "processing"

    def test_running_overrides_pending(self, db: Session, sum_item):
        """Lines 58-59: running still counts as processing (same bucket)."""
        _stage(db, sum_item.id, "chunked", "running")
        _stage(db, sum_item.id, "tagged", "pending")
        stages = db.exec(
            select(EnrichmentStage).where(EnrichmentStage.item_id == sum_item.id)
        ).all()
        result = summarize_stages(stages)
        assert result.overall == "processing"

    def test_defensive_unknown_status(self, db: Session, sum_item):
        """Line 63: unknown status falls through to 'processing' defensive case."""
        # Create a stage with a status not in ("done","skipped","pending","running","failed")
        row = EnrichmentStage(
            item_id=sum_item.id,
            stage="chunked",
            status="done",
        )
        db.add(row)
        db.commit()
        # Override the status directly in DB to simulate edge case
        db.exec(
            select(EnrichmentStage)
            .where(EnrichmentStage.item_id == sum_item.id)
        )
        # Manually patch a row to have unknown status via direct update
        from sqlalchemy import update

        from fourdpocket.models.enrichment import EnrichmentStage as ES

        db.exec(
            update(ES)
            .where(ES.item_id == sum_item.id, ES.stage == "chunked")
            .values(status="unknown_status_xyz")
        )
        db.commit()

        stages = db.exec(
            select(EnrichmentStage).where(EnrichmentStage.item_id == sum_item.id)
        ).all()
        # summarize_stages iterates USER_VISIBLE_STAGES, so chunked row will be found
        # The else branch at line 62-63 handles it
        result = summarize_stages(stages)
        assert result.overall == "processing"

    def test_synthesized_stage_ignored(self, db: Session, sum_item):
        """Lines 19-22: synthesized stage is not included in user-visible stages."""
        _stage(db, sum_item.id, "chunked", "done")
        _stage(db, sum_item.id, "synthesized", "running")  # should be ignored
        stages = db.exec(
            select(EnrichmentStage).where(EnrichmentStage.item_id == sum_item.id)
        ).all()
        result = summarize_stages(stages)
        # Only chunked counts; synthesized (even though running) is filtered out
        assert result.overall == "done"
        assert "synthesized" not in result.stages


# ─── batch_enrichment_summary ─────────────────────────────────────────────────

class TestBatchEnrichmentSummary:
    """Cover lines 73-91."""

    def test_empty_list(self, db: Session):
        """Line 80-81: empty item_ids → empty dict."""
        result = batch_enrichment_summary(db, [])
        assert result == {}

    def test_item_with_no_stages(self, db: Session, sum_item):
        """Line 91: items without any stage rows get 'none' summary."""
        result = batch_enrichment_summary(db, [sum_item.id])
        assert sum_item.id in result
        assert result[sum_item.id].overall == "none"

    def test_multiple_items(self, db: Session, sum_user):
        """Lines 83-91: batch returns dict for each item."""
        item_a = KnowledgeItem(
            user_id=sum_user.id, title="Item A", content="A content"
        )
        item_b = KnowledgeItem(
            user_id=sum_user.id, title="Item B", content="B content"
        )
        db.add_all([item_a, item_b])
        db.commit()

        _stage(db, item_a.id, "chunked", "done")
        _stage(db, item_b.id, "embedded", "failed", error="err")

        result = batch_enrichment_summary(db, [item_a.id, item_b.id])
        assert len(result) == 2
        assert result[item_a.id].overall == "done"
        assert result[item_b.id].overall == "failed"
        assert result[item_b.id].last_error == "err"

    def test_stage_rows_join(self, db: Session, sum_item):
        """Line 89: multiple rows for same item are grouped correctly."""
        _stage(db, sum_item.id, "chunked", "done")
        _stage(db, sum_item.id, "tagged", "done")
        _stage(db, sum_item.id, "embedded", "pending")
        result = batch_enrichment_summary(db, [sum_item.id])
        summary = result[sum_item.id]
        assert summary.overall == "processing"
        assert summary.stages["chunked"] == "done"
        assert summary.stages["tagged"] == "done"
        assert summary.stages["embedded"] == "pending"


# ─── queue_stats ──────────────────────────────────────────────────────────────

class TestQueueStats:
    """Cover lines 94-124."""

    def test_queue_stats_empty(self, db: Session, sum_user):
        """Lines 100-124: no in-flight work → all zeros."""
        result = queue_stats(db, sum_user.id)
        assert result["items_in_flight"] == 0
        assert result["running_items"] == 0
        assert result["pending_items"] == 0

    def test_queue_stats_pending(self, db: Session, sum_user, sum_item):
        """Lines 112-115: pending items counted correctly."""
        _stage(db, sum_item.id, "chunked", "pending")
        _stage(db, sum_item.id, "embedded", "pending")
        result = queue_stats(db, sum_user.id)
        assert result["pending_items"] == 1  # same item, multiple pending stages
        assert result["running_items"] == 0

    def test_queue_stats_running(self, db: Session, sum_user, sum_item):
        """Lines 112-113: running items counted correctly."""
        _stage(db, sum_item.id, "chunked", "running")
        result = queue_stats(db, sum_user.id)
        assert result["running_items"] == 1
        assert result["pending_items"] == 0

    def test_queue_stats_dedup(self, db: Session, sum_user):
        """Line 118: pending + running on same item is de-duplicated."""
        item = KnowledgeItem(
            user_id=sum_user.id, title="Dedup Item", content="..."
        )
        db.add(item)
        db.commit()
        _stage(db, item.id, "chunked", "running")
        _stage(db, item.id, "embedded", "pending")
        result = queue_stats(db, sum_user.id)
        # Same item, should only count once in total
        assert result["items_in_flight"] == 1

    def test_queue_stats_other_user_not_counted(
        self, db: Session, sum_user, sum_item
    ):
        """Line 105: queue_stats is user-scoped."""
        other_user = User(
            email="other@example.com",
            username="otheruser",
            password_hash="$2b$12$fakehash",
            display_name="Other",
        )
        db.add(other_user)
        db.commit()

        other_item = KnowledgeItem(
            user_id=other_user.id, title="Other Item", content="..."
        )
        db.add(other_item)
        db.commit()

        _stage(db, other_item.id, "chunked", "running")

        result = queue_stats(db, sum_user.id)
        assert result["items_in_flight"] == 0  # sum_user has no in-flight items
