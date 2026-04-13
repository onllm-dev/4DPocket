"""Phase 2 targeted tests for enrichment_pipeline to cover uncovered branches."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.user import User
from fourdpocket.workers.enrichment_pipeline import (
    STAGE_DEPS,
    STAGE_HANDLERS,
    STAGES,
    _deps_satisfied,
    _get_or_create_stage,
    _mark_done,
    handle_chunking,
    handle_embedding,
    handle_entity_extraction,
    handle_summarization,
    handle_synthesis,
    handle_tagging,
)

# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def enrich_user(db: Session):
    user = User(
        email="enrichtest2@example.com",
        username="enrichuser2",
        password_hash="$2b$12$fakehash",
        display_name="Enrich Test User 2",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def enrich_item(db: Session, enrich_user):
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="Test Article for Phase 2",
        content=(
            "Machine learning is transforming software engineering. "
            "Large language models can generate code."
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def enrich_item_with_sections(db: Session, enrich_user):
    """Item whose _sections metadata is set."""
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="Article with Sections",
        content="Should be ignored when sections are present.",
        item_metadata={
            "_sections": [
                {
                    "id": "sec-1",
                    "kind": "text",
                    "order": 0,
                    "text": "First section content.",
                    "role": "main",
                    "depth": 0,
                },
                {
                    "id": "sec-2",
                    "kind": "text",
                    "order": 1,
                    "text": "Second section content.",
                    "role": "main",
                    "depth": 1,
                    "author": "Test Author",
                },
            ]
        },
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def enrich_item_empty_content(db: Session, enrich_user):
    """Item with empty/whitespace-only content."""
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="Empty Content Item",
        content="   ",
        description="   ",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def enrich_item_no_sections_fallback(db: Session, enrich_user):
    """Item whose _sections has a malformed entry that requires fallback re-hydration."""
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="Article with Partial Sections",
        content="Fallback content.",
        item_metadata={
            "_sections": [
                {
                    "id": "sec-bad",
                    # missing 'kind' — forces Section(**sd) to raise,
                    # triggering the except → fallback path
                    "order": 0,
                    "text": "Partial section.",
                    "role": "main",
                    "depth": 0,
                },
            ]
        },
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ─── handle_chunking branches ────────────────────────────────────────────────

class TestHandleChunkingBranches:
    """Cover lines 131, 141-168, 177, 228-233."""

    def test_item_not_found_is_noop(self, db: Session, enrich_user):
        """Line 131: handle_chunking returns early when item doesn't exist."""
        fake_id = uuid.uuid4()
        handle_chunking(db, fake_id, enrich_user.id)
        chunks = db.exec(select(ItemChunk).where(ItemChunk.item_id == fake_id)).all()
        assert len(chunks) == 0

    def test_empty_content_returns_early(
        self, db: Session, enrich_item_empty_content, enrich_user
    ):
        """Line 176-177: empty content causes early return before chunk creation."""
        handle_chunking(db, enrich_item_empty_content.id, enrich_user.id)
        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item_empty_content.id)
        ).all()
        assert len(chunks) == 0

    def test_sections_payload_creates_chunks(
        self, db: Session, enrich_item_with_sections, enrich_user
    ):
        """Lines 137-173: sections_payload triggers chunk_sections path."""
        handle_chunking(db, enrich_item_with_sections.id, enrich_user.id)
        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item_with_sections.id)
        ).all()
        assert len(chunks) >= 1
        assert any(c.section_kind == "text" for c in chunks)

    def test_sections_fallback_rehydration(
        self, db: Session, enrich_item_no_sections_fallback, enrich_user
    ):
        """Lines 143-167: Section(**sd) exception triggers fallback re-hydration."""
        # Should not raise even though 'kind' is missing
        handle_chunking(db, enrich_item_no_sections_fallback.id, enrich_user.id)
        chunks = db.exec(
            select(ItemChunk).where(
                ItemChunk.item_id == enrich_item_no_sections_fallback.id
            )
        ).all()
        # Fallback path creates a Section with kind="uncategorized"
        assert len(chunks) >= 1

    def test_raw_chunks_empty_after_chunking(self, db: Session, enrich_user):
        """Line 185-186: when raw_chunks is empty, returns before DB writes."""
        item = KnowledgeItem(
            user_id=enrich_user.id,
            title="No Chunks Item",
            content="",
            description="",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        handle_chunking(db, item.id, enrich_user.id)
        chunks = db.exec(select(ItemChunk).where(ItemChunk.item_id == item.id)).all()
        assert len(chunks) == 0

    def test_chunking_indexing_exception_logged(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 223-233: exception in index_chunks is caught and logged."""
        rollback_called = False
        original_rollback = db.rollback

        def tracking_rollback():
            nonlocal rollback_called
            rollback_called = True
            return original_rollback()

        db.rollback = tracking_rollback

        mock_service = MagicMock()
        mock_service.index_chunks = MagicMock(
            side_effect=RuntimeError("Simulated FTS failure")
        )
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: mock_service,
        )

        # Should not raise — exception is caught and logged
        handle_chunking(db, enrich_item.id, enrich_user.id)

        # Rollback is called after indexing failure
        assert rollback_called
        # Chunks are still committed (before indexing), but rollback was called
        db.expire_all()
        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item.id)
        ).all()
        # Note: chunks ARE committed before indexing, so rollback can't undo them.
        # This test verifies the exception path is exercised.
        assert len(chunks) >= 1


# ─── handle_embedding branches ─────────────────────────────────────────────────

class TestHandleEmbeddingBranches:
    """Cover lines 238-299."""

    def test_embedding_item_not_found(self, db: Session, enrich_user):
        """Lines 243-245: returns early when item not found."""
        fake_id = uuid.uuid4()
        handle_embedding(db, fake_id, enrich_user.id)  # no error

    def test_embedding_no_chunks(self, db: Session, enrich_item, enrich_user, monkeypatch):
        """Lines 267-271: item with no chunks only gets item-level embedding."""
        embed_single_called = False

        class CapturingProvider:
            dimensions = 384

            def embed_single(self, text):
                nonlocal embed_single_called
                embed_single_called = True
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider",
            lambda: CapturingProvider(),
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding",
            lambda *a, **k: None,
        )

        handle_embedding(db, enrich_item.id, enrich_user.id)
        assert embed_single_called

    def test_embedding_with_chunks_and_section_metadata(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 267-299: chunk embeddings with section metadata propagation."""
        # First create chunks
        handle_chunking(db, enrich_item.id, enrich_user.id)

        chunk_embedding_calls: list[dict] = []

        class CapturingProvider:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider",
            lambda: CapturingProvider(),
        )

        def capture_add_chunk_embedding(chunk_id, user_id, item_id, emb, meta):
            chunk_embedding_calls.append(meta)

        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding",
            capture_add_chunk_embedding,
        )

        handle_embedding(db, enrich_item.id, enrich_user.id)
        assert len(chunk_embedding_calls) >= 1


# ─── handle_tagging / handle_summarization ────────────────────────────────────

class TestOtherStageHandlers:
    """Cover lines 302-350."""

    def test_handle_tagging_item_not_found(self, db: Session, enrich_user):
        """Lines 309-311: returns early when item not found."""
        fake_id = uuid.uuid4()
        handle_tagging(db, fake_id, enrich_user.id)  # no error

    def test_handle_tagging_runs(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 313-343: tagging runs end-to-end (with mocks)."""
        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item",
            lambda **kw: [{"name": "ai", "source": "auto"}],
        )
        monkeypatch.setattr(
            "fourdpocket.ai.domain_tagger.attach_domain_tag",
            lambda **kw: None,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy",
            lambda *a, **k: None,
        )
        handle_tagging(db, enrich_item.id, enrich_user.id)  # no error

    def test_handle_summarization_runs(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 348-350: summarization calls summarize_item."""
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item",
            lambda *a, **k: None,
        )
        handle_summarization(db, enrich_item.id, enrich_user.id)  # no error


# ─── handle_entity_extraction ────────────────────────────────────────────────

class TestHandleEntityExtraction:
    """Cover lines 353-429."""

    def test_entity_extraction_item_not_found(self, db: Session, enrich_user):
        """Early return when item not found."""
        fake_id = uuid.uuid4()
        handle_entity_extraction(db, fake_id, enrich_user.id)  # no error

    def test_entity_extraction_no_chunks_fallback(
        self, db: Session, enrich_item_empty_content, enrich_user, monkeypatch
    ):
        """Lines 411-423: no chunks fallback to item content directly."""
        monkeypatch.setattr(
            "fourdpocket.config.get_settings",
            lambda: MagicMock(
                enrichment=MagicMock(
                    extract_entities=True,
                    max_entities_per_chunk=10,
                    max_relations_per_chunk=10,
                )
            ),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.extractor.extract_entities",
            lambda text, **kw: MagicMock(entities=[], relations=[]),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.llm_cache.get_cached_response",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.llm_cache.store_cached_response",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.extractor._parse_entities",
            lambda *a, **k: [],
        )
        monkeypatch.setattr(
            "fourdpocket.ai.extractor._parse_relations",
            lambda *a, **k: [],
        )
        monkeypatch.setattr(
            "fourdpocket.ai.extractor.ExtractionResult",
            lambda **kw: MagicMock(entities=[], relations=[]),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.canonicalizer.canonicalize_entity",
            lambda **kw: MagicMock(id=uuid.uuid4()),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.canonicalizer.increment_item_count",
            lambda *a, **k: None,
        )
        # Should not raise
        handle_entity_extraction(
            db, enrich_item_empty_content.id, enrich_user.id
        )


# ─── handle_synthesis ─────────────────────────────────────────────────────────

class TestHandleSynthesis:
    """Cover lines 529-563."""

    def test_synthesis_disabled(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 540-541: returns when synthesis_enabled=False."""
        # get_settings is imported from fourdpocket.config inside handle_synthesis
        monkeypatch.setattr(
            "fourdpocket.config.get_settings",
            lambda: MagicMock(enrichment=MagicMock(synthesis_enabled=False)),
        )
        handle_synthesis(db, enrich_item.id, enrich_user.id)  # no error

    def test_synthesis_no_entity_links(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 543-547: returns when item has no entity links."""
        monkeypatch.setattr(
            "fourdpocket.config.get_settings",
            lambda: MagicMock(enrichment=MagicMock(synthesis_enabled=True)),
        )
        handle_synthesis(db, enrich_item.id, enrich_user.id)  # no error

    def test_synthesis_calls_synthesize(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 555-563: synthesize_entity is called for eligible entities."""
        from fourdpocket.models.entity import Entity, ItemEntity

        # Create entity linked to item (Entity requires canonical_name)
        entity = Entity(
            user_id=enrich_user.id,
            canonical_name="TestEntity",
            entity_type="concept",
            description="A test entity",
            item_count=1,
            synthesis_item_count=0,
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)

        link = ItemEntity(
            item_id=enrich_item.id,
            entity_id=entity.id,
            salience=0.5,
        )
        db.add(link)
        db.commit()

        synthesis_called = False

        def capture_synthesize(eid, dbsess):
            nonlocal synthesis_called
            synthesis_called = True

        monkeypatch.setattr(
            "fourdpocket.config.get_settings",
            lambda: MagicMock(enrichment=MagicMock(synthesis_enabled=True)),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.synthesizer.should_regenerate",
            lambda e: True,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.synthesizer.synthesize_entity",
            capture_synthesize,
        )

        handle_synthesis(db, enrich_item.id, enrich_user.id)
        assert synthesis_called


# ─── Huey task tests ─────────────────────────────────────────────────────────

class TestRunEnrichmentStage:
    """Cover lines 578-623 using engine monkeypatch + call_local()."""

    def test_already_done(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 588-591: returns early when stage already done."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        _get_or_create_stage(db, enrich_item.id, "chunked")
        _mark_done(db, enrich_item.id, "chunked")

        from fourdpocket.workers import enrichment_pipeline as ep
        result = ep.run_enrichment_stage.call_local(
            str(enrich_item.id), str(enrich_user.id), "chunked"
        )
        assert result["status"] == "already_done"

    def test_deps_not_met(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 593-595: returns early when deps not met."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        from fourdpocket.workers import enrichment_pipeline as ep
        result = ep.run_enrichment_stage.call_local(
            str(enrich_item.id), str(enrich_user.id), "embedded"
        )
        assert result["status"] == "deps_not_met"

    def test_unknown_stage_skipped(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 599-602: unknown stage gets marked skipped."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        from fourdpocket.workers import enrichment_pipeline as ep
        result = ep.run_enrichment_stage.call_local(
            str(enrich_item.id), str(enrich_user.id), "nonexistent_stage"
        )
        assert result["status"] == "skipped"

    def test_successful_run_enqueues_dependents(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 604-611: successful handler run enqueues dependent stages."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        from fourdpocket.workers import enrichment_pipeline as ep

        # Replace STAGE_HANDLERS["chunked"] with a no-op so chunking doesn't run
        original_handler = STAGE_HANDLERS["chunked"]
        STAGE_HANDLERS["chunked"] = lambda *a, **k: None

        try:
            result = ep.run_enrichment_stage.call_local(
                str(enrich_item.id), str(enrich_user.id), "chunked"
            )
            assert result["status"] == "done"
        finally:
            STAGE_HANDLERS["chunked"] = original_handler

    def test_handler_exception_marks_failed(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 614-622: handler exception marks stage failed."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        # Make chunking handler raise
        original = STAGE_HANDLERS["chunked"]
        STAGE_HANDLERS["chunked"] = lambda *a, **k: (_ for _ in ()).throw(
            ValueError("Chunking boom")
        )

        try:
            from fourdpocket.workers import enrichment_pipeline as ep

            with pytest.raises(ValueError, match="Chunking boom"):
                ep.run_enrichment_stage.call_local(
                    str(enrich_item.id), str(enrich_user.id), "chunked"
                )

            db.expire_all()
            row = db.exec(
                select(EnrichmentStage).where(
                    EnrichmentStage.item_id == enrich_item.id,
                    EnrichmentStage.stage == "chunked",
                )
            ).first()
            assert row.status == "failed"
            assert "Chunking boom" in (row.last_error or "")
        finally:
            STAGE_HANDLERS["chunked"] = original


# ─── enrich_item_v2 branches ─────────────────────────────────────────────────

class TestEnrichItemV2:
    """Cover lines 626-659."""

    def test_enrich_item_v2_creates_all_stages(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 638-641: all stage records are created."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        monkeypatch.setattr(
            "fourdpocket.workers.enrichment_pipeline.run_enrichment_stage",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda *a, **k: None),
        )

        from fourdpocket.workers import enrichment_pipeline as ep
        ep.enrich_item_v2.call_local(str(enrich_item.id), str(enrich_user.id))

        for stage in STAGES:
            row = db.exec(
                select(EnrichmentStage).where(
                    EnrichmentStage.item_id == enrich_item.id,
                    EnrichmentStage.stage == stage,
                )
            ).first()
            assert row is not None, f"Stage {stage} not created"
            assert row.status == "pending"

    def test_enrich_item_v2_search_indexing_error(
        self, db: Session, engine, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 643-651: search indexing error is caught and logged."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        call_count = 0

        def raising_index(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Search down")

        monkeypatch.setattr(
            "fourdpocket.workers.enrichment_pipeline.run_enrichment_stage",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=raising_index),
        )

        from fourdpocket.workers import enrichment_pipeline as ep
        # Should not raise
        ep.enrich_item_v2.call_local(str(enrich_item.id), str(enrich_user.id))
        assert call_count == 1


# ─── Dependency satisfaction ────────────────────────────────────────────────

class TestDependencyCoverage:
    """Additional deps_satisfied edge cases."""

    def test_stage_with_no_dep_entry(self, db: Session, enrich_item):
        """STAGE_DEPS lookup for stage with no entry returns empty dep list."""
        assert _deps_satisfied(db, enrich_item.id, "tagged") is True

    def test_all_positive_dep_statuses(self, db: Session, enrich_item):
        """Dep is satisfied when status is 'done'."""
        _get_or_create_stage(db, enrich_item.id, "chunked")
        _mark_done(db, enrich_item.id, "chunked")
        assert _deps_satisfied(db, enrich_item.id, "embedded") is True

    def test_multiple_deps_one_not_met(self, db: Session, enrich_item):
        """embedded depends on chunked; if only tagged done, dep not met."""
        _get_or_create_stage(db, enrich_item.id, "tagged")
        _mark_done(db, enrich_item.id, "tagged")
        assert _deps_satisfied(db, enrich_item.id, "embedded") is False

    def test_synthesized_deps_chain(self, db: Session, enrich_item):
        """synthesized depends on entities_extracted (not directly on chunked)."""
        # Don't meet any deps
        assert _deps_satisfied(db, enrich_item.id, "synthesized") is False
        # Meet entities_extracted but not chunked
        _get_or_create_stage(db, enrich_item.id, "entities_extracted")
        _mark_done(db, enrich_item.id, "entities_extracted")
        # entities_extracted done → synthesized deps met (synthesized only depends on entities_extracted)
        assert _deps_satisfied(db, enrich_item.id, "synthesized") is True


# ─── Stage ordering ──────────────────────────────────────────────────────────

class TestStageOrdering:
    """Verify stage ordering logic."""

    def test_independent_stages_have_no_deps(self):
        """chunked, tagged, summarized have empty dep lists."""
        assert STAGE_DEPS["chunked"] == []
        assert STAGE_DEPS["tagged"] == []
        assert STAGE_DEPS["summarized"] == []

    def test_dependent_stages(self):
        """embedded and entities_extracted depend on chunked."""
        assert "chunked" in STAGE_DEPS["embedded"]
        assert "chunked" in STAGE_DEPS["entities_extracted"]
        assert "entities_extracted" in STAGE_DEPS["synthesized"]

    def test_all_stages_defined(self):
        """Every stage in STAGES has a handler."""
        for stage in STAGES:
            assert stage in STAGE_HANDLERS, f"No handler for {stage}"

    def test_all_handlers_defined(self):
        """Every handler in STAGE_HANDLERS corresponds to a stage in STAGES."""
        for handler_stage in STAGE_HANDLERS:
            assert handler_stage in STAGES, f"Unknown stage {handler_stage}"


# ─── _store_extraction ────────────────────────────────────────────────────────

class TestStoreExtraction:
    """Cover lines 432-527 via handle_entity_extraction with mocked LLM."""

    def test_store_extraction_with_entities_and_relations(
        self, db: Session, enrich_item, enrich_user, monkeypatch
    ):
        """Lines 440-527: stores entities, links, and relations."""
        from fourdpocket.ai.extractor import (
            ExtractedEntity,
            ExtractedRelation,
            ExtractionResult,
        )
        from fourdpocket.models.entity import Entity, ItemEntity

        fake_entity_id = uuid.uuid4()

        extraction_result = ExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Python",
                    entity_type="language",
                    description="Programming language",
                ),
            ],
            relations=[
                ExtractedRelation(
                    source="Python",
                    target="AI",
                    keywords="used_for",
                    description="Python is used for AI",
                ),
            ],
        )

        settings_mock = MagicMock(
            enrichment=MagicMock(
                extract_entities=True,
                max_entities_per_chunk=10,
                max_relations_per_chunk=10,
            )
        )
        monkeypatch.setattr(
            "fourdpocket.config.get_settings",
            lambda: settings_mock,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.extractor.extract_entities",
            lambda *a, **k: extraction_result,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.llm_cache.get_cached_response",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "fourdpocket.ai.llm_cache.store_cached_response",
            lambda *a, **k: None,
        )
        # Also mock increment_item_count since it tries to db.add the mock entity
        monkeypatch.setattr(
            "fourdpocket.ai.canonicalizer.increment_item_count",
            lambda *a, **k: None,
        )

        with patch(
            "fourdpocket.ai.canonicalizer.canonicalize_entity"
        ) as mock_canon:
            mock_entity = MagicMock(spec=Entity)
            mock_entity.id = fake_entity_id
            mock_canon.return_value = mock_entity

            handle_entity_extraction(db, enrich_item.id, enrich_user.id)

            # Verify an ItemEntity link was created
            links = db.exec(
                select(ItemEntity).where(ItemEntity.item_id == enrich_item.id)
            ).all()
            assert len(links) >= 1
