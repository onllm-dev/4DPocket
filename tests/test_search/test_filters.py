"""Tests for search filter parsing — parametrized."""

import pytest

from fourdpocket.search.filters import parse_filters, to_meilisearch_filter


class TestParseFilters:
    """Parametrized tests for parse_filters() — covers all filter syntax variants."""

    @pytest.mark.parametrize("query,expected_query,expected_filters", [
        # Plain query — no filters
        ("python programming", "python programming", {}),
        ("fastapi async", "fastapi async", {}),
        # Empty query — still returns empty dict for query key
        ("", "", {"query": ""}),
        # type: filter
        ("python type:article", "python", {"item_type": "article"}),
        ("rust type:video", "rust", {"item_type": "video"}),
        # source: filter (alias for source_platform)
        ("docker source:youtube", "docker", {"source_platform": "youtube"}),
        # platform: filter (another alias)
        ("golang platform:reddit", "golang", {"source_platform": "reddit"}),
        # tag: filter (single)
        ("python tag:programming", "python", {"tags": ["programming"]}),
        ("fastapi tag:tutorial", "fastapi", {"tags": ["tutorial"]}),
        # tag: filter (multiple)
        ("python tag:a tag:b", "python", {"tags": ["a", "b"]}),
        ("go tag:concurrency tag:golang", "go", {"tags": ["concurrency", "golang"]}),
        # after: filter
        ("fastapi after:2024-01", "fastapi", {"after": "2024-01"}),
        ("rust after:2023-06-15", "rust", {"after": "2023-06-15"}),
        # before: filter
        ("python before:2025-01", "python", {"before": "2025-01"}),
        # is:favorite
        ("python is:favorite", "python", {"is_favorite": True}),
        # is:archived
        ("rust is:archived", "rust", {"is_archived": True}),
        # has: filter
        ("podcast has:transcript", "podcast", {"has": ["transcript"]}),
        ("video has:summary has:transcript", "video", {"has": ["summary", "transcript"]}),
        # Multiple filters combined
        ("python type:article tag:tutorial after:2024-01", "python",
         {"item_type": "article", "tags": ["tutorial"], "after": "2024-01"}),
        # Complex: URL-like query with multiple filters
        ("docker type:video source:youtube tag:containers", "docker",
         {"item_type": "video", "source_platform": "youtube", "tags": ["containers"]}),
        # Quote stripping — quotes are stripped from values but remain in remaining query
        ('python tag:"quoted tag"', 'python  tag"', {"tags": ["quoted"]}),
        ("python tag:'single quoted'", "python  quoted'", {"tags": ["single"]}),
        # Case normalization
        ("Python TYPE:Article TAG:Programming", "Python",
         {"item_type": "Article", "tags": ["Programming"]}),
    ])
    def test_parse_filters(self, query, expected_query, expected_filters):
        result = parse_filters(query)

        assert result["query"] == expected_query
        for key, value in expected_filters.items():
            assert result.get(key) == value, f"Key '{key}' mismatch for query '{query}'"

    @pytest.mark.parametrize("query", [
        "just a plain search",
        "type:article",
        "tag:python",
    ])
    def test_parse_filters_query_key_always_present(self, query):
        """The 'query' key is always present, even when empty or filter-only."""
        result = parse_filters(query)
        assert "query" in result


class TestToMeilisearchFilter:
    """Tests for to_meilisearch_filter() conversion helper."""

    def test_basic_filter(self):
        parsed = {"item_type": "article"}
        result = to_meilisearch_filter(parsed, "user-123")
        assert 'user_id = "user-123"' in result
        assert 'item_type = "article"' in result

    def test_no_filters(self):
        parsed = {"query": "python"}
        result = to_meilisearch_filter(parsed, "user-123")
        assert result == 'user_id = "user-123"'

    def test_is_favorite(self):
        parsed = {"is_favorite": True}
        result = to_meilisearch_filter(parsed, "user-456")
        assert "is_favorite = true" in result

    def test_is_archived(self):
        parsed = {"is_archived": True}
        result = to_meilisearch_filter(parsed, "user-456")
        assert "is_archived = true" in result

    def test_combined_filters(self):
        parsed = {
            "item_type": "article",
            "source_platform": "youtube",
            "is_favorite": True,
        }
        result = to_meilisearch_filter(parsed, "user-789")
        assert 'user_id = "user-789"' in result
        assert 'item_type = "article"' in result
        assert 'source_platform = "youtube"' in result
        assert "is_favorite = true" in result
