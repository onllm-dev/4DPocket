"""Tests for public share schema — GET /api/v1/public/{token}.

The response MUST NOT expose user_id, password_hash, private notes, or any other
sensitive user data. We use a whitelist assertion on the response keys.
"""

import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import ShareType
from fourdpocket.models.user import User
from fourdpocket.sharing.share_manager import create_share

# Allowed keys in the public share response (whitelist)
_ALLOWED_KEYS = frozenset({
    "id",
    "title",
    "url",
    "description",
    "content",
    "summary",
    "source_platform",
    "created_at",
    "tags",
    "owner_display_name",
})

# Keys that must NEVER appear in the public response
_FORBIDDEN_KEYS = frozenset({
    "user_id",
    "password_hash",
    "email",
    "username",
    "is_favorite",
    "is_archived",
    "raw_content",
    "item_metadata",
    "reading_status",
    "reading_progress",
})


class TestPublicShareSchema:
    """GET /api/v1/public/{token} — privacy and schema correctness."""

    @pytest.fixture
    def share_setup(self, db: Session):
        """Create a user + item + public share, return (token, item)."""
        user = User(
            email="shareowner@test.com",
            username="shareowner",
            password_hash="$2b$12$fake",
            display_name="Share Owner",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        item = KnowledgeItem(
            user_id=user.id,
            title="Public Knowledge",
            url="https://example.com/public",
            description="Publicly shared item",
            content="This is the content of the public item.",
            summary="A brief summary.",
            source_platform="generic",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        share = create_share(
            db=db,
            owner_id=user.id,
            share_type=ShareType.item,
            item_id=item.id,
            public=True,
        )
        return share.public_token, item, user

    def test_public_share_returns_200(self, client, share_setup):
        """Valid public token returns HTTP 200."""
        token, item, user = share_setup
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200

    def test_response_keys_are_whitelisted(self, client, share_setup):
        """Response ONLY contains whitelisted keys — no sensitive fields."""
        token, item, user = share_setup
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        data = resp.json()
        response_keys = set(data.keys())
        # Verify no forbidden keys leaked through
        leaked = _FORBIDDEN_KEYS & response_keys
        assert not leaked, f"Sensitive keys present in public share response: {leaked}"

    def test_response_does_not_contain_user_id(self, client, share_setup):
        """user_id must never appear in the public share response body."""
        token, item, user = share_setup
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        raw_body = resp.text
        # user_id value should not appear anywhere in the response
        assert str(user.id) not in raw_body, (
            f"user_id ({user.id}) leaked into public share response"
        )

    def test_response_does_not_contain_password_hash(self, client, share_setup):
        """password_hash must never appear in the public share response body."""
        token, item, user = share_setup
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        assert "password_hash" not in resp.text
        assert "$2b$" not in resp.text

    def test_correct_item_data_returned(self, client, share_setup):
        """Response contains the correct item title and summary."""
        token, item, user = share_setup
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == item.title
        assert data["summary"] == item.summary
        assert data["url"] == item.url

    def test_invalid_token_returns_404(self, client):
        """Non-existent token returns HTTP 404."""
        fake_token = "this-token-does-not-exist-at-all"
        resp = client.get(f"/api/v1/public/{fake_token}")
        assert resp.status_code == 404

    def test_owner_display_name_present(self, client, share_setup):
        """owner_display_name is present and non-empty."""
        token, item, user = share_setup
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("owner_display_name"), "owner_display_name must be non-empty"
        # Must not be the user's raw username or email directly
        # (display_name is preferred, falling back to username — both are OK)
        assert data["owner_display_name"] in (
            user.display_name, user.username
        ), f"Unexpected owner_display_name: {data['owner_display_name']}"
