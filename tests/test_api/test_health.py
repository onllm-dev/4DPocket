"""Health endpoint tests.

Covers both the simple liveness probe and the detailed health check.
"""

import pytest


class TestHealthLiveness:
    """Simple /api/v1/health liveness probe."""

    def test_health_check(self, client):
        """GET /api/v1/health returns 200 with ok status."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_no_auth_required(self, client):
        """Liveness probe is accessible without authentication."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestDetailedHealth:
    """GET /api/v1/health/detailed deep probe."""

    def test_detailed_health_returns_200(self, client):
        """Detailed health endpoint always returns HTTP 200."""
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 200

    def test_detailed_health_no_auth_required(self, client):
        """Detailed health is publicly accessible without credentials."""
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 200

    def test_detailed_health_shape(self, client):
        """Response contains status, version, and checks dict."""
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        assert "status" in body
        assert body["status"] in ("ok", "degraded")
        assert "version" in body
        assert "checks" in body
        checks = body["checks"]
        assert "database" in checks
        assert "search_keyword" in checks
        assert "search_vector" in checks
        assert "worker" in checks

    def test_detailed_health_database_check(self, client):
        """Database check reports ok=True with a latency_ms value in tests."""
        response = client.get("/api/v1/health/detailed")
        db_check = response.json()["checks"]["database"]
        assert db_check["ok"] is True
        assert isinstance(db_check["latency_ms"], int)
        assert db_check["error"] is None

    def test_detailed_health_keyword_backend(self, client):
        """Keyword backend check reports ok=True and a backend label."""
        response = client.get("/api/v1/health/detailed")
        kw = response.json()["checks"]["search_keyword"]
        assert kw["ok"] is True
        assert kw["backend"] in ("sqlite_fts", "meilisearch")

    def test_detailed_health_version_matches_package(self, client):
        """Version in the response matches the installed package version."""
        from fourdpocket import __version__

        response = client.get("/api/v1/health/detailed")
        assert response.json()["version"] == __version__

    def test_detailed_health_status_ok_when_all_checks_pass(self, client):
        """Overall status is 'ok' when database and search backends are up."""
        response = client.get("/api/v1/health/detailed")
        body = response.json()
        # In the test environment DB is in-memory and sqlite_fts is init'd, so
        # database and search_keyword should both be ok.  Worker may be None
        # (no Huey db in tests), which does NOT degrade status.
        db_ok = body["checks"]["database"]["ok"]
        kw_ok = body["checks"]["search_keyword"]["ok"]
        if db_ok and kw_ok:
            assert body["status"] == "ok"

    def test_detailed_health_degraded_on_db_failure(self, client, monkeypatch):
        """Status is 'degraded' when the database check fails."""
        from fourdpocket.api import health as health_module

        def _bad_db():
            return {"ok": False, "latency_ms": None, "error": "connection refused"}

        monkeypatch.setattr(health_module, "_check_database", _bad_db)

        response = client.get("/api/v1/health/detailed")
        assert response.json()["status"] == "degraded"
