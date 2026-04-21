"""Tests for the search admin-override resolver."""

from fourdpocket.search.admin_config import get_resolved_search_config


class TestResolver:
    def test_env_defaults_when_no_overrides(self, monkeypatch):
        """With no DB overrides, env defaults come through unchanged."""
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {},
        )
        config = get_resolved_search_config()
        assert config["graph_ranker_enabled"] is True  # env default flipped to True
        assert 0.0 <= config["graph_ranker_hop_decay"] <= 1.0
        assert config["graph_ranker_top_k"] >= 1

    def test_admin_override_false_wins_over_env_true(self, monkeypatch):
        """Admin flag=False overrides env flag=True (admin wins even for falsy bool)."""
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {"graph_ranker_enabled": False},
        )
        config = get_resolved_search_config()
        assert config["graph_ranker_enabled"] is False

    def test_admin_override_numeric(self, monkeypatch):
        """Numeric overrides propagate."""
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {"graph_ranker_hop_decay": 0.2, "graph_ranker_top_k": 10},
        )
        config = get_resolved_search_config()
        assert config["graph_ranker_hop_decay"] == 0.2
        assert config["graph_ranker_top_k"] == 10

    def test_unknown_keys_ignored(self, monkeypatch):
        """Overrides outside the known key set are dropped silently."""
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {"unknown_key": "boom", "graph_ranker_enabled": False},
        )
        config = get_resolved_search_config()
        assert "unknown_key" not in config
        assert config["graph_ranker_enabled"] is False

    def test_none_override_is_ignored(self, monkeypatch):
        """None in overrides does not clobber env value."""
        monkeypatch.setattr(
            "fourdpocket.search.admin_config.get_search_overrides_from_db",
            lambda: {"graph_ranker_enabled": None},
        )
        config = get_resolved_search_config()
        # None was ignored, env default wins
        assert config["graph_ranker_enabled"] is True
