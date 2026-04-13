"""Background task for URL content extraction."""

import logging
import uuid
from urllib.parse import urlparse

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


def _fetch_favicon(item, url: str) -> None:
    """Fetch favicon for a URL and update the item.

    Tries Google's favicon service (no CORS issues). Skips internal/private
    hostnames to avoid leaking network topology to Google.
    """
    try:
        import ipaddress
        import socket

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        if not domain:
            return
        # Strip port if present
        hostname = domain.split(":")[0]
        # Skip IP addresses and internal hostnames
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return
        except ValueError:
            # Not an IP — check if hostname resolves to internal
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for _, _, _, _, sockaddr in addr_info:
                    ip = ipaddress.ip_address(sockaddr[0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local:
                        return
            except socket.gaierror:
                return
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        item.favicon_url = favicon_url
    except Exception:
        pass  # Silently skip if URL parsing fails


@huey.task(retries=2, retry_delay=30)
def fetch_and_process_url(item_id: str, url: str, user_id: str) -> dict:
    """Fetch URL content and update the knowledge item.

    Runs the extraction pipeline as a background task with retry logic.
    """
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.search import get_search_service

    logger.info("Processing URL %s for item %s", url, item_id)

    engine = get_engine()
    with Session(engine) as db:
        item = db.get(KnowledgeItem, uuid.UUID(item_id))
        if not item:
            logger.error("Item %s not found", item_id)
            return {"status": "error", "error": "Item not found"}

        search_service = get_search_service()

        try:
            import asyncio

            from fourdpocket.processors.registry import match_processor

            processor = match_processor(url)
            result = asyncio.run(processor.process(url))

            # Update existing item with extracted content
            if result.title:
                item.title = result.title
            if result.description:
                item.description = result.description
            if result.source_platform:
                item.source_platform = result.source_platform
            if result.item_type:
                item.item_type = result.item_type

            # Section-aware: stash structured sections + auto-derive
            # legacy content for processors that haven't migrated.
            from dataclasses import asdict

            from fourdpocket.processors.sections import (
                section_summary_for_metadata,
                sections_to_text,
            )
            sections = getattr(result, "sections", None) or []
            if sections:
                # Persist the section payload alongside other metadata so
                # the chunker can re-hydrate it. Capped per item via
                # max_chunks at chunking time.
                serialized = [asdict(s) for s in sections]
                item.item_metadata = {
                    **item.item_metadata,
                    **section_summary_for_metadata(sections),
                    "_sections": serialized,
                }
                # Always overwrite content from sections — they're the
                # authoritative source. Falls back to result.content for
                # processors mid-migration.
                item.content = sections_to_text(sections) or result.content
            elif result.content:
                item.content = result.content

            if result.raw_content:
                item.raw_content = result.raw_content
            if result.media:
                item.media = list(result.media)
            if result.metadata:
                # Don't let processor metadata clobber the _sections we
                # just stored above.
                merged = {**item.item_metadata, **result.metadata}
                if "_sections" in item.item_metadata and "_sections" not in result.metadata:
                    merged["_sections"] = item.item_metadata["_sections"]
                item.item_metadata = merged

            db.add(item)
            db.commit()
            db.refresh(item)

            # Index for search
            search_service.index_item(db, item)

            # Set favicon URL for generic URLs (brand platforms already have custom icons)
            if item.source_platform.value == "generic":
                _fetch_favicon(item, url)
                db.add(item)
                db.commit()

            # Chain: AI enrichment (content now available)
            try:
                from fourdpocket.workers.enrichment_pipeline import enrich_item_v2
                enrich_item_v2(item_id, user_id)
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
