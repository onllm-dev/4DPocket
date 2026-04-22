"""Tests for ExtractionPipeline.run(), asyncio handling, and error propagation."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session

from fourdpocket.models.base import ItemType, SourcePlatform
from fourdpocket.processors.base import ProcessorResult, ProcessorStatus
from fourdpocket.processors.pipeline import ExtractionPipeline, _map_item_type, _map_platform


class TestMapFunctions:
    """_map_platform and _map_item_type helpers."""

    @pytest.mark.parametrize("platform,expected", [
        ("github", SourcePlatform.github),
        ("reddit", SourcePlatform.reddit),
        ("youtube", SourcePlatform.youtube),
        ("medium", SourcePlatform.medium),
        ("hackernews", SourcePlatform.hackernews),
        ("stackoverflow", SourcePlatform.stackoverflow),
        ("generic", SourcePlatform.generic),
    ])
    def test_map_platform_valid(self, platform, expected):
        assert _map_platform(platform) == expected

    def test_map_platform_unknown_falls_back_to_generic(self):
        assert _map_platform("unknown_platform_xyz") == SourcePlatform.generic

    @pytest.mark.parametrize("item_type,expected", [
        ("note", ItemType.note),
        ("image", ItemType.image),
        ("pdf", ItemType.pdf),
        ("code_snippet", ItemType.code_snippet),
        ("url", ItemType.url),
    ])
    def test_map_item_type_valid(self, item_type, expected):
        assert _map_item_type(item_type) == expected

    def test_map_item_type_unknown_falls_back_to_url(self):
        assert _map_item_type("made_up_type") == ItemType.url


# ---------------------------------------------------------------------------
# Helper: build a mock processor that returns a specific ProcessorResult
# ---------------------------------------------------------------------------

def make_mock_processor(result: ProcessorResult) -> MagicMock:
    """Return a mock processor whose async process() yields `result`."""
    mock = MagicMock()
    async def async_process(url: str, **kwargs) -> ProcessorResult:
        return result
    mock.process = async_process
    return mock


def make_failing_mock_processor(exc: Exception) -> MagicMock:
    """Return a mock processor whose async process() raises `exc`."""
    mock = MagicMock()
    async def async_process(url: str, **kwargs) -> ProcessorResult:
        raise exc
    mock.process = async_process
    return mock


@contextmanager
def _patch_match_processor(mock_proc: MagicMock):
    """Patch match_processor in the pipeline module."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("fourdpocket.processors.pipeline.match_processor", lambda url: mock_proc)
        yield


class TestExtractionPipelineRun:
    """ExtractionPipeline.run() orchestrates matching, processing, and DB write."""

    def test_run_creates_item_in_db(self, engine):
        """Pipeline should write a KnowledgeItem to the DB."""

        mock_result = ProcessorResult(
            title="Linux Kernel",
            description="The Linux kernel source",
            content="Linux is a free open-source OS",
            source_platform="github",
            status=ProcessorStatus.success,
        )
        mock_proc = make_mock_processor(mock_result)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://github.com/torvalds/linux",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )

        assert item is not None
        assert item.user_id == user_id
        assert item.url == "https://github.com/torvalds/linux"
        assert item.title == "Linux Kernel"

    def test_run_maps_source_platform(self, engine):
        """Known platform should be stored as the SourcePlatform enum."""

        mock_result = ProcessorResult(
            title="Test",
            source_platform="reddit",
            status=ProcessorStatus.success,
        )
        mock_proc = make_mock_processor(mock_result)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://www.reddit.com/r/python/comments/abc/",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )

        assert item.source_platform == SourcePlatform.reddit

    def test_run_stores_content_and_metadata(self, engine):
        """Processor result fields should be transferred to the item."""

        mock_result = ProcessorResult(
            title="HN Post",
            description="A Hacker News post",
            content="Some content",
            media=[{"type": "image", "url": "https://example.com/img.jpg"}],
            metadata={"author": "alice"},
            source_platform="hackernews",
            item_type="article",
            status=ProcessorStatus.success,
        )
        mock_proc = make_mock_processor(mock_result)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://news.ycombinator.com/item?id=1",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )

        assert item.title == "HN Post"
        assert item.description == "A Hacker News post"
        assert item.content == "Some content"
        assert item.item_metadata.get("author") == "alice"

    def test_run_with_search_indexer(self, engine):
        """When search_indexer is provided, index_item should be called."""

        mock_result = ProcessorResult(title="Test", status=ProcessorStatus.success)
        mock_proc = make_mock_processor(mock_result)

        indexed_items = []

        class MockIndexer:
            def index_item(self, item):
                indexed_items.append(item)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                pipeline.run(
                    url="https://github.com/torvalds/linux",
                    user_id=user_id,
                    db=db,
                    search_indexer=MockIndexer(),
                )

        assert len(indexed_items) == 1

    def test_run_search_indexer_error_does_not_crash(self, engine):
        """Search indexing failure should be caught and logged but not propagate."""

        mock_result = ProcessorResult(title="Test", status=ProcessorStatus.success)
        mock_proc = make_mock_processor(mock_result)

        class BadIndexer:
            def index_item(self, item):
                raise RuntimeError("Search unavailable")

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://github.com/torvalds/linux",
                    user_id=user_id,
                    db=db,
                    search_indexer=BadIndexer(),
                )

        # Item was still created despite indexing failure
        assert item is not None

    def test_run_partial_result_sets_warning_metadata(self, engine):
        """When processor returns partial status, _processing_warning is set."""

        mock_result = ProcessorResult(
            title="https://unknown.example.com",
            source_platform="generic",
            status=ProcessorStatus.partial,
            error="HTTP 404: Not Found",
        )
        mock_proc = make_mock_processor(mock_result)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://unknown.example.com/page",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )

        assert item is not None
        assert "_processing_warning" in item.item_metadata

    def test_run_failed_result_sets_error_metadata(self, engine):
        """When processor returns failed status, _processing_error is set."""

        mock_result = ProcessorResult(
            title="https://unknown.example.com",
            source_platform="generic",
            status=ProcessorStatus.failed,
            error="Connection refused",
        )
        mock_proc = make_mock_processor(mock_result)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://unknown.example.com/page",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )

        assert item is not None
        assert "_processing_error" in item.item_metadata


class TestExtractionPipelineAsyncioHandling:
    """ExtractionPipeline.run() asyncio event loop edge cases."""

    def test_run_when_no_event_loop_exists(self, engine):
        """When no loop is running, asyncio.run() is called directly."""

        mock_result = ProcessorResult(title="Test", status=ProcessorStatus.success)
        mock_proc = make_mock_processor(mock_result)

        # Close any existing loop so we start clean
        try:
            asyncio.get_event_loop().close()
        except RuntimeError:
            pass

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://github.com/torvalds/linux",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )

        assert item is not None

    def test_run_with_already_running_loop(self, engine):
        """When an event loop is already running, ThreadPoolExecutor is used."""

        mock_result = ProcessorResult(title="Test", status=ProcessorStatus.success)
        mock_proc = make_mock_processor(mock_result)

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        async def run():
            with Session(engine) as db:
                with _patch_match_processor(mock_proc):
                    return pipeline.run(
                        url="https://github.com/torvalds/linux",
                        user_id=user_id,
                        db=db,
                        search_indexer=None,
                    )

        # asyncio.run() creates a fresh loop; inside the async context,
        # loop.is_running() == True, which exercises the ThreadPoolExecutor branch.
        item = asyncio.run(run())
        assert item is not None


class TestExtractionPipelineErrorPropagation:
    """Processor errors are caught and converted to ProcessorResult, not raised."""

    def test_processor_exception_does_not_bubble_up(self, engine):
        """If a processor raises, the pipeline handles it and creates a failed item."""

        mock_proc = make_failing_mock_processor(RuntimeError("Simulated processor failure"))

        pipeline = ExtractionPipeline()
        user_id = uuid.uuid4()

        with Session(engine) as db:
            with _patch_match_processor(mock_proc):
                item = pipeline.run(
                    url="https://unknown.example.com/page",
                    user_id=user_id,
                    db=db,
                    search_indexer=None,
                )
            assert item is not None
            assert "_processing_error" in item.item_metadata


class TestRuntimeErrorRetry:
    """Tests for RuntimeError inner Exception handler in pipeline."""

    def test_pipeline_runtime_error_inner_exception(self, engine, monkeypatch):
        """RuntimeError retry that also fails returns a failed ProcessorResult."""
        # Ensure a fresh event loop — a sibling test in this module closes its
        # loop deliberately, which leaves the worker in a no-current-loop
        # state under xdist. Install a new loop so `pipeline.run` can call
        # asyncio.get_event_loop() successfully.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            call_count = [0]

            def mock_process(url, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("first failure")
                raise Exception("second failure")

            mock_proc = MagicMock()
            mock_proc.process = mock_process

            pipeline = ExtractionPipeline()
            user_id = uuid.uuid4()

            with Session(engine) as db:
                with _patch_match_processor(mock_proc):
                    item = pipeline.run(
                        url="https://example.com/page",
                        user_id=user_id,
                        db=db,
                        search_indexer=None,
                    )
                # The pipeline should catch the second Exception and create a failed item
                assert item is not None
                assert "_processing_error" in item.item_metadata
                assert "second failure" in item.item_metadata["_processing_error"] or "Exception" in item.item_metadata["_processing_error"]
        finally:
            loop.close()
