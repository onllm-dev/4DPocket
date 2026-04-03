"""RSS feed polling worker."""

import logging
from datetime import datetime, timezone

import httpx
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.rss_feed import RSSFeed
from fourdpocket.utils.ssrf import is_safe_url

logger = logging.getLogger(__name__)


def fetch_rss_feed(feed: RSSFeed, db: Session) -> int:
    """Fetch new entries from an RSS feed. Returns count of new items."""
    try:
        import xml.etree.ElementTree as ET

        if not is_safe_url(feed.url):
            logger.warning("SSRF blocked: RSS feed URL %s targets internal network", feed.url)
            return 0

        resp = httpx.get(feed.url, timeout=15, follow_redirects=True)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        new_count = 0

        # Handle both RSS 2.0 and Atom feeds
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for entry in entries[:50]:  # Cap at 50 per fetch
            # Extract link and title
            link_el = entry.find("link")
            title_el = entry.find("title")
            desc_el = entry.find("description") or entry.find("atom:summary", ns)
            guid_el = entry.find("guid") or entry.find("atom:id", ns)

            if link_el is None:
                # Atom feeds store link in href attribute
                link_el = entry.find("atom:link", ns)
                url = link_el.get("href", "") if link_el is not None else ""
            else:
                url = link_el.text or ""

            if not url:
                continue

            if not is_safe_url(url):
                logger.warning("SSRF blocked: RSS entry URL %s targets internal network", url)
                continue

            title = title_el.text if title_el is not None else url
            description = desc_el.text if desc_el is not None else None
            guid = guid_el.text if guid_el is not None else url  # noqa: F841

            # Skip if already fetched (by URL)
            from sqlmodel import select
            existing = db.exec(
                select(KnowledgeItem).where(
                    KnowledgeItem.user_id == feed.user_id,
                    KnowledgeItem.url == url,
                )
            ).first()
            if existing:
                continue

            # Create knowledge item
            item = KnowledgeItem(
                user_id=feed.user_id,
                url=url,
                title=title,
                description=description,
                item_type="url",
                source_platform="generic",
            )
            db.add(item)
            new_count += 1

        feed.last_fetched_at = datetime.now(timezone.utc)
        db.commit()

        return new_count
    except Exception as e:
        logger.error(f"Failed to fetch RSS feed {feed.url}: {e}")
        return 0
