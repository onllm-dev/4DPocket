"""Tests for enrichment_summary helpers."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.workers.enrichment_summary import (
    batch_enrichment_summary,
    summarize_stages,
)


def _stage(item_id, name, status, error=None, offset=0):
    return EnrichmentStage(
        item_id=item_id,
        stage=name,
        status=status,
        attempts=1,
        last_error=error,
        updated_at=datetime(2026, 1, 1, 12, offset, tzinfo=timezone.utc),
    )


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_summarize_empty_returns_none():
    s = summarize_stages([])
    assert s.overall == "none"
    assert s.stages == {}
    assert s.failed_stages == []


def test_summarize_all_done():
    iid = uuid.uuid4()
    rows = [
        _stage(iid, "chunked", "done"),
        _stage(iid, "embedded", "done"),
        _stage(iid, "tagged", "done"),
        _stage(iid, "summarized", "done"),
        _stage(iid, "entities_extracted", "done"),
    ]
    s = summarize_stages(rows)
    assert s.overall == "done"
    assert s.failed_stages == []


def test_summarize_skipped_counts_as_done():
    iid = uuid.uuid4()
    rows = [
        _stage(iid, "chunked", "done"),
        _stage(iid, "embedded", "skipped"),
        _stage(iid, "tagged", "done"),
        _stage(iid, "summarized", "done"),
        _stage(iid, "entities_extracted", "skipped"),
    ]
    s = summarize_stages(rows)
    assert s.overall == "done"


def test_summarize_in_flight():
    iid = uuid.uuid4()
    rows = [
        _stage(iid, "chunked", "done"),
        _stage(iid, "embedded", "running"),
        _stage(iid, "tagged", "pending"),
        _stage(iid, "summarized", "done"),
    ]
    s = summarize_stages(rows)
    assert s.overall == "processing"


def test_summarize_failed_takes_priority():
    iid = uuid.uuid4()
    rows = [
        _stage(iid, "chunked", "done"),
        _stage(iid, "embedded", "failed", error="provider timeout"),
        _stage(iid, "tagged", "running"),  # still in flight but failed wins
        _stage(iid, "summarized", "done"),
    ]
    s = summarize_stages(rows)
    assert s.overall == "failed"
    assert s.failed_stages == ["embedded"]
    assert s.last_error == "provider timeout"


def test_summarize_picks_most_recent_error():
    iid = uuid.uuid4()
    rows = [
        _stage(iid, "embedded", "failed", error="old error", offset=1),
        _stage(iid, "tagged", "failed", error="new error", offset=5),
    ]
    s = summarize_stages(rows)
    assert s.last_error == "new error"
    assert set(s.failed_stages) == {"embedded", "tagged"}


def test_synthesized_stage_is_ignored_for_overall():
    """Synthesis is entity-level, not item-level — don't block 'done' badge."""
    iid = uuid.uuid4()
    rows = [
        _stage(iid, "chunked", "done"),
        _stage(iid, "embedded", "done"),
        _stage(iid, "tagged", "done"),
        _stage(iid, "summarized", "done"),
        _stage(iid, "entities_extracted", "done"),
        _stage(iid, "synthesized", "pending"),  # not in USER_VISIBLE_STAGES
    ]
    s = summarize_stages(rows)
    assert s.overall == "done"


def test_batch_empty_returns_empty():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        assert batch_enrichment_summary(db, []) == {}


def test_batch_returns_none_for_items_without_stages(db):
    iid = uuid.uuid4()
    result = batch_enrichment_summary(db, [iid])
    assert iid in result
    assert result[iid].overall == "none"
