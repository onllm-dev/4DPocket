"""Background task for AI enrichment — tagging, summarization, embeddings."""

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

        # Step 1: Auto-tag
        try:
            from fourdpocket.ai.tagger import auto_tag_item

            tags = auto_tag_item(
                item_id=item.id,
                user_id=uid,
                title=item.title or "",
                content=item.content,
                description=item.description,
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
                            "item_type": item.item_type.value if item.item_type else "",
                            "source_platform": item.source_platform.value if item.source_platform else "",
                        },
                    )
                    results["steps"]["embedding"] = {"status": "success"}
                else:
                    results["steps"]["embedding"] = {"status": "skipped", "reason": "empty embedding"}
            else:
                results["steps"]["embedding"] = {"status": "skipped", "reason": "no content"}

        except Exception as e:
            logger.warning("Embedding failed for item %s: %s", item_id, e)
            results["steps"]["embedding"] = {"status": "error", "error": str(e)[:200]}

        # Step 4: Index to search
        try:
            from fourdpocket.search.indexer import SearchIndexer

            indexer = SearchIndexer(db)
            indexer.index_item(item)
            results["steps"]["indexing"] = {"status": "success"}
        except Exception as e:
            logger.warning("Indexing failed for item %s: %s", item_id, e)
            results["steps"]["indexing"] = {"status": "error", "error": str(e)[:200]}

    results["status"] = "success"
    logger.info("Enrichment complete for item %s: %s", item_id, results)
    return results
