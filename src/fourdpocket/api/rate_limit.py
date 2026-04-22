"""Database-backed rate limiting — shared across workers, works with SQLite & PostgreSQL."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from fourdpocket.models.rate_limit import RateLimitEntry

# Cleanup: evict entries older than this many seconds
_EVICT_AGE_SECS = 7200  # 2 hours
_MAX_ENTRIES_PER_ACTION = 10000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _evict_stale(db: Session, action: str) -> None:
    """Remove stale entries to prevent unbounded table growth."""
    cutoff = _now() - timedelta(seconds=_EVICT_AGE_SECS)
    db.exec(
        sa_delete(RateLimitEntry).where(
            RateLimitEntry.action == action,
            RateLimitEntry.locked_until == None,  # noqa: E711
            RateLimitEntry.attempts <= 0,
            RateLimitEntry.last_attempt < cutoff,
        )
    )
    db.flush()


def check_rate_limit(
    db: Session,
    key: str,
    action: str,
    max_attempts: int,
    window_seconds: int,
    lockout_minutes: int | None = None,
    escalating_lockout: list[int] | None = None,
) -> None:
    """Check rate limit and raise 429 if exceeded.

    Args:
        db: Database session
        key: Rate limit key (e.g. IP address or email)
        action: Action name (e.g. "login", "register", "public_token")
        max_attempts: Maximum attempts allowed in the window
        window_seconds: Time window in seconds
        lockout_minutes: Fixed lockout duration (mutually exclusive with escalating_lockout)
        escalating_lockout: List of escalating lockout durations in minutes
    """
    now = _now()
    entry = db.exec(
        select(RateLimitEntry).where(
            RateLimitEntry.key == key,
            RateLimitEntry.action == action,
        )
    ).first()

    if not entry:
        return  # No prior attempts — allowed

    # Normalize datetimes to aware (SQLite may store naive)
    def _ensure_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # Check if currently locked out
    if entry.locked_until:
        locked = _ensure_aware(entry.locked_until)
        if locked > now:
            remaining = int((locked - now).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked due to too many failed attempts. Try again in {remaining} seconds.",
            )

    # Check if entry is within the window
    last = _ensure_aware(entry.last_attempt)
    elapsed = (now - last).total_seconds()
    if elapsed > window_seconds:
        # Window expired — reset
        entry.attempts = 0
        entry.locked_until = None
        db.add(entry)
        db.flush()
        return

    # Check if attempts exceeded
    if entry.attempts >= max_attempts:
        if escalating_lockout:
            lockout_idx = min(entry.attempts - max_attempts, len(escalating_lockout) - 1)
            lockout_secs = escalating_lockout[lockout_idx] * 60
        elif lockout_minutes:
            lockout_secs = lockout_minutes * 60
        else:
            lockout_secs = 60  # Default 1 minute

        from datetime import timedelta
        entry.locked_until = now + timedelta(seconds=lockout_secs)
        db.add(entry)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Account locked for {lockout_secs // 60} minutes.",
        )


def record_attempt(db: Session, key: str, action: str) -> None:
    """Record a rate-limited attempt."""
    now = _now()
    entry = db.exec(
        select(RateLimitEntry).where(
            RateLimitEntry.key == key,
            RateLimitEntry.action == action,
        )
    ).first()

    if entry:
        entry.attempts += 1
        entry.last_attempt = now
    else:
        entry = RateLimitEntry(key=key, action=action, attempts=1, last_attempt=now)

    db.add(entry)
    db.flush()


def reset_rate_limit(db: Session, key: str, action: str) -> None:
    """Reset rate limit on successful action (e.g. successful login)."""
    entry = db.exec(
        select(RateLimitEntry).where(
            RateLimitEntry.key == key,
            RateLimitEntry.action == action,
        )
    ).first()
    if entry:
        db.delete(entry)
        db.flush()
