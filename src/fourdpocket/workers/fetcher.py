"""Background task for URL content extraction."""

import logging
import uuid

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.task(retries=2, retry_delay=30)
def fetch_and_process_url(item_id: str, url: str, user_id: str) -> dict:
    """Fetch URL content and update the knowledge item.

    Runs the extraction pipeline as a background task with retry logic.
    """
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.processors.pipeline import ExtractionPipeline
    from fourdpocket.search.indexer import SearchIndexer

    logger.info("Processing URL %s for item %s", url, item_id)

    engine = get_engine()
    with Session(engine) as db:
        item = db.get(KnowledgeItem, uuid.UUID(item_id))
        if not item:
            logger.error("Item %s not found", item_id)
            return {"status": "error", "error": "Item not found"}

        pipeline = ExtractionPipeline()
        indexer = SearchIndexer(db)

        try:
            from fourdpocket.processors.registry import match_processor
            import asyncio

            processor = match_processor(url)
            result = asyncio.run(processor.process(url))

            # Update existing item with extracted content
            if result.title:
                item.title = result.title
            if result.description:
                item.description = result.description
            if result.content:
                item.content = result.content
            if result.raw_content:
                item.raw_content = result.raw_content
            if result.media:
                item.media = list(result.media)
            if result.metadata:
                item.item_metadata = {**item.item_metadata, **result.metadata}

            db.add(item)
            db.commit()
            db.refresh(item)

            # Index for search
            indexer.index_item(item)

            # Chain: AI enrichment (content now available)
            try:
                from fourdpocket.workers.ai_enrichment import enrich_item
                enrich_item(item_id, user_id)
            except Exception as chain_err:
                logger.warning("Failed to chain enrich_item for %s: %s", item_id, chain_err)

            # Chain: download media if processor found media URLs
            try:
                if result.media:
                    media_urls = [
                        {"url": m.get("url", ""), "type": m.get("type", "unknown"), "role": m.get("role", "")}
                        for m in result.media if m.get("url")
                    ]
                    if media_urls:
                        from fourdpocket.workers.media_downloader import download_media
                        download_media(item_id, user_id, media_urls)
            except Exception as chain_err:
                logger.warning("Failed to chain download_media for %s: %s", item_id, chain_err)

            logger.info("Successfully processed item %s", item_id)
            return {"status": "success", "item_id": item_id}

        except Exception as e:
            logger.error("Failed to process item %s: %s", item_id, e)
            item.item_metadata = {**item.item_metadata, "_processing_error": str(e)[:500]}
            db.add(item)
            db.commit()
            return {"status": "error", "error": str(e)[:500]}
