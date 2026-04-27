"""Quota enforcement helper.

Usage::

    from fourdpocket.quotas.enforcement import check_quota
    check_quota(db, user_id, "items")        # raises HTTPException(429) on breach
    check_quota(db, user_id, "storage", delta=file_size_bytes)
    check_quota(db, user_id, "api_call")
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import HTTPException, status
from sqlmodel import Session

from fourdpocket.models.base import UserRole, utc_now
from fourdpocket.models.quota import UserQuota
from fourdpocket.models.user import User


def check_quota(
    db: Session,
    user_id: uuid.UUID,
    kind: Literal["items", "storage", "api_call"],
    delta: int = 1,
) -> None:
    """Raise HTTPException(429) if the user has exceeded the quota for *kind*.

    No-op when:
    - no UserQuota row exists for the user (unlimited by default), or
    - the relevant max column is NULL, or
    - the user is an admin.

    On success the appropriate usage counter is incremented and the change is
    flushed (but NOT committed — the caller owns the transaction).
    """
    # Admin users bypass all quota checks.
    user = db.get(User, user_id)
    if user is not None and user.role == UserRole.admin:
        return

    quota: UserQuota | None = (
        db.get(UserQuota, user_id)  # primary key lookup — fast
    )
    if quota is None:
        return  # no quota row ⟹ unlimited

    now = utc_now()

    if kind == "items":
        if quota.items_max is not None and quota.items_used + delta > quota.items_max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Item quota exceeded: limit is {quota.items_max}, "
                    f"currently at {quota.items_used}."
                ),
            )
        quota.items_used += delta

    elif kind == "storage":
        if (
            quota.storage_bytes_max is not None
            and quota.storage_bytes_used + delta > quota.storage_bytes_max
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Storage quota exceeded: limit is {quota.storage_bytes_max} bytes, "
                    f"currently at {quota.storage_bytes_used} bytes."
                ),
            )
        quota.storage_bytes_used += delta

    elif kind == "api_call":
        # Rotate the daily window if it is older than 24 hours.
        # daily_window_start may be stored as a naive datetime by some backends
        # (SQLite). Normalise to UTC-aware before comparing.
        window_start = quota.daily_window_start
        from datetime import timezone as _tz
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=_tz.utc)
        window_age = now - window_start
        if window_age >= timedelta(hours=24):
            quota.daily_window_start = now
            quota.daily_api_calls_used = 0

        if (
            quota.daily_api_calls_max is not None
            and quota.daily_api_calls_used + delta > quota.daily_api_calls_max
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily API call quota exceeded: limit is {quota.daily_api_calls_max}, "
                    f"used {quota.daily_api_calls_used} today."
                ),
            )
        quota.daily_api_calls_used += delta

    db.add(quota)
    db.flush()
