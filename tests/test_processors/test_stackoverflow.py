"""Tests for Stack Overflow / Stack Exchange processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.stackoverflow import (
    StackOverflowProcessor,
    _extract_question_id,
    _extract_site,
)


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_success(self):
        """Happy path: valid SO question → ProcessorResult with question + answers."""
        processor = StackOverflowProcessor()
        url = "https://stackoverflow.com/questions/12345678/how-do-i-extract-a-substring-in-python"

        # Mock the rich SE API response
        mock_response = {
            "items": [{
                "question_id": 12345678,
                "title": "How do I extract a substring in Python?",
                "body": "<p>I have a string and want to extract a substring...</p>",
                "tags": ["python", "string", "substring"],
                "owner": {"display_name": "PythonDev"},
                "score": 42,
                "view_count": 1234,
                "creation_date": 1700000000,
                "comments": [
                    {
                        "comment_id": 111,
                        "body": "Have you tried using slicing?",
                        "owner": {"display_name": "ExpertDev"},
                        "score": 5,
                        "creation_date": 1700000100,
                    }
                ],
                "answers": [
                    {
                        "answer_id": 999,
                        "is_accepted": True,
                        "body": "<p>You can use slicing: <code>s[1:5]</code></p>",
                        "owner": {"display_name": "ExpertDev"},
                        "score": 100,
                        "creation_date": 1700000200,
                        "comments": [
                            {
                                "comment_id": 222,
                                "body": "This worked! Thanks.",
                                "owner": {"display_name": "PythonDev"},
                                "score": 3,
                                "creation_date": 1700000300,
                            }
                        ],
                    },
                    {
                        "answer_id": 998,
                        "is_accepted": False,
                        "body": "<p>Use regex: <code>re.search(r'pattern', s)</code></p>",
                        "owner": {"display_name": "RegexFan"},
                        "score": 20,
                        "creation_date": 1700000400,
                        "comments": [],
                    },
                ],
            }]
        }

        route = respx.get(
            url__regex=r"https://api\.stackexchange\.com/2\.3/questions/12345678"
        ).mock(
            return_value=Response(200, json=mock_response)
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        assert "substring" in result.title
        assert result.source_platform == "stackoverflow"
        assert result.metadata["question_id"] == "12345678"
        assert result.metadata["site"] == "stackoverflow"
        assert result.metadata["score"] == 42
        assert "python" in result.metadata["tags"]
        assert result.metadata["has_accepted_answer"] is True
        # Check sections
        section_kinds = [s.kind for s in result.sections]
        assert "question" in section_kinds
        assert "accepted_answer" in section_kinds
        assert "comment" in section_kinds
        assert len(result.sections) > 0

    @respx.mock
    def test_extract_network_error(self):
        """Network error → failed result."""
        processor = StackOverflowProcessor()
        url = "https://stackoverflow.com/questions/12345678/test"

        respx.get(url__regex=r"https://api\.stackexchange\.com").mock(
            side_effect=Exception("Connection refused")
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"

    def test_extract_invalid_url(self):
        """URL without question ID → failed result."""
        processor = StackOverflowProcessor()
        url = "https://stackoverflow.com/users/test"

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"
        assert "question ID" in result.error

    def test_extract_question_id_extraction(self):
        """Various SO URL formats extract correctly."""
        assert _extract_question_id(
            "https://stackoverflow.com/questions/12345678/how-do-i"
        ) == "12345678"
        assert _extract_question_id(
            "https://serverfault.com/questions/123456/test"
        ) == "123456"
        assert _extract_question_id(
            "https://unix.stackexchange.com/questions/123456/shell-scripting"
        ) == "123456"
        assert _extract_question_id(
            "https://stackoverflow.com/users/test"
        ) is None

    def test_extract_site_extraction(self):
        """Host maps to correct SE site parameter."""
        assert _extract_site("https://stackoverflow.com/questions/123/test") == "stackoverflow"
        assert _extract_site("https://serverfault.com/questions/123/test") == "serverfault"
        assert _extract_site("https://superuser.com/questions/123/test") == "superuser"
        assert _extract_site("https://askubuntu.com/questions/123/test") == "askubuntu"
        assert _extract_site("https://math.stackexchange.com/questions/123/test") == "math"
        assert _extract_site("https://datascience.stackexchange.com/questions/123/test") == "datascience"
        assert _extract_site("https://custom.stackexchange.com/questions/123/test") == "stackoverflow"

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        # StackOverflowProcessor should match these URLs
        proc = match_processor("https://stackoverflow.com/questions/123/test")
        assert type(proc).__name__ == "StackOverflowProcessor"

        proc = match_processor("https://serverfault.com/questions/456/test")
        assert type(proc).__name__ == "StackOverflowProcessor"

        # Should fall back to generic for non-question URLs
        proc = match_processor("https://stackoverflow.com/users/test")
        assert type(proc).__name__ == "GenericURLProcessor"
