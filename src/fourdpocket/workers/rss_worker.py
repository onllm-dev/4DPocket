"""RSS feed polling worker."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from huey import crontab
from sqlmodel import Session, select


def _strip_html_tags(text: str | None) -> str | None:
    """Strip HTML tags from RSS content to prevent stored XSS."""
    if not text:
        return text
    return re.sub(r"<[^>]+>", "", text).strip()

from fourdpocket.models.base import ItemType, SourcePlatform
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.rss_feed import RSSFeed
from fourdpocket.utils.ssrf import is_safe_url
from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.periodic_task(crontab(minute="*/15"))
def poll_all_feeds():
    """Poll all RSS feeds that are due for update."""
    from fourdpocket.db.session import get_engine

    engine = get_engine()
    with Session(engine) as db:
        feeds = db.exec(select(RSSFeed).where(RSSFeed.is_active == True)).all()  # noqa: E712
        for feed in feeds:
            # Skip if fetched recently (respect poll_interval in seconds)
            if feed.last_fetched_at:
                interval_secs = feed.poll_interval or 3600
                next_fetch = feed.last_fetched_at + timedelta(seconds=interval_secs)
                if datetime.now(timezone.utc) < next_fetch:
                    continue
            try:
                count = fetch_rss_feed(feed, db)
                if count > 0:
                    logger.info("Feed %s: %d new items", feed.title or feed.url, count)
            except Exception as e:
                logger.error("Failed to poll feed %s: %s", feed.url, e)


def _parse_json_feed(feed: RSSFeed, content: str, db: Session) -> int:
    """Parse JSON Feed format (https://www.jsonfeed.org/)."""
    data = json.loads(content)
    items = data.get("items", [])
    new_count = 0

    for entry in items[:50]:
        url = entry.get("url") or entry.get("external_url") or ""
        if not url:
            continue
        if not is_safe_url(url):
            logger.warning("SSRF blocked: JSON feed entry URL %s targets internal network", url)
            continue

        title = entry.get("title") or url
        description = _strip_html_tags(entry.get("summary") or entry.get("content_text") or None)

        # Apply keyword filters if set
        if feed.filters:
            keywords = [k.strip().lower() for k in feed.filters.split(",") if k.strip()]
            if keywords:
                text_to_check = f"{title} {description or ''}".lower()
                if not any(kw in text_to_check for kw in keywords):
                    continue

        if feed.mode == "approval":
            from fourdpocket.models.feed_entry import FeedEntry

            existing_entry = db.exec(
                select(FeedEntry).where(
                    FeedEntry.feed_id == feed.id,
                    FeedEntry.url == url,
                )
            ).first()
            if not existing_entry:
                entry_record = FeedEntry(
                    feed_id=feed.id,
                    user_id=feed.user_id,
                    url=url,
                    title=title,
                    content_snippet=description,
                    status="pending",
                )
                db.add(entry_record)
                new_count += 1
        else:
            existing = db.exec(
                select(KnowledgeItem).where(
                    KnowledgeItem.user_id == feed.user_id,
                    KnowledgeItem.url == url,
                )
            ).first()
            if not existing:
                item = KnowledgeItem(
                    user_id=feed.user_id,
                    url=url,
                    title=title,
                    description=description,
                    item_type=ItemType.url,
                    source_platform=SourcePlatform.generic,
                )
                db.add(item)
                new_count += 1

    return new_count


def fetch_rss_feed(feed: RSSFeed, db: Session) -> int:
    """Fetch new entries from an RSS feed. Returns count of new items."""
    try:
        import xml.etree.ElementTree as ET

        if not is_safe_url(feed.url):
            logger.warning("SSRF blocked: RSS feed URL %s targets internal network", feed.url)
            return 0

        resp = httpx.get(feed.url, timeout=15, follow_redirects=False)
        # Manually follow redirects with SSRF check per hop
        for _ in range(5):
            if not resp.is_redirect:
                break
            location = resp.headers.get("location", "")
            if not location or not is_safe_url(location):
                logger.warning("SSRF blocked: RSS redirect to %s", location)
                return 0
            resp = httpx.get(location, timeout=15, follow_redirects=False)
        resp.raise_for_status()

        # JSON Feed detection
        content_type = resp.headers.get("content-type", "")
        if "json" in content_type or feed.format == "json_feed":
            new_count = _parse_json_feed(feed, resp.text, db)
            feed.last_fetched_at = datetime.now(timezone.utc)
            feed.last_error = None
            feed.error_count = 0
            db.commit()
            return new_count

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
            guid_el = entry.find("guid") or entry.find("atom:id", ns)  # noqa: F841

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
            description = _strip_html_tags(desc_el.text) if desc_el is not None else None

            # Apply keyword filters if set
            if feed.filters:
                keywords = [k.strip().lower() for k in feed.filters.split(",") if k.strip()]
                if keywords:
                    text_to_check = f"{title} {description or ''}".lower()
                    if not any(kw in text_to_check for kw in keywords):
                        continue

            if feed.mode == "approval":
                from fourdpocket.models.feed_entry import FeedEntry

                existing_entry = db.exec(
                    select(FeedEntry).where(
                        FeedEntry.feed_id == feed.id,
                        FeedEntry.url == url,
                    )
                ).first()
                if not existing_entry:
                    entry_record = FeedEntry(
                        feed_id=feed.id,
                        user_id=feed.user_id,
                        url=url,
                        title=title,
                        content_snippet=description,
                        status="pending",
                    )
                    db.add(entry_record)
                    new_count += 1
            else:
                # Auto mode: create knowledge item directly
                existing = db.exec(
                    select(KnowledgeItem).where(
                        KnowledgeItem.user_id == feed.user_id,
                        KnowledgeItem.url == url,
                    )
                ).first()
                if not existing:
                    item = KnowledgeItem(
                        user_id=feed.user_id,
                        url=url,
                        title=title,
                        description=description,
                        item_type=ItemType.url,
                        source_platform=SourcePlatform.generic,
                    )
                    db.add(item)
                    new_count += 1

        feed.last_fetched_at = datetime.now(timezone.utc)
        feed.last_error = None
        feed.error_count = 0
        db.commit()

        return new_count
    except Exception as e:
        logger.error("Failed to fetch RSS feed %s: %s", feed.url, e)
        feed.last_error = str(e)[:500]
        feed.error_count = (feed.error_count or 0) + 1
        db.commit()
        return 0
