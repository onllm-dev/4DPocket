"""Tests for the enrichment pipeline stage management."""

import uuid
from unittest.mock import MagicMock

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
def enrich_user_p1(db: Session):
    user = User(
        email="enrichtest_p1@example.com",
        username="enrichuserp1",
        password_hash="$2b$12$fakehash",
        display_name="Enrich Test User P1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def enrich_item(db: Session, enrich_user_p1):
    item = KnowledgeItem(
        user_id=enrich_user_p1.id,
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
    def test_chunks_created(self, db: Session, enrich_item):
        handle_chunking(db, enrich_item.id, enrich_item.user_id)

        from fourdpocket.models.item_chunk import ItemChunk

        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item.id)
        ).all()
        assert len(chunks) >= 1
        for c in chunks:
            assert c.text.strip()
            assert c.user_id == enrich_item.user_id

    def test_chunking_idempotent(self, db: Session, enrich_item):
        handle_chunking(db, enrich_item.id, enrich_item.user_id)
        handle_chunking(db, enrich_item.id, enrich_item.user_id)

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


# === PHASE 2B MOPUP ADDITIONS ===

class TestHandleEmbedding:
    """Test the handle_embedding stage handler."""

    def test_handle_embedding_with_metadata(self, db: Session, enrich_user, monkeypatch):
        """Item with title+description+content → all in embed_parts."""
        # Create item with description (enrich_item fixture doesn't set it)
        item = KnowledgeItem(
            user_id=enrich_user.id,
            title="Test Article Title",
            description="This is a test description.",
            content="This is the main content of the article.",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 384
        mock_provider.__class__.__name__ = "MockEmbeddingProvider"
        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: mock_provider)
        monkeypatch.setattr("fourdpocket.search.semantic.add_embedding", lambda *a, **kw: None)

        from fourdpocket.workers.enrichment_pipeline import handle_embedding
        handle_embedding(db, item.id, enrich_user.id)

        # Verify embed_single was called with text combining title + description + content
        mock_provider.embed_single.assert_called_once()
        call_arg = mock_provider.embed_single.call_args[0][0]
        assert item.title in call_arg
        assert item.description in call_arg
        assert item.content[:5000] in call_arg


class TestHandleEntityExtraction:
    """Test the handle_entity_extraction stage handler."""

    def test_handle_entity_extraction_no_chunks(self, db: Session, enrich_item, enrich_user, monkeypatch):
        """No chunks → fallback to item content for entity extraction."""
        from fourdpocket.ai.extractor import ExtractionResult

        mock_result = ExtractionResult(entities=[], relations=[])
        mock_extractor = MagicMock(return_value=mock_result)
        monkeypatch.setattr("fourdpocket.ai.extractor.extract_entities", mock_extractor)
        monkeypatch.setattr("fourdpocket.ai.llm_cache.get_cached_response", lambda *a: None)
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: MagicMock(enrichment=MagicMock(
            extract_entities=True,
            max_entities_per_chunk=10,
            max_relations_per_chunk=10,
        )))

        # Ensure no chunks exist
        from sqlmodel import select

        from fourdpocket.models.item_chunk import ItemChunk
        from fourdpocket.workers.enrichment_pipeline import handle_entity_extraction
        existing = db.exec(select(ItemChunk).where(ItemChunk.item_id == enrich_item.id)).all()
        for c in existing:
            db.delete(c)
        db.commit()

        handle_entity_extraction(db, enrich_item.id, enrich_user.id)

        # Should have called extract_entities with item content fallback
        mock_extractor.assert_called_once()

    def test_handle_entity_extraction_cache_hit(self, db: Session, enrich_item, enrich_user, monkeypatch):
        """get_cached_response returns data → no extraction call."""
        cached_data = {
            "entities": [{"name": "Test Entity", "type": "person", "description": "A test"}],
            "relations": [],
        }
        monkeypatch.setattr("fourdpocket.ai.llm_cache.get_cached_response", lambda *a: cached_data)
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: MagicMock(enrichment=MagicMock(
            extract_entities=True,
            max_entities_per_chunk=10,
            max_relations_per_chunk=10,
        )))

        mock_extractor = MagicMock()
        monkeypatch.setattr("fourdpocket.ai.extractor.extract_entities", mock_extractor)

        from fourdpocket.workers.enrichment_pipeline import handle_entity_extraction
        handle_entity_extraction(db, enrich_item.id, enrich_user.id)

        # Should NOT call extract_entities due to cache hit
        mock_extractor.assert_not_called()


class TestHandleSynthesis:
    """Test the handle_synthesis stage handler."""

    def test_handle_synthesis_disabled(self, db: Session, enrich_item, enrich_user, monkeypatch):
        """synthesis_enabled=False → early return."""
        mock_settings = MagicMock()
        mock_settings.enrichment.synthesis_enabled = False
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        from fourdpocket.workers.enrichment_pipeline import handle_synthesis
        # Should return early without error
        handle_synthesis(db, enrich_item.id, enrich_user.id)


class TestRunStage:
    """Test the run_enrichment_stage Huey task."""

    def test_run_stage_already_done(self, db: Session, enrich_item, enrich_user, engine, monkeypatch):
        """Stage status='done' → returns already_done."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        from fourdpocket.models.enrichment import EnrichmentStage
        es = EnrichmentStage(item_id=enrich_item.id, stage="tagged", status="done")
        db.add(es)
        db.commit()

        from fourdpocket.workers.enrichment_pipeline import run_enrichment_stage
        result = run_enrichment_stage.call_local(str(enrich_item.id), str(enrich_user.id), "tagged")
        assert result["status"] == "already_done"

    def test_run_stage_deps_not_met(self, db: Session, enrich_item, enrich_user, engine, monkeypatch):
        """Dependent stage still pending → deps_not_met."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        from fourdpocket.models.enrichment import EnrichmentStage
        # chunked exists but is still pending, not done
        es = EnrichmentStage(item_id=enrich_item.id, stage="chunked", status="pending")
        db.add(es)
        db.commit()

        from fourdpocket.workers.enrichment_pipeline import run_enrichment_stage
        # embedded depends on chunked, which is pending
        result = run_enrichment_stage.call_local(str(enrich_item.id), str(enrich_user.id), "embedded")
        assert result["status"] == "deps_not_met"

    def test_run_stage_unknown(self, db: Session, enrich_item, enrich_user, engine, monkeypatch):
        """Unknown stage name → skipped."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        from fourdpocket.workers.enrichment_pipeline import run_enrichment_stage
        result = run_enrichment_stage.call_local(str(enrich_item.id), str(enrich_user.id), "nonexistent_stage")
        assert result["status"] == "skipped"

    def test_run_stage_handler_exception(self, db: Session, enrich_item, enrich_user, engine, monkeypatch):
        """Handler raises → rollback + mark_failed."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        def bad_handler(*a, **kw):
            raise RuntimeError("AI failed")

        # Patch the dict entry directly since STAGE_HANDLERS is a module-level dict
        import fourdpocket.workers.enrichment_pipeline as ep_module
        original_handler = ep_module.STAGE_HANDLERS["tagged"]
        ep_module.STAGE_HANDLERS["tagged"] = bad_handler
        try:
            from fourdpocket.workers.enrichment_pipeline import run_enrichment_stage
            # The function raises after marking failed, so catch the exception
            try:
                run_enrichment_stage.call_local(str(enrich_item.id), str(enrich_user.id), "tagged")
                assert False, "Expected RuntimeError to be raised"
            except RuntimeError as exc:
                assert str(exc) == "AI failed"
            # Verify stage was marked failed in DB
            from fourdpocket.models.enrichment import EnrichmentStage
            stage = db.exec(
                select(EnrichmentStage).where(
                    EnrichmentStage.item_id == enrich_item.id,
                    EnrichmentStage.stage == "tagged",
                )
            ).first()
            assert stage is not None
            assert stage.status == "failed"
        finally:
            ep_module.STAGE_HANDLERS["tagged"] = original_handler


class TestMaxAttemptsGuard:
    """Regression tests for _mark_running max_attempts enforcement."""

    def test_mark_running_returns_false_when_max_attempts_exceeded(
        self, db: Session, enrich_user_p1, monkeypatch
    ):
        """Regression: stages exceeding max_attempts were retried indefinitely.

        Root cause: _mark_running incremented attempts unconditionally.
        Fixed by checking attempts >= max_attempts before proceeding.
        """
        from fourdpocket.workers.enrichment_pipeline import (
            _get_or_create_stage,
            _mark_running,
        )

        item = KnowledgeItem(
            user_id=enrich_user_p1.id,
            title="Max Attempts Test",
            content="Content",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        # Simulate a stage that has already hit max attempts (default 5)
        stage = _get_or_create_stage(db, item.id, "tagged")
        stage.attempts = 5
        db.add(stage)
        db.commit()

        result = _mark_running(db, item.id, "tagged")

        assert result is False, "_mark_running should return False when max_attempts exceeded"
        db.expire(stage)
        refreshed = db.get(EnrichmentStage, {"item_id": item.id, "stage": "tagged"})
        assert refreshed.status == "failed"

    def test_mark_running_returns_true_below_max_attempts(
        self, db: Session, enrich_user_p1, monkeypatch
    ):
        """_mark_running returns True and increments when under the limit."""
        from fourdpocket.workers.enrichment_pipeline import (
            _get_or_create_stage,
            _mark_running,
        )

        item = KnowledgeItem(
            user_id=enrich_user_p1.id,
            title="Below Max Attempts",
            content="Content",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        _get_or_create_stage(db, item.id, "summarized")
        result = _mark_running(db, item.id, "summarized")

        assert result is True
        stage = db.exec(
            select(EnrichmentStage).where(
                EnrichmentStage.item_id == item.id,
                EnrichmentStage.stage == "summarized",
            )
        ).first()
        assert stage.status == "running"
        assert stage.attempts == 1
