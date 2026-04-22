"""Stage-based enrichment pipeline with status tracking and retry support."""

import logging
import uuid
from datetime import datetime, timezone

import sqlalchemy.exc
from sqlmodel import Session, select

from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.workers import huey

logger = logging.getLogger(__name__)

STAGES = [
    "chunked",
    "embedded",
    "tagged",
    "summarized",
    "entities_extracted",
    "synthesized",
]
STAGE_DEPS = {
    "chunked": [],
    "embedded": ["chunked"],
    "tagged": [],
    "summarized": [],
    "entities_extracted": ["chunked"],
    "synthesized": ["entities_extracted"],
}


def _now():
    return datetime.now(timezone.utc)


def _get_or_create_stage(db: Session, item_id: uuid.UUID, stage: str) -> EnrichmentStage:
    """Get or create an enrichment stage record."""
    row = db.exec(
        select(EnrichmentStage).where(
            EnrichmentStage.item_id == item_id,
            EnrichmentStage.stage == stage,
        )
    ).first()
    if row is None:
        try:
            row = EnrichmentStage(
                item_id=item_id,
                stage=stage,
                status="pending",
                updated_at=_now(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        except sqlalchemy.exc.IntegrityError:
            db.rollback()
            row = db.exec(
                select(EnrichmentStage).where(
                    EnrichmentStage.item_id == item_id,
                    EnrichmentStage.stage == stage,
                )
            ).first()
    return row


def _mark_running(db: Session, item_id: uuid.UUID, stage: str) -> None:
    row = _get_or_create_stage(db, item_id, stage)
    row.status = "running"
    row.attempts += 1
    row.started_at = _now()
    row.updated_at = _now()
    row.last_error = None
    db.add(row)
    db.commit()


def _mark_done(db: Session, item_id: uuid.UUID, stage: str) -> None:
    row = _get_or_create_stage(db, item_id, stage)
    row.status = "done"
    row.finished_at = _now()
    row.updated_at = _now()
    db.add(row)
    db.commit()


def _mark_failed(db: Session, item_id: uuid.UUID, stage: str, error: str) -> None:
    row = _get_or_create_stage(db, item_id, stage)
    row.status = "failed"
    row.last_error = error[:500]
    row.finished_at = _now()
    row.updated_at = _now()
    db.add(row)
    db.commit()


def _mark_skipped(db: Session, item_id: uuid.UUID, stage: str) -> None:
    row = _get_or_create_stage(db, item_id, stage)
    row.status = "skipped"
    row.finished_at = _now()
    row.updated_at = _now()
    db.add(row)
    db.commit()


def _deps_satisfied(db: Session, item_id: uuid.UUID, stage: str) -> bool:
    """Check if all dependency stages are done or skipped."""
    deps = STAGE_DEPS.get(stage, [])
    if not deps:
        return True
    for dep in deps:
        row = db.exec(
            select(EnrichmentStage).where(
                EnrichmentStage.item_id == item_id,
                EnrichmentStage.stage == dep,
            )
        ).first()
        if row is None or row.status not in ("done", "skipped"):
            return False
    return True


# ─── Stage Handlers ──────────────────────────────────────────

def handle_chunking(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Chunk item content into ItemChunk rows and index in FTS5.

    When ``item.item_metadata['_sections']`` is populated by a
    section-aware processor, prefer ``chunk_sections`` so chunks carry
    section provenance (kind/role/author/heading_path/page/timestamp).
    Falls back to the legacy ``chunk_text`` path on the item's flat
    content for processors not yet migrated.
    """
    from fourdpocket.config import get_settings
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.models.item_chunk import ItemChunk
    from fourdpocket.search.chunking import Chunk, chunk_sections, chunk_text

    item = db.get(KnowledgeItem, item_id)
    if not item:
        return

    settings = get_settings()
    sections_payload = (item.item_metadata or {}).get("_sections") or []
    raw_chunks: list[Chunk]

    if sections_payload:
        # Re-hydrate the dataclass list from the JSON payload the
        # processor stashed in metadata. Done here (not in the processor)
        # so we keep one chunking pipeline.
        from fourdpocket.processors.sections import Section
        section_objs = []
        for sd in sections_payload:
            try:
                section_objs.append(Section(**sd))
            except Exception as sec_err:
                # Forward-compat: preserve all available fields so
                # provenance (author, depth, parent_id, etc.) survives
                # even when the schema diverges.
                logger.warning(
                    "Section re-hydration fallback for %s: %s",
                    sd.get("id", "?"), sec_err,
                )
                section_objs.append(Section(
                    id=sd.get("id", ""),
                    kind=sd.get("kind", "uncategorized"),
                    order=sd.get("order", 0),
                    text=sd.get("text", ""),
                    role=sd.get("role", "main"),
                    parent_id=sd.get("parent_id"),
                    depth=sd.get("depth", 0),
                    author=sd.get("author"),
                    score=sd.get("score"),
                    created_at=sd.get("created_at"),
                    source_url=sd.get("source_url"),
                    extra=sd.get("extra"),
                ))
        raw_chunks = chunk_sections(
            section_objs,
            target_tokens=settings.search.chunk_size_tokens,
            overlap_tokens=settings.search.chunk_overlap_tokens,
            max_chunks=settings.search.max_chunks_per_item,
        )
    else:
        content = item.content or item.description or ""
        if not content.strip():
            return
        raw_chunks = chunk_text(
            content,
            target_tokens=settings.search.chunk_size_tokens,
            overlap_tokens=settings.search.chunk_overlap_tokens,
            max_chunks=settings.search.max_chunks_per_item,
        )

    if not raw_chunks:
        return

    # Remove old chunks
    old = db.exec(select(ItemChunk).where(ItemChunk.item_id == item_id)).all()
    for oc in old:
        db.delete(oc)
    db.flush()

    # Insert new
    chunk_models = []
    for i, c in enumerate(raw_chunks):
        cm = ItemChunk(
            item_id=item_id,
            user_id=user_id,
            chunk_order=i,
            text=c.text,
            token_count=c.token_count,
            char_start=c.char_start,
            char_end=c.char_end,
            content_hash=c.content_hash,
            section_id=c.section_id,
            section_kind=c.section_kind,
            section_role=c.section_role,
            parent_section_id=c.parent_section_id,
            heading_path=list(c.heading_path) if c.heading_path else None,
            page_no=c.page_no,
            timestamp_start_s=c.timestamp_start_s,
            author=c.author,
            is_accepted_answer=c.is_accepted_answer,
        )
        db.add(cm)
        chunk_models.append(cm)
    db.commit()

    # Index in the configured keyword backend (sqlite_fts or meilisearch).
    # Route through SearchService so we honor FDP_SEARCH__BACKEND instead of
    # unconditionally running SQLite FTS SQL against Postgres.
    try:
        from fourdpocket.search import get_search_service
        get_search_service().index_chunks(
            db, item_id, user_id, chunk_models, item.title, item.url
        )
    except Exception as e:
        logger.warning("Chunk keyword indexing failed: %s", e)
        # Reset the SQLAlchemy session — a failed SQL in the backend (e.g.
        # a wrong-dialect query) aborts the transaction, and the next query
        # would fail with InFailedSqlTransaction. Rolling back restores it.
        db.rollback()


def handle_embedding(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Generate embeddings for item chunks and store in vector backend."""
    from fourdpocket.ai.factory import get_embedding_provider
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.models.item_chunk import ItemChunk
    from fourdpocket.search.semantic import add_chunk_embedding, add_embedding

    item = db.get(KnowledgeItem, item_id)
    if not item:
        return

    provider = get_embedding_provider()

    # Item-level embedding (backward compat)
    embed_parts = []
    if item.title:
        embed_parts.append(item.title)
    if item.description:
        embed_parts.append(item.description)
    if item.content:
        embed_parts.append(item.content[:5000])
    if embed_parts:
        embedding = provider.embed_single(" ".join(embed_parts))
        if embedding:
            add_embedding(item.id, user_id, embedding, {
                "item_type": item.item_type.value if item.item_type else "",
                "source_platform": item.source_platform.value if item.source_platform else "",
            })

    # Chunk-level embeddings — contextualize with heading_path so
    # deeply-nested content embeds with breadcrumb context (Docling trick).
    chunks = db.exec(
        select(ItemChunk).where(ItemChunk.item_id == item_id)
        .order_by(ItemChunk.chunk_order)
    ).all()
    if chunks:
        chunk_texts = []
        for c in chunks:
            if c.heading_path:
                breadcrumb = " > ".join(c.heading_path)
                chunk_texts.append(f"{breadcrumb}\n\n{c.text}")
            else:
                chunk_texts.append(c.text)
        chunk_embeddings = provider.embed(chunk_texts)
        for cm, emb in zip(chunks, chunk_embeddings):
            if emb:
                meta = {
                    "item_type": item.item_type.value if item.item_type else "",
                    "source_platform": item.source_platform.value if item.source_platform else "",
                }
                # Propagate section provenance into vector metadata so
                # search filters like kind:comment work end-to-end.
                if cm.section_kind:
                    meta["section_kind"] = cm.section_kind
                if cm.section_role:
                    meta["section_role"] = cm.section_role
                if cm.author:
                    meta["author"] = cm.author
                if cm.is_accepted_answer:
                    meta["is_accepted_answer"] = True
                add_chunk_embedding(cm.id, user_id, item_id, emb, meta)
                cm.embedding_model = provider.__class__.__name__
                db.add(cm)
        db.commit()


def handle_tagging(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Auto-tag item using AI, plus attach a domain tag for generic items."""
    from fourdpocket.ai.domain_tagger import attach_domain_tag
    from fourdpocket.ai.sanitizer import sanitize_for_prompt
    from fourdpocket.ai.tagger import auto_tag_item
    from fourdpocket.models.item import KnowledgeItem

    item = db.get(KnowledgeItem, item_id)
    if not item:
        return

    tags = auto_tag_item(
        item_id=item.id,
        user_id=user_id,
        title=sanitize_for_prompt(item.title or "", max_length=2000),
        content=sanitize_for_prompt(item.content or "", max_length=4000),
        description=sanitize_for_prompt(item.description or "", max_length=1000),
        db=db,
    )

    # Apply hierarchy
    if tags:
        try:
            from fourdpocket.ai.hierarchy import apply_hierarchy
            for tag_info in tags:
                apply_hierarchy(tag_info["name"], user_id, db)
        except Exception as e:
            logger.debug("Hierarchy application failed: %s", e)

    # For generic/web items, also attach the source domain as a deterministic tag
    # so "everything from theverge.com" is one click away.
    try:
        platform = item.source_platform.value if item.source_platform else None
        attach_domain_tag(
            item_id=item.id,
            user_id=user_id,
            url=item.url,
            source_platform=platform,
            db=db,
        )
    except Exception as e:
        logger.debug("Domain-tag attach failed: %s", e)


def handle_summarization(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Generate summary for item."""
    from fourdpocket.ai.summarizer import summarize_item

    summarize_item(item_id, db)


def handle_entity_extraction(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Extract entities and relations from item chunks, with LLM caching."""
    from fourdpocket.config import get_settings

    settings = get_settings()
    if not settings.enrichment.extract_entities:
        return

    from fourdpocket.ai.extractor import extract_entities
    from fourdpocket.ai.factory import get_chat_provider as _get_chat
    from fourdpocket.ai.llm_cache import get_cached_response, store_cached_response
    from fourdpocket.models.item_chunk import ItemChunk

    _chat = _get_chat()
    _model_name = getattr(_chat, "_model", "") or settings.ai.ollama_model

    def _extract_with_cache(text: str):
        """Extract entities, using LLM cache when available."""
        from fourdpocket.ai.extractor import ExtractionResult

        cached = get_cached_response(db, text, "extraction", _model_name)
        if cached:
            from fourdpocket.ai.extractor import _parse_entities, _parse_relations
            entities = _parse_entities(
                cached.get("entities", []),
                settings.enrichment.max_entities_per_chunk,
            )
            entity_names = {e.name for e in entities}
            relations = _parse_relations(
                cached.get("relations", []),
                entity_names,
                settings.enrichment.max_relations_per_chunk,
            )
            return ExtractionResult(entities=entities, relations=relations)

        result = extract_entities(
            text,
            max_entities=settings.enrichment.max_entities_per_chunk,
            max_relations=settings.enrichment.max_relations_per_chunk,
        )

        # Cache the result
        if result.entities:
            store_cached_response(db, text, "extraction", {
                "entities": [
                    {"name": e.name, "type": e.entity_type, "description": e.description}
                    for e in result.entities
                ],
                "relations": [
                    {"source": r.source, "target": r.target,
                     "keywords": r.keywords, "description": r.description}
                    for r in result.relations
                ],
            }, _model_name)

        return result

    chunks = db.exec(
        select(ItemChunk).where(ItemChunk.item_id == item_id)
        .order_by(ItemChunk.chunk_order)
    ).all()

    if not chunks:
        # Fall back to item content directly
        from fourdpocket.models.item import KnowledgeItem

        item = db.get(KnowledgeItem, item_id)
        if not item or not (item.content or item.description):
            return

        text = (item.title or "") + " " + (item.content or item.description or "")
        result = _extract_with_cache(text)
        _store_extraction(db, item_id, user_id, None, result)
        db.commit()
        return

    for chunk in chunks:
        result = _extract_with_cache(chunk.text)
        _store_extraction(db, item_id, user_id, chunk.id, result)

    db.commit()


def _store_extraction(db, item_id, user_id, chunk_id, result):
    """Store extracted entities and relations in the database."""
    from fourdpocket.ai.canonicalizer import canonicalize_entity, increment_item_count
    from fourdpocket.models.entity import ItemEntity
    from fourdpocket.models.entity_relation import EntityRelation, RelationEvidence

    entity_map = {}  # name -> Entity

    for ext_entity in result.entities:
        entity = canonicalize_entity(
            name=ext_entity.name,
            entity_type=ext_entity.entity_type,
            user_id=user_id,
            db=db,
            description=ext_entity.description,
        )
        entity_map[ext_entity.name] = entity

        # Create item-entity link (skip if exists)
        existing = db.exec(
            select(ItemEntity).where(
                ItemEntity.item_id == item_id,
                ItemEntity.entity_id == entity.id,
            )
        ).first()
        if not existing:
            link = ItemEntity(
                item_id=item_id,
                entity_id=entity.id,
                chunk_id=chunk_id,
                salience=0.5,
                context=ext_entity.description[:200] if ext_entity.description else None,
            )
            db.add(link)
            increment_item_count(entity, db)

    db.flush()

    # Store relations
    for ext_rel in result.relations:
        source = entity_map.get(ext_rel.source)
        target = entity_map.get(ext_rel.target)
        if not source or not target:
            continue

        # Normalize direction: smaller UUID is always source
        if str(source.id) > str(target.id):
            source, target = target, source

        existing_rel = db.exec(
            select(EntityRelation).where(
                EntityRelation.source_id == source.id,
                EntityRelation.target_id == target.id,
            )
        ).first()

        if existing_rel:
            rel_id = existing_rel.id
            # Only increment counters if this item has not contributed evidence
            # before (i.e. this is a first-time enrichment, not a replay).
            already_evidenced = db.exec(
                select(RelationEvidence).where(
                    RelationEvidence.relation_id == rel_id,
                    RelationEvidence.item_id == item_id,
                )
            ).first()
            if not already_evidenced:
                existing_rel.weight += 1.0
                existing_rel.item_count += 1
                if ext_rel.keywords:
                    existing_kw = set((existing_rel.keywords or "").split(", "))
                    new_kw = set(ext_rel.keywords.split(", "))
                    existing_rel.keywords = ", ".join(existing_kw | new_kw)
                db.add(existing_rel)
        else:
            rel = EntityRelation(
                user_id=user_id,
                source_id=source.id,
                target_id=target.id,
                keywords=ext_rel.keywords,
                description=ext_rel.description,
                weight=1.0,
                item_count=1,
            )
            db.add(rel)
            db.flush()
            rel_id = rel.id

        # Add evidence (idempotent — composite PK prevents duplicates)
        already_evidenced = db.exec(
            select(RelationEvidence).where(
                RelationEvidence.relation_id == rel_id,
                RelationEvidence.item_id == item_id,
            )
        ).first()
        if not already_evidenced:
            ev = RelationEvidence(
                relation_id=rel_id,
                item_id=item_id,
                chunk_id=chunk_id,
            )
            db.add(ev)

    db.flush()


def handle_synthesis(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Refresh entity synthesis for entities touched by this item.

    Regeneration is guarded by threshold + interval rules in
    :func:`fourdpocket.ai.synthesizer.should_regenerate` so most item saves
    trigger at most 0-1 actual LLM calls.
    """
    from fourdpocket.ai.synthesizer import should_regenerate, synthesize_entity
    from fourdpocket.config import get_settings
    from fourdpocket.models.entity import Entity, ItemEntity

    if not get_settings().enrichment.synthesis_enabled:
        return

    entity_links = db.exec(
        select(ItemEntity.entity_id).where(ItemEntity.item_id == item_id)
    ).all()
    if not entity_links:
        return

    seen: set[uuid.UUID] = set()
    for entity_id in entity_links:
        if entity_id in seen:
            continue
        seen.add(entity_id)

        entity = db.get(Entity, entity_id)
        if entity is None or entity.user_id != user_id:
            continue
        if not should_regenerate(entity):
            continue
        try:
            synthesize_entity(entity.id, db)
        except Exception as e:  # nosec — synthesis is best-effort
            logger.debug("Synthesis failed for entity %s: %s", entity.id, e)


STAGE_HANDLERS = {
    "chunked": handle_chunking,
    "embedded": handle_embedding,
    "tagged": handle_tagging,
    "summarized": handle_summarization,
    "entities_extracted": handle_entity_extraction,
    "synthesized": handle_synthesis,
}


# ─── Huey Tasks ──────────────────────────────────────────────

@huey.task(retries=3, retry_delay=60)
def run_enrichment_stage(item_id: str, user_id: str, stage: str) -> dict:
    """Run a single enrichment stage for an item."""
    from fourdpocket.db.session import get_engine

    engine = get_engine()
    iid = uuid.UUID(item_id)
    uid = uuid.UUID(user_id)

    with Session(engine) as db:
        # Check if already done
        existing = _get_or_create_stage(db, iid, stage)
        if existing.status == "done":
            return {"status": "already_done", "stage": stage}

        # Check dependencies
        if not _deps_satisfied(db, iid, stage):
            return {"status": "deps_not_met", "stage": stage}

        _mark_running(db, iid, stage)
        try:
            handler = STAGE_HANDLERS.get(stage)
            if handler is None:
                _mark_skipped(db, iid, stage)
                return {"status": "skipped", "stage": stage, "reason": "unknown stage"}

            handler(db, iid, uid)
            _mark_done(db, iid, stage)

            # Enqueue dependent stages
            for s, deps in STAGE_DEPS.items():
                if stage in deps:
                    if _deps_satisfied(db, iid, s):
                        run_enrichment_stage(item_id, user_id, s)

            return {"status": "done", "stage": stage}
        except Exception as e:
            # If the handler poisoned the transaction, _mark_failed's SELECT
            # would fail with InFailedSqlTransaction. Rollback first.
            try:
                db.rollback()
            except Exception:
                pass
            _mark_failed(db, iid, stage, str(e))
            raise


@huey.task()
def enrich_item_v2(item_id: str, user_id: str) -> dict:
    """Enqueue all enrichment stages for an item.

    Independent stages (chunked, tagged, summarized) run in parallel.
    Dependent stages (embedded, entities_extracted) auto-enqueue when deps complete.
    """
    from fourdpocket.db.session import get_engine

    engine = get_engine()
    iid = uuid.UUID(item_id)

    with Session(engine) as db:
        # Create pending records for all stages
        for stage in STAGES:
            _get_or_create_stage(db, iid, stage)

        # Also index item to search
        try:
            from fourdpocket.models.item import KnowledgeItem
            from fourdpocket.search import get_search_service

            item = db.get(KnowledgeItem, iid)
            if item:
                get_search_service().index_item(db, item)
        except Exception as e:
            logger.debug("Search indexing during enrichment init failed: %s", e)

    # Enqueue independent stages
    for stage in STAGES:
        deps = STAGE_DEPS.get(stage, [])
        if not deps:
            run_enrichment_stage(item_id, user_id, stage)

    return {"status": "enqueued", "stages": STAGES}
