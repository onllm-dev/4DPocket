"""Tests for the PAT audit events endpoint.

Covers:
- Owner can list events for their own token
- Another user gets 403 (or 404) attempting to list events for a token they don't own
- Mint/revoke actions record audit events automatically
"""

import uuid

from sqlmodel import select

from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.pat_event import PatEvent
from fourdpocket.models.user import User
from tests.factories import make_pat


def _current_user(db):
    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert user is not None, "test user must exist (requires auth_headers fixture)"
    return user


class TestPatEventsEndpoint:
    def test_owner_can_list_events_for_own_token(self, client, auth_headers, db):
        """Token owner can GET /auth/tokens/{id}/events."""
        user = _current_user(db)
        token, _raw = make_pat(db, user.id, name="audit-token")

        # Manually insert an event for this token
        db.add(PatEvent(
            pat_id=token.id,
            user_id=user.id,
            action="rest_call",
            resource="/api/v1/items",
            status_code=200,
        ))
        db.commit()

        response = client.get(
            f"/api/v1/auth/tokens/{token.id}/events",
            headers=auth_headers,
        )

        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)
        assert len(events) >= 1
        actions = {e["action"] for e in events}
        assert "rest_call" in actions

    def test_other_user_gets_403_for_foreign_token(
        self, client, auth_headers, second_user_headers, db
    ):
        """A user must not be able to read events for another user's token."""
        user = _current_user(db)
        token, _raw = make_pat(db, user.id, name="foreign-token")

        response = client.get(
            f"/api/v1/auth/tokens/{token.id}/events",
            headers=second_user_headers,
        )

        assert response.status_code in (403, 404)

    def test_nonexistent_token_returns_403(self, client, auth_headers):
        """Querying events for a random UUID returns 403 (not found)."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/auth/tokens/{fake_id}/events",
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_mint_action_records_event(self, client, auth_headers, db):
        """Creating a token via POST /auth/tokens writes a 'mint' PatEvent."""
        response = client.post(
            "/api/v1/auth/tokens",
            json={"name": "event-test-token", "role": "viewer", "all_collections": True},
            headers=auth_headers,
        )
        assert response.status_code == 201
        token_id = response.json()["id"]

        events_resp = client.get(
            f"/api/v1/auth/tokens/{token_id}/events",
            headers=auth_headers,
        )
        assert events_resp.status_code == 200
        events = events_resp.json()
        mint_events = [e for e in events if e["action"] == "mint"]
        assert len(mint_events) >= 1

    def test_revoke_action_records_event(self, client, auth_headers, db):
        """Revoking a token via DELETE /auth/tokens/{id} writes a 'revoke' PatEvent."""
        # Create token first
        create_resp = client.post(
            "/api/v1/auth/tokens",
            json={"name": "revoke-test-token", "role": "viewer", "all_collections": True},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        token_id = create_resp.json()["id"]

        # Revoke it
        delete_resp = client.delete(
            f"/api/v1/auth/tokens/{token_id}",
            headers=auth_headers,
        )
        assert delete_resp.status_code == 204

        # Check events
        events_resp = client.get(
            f"/api/v1/auth/tokens/{token_id}/events",
            headers=auth_headers,
        )
        assert events_resp.status_code == 200
        events = events_resp.json()
        revoke_events = [e for e in events if e["action"] == "revoke"]
        assert len(revoke_events) >= 1

    def test_events_limit_parameter(self, client, auth_headers, db):
        """The limit query parameter is respected."""
        user = _current_user(db)
        token, _raw = make_pat(db, user.id, name="limit-test-token")

        # Insert 5 events
        for i in range(5):
            db.add(PatEvent(
                pat_id=token.id,
                user_id=user.id,
                action="rest_call",
                resource=f"/items/{i}",
                status_code=200,
            ))
        db.commit()

        response = client.get(
            f"/api/v1/auth/tokens/{token.id}/events?limit=3",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) <= 3
