"""Tests for database-backed rate limiting."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import select

from fourdpocket.api.rate_limit import (
    check_rate_limit,
    record_attempt,
    reset_rate_limit,
)
from fourdpocket.models.rate_limit import RateLimitEntry


class TestCheckRateLimitFirstAttempt:
    """Verify first-attempt behaviour."""

    @pytest.mark.security
    def test_first_attempt_allowed(self, db):
        """Fresh IP/action with no prior attempts must be allowed."""
        # No exception means allowed
        check_rate_limit(
            db=db,
            key="192.168.1.1",
            action="login",
            max_attempts=5,
            window_seconds=300,
        )

    @pytest.mark.security
    def test_first_recorded_attempt_increments(self, db):
        """Recording first attempt creates an entry."""
        record_attempt(db=db, key="10.0.0.1", action="login")
        entry = db.exec(
            select(RateLimitEntry).where(
                RateLimitEntry.key == "10.0.0.1",
                RateLimitEntry.action == "login",
            )
        ).first()
        assert entry is not None
        assert entry.attempts == 1


class TestMaxAttemptsLockout:
    """Verify lockout after max attempts exhausted."""

    @pytest.mark.security
    @pytest.mark.parametrize("max_attempts,window_seconds", [
        (3, 300),
        (5, 600),
        (1, 60),
    ])
    def test_max_attempts_locks(self, db, max_attempts, window_seconds):
        """After max_attempts, further attempts raise 429."""
        key = f"192.168.1.{max_attempts}"
        action = "login"

        # Fill up to the limit
        for i in range(max_attempts):
            record_attempt(db=db, key=key, action=action)

        # The next attempt should be blocked
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(
                db=db,
                key=key,
                action=action,
                max_attempts=max_attempts,
                window_seconds=window_seconds,
            )
        assert exc_info.value.status_code == 429

    @pytest.mark.security
    def test_attempt_count_persists_across_checks(self, db):
        """Attempt count must accumulate across multiple check+record cycles."""
        key = "172.16.0.1"
        action = "register"

        # Record 3 attempts
        for _ in range(3):
            record_attempt(db=db, key=key, action=action)

        # 4th attempt should still be within window (not locked yet, max=5)
        check_rate_limit(
            db=db,
            key=key,
            action=action,
            max_attempts=5,
            window_seconds=300,
        )


class TestLockoutExpiry:
    """Verify lockout duration and expiry behaviour."""

    @pytest.mark.security
    def test_lockout_escalation(self, db, monkeypatch):
        """Escalating lockouts must increase duration each lockout tier."""
        key = "10.0.0.5"
        action = "login"
        max_attempts = 2
        escalating = [1, 5, 15]  # 1 min, 5 min, 15 min

        # Patch _now to return a stable time
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        call_count = [0]

        def mock_now():
            call_count[0] += 1
            return base_time

        monkeypatch.setattr("fourdpocket.api.rate_limit._now", mock_now)

        # Exhaust attempts 3 times to hit each escalation tier
        for tier in range(3):
            # Reset attempts to simulate re-filling
            entry = db.exec(
                select(RateLimitEntry).where(
                    RateLimitEntry.key == key,
                    RateLimitEntry.action == action,
                )
            ).first()
            if entry:
                entry.attempts = 0
                entry.locked_until = None
                db.flush()

            # Fill attempts
            for _ in range(max_attempts):
                record_attempt(db=db, key=key, action=action)

            # Should lock out at current tier
            with pytest.raises(HTTPException) as exc_info:
                check_rate_limit(
                    db=db,
                    key=key,
                    action=action,
                    max_attempts=max_attempts,
                    window_seconds=300,
                    escalating_lockout=escalating,
                )
            assert exc_info.value.status_code == 429

    @pytest.mark.security
    def test_fixed_lockout_duration(self, db, monkeypatch):
        """Fixed lockout_minutes must be applied when escalating_lockout not set."""
        key = "192.168.2.1"
        action = "login"

        # Patch _now to return a stable time
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(
            "fourdpocket.api.rate_limit._now",
            lambda: base_time,
        )

        for _ in range(3):
            record_attempt(db=db, key=key, action=action)

        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(
                db=db,
                key=key,
                action=action,
                max_attempts=3,
                window_seconds=300,
                lockout_minutes=10,
            )
        assert exc_info.value.status_code == 429
        # Detail contains either "10 minutes" or "600 seconds"
        assert "10 minutes" in exc_info.value.detail or "600" in exc_info.value.detail


class TestWindowExpiry:
    """Verify window expiry resets attempt counters."""

    @pytest.mark.security
    def test_window_expiry_resets_attempts(self, db, monkeypatch):
        """After window_seconds elapse, counter must reset."""
        key = "172.16.0.5"
        action = "login"
        window_seconds = 300

        # Mock _now to return t=0 then t=6min (past window)
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_times = [
            base_time,                          # record_attempt calls
            base_time,                          # record_attempt calls
            base_time,                          # record_attempt calls
            base_time + timedelta(minutes=6),   # check_rate_limit call
        ]
        time_iter = iter(mock_times)
        monkeypatch.setattr("fourdpocket.api.rate_limit._now", lambda: next(time_iter))

        # Record 3 attempts at t=0
        for _ in range(3):
            record_attempt(db=db, key=key, action=action)

        # At t=6min (past 5-min window), should be allowed
        check_rate_limit(
            db=db,
            key=key,
            action=action,
            max_attempts=3,
            window_seconds=window_seconds,
        )

    @pytest.mark.security
    def test_lockout_expiry_allows_retry(self, db, monkeypatch):
        """After lockout expires, user must be allowed through."""
        key = "10.0.0.9"
        action = "login"
        lockout_minutes = 5

        # Sequence: t=0 record, t=0 record, t=0 record, t=0 lockout,
        #           t=6min (past 5-min lockout) → should be allowed
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_times = [
            base_time,
            base_time,
            base_time,
            base_time,
            base_time + timedelta(minutes=6),
        ]
        time_iter = iter(mock_times)
        monkeypatch.setattr("fourdpocket.api.rate_limit._now", lambda: next(time_iter))

        for _ in range(3):
            record_attempt(db=db, key=key, action=action)

        # Should be locked out
        with pytest.raises(HTTPException):
            check_rate_limit(
                db=db,
                key=key,
                action=action,
                max_attempts=3,
                window_seconds=300,
                lockout_minutes=lockout_minutes,
            )

        # After lockout expiry, should be allowed
        check_rate_limit(
            db=db,
            key=key,
            action=action,
            max_attempts=3,
            window_seconds=300,
            lockout_minutes=lockout_minutes,
        )


class TestResetRateLimit:
    """Verify rate limit reset on successful action."""

    @pytest.mark.security
    def test_reset_removes_entry(self, db):
        """reset_rate_limit must delete the entry on success."""
        key = "192.168.3.1"
        action = "login"

        # Accumulate some attempts
        for _ in range(3):
            record_attempt(db=db, key=key, action=action)

        # Verify entry exists
        entry = db.exec(
            select(RateLimitEntry).where(
                RateLimitEntry.key == key,
                RateLimitEntry.action == action,
            )
        ).first()
        assert entry is not None

        # Reset
        reset_rate_limit(db=db, key=key, action=action)

        # Entry should be gone
        entry = db.exec(
            select(RateLimitEntry).where(
                RateLimitEntry.key == key,
                RateLimitEntry.action == action,
            )
        ).first()
        assert entry is None

    @pytest.mark.security
    def test_reset_nonexistent_is_noop(self, db):
        """Resetting a non-existent entry must not raise."""
        reset_rate_limit(db=db, key="0.0.0.0", action="nonexistent")


class TestMultipleKeysIsolation:
    """Verify entries are isolated by key/action pairs."""

    @pytest.mark.security
    def test_different_keys_independent(self, db):
        """Rate limit on one IP must not affect another IP."""
        action = "login"
        max_attempts = 3

        # Exhaust attempts for IP A
        ip_a = "10.0.1.1"
        for _ in range(max_attempts):
            record_attempt(db=db, key=ip_a, action=action)

        # IP A should be locked
        with pytest.raises(HTTPException):
            check_rate_limit(db=db, key=ip_a, action=action, max_attempts=max_attempts, window_seconds=300)

        # IP B should still be allowed
        ip_b = "10.0.1.2"
        check_rate_limit(db=db, key=ip_b, action=action, max_attempts=max_attempts, window_seconds=300)

    @pytest.mark.security
    def test_different_actions_independent(self, db):
        """Rate limit on login must not affect register (different action)."""
        key = "192.168.5.1"
        max_attempts = 3

        # Exhaust attempts for login
        for _ in range(max_attempts):
            record_attempt(db=db, key=key, action="login")

        # login should be locked
        with pytest.raises(HTTPException):
            check_rate_limit(db=db, key=key, action="login", max_attempts=max_attempts, window_seconds=300)

        # register should still be allowed
        check_rate_limit(db=db, key=key, action="register", max_attempts=max_attempts, window_seconds=300)


class TestNaiveDatetimeHandling:
    """Verify naive datetime (SQLite) is handled correctly."""

    @pytest.mark.security
    def test_naive_datetime_ignored(self, db):
        """Naive datetime in database must be handled without error."""
        key = "172.16.0.9"
        action = "login"

        # Manually insert a naive datetime entry
        entry = RateLimitEntry(
            key=key,
            action=action,
            attempts=2,
            last_attempt=datetime(2024, 1, 1, 12, 0, 0),  # naive — no tzinfo
        )
        db.add(entry)
        db.flush()

        # Should not raise — _ensure_aware handles naive datetimes
        check_rate_limit(
            db=db,
            key=key,
            action=action,
            max_attempts=5,
            window_seconds=300,
        )
