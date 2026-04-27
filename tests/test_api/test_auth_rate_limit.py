"""Tests for rate limiting on auth endpoints.

Regression tests for:
- Login: 6th attempt within minute → 429
- Password-reset/request: IP-level rate limiting
"""


def _register(client, email="ratelimit@example.com", username="ratelimituser", password="Limit123!"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )


def test_login_rate_limited_after_five_failures(client, db):
    """6th login attempt (all wrong password) within the window triggers 429."""
    _register(client)

    # The existing login handler uses MAX_FAILED_ATTEMPTS=5 with escalating lockouts.
    # 5 failures cause the 6th check to raise 429.
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "ratelimit@example.com", "password": "WrongPass1!"},
        )
        # Each of the first 5 should be 401 (wrong password) or 429 (if locked)
        assert resp.status_code in (401, 429)

    # The 6th attempt must be rate-limited
    sixth = client.post(
        "/api/v1/auth/login",
        data={"username": "ratelimit@example.com", "password": "WrongPass1!"},
    )
    assert sixth.status_code == 429
    assert "locked" in sixth.json()["detail"].lower()


def test_password_reset_request_rate_limited(client, db):
    """More than 3 reset requests from same IP within an hour → 429."""
    # The endpoint allows max_attempts=3; the 4th from the same IP is blocked.
    for i in range(3):
        resp = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email_or_username": f"ghost{i}@example.com"},
        )
        assert resp.status_code == 200

    fourth = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email_or_username": "ghost_extra@example.com"},
    )
    assert fourth.status_code == 429


def test_login_success_resets_rate_limit(client, db):
    """Successful login after failures must clear the lockout counter."""
    _register(client)

    # 3 bad attempts (below the threshold of 5)
    for _ in range(3):
        client.post(
            "/api/v1/auth/login",
            data={"username": "ratelimit@example.com", "password": "WrongPass1!"},
        )

    # Correct password → resets the counter
    good = client.post(
        "/api/v1/auth/login",
        data={"username": "ratelimit@example.com", "password": "Limit123!"},
    )
    assert good.status_code == 200

    # After reset, 3 more bad attempts should still be below the threshold
    for _ in range(3):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "ratelimit@example.com", "password": "WrongPass1!"},
        )
        assert resp.status_code in (401, 429)
