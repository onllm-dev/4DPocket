"""Tests for automation rules CRUD endpoints."""

import uuid

RULE_URL_MATCH_CONDITION = {"type": "url_matches", "value": "example\\.com"}
RULE_PLATFORM_CONDITION = {"type": "source_platform", "value": "generic"}
RULE_TITLE_CONDITION = {"type": "title_contains", "value": "Test"}
RULE_TAG_CONDITION = {"type": "has_tag", "value": "python"}

RULE_ADD_TAG_ACTION = {"type": "add_tag", "value": "auto-tagged"}
RULE_FAVORITE_ACTION = {"type": "set_favorite", "value": "true"}
RULE_ARCHIVE_ACTION = {"type": "archive", "value": None}


class TestCreateRule:
    def test_create_rule_returns_201(self, client, auth_headers):
        response = client.post(
            "/api/v1/rules",
            json={
                "name": "My First Rule",
                "condition": RULE_URL_MATCH_CONDITION,
                "action": RULE_ADD_TAG_ACTION,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My First Rule"
        assert data["condition"] == RULE_URL_MATCH_CONDITION
        assert data["action"] == RULE_ADD_TAG_ACTION
        assert data["is_active"] is True
        assert "id" in data
        assert "user_id" in data
        assert "created_at" in data

    def test_create_rule_with_all_condition_types(self, client, auth_headers):
        for condition in [
            RULE_URL_MATCH_CONDITION,
            RULE_PLATFORM_CONDITION,
            RULE_TITLE_CONDITION,
            RULE_TAG_CONDITION,
        ]:
            response = client.post(
                "/api/v1/rules",
                json={"name": f"Rule {condition['type']}", "condition": condition, "action": RULE_FAVORITE_ACTION},
                headers=auth_headers,
            )
            assert response.status_code == 201

    def test_create_rule_with_all_action_types(self, client, auth_headers):
        for action in [
            RULE_ADD_TAG_ACTION,
            RULE_FAVORITE_ACTION,
            RULE_ARCHIVE_ACTION,
            {"type": "add_to_collection", "value": str(uuid.uuid4())},
        ]:
            response = client.post(
                "/api/v1/rules",
                json={"name": "Action Rule", "condition": RULE_URL_MATCH_CONDITION, "action": action},
                headers=auth_headers,
            )
            assert response.status_code == 201

    def test_create_rule_inactive(self, client, auth_headers):
        response = client.post(
            "/api/v1/rules",
            json={
                "name": "Inactive Rule",
                "condition": RULE_URL_MATCH_CONDITION,
                "action": RULE_ADD_TAG_ACTION,
                "is_active": False,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["is_active"] is False

    def test_create_rule_forbids_extra_fields(self, client, auth_headers):
        response = client.post(
            "/api/v1/rules",
            json={
                "name": "Bad Rule",
                "condition": RULE_URL_MATCH_CONDITION,
                "action": RULE_ADD_TAG_ACTION,
                "unknown_field": "not allowed",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_rule_requires_auth(self, client):
        response = client.post(
            "/api/v1/rules",
            json={"name": "No Auth", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
        )
        assert response.status_code == 401


class TestListRules:
    def test_list_rules_returns_users_rules(self, client, auth_headers, second_user_headers):
        client.post("/api/v1/rules", json={
            "name": "User A Rule", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION,
        }, headers=auth_headers)
        client.post("/api/v1/rules", json={
            "name": "User A Rule 2", "condition": RULE_PLATFORM_CONDITION, "action": RULE_FAVORITE_ACTION,
        }, headers=auth_headers)
        client.post("/api/v1/rules", json={
            "name": "User B Rule", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ARCHIVE_ACTION,
        }, headers=second_user_headers)

        response = client.get("/api/v1/rules", headers=auth_headers)
        assert response.status_code == 200
        rules = response.json()
        assert len(rules) == 2
        names = {r["name"] for r in rules}
        assert "User A Rule" in names
        assert "User A Rule 2" in names
        assert "User B Rule" not in names

    def test_list_rules_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/api/v1/rules", json={
                "name": f"Rule {i}", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION,
            }, headers=auth_headers)

        response = client.get("/api/v1/rules?offset=2&limit=2", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_rules_enforces_limit_max(self, client, auth_headers):
        response = client.get("/api/v1/rules?limit=200", headers=auth_headers)
        assert response.status_code == 422  # limit must be <= 100

    def test_list_rules_requires_auth(self, client):
        response = client.get("/api/v1/rules")
        assert response.status_code == 401


class TestUpdateRule:
    def test_update_rule_name(self, client, auth_headers):
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "Original Name", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/rules/{rule_id}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_update_rule_is_active(self, client, auth_headers):
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "Toggle Me", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION, "is_active": True},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/rules/{rule_id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_update_rule_condition_and_action(self, client, auth_headers):
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "Change Me", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/rules/{rule_id}",
            json={"condition": RULE_PLATFORM_CONDITION, "action": RULE_FAVORITE_ACTION},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["condition"] == RULE_PLATFORM_CONDITION
        assert response.json()["action"] == RULE_FAVORITE_ACTION

    def test_update_nonexistent_rule_returns_404(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000002"
        response = client.patch(
            f"/api/v1/rules/{fake_id}",
            json={"name": "Ghost"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_update_other_users_rule_returns_404(self, client, auth_headers, second_user_headers):
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "Other User Rule", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        # Second user tries to update user A's rule
        response = client.patch(
            f"/api/v1/rules/{rule_id}",
            json={"name": "Hijacked"},
            headers=second_user_headers,
        )
        assert response.status_code == 404


class TestDeleteRule:
    def test_delete_rule_returns_204(self, client, auth_headers):
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "To Delete", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/v1/rules/{rule_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        get_resp = client.get(f"/api/v1/rules/{rule_id}", headers=auth_headers)
        # No individual get endpoint, so verify via list
        list_resp = client.get("/api/v1/rules", headers=auth_headers)
        rule_ids = [r["id"] for r in list_resp.json()]
        assert rule_id not in rule_ids

    def test_delete_nonexistent_rule_returns_404(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000002"
        response = client.delete(f"/api/v1/rules/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_other_users_rule_returns_404(self, client, auth_headers, second_user_headers):
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "Protected Rule", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/rules/{rule_id}", headers=second_user_headers)
        assert response.status_code == 404

        # Verify rule still exists for owner
        list_resp = client.get("/api/v1/rules", headers=auth_headers)
        assert any(r["id"] == rule_id for r in list_resp.json())


class TestRuleScoping:
    def test_rules_are_user_scoped(self, client, auth_headers, second_user_headers):
        # Create rule as user A
        create_resp = client.post(
            "/api/v1/rules",
            json={"name": "User A Rule", "condition": RULE_URL_MATCH_CONDITION, "action": RULE_ADD_TAG_ACTION},
            headers=auth_headers,
        )
        rule_id = create_resp.json()["id"]

        # User B cannot see it
        list_resp = client.get("/api/v1/rules", headers=second_user_headers)
        assert all(r["id"] != rule_id for r in list_resp.json())

        # User B cannot update it
        patch_resp = client.patch(f"/api/v1/rules/{rule_id}", json={"name": "Hijacked"}, headers=second_user_headers)
        assert patch_resp.status_code == 404

        # User B cannot delete it
        del_resp = client.delete(f"/api/v1/rules/{rule_id}", headers=second_user_headers)
        assert del_resp.status_code == 404
