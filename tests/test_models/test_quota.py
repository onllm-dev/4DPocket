"""Tests for the UserQuota model and check_quota enforcement.

Covers:
- Enforcement raises 429 at boundary (items_used + 1 > items_max)
- Enforcement allows at limit - 1
- Admin user bypasses enforcement
- Storage quota enforcement
- API-call daily window rotation
- No quota row ⟹ unlimited
"""

import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from fourdpocket.models.base import UserRole, utc_now
from fourdpocket.models.quota import UserQuota
from fourdpocket.models.user import User
from fourdpocket.quotas.enforcement import check_quota


def _make_user(db: Session, suffix: str = "", role: UserRole = UserRole.user) -> User:
    user = User(
        email=f"quota{suffix}@test.com",
        username=f"quotauser{suffix}",
        password_hash="$2b$12$fake",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_quota(db: Session, user_id: uuid.UUID, **kw) -> UserQuota:
    quota = UserQuota(user_id=user_id, daily_window_start=utc_now(), **kw)
    db.add(quota)
    db.commit()
    db.refresh(quota)
    return quota


class TestQuotaEnforcement:
    def test_no_quota_row_is_unlimited(self, db: Session):
        """With no UserQuota row the user is unlimited — no exception raised."""
        user = _make_user(db, "no_row")
        # No quota row — should not raise
        check_quota(db, user.id, "items")

    def test_items_allowed_at_limit_minus_one(self, db: Session):
        """When items_used + 1 == items_max, the call is allowed (boundary inclusive)."""
        user = _make_user(db, "boundary_ok")
        _make_quota(db, user.id, items_max=10, items_used=9)
        # 9 + 1 == 10, which is exactly at limit — allowed
        check_quota(db, user.id, "items")

    def test_items_raises_at_boundary(self, db: Session):
        """When items_used + 1 > items_max the function raises HTTPException(429)."""
        user = _make_user(db, "boundary_breach")
        _make_quota(db, user.id, items_max=10, items_used=10)

        with pytest.raises(HTTPException) as exc_info:
            check_quota(db, user.id, "items")

        assert exc_info.value.status_code == 429
        assert "quota" in exc_info.value.detail.lower()

    def test_items_raises_with_null_items_max_not_set(self, db: Session):
        """items_max=None means unlimited even with items_used very high."""
        user = _make_user(db, "unlimited")
        _make_quota(db, user.id, items_max=None, items_used=99999)
        # Should not raise
        check_quota(db, user.id, "items")

    def test_storage_raises_on_breach(self, db: Session):
        """storage quota raises 429 when storage_bytes_used + delta > storage_bytes_max."""
        user = _make_user(db, "storage_breach")
        _make_quota(db, user.id, storage_bytes_max=1000, storage_bytes_used=999)

        with pytest.raises(HTTPException) as exc_info:
            check_quota(db, user.id, "storage", delta=10)

        assert exc_info.value.status_code == 429

    def test_storage_allowed_exactly_at_max(self, db: Session):
        """storage_bytes_used + delta == storage_bytes_max is allowed."""
        user = _make_user(db, "storage_ok")
        _make_quota(db, user.id, storage_bytes_max=1000, storage_bytes_used=990)
        check_quota(db, user.id, "storage", delta=10)

    def test_admin_bypasses_items_quota(self, db: Session):
        """Admin users skip all quota enforcement regardless of limits."""
        admin = _make_user(db, "admin_bypass", role=UserRole.admin)
        _make_quota(db, admin.id, items_max=0, items_used=0)

        # Should not raise even though items_max=0
        check_quota(db, admin.id, "items")

    def test_api_call_raises_on_daily_breach(self, db: Session):
        """daily_api_calls: raises 429 when daily_api_calls_used + 1 > max."""
        user = _make_user(db, "api_breach")
        _make_quota(db, user.id, daily_api_calls_max=100, daily_api_calls_used=100)

        with pytest.raises(HTTPException) as exc_info:
            check_quota(db, user.id, "api_call")

        assert exc_info.value.status_code == 429

    def test_api_call_window_rotates_after_24h(self, db: Session):
        """When the daily window is >24h old, the counter resets before enforcement."""
        user = _make_user(db, "window_rotate")
        old_start = utc_now() - timedelta(hours=25)
        quota = UserQuota(
            user_id=user.id,
            daily_api_calls_max=5,
            daily_api_calls_used=5,  # would normally breach
            daily_window_start=old_start,
        )
        db.add(quota)
        db.commit()

        # Window is >24h old — counter should reset to 0 and then allow this call
        check_quota(db, user.id, "api_call")

    def test_counter_increments_on_success(self, db: Session):
        """Successful check_quota increments the items_used counter."""
        user = _make_user(db, "counter")
        _make_quota(db, user.id, items_max=5, items_used=2)

        check_quota(db, user.id, "items")

        db.expire_all()
        updated = db.get(UserQuota, user.id)
        assert updated is not None
        assert updated.items_used == 3
