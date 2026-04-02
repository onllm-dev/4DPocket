"""Configuration tests."""

from fourdpocket.config import Settings, get_settings


def test_default_settings():
    settings = Settings()
    assert settings.database.url == "sqlite:///./data/4dpocket.db"
    assert settings.search.backend == "sqlite"
    assert settings.ai.chat_provider == "ollama"
    assert settings.auth.mode == "single"
    assert settings.server.port == 4040
    assert settings.ai.tag_confidence_threshold == 0.7
    assert settings.ai.tag_suggestion_threshold == 0.4


def test_get_settings_returns_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
