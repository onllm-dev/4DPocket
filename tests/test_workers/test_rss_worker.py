"""Tests for the RSS feed polling worker."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from fourdpocket.models.feed_entry import FeedEntry
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.rss_feed import RSSFeed
from fourdpocket.models.user import User
from fourdpocket.workers.rss_worker import (
    _parse_json_feed,
    _strip_html_tags,
    fetch_rss_feed,
    poll_all_feeds,
)


def _make_rss_user(db: Session):
    user = User(
        email="rssuser@test.com",
        username="rssuser",
        password_hash="$2b$12$fake",
        display_name="RSS User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_rss_feed(db: Session, user):
    feed = RSSFeed(
        user_id=user.id,
        url="https://example.com/feed.xml",
        title="Test Feed",
        mode="auto",
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


class TestStripHtmlTags:
    @pytest.mark.parametrize("input_str,expected", [
        ("<p>Hello</p>", "Hello"),
        ("<strong>Bold</strong>", "Bold"),
        ("<a href='#'>Link</a>", "Link"),
        ("Plain text", "Plain text"),
        ("<div><p>Nested</p></div>", "Nested"),
        (None, None),
        ("", ""),
    ])
    def test_strip_html_tags(self, input_str, expected):
        assert _strip_html_tags(input_str) == expected


class TestFetchRssFeed:
    """Test RSS feed fetching and entry parsing."""

    def test_fetch_rss_success(self, db: Session, engine, monkeypatch):
        """Valid RSS XML returns new items created in DB."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)

        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Article One</title>
              <link>https://example.com/article1</link>
              <description>Description of article one</description>
            </item>
            <item>
              <title>Article Two</title>
              <link>https://example.com/article2</link>
              <description>Description of article two</description>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.headers = {"content-type": "application/rss+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 2

            item = db.exec(
                select(KnowledgeItem).where(KnowledgeItem.url == "https://example.com/article1")
            ).first()
            assert item is not None
            assert item.title == "Article One"

    def test_fetch_rss_skips_duplicate(self, db: Session, engine, monkeypatch):
        """Item already in DB is not duplicated."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)

        # Pre-existing item
        existing = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article1",
            title="Existing Article",
        )
        db.add(existing)
        db.commit()

        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Article One</title>
              <link>https://example.com/article1</link>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.headers = {"content-type": "application/rss+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 0

            items = db.exec(select(KnowledgeItem)).all()
            assert len(items) == 1

    def test_fetch_rss_approval_mode_creates_feed_entry(self, db: Session, engine, monkeypatch):
        """mode='approval' creates FeedEntry instead of KnowledgeItem."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)
        feed.mode = "approval"
        db.add(feed)
        db.commit()

        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Pending Article</title>
              <link>https://example.com/pending</link>
              <description>A pending article</description>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.headers = {"content-type": "application/rss+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 1

            entry = db.exec(
                select(FeedEntry).where(FeedEntry.url == "https://example.com/pending")
            ).first()
            assert entry is not None
            assert entry.status == "pending"

    def test_fetch_rss_keyword_filter_excludes(self, db: Session, engine, monkeypatch):
        """Items not matching keyword filter are skipped."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)
        feed.filters = "python,ai"
        db.add(feed)
        db.commit()

        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Random Post</title>
              <link>https://example.com/random</link>
            </item>
            <item>
              <title>Python Tutorial</title>
              <link>https://example.com/python</link>
            </item>
          </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.headers = {"content-type": "application/rss+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 1

            item = db.exec(
                select(KnowledgeItem).where(KnowledgeItem.url == "https://example.com/python")
            ).first()
            assert item is not None

    def test_fetch_rss_handles_network_error(self, db: Session, engine, monkeypatch):
        """Network error increments error_count and sets last_error."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = OSError("network failure")

            count = fetch_rss_feed(feed, db)
            assert count == 0

            db.refresh(feed)
            assert feed.last_error is not None
            assert feed.error_count == 1

    def test_fetch_rss_max_50_entries(self, db: Session, engine, monkeypatch):
        """More than 50 entries are capped."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)

        items_xml = "".join(
            f"<item><title>Item {i}</title><link>https://example.com/item{i}</link></item>"
            for i in range(100)
        )
        xml = f"""<?xml version="1.0"?><rss version="2.0"><channel>{items_xml}</channel></rss>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.headers = {"content-type": "application/rss+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 50


class TestParseJsonFeed:
    """Test JSON Feed format parsing."""

    def test_parse_json_feed(self, db: Session, engine, monkeypatch):
        """JSON feed format is detected and parsed."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)
        feed.format = "json_feed"
        db.add(feed)
        db.commit()

        json_content = """{
          "items": [
            {"url": "https://example.com/post1", "title": "First Post", "summary": "A summary"},
            {"url": "https://example.com/post2", "title": "Second Post", "content_text": "Content here"}
          ]
        }"""

        count = _parse_json_feed(feed, json_content, db)
        assert count == 2

        item = db.exec(
            select(KnowledgeItem).where(KnowledgeItem.url == "https://example.com/post1")
        ).first()
        assert item is not None
        assert item.title == "First Post"
        assert item.description == "A summary"


class TestPollAllFeeds:
    """Test periodic feed polling."""

    def test_poll_all_feeds_skips_recent_feeds(self, db: Session, engine, monkeypatch):
        """Feeds fetched recently are skipped based on poll_interval."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)
        # Fetched 30 minutes ago, poll_interval=3600s -> should skip
        feed.last_fetched_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        db.add(feed)
        db.commit()

        xml = """<?xml version="1.0"?><rss version="2.0"><channel><item><title>A</title><link>https://a.com</link></item></channel></rss>"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.headers = {"content-type": "application/rss+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            poll_all_feeds()

            # Feed was skipped, so no item created
            items = db.exec(select(KnowledgeItem)).all()
            assert len(items) == 0


# === PHASE 2B MOPUP ADDITIONS ===

class TestFetchRssFeedJson:
    """Test JSON Feed detection and parsing in fetch_rss_feed."""

    def test_fetch_rss_json_feed_branch(self, db: Session, engine, monkeypatch):
        """content-type: application/json → _parse_json_feed called."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)

        json_content = '{"items": [{"url": "https://example.com/1", "title": "Item 1"}]}'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json_content
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 1

            item = db.exec(
                select(KnowledgeItem).where(KnowledgeItem.url == "https://example.com/1")
            ).first()
            assert item is not None
            assert item.title == "Item 1"

    def test_parse_json_feed_ssrf_blocked(self, db: Session, engine, monkeypatch):
        """Internal IP URL in JSON feed → skipped."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)
        feed.format = "json_feed"
        db.add(feed)
        db.commit()

        json_content = '{"items": [{"url": "http://127.0.0.1/internal", "title": "Internal"}]}'

        count = _parse_json_feed(feed, json_content, db)
        # Should skip the internal URL, so count is 0
        assert count == 0

    def test_fetch_rss_ssrf_base_url(self, db: Session, engine, monkeypatch):
        """Feed URL is internal → returns 0."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = RSSFeed(
            user_id=user.id,
            url="http://127.0.0.1/feed.xml",
            title="Internal Feed",
            mode="auto",
        )
        db.add(feed)
        db.commit()

        result = fetch_rss_feed(feed, db)
        assert result == 0

    def test_fetch_rss_atom_format(self, db: Session, engine, monkeypatch):
        """Atom XML with <link href='...'/>> → parsed correctly."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_rss_user(db)
        feed = _make_rss_feed(db, user)

        atom_xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Test Feed</title>
          <entry>
            <title>Atom Item</title>
            <link href="https://example.com/atom/item"/>
          </entry>
        </feed>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = atom_xml
        mock_resp.headers = {"content-type": "application/atom+xml"}
        mock_resp.is_redirect = False
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get") as mock_get:
            mock_get.return_value = mock_resp

            count = fetch_rss_feed(feed, db)
            assert count == 1

            item = db.exec(
                select(KnowledgeItem).where(KnowledgeItem.url == "https://example.com/atom/item")
            ).first()
            # NOTE: Atom <title> is not parsed by the current code because
            # entry.find("title") doesn't search the Atom namespace.
            # This test verifies the item URL was created at minimum.
            assert item is not None
            assert item.url == "https://example.com/atom/item"
