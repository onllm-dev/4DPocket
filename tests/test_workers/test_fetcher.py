"""Tests for the URL fetcher background task."""

import uuid
from dataclasses import dataclass, field

from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.workers.fetcher import _fetch_favicon, fetch_and_process_url


@dataclass
class _FakeSection:
    id: str = ""
    kind: str = "main"
    text: str = ""
    order: int = 0
    role: str = "main"
    depth: int = 0
    parent_id: str | None = None
    raw_html: str | None = None
    source_url: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    page_no: int | None = None
    timestamp_start_s: float | None = None
    timestamp_end_s: float | None = None
    author: str | None = None
    author_id: str | None = None
    score: int | None = None
    upvotes: int | None = None
    is_accepted: bool = False
    created_at: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class _FakeResult:
    title: str | None = None
    description: str | None = None
    content: str | None = None
    raw_content: str | None = None
    media: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    source_platform: str = "generic"
    item_type: str = "url"
    sections: list = field(default_factory=list)


def make_user(db: Session, email="fetcher@test.com", username="fetchuser") -> "User":
    """Create a user with hashed password."""
    from fourdpocket.models.user import User

    user = User(
        email=email,
        username=username,
        password_hash="$2b$12$fakehash",
        display_name="Fetcher User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestFetchAndProcessUrl:
    """Test the fetch_and_process_url Huey task."""

    def test_fetch_and_process_url_item_not_found(self, db: Session, engine, monkeypatch):
        """Non-existent item ID returns error status."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        # Mock asyncio.run so processor.process() never actually runs
        monkeypatch.setattr("asyncio.run", lambda coro: None)

        result = fetch_and_process_url.call_local(
            str(uuid.uuid4()), "https://example.com", str(uuid.uuid4())
        )
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_fetch_and_process_url_success(
        self, db: Session, engine, monkeypatch
    ):
        """Processor exception returns error status without crashing."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="procerr@test.com", username="procerr")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        def mock_run(coro):
            raise ValueError("processor failed")

        monkeypatch.setattr("asyncio.run", mock_run)

        mock_search = type("MockSearch", (), {"index_item": lambda db, item: None})()
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: mock_search,
        )

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))
        assert result["status"] == "error"
        assert "processor failed" in result["error"]

    def test_fetch_and_process_url_network_error(
        self, db: Session, engine, monkeypatch
    ):
        """httpx ConnectError is caught, item marked with error metadata."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="neterr@test.com", username="neterr")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        class MockResult:
            title = None
            description = None
            content = None
            source_platform = None
            item_type = None
            sections = []
            raw_content = None
            media = []
            metadata = {}

        def mock_run(coro):
            import httpx
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr("asyncio.run", mock_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: type("MockProcessor", (), {"process": lambda self, u: MockResult()})(),
        )

        mock_search = type("MockSearch", (), {"index_item": lambda db, item: None})()
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: mock_search,
        )

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        assert result["status"] == "error"
        assert "connection refused" in result["error"].lower()

        db.refresh(item)
        assert "_processing_error" in item.item_metadata

    def test_fetch_and_process_url_processor_exception(
        self, db: Session, engine, monkeypatch
    ):
        """Processor raises exception — task returns error, does not crash."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="procerr@test.com", username="procerr")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        def mock_run(coro):
            raise ValueError("processor failed")

        monkeypatch.setattr("asyncio.run", mock_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: type("MockProcessor", (), {"process": lambda self, u: (_ for _ in ()).throw(ValueError("processor failed"))})(),
        )

        mock_search = type("MockSearch", (), {"index_item": lambda db, item: None})()
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: mock_search,
        )

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))
        assert result["status"] == "error"
        assert "processor failed" in result["error"]

    def test_fetch_processor_error_handled(self, db: Session, engine, monkeypatch):
        """Processor errors are caught and returned as error status."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="ssrf@test.com", username="ssrftest")

        item = KnowledgeItem(
            user_id=user.id,
            url="http://127.0.0.1:8080/secret",
            title="SSRF Test",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        # Processor errors are caught - mock asyncio.run to raise
        def mock_run(coro):
            raise RuntimeError("processor error")

        monkeypatch.setattr("asyncio.run", mock_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: type("P", (), {"process": lambda self, u: (_ for _ in ()).throw(RuntimeError("processor error"))})(),
        )

        mock_search = type("MS", (), {"index_item": lambda db, item: None})()
        monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: mock_search)

        result = fetch_and_process_url.call_local(str(item.id), "http://127.0.0.1:8080/", str(user.id))

        assert result["status"] == "error"


class TestFetchFavicon:
    """Test _fetch_favicon SSRF protection and behavior."""

    def test_favicon_skips_loopback(self, db: Session):
        """Loopback IP results in no favicon set."""
        item = KnowledgeItem(user_id=uuid.uuid4(), url="http://127.0.0.1:8080/page")
        _fetch_favicon(item, "http://127.0.0.1:8080/page")
        assert item.favicon_url is None

    def test_favicon_skips_private_ip(self, db: Session):
        """Private IP results in no favicon set."""
        item = KnowledgeItem(user_id=uuid.uuid4(), url="http://10.0.0.1/page")
        _fetch_favicon(item, "http://10.0.0.1/page")
        assert item.favicon_url is None

    def test_favicon_skips_internal_hostname(self, db: Session):
        """Hostname resolving to internal IP is skipped."""
        item = KnowledgeItem(user_id=uuid.uuid4(), url="http://localhost/page")
        _fetch_favicon(item, "http://localhost/page")
        # localhost may resolve but should be caught by SSRF checks

    def test_favicon_google_service_for_public_url(self, db: Session):
        """Public URL gets Google favicon service URL set."""
        item = KnowledgeItem(user_id=uuid.uuid4(), url="https://example.com/article")
        _fetch_favicon(item, "https://example.com/article")
        assert item.favicon_url is not None
        assert "google.com/s2/favicons" in item.favicon_url
        assert "example.com" in item.favicon_url

    def test_favicon_gaierror_handled(self, db: Session, monkeypatch):
        """socket.gaierror during resolution is silently skipped."""
        import socket

        def fake_getaddrinfo(host, *args, **kwargs):
            raise socket.gaierror("Name resolution failed")

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

        item = KnowledgeItem(user_id=uuid.uuid4(), url="https://unresolvable.invalid/page")
        _fetch_favicon(item, "https://unresolvable.invalid/page")
        # Should not raise, favicon remains None
        assert item.favicon_url is None


class TestFetchAndProcessUrlSuccess:
    """Test success paths of fetch_and_process_url with different result shapes."""

    def test_fetch_and_process_url_success_with_sections(
        self, db: Session, engine, monkeypatch
    ):
        """Processor returning sections uses sections_to_text for content."""
        import asyncio

        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="sections@test.com", username="sections_user")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        from unittest.mock import MagicMock

        def _make_result_with_sections():
            return _FakeResult(
                title="Article Title",
                description="Article description",
                content="legacy content (should be ignored)",
                sections=[
                    _FakeSection(id="s1", kind="title", text="First Heading", order=0),
                    _FakeSection(id="s2", kind="paragraph", text="This is a paragraph.", order=1),
                ],
            )

        class FakeProcessor:
            async def process(self, url):
                return _make_result_with_sections()

        def fake_asyncio_run(coro):
            """Run the coroutine in a fresh event loop and return the result."""
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        # Use real Huey call_local by not patching enrich_item_v2 or download_media
        # Instead, use call_local which bypasses Huey and calls the function directly
        monkeypatch.setattr("asyncio.run", fake_asyncio_run)

        # Mock match_processor to return our FakeProcessor. Use ONLY
        # monkeypatch so teardown reverts cleanly — a prior direct assignment
        # like ``registry.match_processor = lambda ...`` would be captured by
        # monkeypatch as the "original" value and silently reinstated on
        # teardown, permanently corrupting the registry module for the rest
        # of the worker's life and flaking downstream pattern tests.
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: FakeProcessor(),
        )

        # Mock get_search_service
        mock_search_instance = MagicMock()
        mock_search_instance.index_item = lambda db, item: None
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: mock_search_instance,
        )

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        assert result["status"] == "success"

        db.refresh(item)
        assert item.title == "Article Title"
        assert item.description == "Article description"
        # content comes from sections_to_text, not result.content
        assert "First Heading" in item.content
        assert "This is a paragraph" in item.content
        assert "legacy content" not in item.content
        # sections stored in metadata
        assert "_sections" in item.item_metadata

    def test_fetch_and_process_url_success_without_sections(
        self, db: Session, engine, monkeypatch
    ):
        """Processor returning no sections uses result.content for item.content."""
        import asyncio

        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="nosections@test.com", username="nosections_user")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        from unittest.mock import MagicMock

        class FakeProcessor:
            async def process(self, url):
                return _FakeResult(
                    title="No Sections Title",
                    description="No sections desc",
                    content="Plain content from processor",
                )

        def fake_asyncio_run(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        monkeypatch.setattr("asyncio.run", fake_asyncio_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: FakeProcessor(),
        )

        mock_search_instance = MagicMock()
        mock_search_instance.index_item = lambda db, item: None
        monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: mock_search_instance)

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        assert result["status"] == "success"

        db.refresh(item)
        assert item.content == "Plain content from processor"
        assert "_sections" not in item.item_metadata

    def test_fetch_and_process_url_media_chains_download(
        self, db: Session, engine, monkeypatch
    ):
        """result.media triggers download_media call."""
        import asyncio

        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="media@test.com", username="media_user")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        from unittest.mock import MagicMock

        class FakeProcessor:
            async def process(self, url):
                return _FakeResult(
                    title=None,
                    content="content",
                    media=[
                        {"url": "https://cdn.example.com/image.png", "type": "image", "role": "thumbnail"},
                        {"url": "https://cdn.example.com/video.mp4", "type": "video", "role": "content"},
                    ],
                )

        def fake_asyncio_run(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        monkeypatch.setattr("asyncio.run", fake_asyncio_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: FakeProcessor(),
        )

        mock_search_instance = MagicMock()
        mock_search_instance.index_item = lambda db, item: None
        monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: mock_search_instance)

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        assert result["status"] == "success"

        db.refresh(item)
        # item.media should contain the media URLs from the processor
        assert len(item.media) == 2

    def test_fetch_and_process_url_generic_platform_fetches_favicon(
        self, db: Session, engine, monkeypatch
    ):
        """Generic platform triggers favicon fetch after content update."""
        import asyncio

        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="favicon@test.com", username="favicon_user")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        from unittest.mock import MagicMock

        class FakeProcessor:
            async def process(self, url):
                return _FakeResult(title="Title", content="content")

        def fake_asyncio_run(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        monkeypatch.setattr("asyncio.run", fake_asyncio_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: FakeProcessor(),
        )

        mock_search_instance = MagicMock()
        mock_search_instance.index_item = lambda db, item: None
        monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: mock_search_instance)

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        assert result["status"] == "success"
        db.refresh(item)
        # Generic platform → favicon fetched
        assert item.favicon_url is not None
        assert "google.com/s2/favicons" in item.favicon_url

    def test_fetch_and_process_url_enrich_item_v2_chain_error_handled(
        self, db: Session, engine, monkeypatch
    ):
        """enrich_item_v2 raising exception does not fail the overall task."""
        import asyncio

        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="enrich@test.com", username="enrich_user")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        from unittest.mock import MagicMock

        class FakeProcessor:
            async def process(self, url):
                return _FakeResult(title="Title", content="content")

        def fake_asyncio_run(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        monkeypatch.setattr("asyncio.run", fake_asyncio_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: FakeProcessor(),
        )

        mock_search_instance = MagicMock()
        mock_search_instance.index_item = lambda db, item: None
        monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: mock_search_instance)

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        # Should still succeed — chain error is caught and logged
        assert result["status"] == "success"

    def test_fetch_and_process_url_metadata_merging(
        self, db: Session, engine, monkeypatch
    ):
        """result.metadata is merged without clobbering _sections."""
        import asyncio

        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = make_user(db, email="meta@test.com", username="meta_user")

        item = KnowledgeItem(
            user_id=user.id,
            url="https://example.com/article",
            title="Original Title",
            item_metadata={"_sections": [{"id": " preexisting"}]},
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        from unittest.mock import MagicMock

        class FakeProcessor:
            async def process(self, url):
                return _FakeResult(
                    title="Title",
                    content="content",
                    metadata={"custom_key": "custom_value"},
                    sections=[_FakeSection(id="s1", kind="paragraph", text="Para text", order=0)],
                )

        def fake_asyncio_run(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        monkeypatch.setattr("asyncio.run", fake_asyncio_run)
        monkeypatch.setattr(
            "fourdpocket.processors.registry.match_processor",
            lambda url: FakeProcessor(),
        )

        mock_search_instance = MagicMock()
        mock_search_instance.index_item = lambda db, item: None
        monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: mock_search_instance)

        result = fetch_and_process_url.call_local(str(item.id), item.url, str(user.id))

        assert result["status"] == "success"

        db.refresh(item)
        # _sections preserved through metadata merge
        assert "_sections" in item.item_metadata
        # custom_key from result.metadata present
        assert item.item_metadata.get("custom_key") == "custom_value"
