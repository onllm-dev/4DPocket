"""Tests for the N-ranker RRF fusion (_rrf_fusion_n)."""

from unittest.mock import MagicMock

from fourdpocket.search.base import GraphHit, KeywordHit, VectorHit
from fourdpocket.search.service import SearchService


def _make_service():
    return SearchService(keyword=MagicMock(), vector=MagicMock())


class TestRrfFusionN:
    def test_single_ranker_passthrough_preserves_order(self):
        service = _make_service()
        hits = [
            KeywordHit(item_id="a", title_snippet="A"),
            KeywordHit(item_id="b", title_snippet="B"),
            KeywordHit(item_id="c", title_snippet="C"),
        ]
        results = service._rrf_fusion_n([("fts", hits)])
        assert [r.item_id for r in results] == ["a", "b", "c"]
        assert all(r.sources == ["fts"] for r in results)

    def test_three_ranker_merge_overlap_boosts_score(self):
        service = _make_service()
        kw = [KeywordHit(item_id="a"), KeywordHit(item_id="b")]
        vec = [VectorHit(item_id="b"), VectorHit(item_id="c")]
        graph = [GraphHit(item_id="b"), GraphHit(item_id="d")]

        results = service._rrf_fusion_n([
            ("fts", kw),
            ("semantic", vec),
            ("graph", graph),
        ])

        # b is in all three → highest
        assert results[0].item_id == "b"
        assert set(results[0].sources) == {"fts", "semantic", "graph"}
        ids = {r.item_id for r in results}
        assert ids == {"a", "b", "c", "d"}

    def test_empty_lists_handled(self):
        service = _make_service()
        results = service._rrf_fusion_n([("fts", []), ("semantic", []), ("graph", [])])
        assert results == []

    def test_zero_rankers_returns_empty(self):
        service = _make_service()
        assert service._rrf_fusion_n([]) == []

    def test_snippet_attribution_from_first_source_with_snippet(self):
        service = _make_service()
        # Graph hit has no snippets, FTS has them — result should carry FTS snippets
        graph = [GraphHit(item_id="x")]
        kw = [KeywordHit(item_id="x", title_snippet="T", content_snippet="C")]
        results = service._rrf_fusion_n([("graph", graph), ("fts", kw)])
        assert len(results) == 1
        assert results[0].title_snippet == "T"
        assert results[0].content_snippet == "C"
        assert set(results[0].sources) == {"graph", "fts"}

    def test_score_decreases_with_rank(self):
        service = _make_service()
        hits = [KeywordHit(item_id=f"item-{i}") for i in range(5)]
        results = service._rrf_fusion_n([("fts", hits)])
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        assert len(set(scores)) == 5  # all distinct

    def test_backward_compat_wrapper_delegates(self):
        """_rrf_fusion(kw, vec) still works for existing callers."""
        service = _make_service()
        kw = [KeywordHit(item_id="a")]
        vec = [VectorHit(item_id="b")]
        results = service._rrf_fusion(kw, vec)
        ids = {r.item_id for r in results}
        assert ids == {"a", "b"}
