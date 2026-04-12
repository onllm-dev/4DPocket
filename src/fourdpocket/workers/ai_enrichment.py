"""Background task for AI enrichment - tagging, summarization, embeddings."""

import logging
import uuid

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.task(retries=2, retry_delay=30)
def enrich_item(item_id: str, user_id: str) -> dict:
    """Run the full AI enrichment pipeline on an item.

    Steps:
    1. Auto-tag with confidence scores
    2. Generate summary
    3. Generate embedding and store in ChromaDB
    4. Index to search engine
    """
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem

    logger.info("Enriching item %s", item_id)
    engine = get_engine()
    results = {"item_id": item_id, "steps": {}}

    with Session(engine) as db:
        item = db.get(KnowledgeItem, uuid.UUID(item_id))
        if not item:
            logger.error("Item %s not found for enrichment", item_id)
            return {"status": "error", "error": "Item not found"}

        uid = uuid.UUID(user_id)

        # Step 0: Chunk content for paragraph-level retrieval
        try:
            from fourdpocket.config import get_settings
            from fourdpocket.models.item_chunk import ItemChunk
            from fourdpocket.search.chunking import chunk_text

            settings = get_settings()
            content_to_chunk = item.content or item.description or ""
            if content_to_chunk.strip():
                raw_chunks = chunk_text(
                    content_to_chunk,
                    target_tokens=settings.search.chunk_size_tokens,
                    overlap_tokens=settings.search.chunk_overlap_tokens,
                    max_chunks=settings.search.max_chunks_per_item,
                )

                if raw_chunks:
                    # Remove old chunks for this item
                    from sqlmodel import select as _select
                    old_chunks = db.exec(
                        _select(ItemChunk).where(ItemChunk.item_id == item.id)
                    ).all()
                    for oc in old_chunks:
                        db.delete(oc)
                    db.flush()

                    # Insert new chunks
                    chunk_models = []
                    for i, c in enumerate(raw_chunks):
                        chunk_model = ItemChunk(
                            item_id=item.id,
                            user_id=uid,
                            chunk_order=i,
                            text=c.text,
                            token_count=c.token_count,
                            char_start=c.char_start,
                            char_end=c.char_end,
                            content_hash=c.content_hash,
                        )
                        db.add(chunk_model)
                        chunk_models.append(chunk_model)
                    db.commit()

                    # Index chunks in FTS5
                    try:
                        from fourdpocket.search.sqlite_fts import index_chunks
                        index_chunks(db, item.id, uid, chunk_models, item.title, item.url)
                    except Exception as fts_err:
                        logger.debug("Chunk FTS indexing skipped: %s", fts_err)

                    results["steps"]["chunking"] = {
                        "status": "success",
                        "chunks_count": len(chunk_models),
                    }
                else:
                    results["steps"]["chunking"] = {"status": "skipped", "reason": "no chunks"}
            else:
                results["steps"]["chunking"] = {"status": "skipped", "reason": "no content"}
        except Exception as e:
            logger.warning("Chunking failed for item %s: %s", item_id, e)
            results["steps"]["chunking"] = {"status": "error", "error": str(e)[:200]}

        # Step 1: Auto-tag (content sanitized before LLM call)
        try:
            from fourdpocket.ai.sanitizer import sanitize_for_prompt
            from fourdpocket.ai.tagger import auto_tag_item

            tags = auto_tag_item(
                item_id=item.id,
                user_id=uid,
                title=sanitize_for_prompt(item.title or "", max_length=2000),
                content=sanitize_for_prompt(item.content or "", max_length=4000),
                description=sanitize_for_prompt(item.description or "", max_length=1000),
                db=db,
            )
            results["steps"]["tagging"] = {
                "status": "success",
                "tags_count": len(tags),
            }
        except Exception as e:
            logger.warning("Tagging failed for item %s: %s", item_id, e)
            results["steps"]["tagging"] = {"status": "error", "error": str(e)[:200]}

        # Step 1b: Apply tag hierarchy
        try:
            from fourdpocket.ai.hierarchy import apply_hierarchy

            if tags:
                for tag_info in tags:
                    apply_hierarchy(tag_info["name"], uid, db)
                results["steps"]["hierarchy"] = {"status": "success"}
        except Exception as e:
            logger.warning("Hierarchy failed for item %s: %s", item_id, e)
            results["steps"]["hierarchy"] = {"status": "error", "error": str(e)[:200]}

        # Step 2: Summarize
        try:
            from fourdpocket.ai.summarizer import summarize_item

            summary = summarize_item(item.id, db)
            results["steps"]["summarization"] = {
                "status": "success" if summary else "skipped",
            }
        except Exception as e:
            logger.warning("Summarization failed for item %s: %s", item_id, e)
            results["steps"]["summarization"] = {"status": "error", "error": str(e)[:200]}

        # Step 3: Generate embedding
        try:
            from fourdpocket.ai.factory import get_embedding_provider
            from fourdpocket.search.semantic import add_embedding

            # Build text for embedding
            embed_parts = []
            if item.title:
                embed_parts.append(item.title)
            if item.description:
                embed_parts.append(item.description)
            if item.content:
                embed_parts.append(item.content[:5000])

            if embed_parts:
                embed_text = " ".join(embed_parts)
                provider = get_embedding_provider()
                embedding = provider.embed_single(embed_text)

                if embedding:
                    add_embedding(
                        item_id=item.id,
                        user_id=uid,
                        embedding=embedding,
                        metadata={
                            "item_type": (
                                item.item_type.value if item.item_type else ""
                            ),
                            "source_platform": (
                                item.source_platform.value
                                if item.source_platform
                                else ""
                            ),
                        },
                    )
                    results["steps"]["embedding"] = {"status": "success"}
                else:
                    results["steps"]["embedding"] = {
                        "status": "skipped",
                        "reason": "empty embedding",
                    }
            else:
                results["steps"]["embedding"] = {"status": "skipped", "reason": "no content"}

        except Exception as e:
            logger.warning("Embedding failed for item %s: %s", item_id, e)
            results["steps"]["embedding"] = {"status": "error", "error": str(e)[:200]}

        # Step 3b: Generate per-chunk embeddings
        try:
            from sqlmodel import select as _sel

            from fourdpocket.models.item_chunk import ItemChunk
            from fourdpocket.search.semantic import add_chunk_embedding
            item_chunks = db.exec(
                _sel(ItemChunk).where(ItemChunk.item_id == item.id)
                .order_by(ItemChunk.chunk_order)
            ).all()

            if item_chunks:
                provider = get_embedding_provider()
                chunk_texts = [c.text for c in item_chunks]
                chunk_embeddings = provider.embed(chunk_texts)

                embedded_count = 0
                for chunk_model, emb in zip(item_chunks, chunk_embeddings):
                    if emb:
                        add_chunk_embedding(
                            chunk_id=chunk_model.id,
                            user_id=uid,
                            item_id=item.id,
                            embedding=emb,
                            metadata={
                                "item_type": (
                                    item.item_type.value if item.item_type else ""
                                ),
                                "source_platform": (
                                    item.source_platform.value
                                    if item.source_platform
                                    else ""
                                ),
                            },
                        )
                        chunk_model.embedding_model = provider.__class__.__name__
                        db.add(chunk_model)
                        embedded_count += 1
                db.commit()
                results["steps"]["chunk_embedding"] = {
                    "status": "success",
                    "count": embedded_count,
                }
            else:
                results["steps"]["chunk_embedding"] = {
                    "status": "skipped",
                    "reason": "no chunks",
                }
        except Exception as e:
            logger.warning("Chunk embedding failed for item %s: %s", item_id, e)
            results["steps"]["chunk_embedding"] = {"status": "error", "error": str(e)[:200]}

        # Step 4: Index to search
        try:
            from fourdpocket.search import get_search_service

            get_search_service().index_item(db, item)
            results["steps"]["indexing"] = {"status": "success"}
        except Exception as e:
            logger.warning("Indexing failed for item %s: %s", item_id, e)
            results["steps"]["indexing"] = {"status": "error", "error": str(e)[:200]}

    results["status"] = "success"
    logger.info("Enrichment complete for item %s: %s", item_id, results)
    return results
