"""Configuration tests."""

import os

from fourdpocket.config import Settings, get_settings


def test_default_settings():
    # Clear FDP_* env vars that may have been set by earlier tests in the suite
    # to ensure we get truly default values
    for key in list(os.environ):
        if key.startswith("FDP_"):
            del os.environ[key]
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


# === PHASE 3 MOPUP ADDITIONS ===

def test_settings_nested_env_prefix(monkeypatch):
    """FDP_DATABASE__URL overrides nested database.url."""
    monkeypatch.setenv("FDP_DATABASE__URL", "sqlite:///./test.db")
    monkeypatch.setenv("FDP_AUTH__MODE", "multi")
    # Clear singleton
    import fourdpocket.config as config_module
    config_module._settings = None
    settings = Settings()
    assert settings.database.url == "sqlite:///./test.db"
    assert settings.auth.mode == "multi"


def test_settings_storage_fields(monkeypatch):
    """Storage settings can be configured via env vars."""
    monkeypatch.setenv("FDP_STORAGE__BASE_PATH", "/tmp/custom/storage")
    monkeypatch.setenv("FDP_STORAGE__MAX_ARCHIVE_SIZE_MB", "100")
    # Clear singleton
    import fourdpocket.config as config_module
    config_module._settings = None
    settings = Settings()
    assert settings.storage.base_path == "/tmp/custom/storage"
    assert settings.storage.max_archive_size_mb == 100
