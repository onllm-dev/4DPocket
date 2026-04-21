"""Tests for the graph-anchored ranker."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session

from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.base import KeywordHit
from fourdpocket.search.graph_ranker import _tokenize, graph_anchored_hits
from fourdpocket.search.service import SearchService


@pytest.fixture
def graph_user(db: Session):
    user = User(
        email="graph@example.com",
        username="graphuser",
        password_hash="$2b$12$fakehash",
        display_name="Graph Test",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def graph_fixture(db: Session, graph_user):
    """3 items, 2 entities (Rust, WASM), 1 relation Rust↔WASM.

    - item_rust: mentions Rust only
    - item_rust_wasm: mentions both (via relation)
    - item_unrelated: mentions neither
    """
    items = {
        "rust": KnowledgeItem(
            user_id=graph_user.id, title="Rust Basics", content="About Rust."
        ),
        "rust_wasm": KnowledgeItem(
            user_id=graph_user.id,
            title="Rust to WASM",
            content="Rust compiles to WebAssembly.",
        ),
        "unrelated": KnowledgeItem(
            user_id=graph_user.id, title="Docker", content="Containers."
        ),
    }
    for item in items.values():
        db.add(item)
    db.commit()
    for item in items.values():
        db.refresh(item)

    rust = Entity(
        user_id=graph_user.id,
        canonical_name="Rust",
        entity_type="tool",
        description="Systems language.",
        item_count=2,
    )
    wasm = Entity(
        user_id=graph_user.id,
        canonical_name="WebAssembly",
        entity_type="tool",
        description="Binary instruction format.",
        item_count=1,
    )
    db.add(rust)
    db.add(wasm)
    db.commit()
    db.refresh(rust)
    db.refresh(wasm)

    # Alias so "WASM" query finds WebAssembly entity
    db.add(EntityAlias(entity_id=wasm.id, alias="WASM", source="extraction"))
    db.commit()

    # ItemEntity links
    db.add(ItemEntity(item_id=items["rust"].id, entity_id=rust.id, salience=0.8))
    db.add(ItemEntity(item_id=items["rust_wasm"].id, entity_id=rust.id, salience=0.9))
    db.add(ItemEntity(item_id=items["rust_wasm"].id, entity_id=wasm.id, salience=0.9))
    db.commit()

    # Normalized edge (smaller UUID first)
    src, tgt = (rust.id, wasm.id) if str(rust.id) < str(wasm.id) else (wasm.id, rust.id)
    db.add(EntityRelation(
        user_id=graph_user.id,
        source_id=src,
        target_id=tgt,
        keywords="compiles-to",
        weight=1.0,
        item_count=1,
    ))
    db.commit()

    return {
        "items": items,
        "rust": rust,
        "wasm": wasm,
        "user": graph_user,
    }


class TestTokenize:
    def test_lowercase_and_strip_punctuation(self):
        assert _tokenize("Rust, WASM!") == ["rust", "wasm"]

    def test_drops_stopwords_and_short_tokens(self):
        assert _tokenize("the a is X rust") == ["rust"]

    def test_empty_query_returns_empty(self):
        assert _tokenize("") == []
        assert _tokenize("   ") == []


class TestGraphAnchoredHits:
    def test_seed_by_canonical_name(self, db: Session, graph_fixture):
        user = graph_fixture["user"]
        hits = graph_anchored_hits(db, "rust", user.id)
        item_ids = {h.item_id for h in hits}
        # Both rust and rust_wasm items should appear
        assert str(graph_fixture["items"]["rust"].id) in item_ids
        assert str(graph_fixture["items"]["rust_wasm"].id) in item_ids
        # Unrelated item should NOT appear
        assert str(graph_fixture["items"]["unrelated"].id) not in item_ids

    def test_seed_by_alias(self, db: Session, graph_fixture):
        user = graph_fixture["user"]
        hits = graph_anchored_hits(db, "wasm", user.id)
        item_ids = {h.item_id for h in hits}
        # Only rust_wasm mentions WebAssembly directly, but 1-hop expansion
        # via Rust↔WASM relation also pulls the rust-only item.
        assert str(graph_fixture["items"]["rust_wasm"].id) in item_ids

    def test_one_hop_expansion_pulls_neighbor_items(self, db: Session, graph_fixture):
        """Query matches WASM → expand to Rust neighbor → rust-only item appears."""
        user = graph_fixture["user"]
        hits = graph_anchored_hits(db, "wasm", user.id, hop_decay=0.5)
        item_ids = {h.item_id for h in hits}
        # 1-hop expansion pulls the rust-only item via Rust↔WASM edge
        assert str(graph_fixture["items"]["rust"].id) in item_ids

    def test_items_mentioning_multiple_seeds_outrank_single_seed(
        self, db: Session, graph_fixture
    ):
        user = graph_fixture["user"]
        # Query hits both Rust and WASM as seeds
        hits = graph_anchored_hits(db, "rust wasm", user.id)
        assert len(hits) >= 2
        # rust_wasm mentions both entities → higher score than rust-only item
        scores = {h.item_id: h.score for h in hits}
        rust_wasm_id = str(graph_fixture["items"]["rust_wasm"].id)
        rust_id = str(graph_fixture["items"]["rust"].id)
        assert scores[rust_wasm_id] > scores[rust_id]

    def test_empty_query_returns_empty(self, db: Session, graph_fixture):
        user = graph_fixture["user"]
        assert graph_anchored_hits(db, "", user.id) == []
        assert graph_anchored_hits(db, "   ", user.id) == []

    def test_no_matching_entities_returns_empty(self, db: Session, graph_fixture):
        user = graph_fixture["user"]
        assert graph_anchored_hits(db, "kubernetes", user.id) == []

    def test_user_scoping(self, db: Session, graph_fixture):
        """Another user's query finds nothing in this user's graph."""
        other_user_id = uuid.uuid4()
        assert graph_anchored_hits(db, "rust", other_user_id) == []

    def test_top_k_limit(self, db: Session, graph_fixture):
        user = graph_fixture["user"]
        hits = graph_anchored_hits(db, "rust", user.id, k=1)
        assert len(hits) == 1

    def test_hop_decay_reduces_neighbor_score(self, db: Session, graph_fixture):
        """With hop_decay=0, neighbor items should not get score from relation."""
        user = graph_fixture["user"]
        # Query only matches WASM (not Rust). Rust items only appear via relation.
        hits_no_decay = graph_anchored_hits(db, "wasm", user.id, hop_decay=0.0)
        item_ids = {h.item_id for h in hits_no_decay}
        # Rust-only item has no direct WASM link, so with hop_decay=0 it drops out
        assert str(graph_fixture["items"]["rust"].id) not in item_ids


class TestSearchServiceIntegration:
    def test_graph_flag_default_on_fuses_graph_hits(
        self, db: Session, graph_fixture, monkeypatch
    ):
        """Default config (flag on) — graph ranker contributes; sources include 'graph'."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = []  # FTS/vector find nothing

        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock()
        )

        # Force admin-override resolver to return no overrides — env default wins
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {},
        )

        service = SearchService(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "rust", user_id=graph_fixture["user"].id)

        assert len(results) >= 1
        assert all("graph" in r.sources for r in results)
        item_ids = {r.item_id for r in results}
        assert str(graph_fixture["items"]["rust"].id) in item_ids

    def test_admin_override_disables_graph_ranker(
        self, db: Session, graph_fixture, monkeypatch
    ):
        """Admin override (graph_ranker_enabled=False) suppresses graph ranker."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = [
            KeywordHit(item_id=str(graph_fixture["items"]["unrelated"].id), rank=1.0),
        ]

        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock()
        )
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {"graph_ranker_enabled": False},
        )

        service = SearchService(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "rust", user_id=graph_fixture["user"].id)

        assert len(results) == 1
        assert "graph" not in results[0].sources

    def test_env_default_disable_is_honored(
        self, db: Session, graph_fixture, monkeypatch
    ):
        """When env default flips to False and no admin override exists, ranker is off."""
        from fourdpocket.config import get_settings

        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = []

        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock()
        )
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {},
        )
        settings = get_settings()
        monkeypatch.setattr(settings.search, "graph_ranker_enabled", False)

        service = SearchService(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "rust", user_id=graph_fixture["user"].id)

        assert results == []
