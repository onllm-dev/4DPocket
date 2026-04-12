"""Tests for the enrichment pipeline stage management."""

import uuid

import pytest
from sqlmodel import Session, select

from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.workers.enrichment_pipeline import (
    _deps_satisfied,
    _get_or_create_stage,
    _mark_done,
    _mark_failed,
    _mark_running,
    _mark_skipped,
    handle_chunking,
)


@pytest.fixture
def enrich_user(db: Session):
    user = User(
        email="enrichtest@example.com",
        username="enrichuser",
        password_hash="$2b$12$fakehash",
        display_name="Enrich Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def enrich_item(db: Session, enrich_user):
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="Enrichment Pipeline Test Article",
        content=(
            "Machine learning is transforming software engineering. "
            "Large language models can generate code, debug issues, and write tests.\n\n"
            "Retrieval augmented generation helps ground LLM outputs in facts. "
            "This reduces hallucination and improves accuracy significantly."
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class TestStageManagement:
    def test_get_or_create_stage(self, db: Session, enrich_item):
        stage = _get_or_create_stage(db, enrich_item.id, "chunked")
        assert stage.item_id == enrich_item.id
        assert stage.stage == "chunked"
        assert stage.status == "pending"
        assert stage.attempts == 0

    def test_get_existing_stage(self, db: Session, enrich_item):
        s1 = _get_or_create_stage(db, enrich_item.id, "tagged")
        s2 = _get_or_create_stage(db, enrich_item.id, "tagged")
        assert s1.item_id == s2.item_id
        assert s1.stage == s2.stage

    def test_mark_running(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "chunked")
        _mark_running(db, enrich_item.id, "chunked")

        stage = db.exec(
            select(EnrichmentStage).where(
                EnrichmentStage.item_id == enrich_item.id,
                EnrichmentStage.stage == "chunked",
            )
        ).first()
        assert stage.status == "running"
        assert stage.attempts == 1
        assert stage.started_at is not None

    def test_mark_done(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "tagged")
        _mark_done(db, enrich_item.id, "tagged")

        stage = db.exec(
            select(EnrichmentStage).where(
                EnrichmentStage.item_id == enrich_item.id,
                EnrichmentStage.stage == "tagged",
            )
        ).first()
        assert stage.status == "done"
        assert stage.finished_at is not None

    def test_mark_failed(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "embedded")
        _mark_failed(db, enrich_item.id, "embedded", "Connection refused")

        stage = db.exec(
            select(EnrichmentStage).where(
                EnrichmentStage.item_id == enrich_item.id,
                EnrichmentStage.stage == "embedded",
            )
        ).first()
        assert stage.status == "failed"
        assert stage.last_error == "Connection refused"

    def test_mark_skipped(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "entities_extracted")
        _mark_skipped(db, enrich_item.id, "entities_extracted")

        stage = db.exec(
            select(EnrichmentStage).where(
                EnrichmentStage.item_id == enrich_item.id,
                EnrichmentStage.stage == "entities_extracted",
            )
        ).first()
        assert stage.status == "skipped"


class TestDependencies:
    def test_no_deps_satisfied(self, db: Session, enrich_item):
        # Stages without deps should always be satisfied
        assert _deps_satisfied(db, enrich_item.id, "chunked") is True
        assert _deps_satisfied(db, enrich_item.id, "tagged") is True
        assert _deps_satisfied(db, enrich_item.id, "summarized") is True

    def test_deps_not_met(self, db: Session, enrich_item):
        # "embedded" depends on "chunked" which hasn't been created
        assert _deps_satisfied(db, enrich_item.id, "embedded") is False

    def test_deps_met_after_done(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "chunked")
        _mark_done(db, enrich_item.id, "chunked")
        assert _deps_satisfied(db, enrich_item.id, "embedded") is True

    def test_deps_met_after_skipped(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "chunked")
        _mark_skipped(db, enrich_item.id, "chunked")
        assert _deps_satisfied(db, enrich_item.id, "embedded") is True

    def test_deps_not_met_when_failed(self, db: Session, enrich_item):
        _get_or_create_stage(db, enrich_item.id, "chunked")
        _mark_failed(db, enrich_item.id, "chunked", "error")
        assert _deps_satisfied(db, enrich_item.id, "embedded") is False


class TestHandleChunking:
    def test_chunks_created(self, db: Session, enrich_item, enrich_user):
        handle_chunking(db, enrich_item.id, enrich_user.id)

        from fourdpocket.models.item_chunk import ItemChunk

        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item.id)
        ).all()
        assert len(chunks) >= 1
        for c in chunks:
            assert c.text.strip()
            assert c.user_id == enrich_user.id

    def test_chunking_idempotent(self, db: Session, enrich_item, enrich_user):
        handle_chunking(db, enrich_item.id, enrich_user.id)
        handle_chunking(db, enrich_item.id, enrich_user.id)

        from fourdpocket.models.item_chunk import ItemChunk

        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item.id)
        ).all()
        # Should not double the chunks
        assert len(chunks) >= 1
        orders = [c.chunk_order for c in chunks]
        assert len(orders) == len(set(orders)), "Duplicate chunk orders"


class TestEnrichmentEndpoint:
    def test_enrichment_status_empty(self, client, auth_headers):
        # Create an item first
        resp = client.post(
            "/api/v1/items",
            json={"title": "Test Enrichment Status", "content": "Some content."},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        item_id = resp.json()["id"]

        # Get enrichment status (should be empty for items without enrichment)
        resp = client.get(f"/api/v1/items/{item_id}/enrichment", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_enrichment_status_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/items/{fake_id}/enrichment", headers=auth_headers)
        assert resp.status_code == 404

    def test_enrichment_status_user_scoped(self, client, auth_headers, second_user_headers):
        resp = client.post(
            "/api/v1/items",
            json={"title": "Scoped Item", "content": "Content."},
            headers=auth_headers,
        )
        item_id = resp.json()["id"]

        # Other user should get 404
        resp = client.get(f"/api/v1/items/{item_id}/enrichment", headers=second_user_headers)
        assert resp.status_code == 404
