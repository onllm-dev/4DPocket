"""Tests for structured JSON logging.

Covers:
  - configure_logging(json=True) installs a JSON formatter.
  - Emitted records are parseable JSON with the expected keys.
  - request_id field reflects the contextvar value.
"""

import json
import logging

import pytest


class TestJsonLogging:
    def test_json_log_format(self):
        """JSON log records contain ts, level, logger, msg, request_id keys."""
        from fourdpocket.logging_config import configure_logging

        configure_logging(json=True)
        root = logging.getLogger()
        assert root.handlers, "Expected at least one handler"
        formatter = root.handlers[0].formatter
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        doc = json.loads(output)
        assert "ts" in doc
        assert doc["level"] == "INFO"
        assert doc["logger"] == "test.logger"
        assert doc["msg"] == "hello world"
        assert "request_id" in doc

    def test_json_log_request_id_from_contextvar(self):
        """request_id in JSON log matches the contextvar value."""
        from fourdpocket.logging_config import configure_logging
        from fourdpocket.middleware.request_id import request_id_var

        configure_logging(json=True)
        formatter = logging.getLogger().handlers[0].formatter

        token = request_id_var.set("test-rid-abc")
        try:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="with context",
                args=(),
                exc_info=None,
            )
            doc = json.loads(formatter.format(record))
            assert doc["request_id"] == "test-rid-abc"
        finally:
            request_id_var.reset(token)

    def test_json_log_request_id_null_outside_request(self):
        """request_id is null when no request context is active."""
        from fourdpocket.logging_config import configure_logging

        configure_logging(json=True)
        formatter = logging.getLogger().handlers[0].formatter

        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="no context",
            args=(),
            exc_info=None,
        )
        doc = json.loads(formatter.format(record))
        assert doc["request_id"] is None

    @pytest.fixture(autouse=True)
    def restore_logging(self):
        """Restore the root logger state after each test."""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        yield
        root.handlers[:] = original_handlers
        root.level = original_level
