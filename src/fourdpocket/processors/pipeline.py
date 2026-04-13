"""Extraction pipeline - orchestrates URL processing and item creation."""

import asyncio
import logging
import uuid

from sqlmodel import Session

from fourdpocket.models.base import ItemType, SourcePlatform
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.processors.base import ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import match_processor

logger = logging.getLogger(__name__)


def _map_platform(platform_str: str) -> SourcePlatform:
    """Map processor's platform string to SourcePlatform enum."""
    try:
        return SourcePlatform(platform_str)
    except ValueError:
        return SourcePlatform.generic


def _map_item_type(type_str: str) -> ItemType:
    """Map processor's item_type string to ItemType enum."""
    try:
        return ItemType(type_str)
    except ValueError:
        return ItemType.url


class ExtractionPipeline:
    """Orchestrates the content extraction flow."""

    def run(
        self,
        url: str,
        user_id: uuid.UUID,
        db: Session,
        search_indexer=None,
    ) -> KnowledgeItem:
        """Run the full extraction pipeline for a URL.

        Steps:
        1. Route - match URL to processor
        2. Process - extract content
        3. Create item - save to DB
        4. Index - push to search engine
        """
        # 1. Route
        processor = match_processor(url)
        logger.info("Matched processor %s for URL: %s", type(processor).__name__, url)

        # 2. Process (run async processor in sync context)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run, processor.process(url)
                    ).result()
            else:
                result = asyncio.run(processor.process(url))
        except RuntimeError:
            try:
                result = asyncio.run(processor.process(url))
            except Exception as e:
                logger.error("Processor failed for %s: %s", url, e)
                result = ProcessorResult(
                    title=url,
                    source_platform="generic",
                    status=ProcessorStatus.failed,
                    error=str(e)[:500],
                )
        except Exception as e:
            logger.error("Processor failed for %s: %s", url, e)
            result = ProcessorResult(
                title=url,
                source_platform="generic",
                status=ProcessorStatus.failed,
                error=str(e)[:500],
            )

        # 3. Create item
        item = self._create_item(result, url, user_id, db)

        # 4. Index to search
        if search_indexer is not None:
            try:
                search_indexer.index_item(item)
            except Exception as e:
                logger.warning("Search indexing failed for item %s: %s", item.id, e)

        return item

    def _create_item(
        self,
        result: ProcessorResult,
        url: str,
        user_id: uuid.UUID,
        db: Session,
    ) -> KnowledgeItem:
        """Create a KnowledgeItem from a ProcessorResult."""
        item = KnowledgeItem(
            user_id=user_id,
            url=url,
            title=result.title,
            description=result.description,
            content=result.content,
            raw_content=result.raw_content,
            item_type=_map_item_type(result.item_type),
            source_platform=_map_platform(result.source_platform),
            media=list(result.media),
            item_metadata=dict(result.metadata),
        )

        if result.status == ProcessorStatus.failed:
            item.item_metadata["_processing_error"] = result.error
        elif result.status == ProcessorStatus.partial:
            item.item_metadata["_processing_warning"] = result.error

        db.add(item)
        db.commit()
        db.refresh(item)

        logger.info(
            "Created item %s (status=%s, platform=%s)",
            item.id,
            result.status.value,
            result.source_platform,
        )
        return item
