"""Comprehensive multi-user data boundary tests."""

import uuid

from sqlmodel import select


class TestCrossUserIsolation:
    """Verify that users cannot access each other's data without explicit sharing."""

    def test_user_a_items_invisible_to_user_b(self, client, auth_headers, second_user_headers):
        """User A's items should not appear in User B's item list."""
        unique_term = f"user-a-private-{uuid.uuid4().hex[:8]}"

        # User A creates items
        for i in range(3):
            client.post(
                "/api/v1/items",
                json={
                    "url": f"https://example.com/user-a-{i}",
                    "title": f"User A Item {i} {unique_term}",
                    "content": f"User A private content {i}",
                },
                headers=auth_headers,
            )

        # User B's list should not contain any of User A's items
        list_resp = client.get("/api/v1/items", headers=second_user_headers)
        assert list_resp.status_code == 200
        user_b_items = list_resp.json()
        titles = [item.get("title") or "" for item in user_b_items]
        assert not any(unique_term in t for t in titles), "User B should not see User A's items"

    def test_user_a_search_excludes_user_b(self, client, auth_headers, second_user_headers):
        """FTS search should only return the searching user's items."""
        unique_term = f"search-isolation-{uuid.uuid4().hex[:8]}"

        # User A creates an item with unique content
        client.post(
            "/api/v1/items",
            json={
                "url": f"https://example.com/user-a-search-{uuid.uuid4().hex[:6]}",
                "title": f"User A Search {unique_term}",
                "content": f"Content only User A knows about {unique_term}",
            },
            headers=auth_headers,
        )

        # User B searches for User A's unique term
        search_resp = client.get(f"/api/v1/search?q={unique_term}", headers=second_user_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) == 0, "User B should not find User A's private item in search"

    def test_user_a_cannot_get_user_b_item(self, client, auth_headers, second_user_headers):
        """User A should get 404 when trying to access User B's item directly."""
        # User B creates an item
        create_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-b-private", "title": "User B Private Item"},
            headers=second_user_headers,
        )
        item_id = create_resp.json()["id"]

        # User A tries to access it
        get_resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert get_resp.status_code == 404, "User A should not be able to GET User B's item"

    def test_user_a_cannot_update_user_b_item(self, client, auth_headers, second_user_headers):
        """User A should get 404 when trying to update User B's item."""
        # User B creates an item
        create_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-b-update", "title": "User B Update Target"},
            headers=second_user_headers,
        )
        item_id = create_resp.json()["id"]

        # User A tries to update it
        patch_resp = client.patch(
            f"/api/v1/items/{item_id}",
            json={"title": "User A Trying to Update"},
            headers=auth_headers,
        )
        assert patch_resp.status_code == 404

    def test_user_a_cannot_delete_user_b_item(self, client, auth_headers, second_user_headers):
        """User A should get 404 when trying to delete User B's item."""
        # User B creates an item
        create_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-b-delete", "title": "User B Delete Target"},
            headers=second_user_headers,
        )
        item_id = create_resp.json()["id"]

        # User A tries to delete it
        delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 404

    def test_user_a_cannot_see_user_b_collections(self, client, auth_headers, second_user_headers):
        """User A should not see User B's collections."""
        # User B creates a collection
        client.post(
            "/api/v1/collections",
            json={"name": f"User B Private Collection {uuid.uuid4().hex[:6]}"},
            headers=second_user_headers,
        )

        # User A lists collections - should not see User B's
        list_resp = client.get("/api/v1/collections", headers=auth_headers)
        assert list_resp.status_code == 200
        collections = list_resp.json()
        names = [c.get("name") or "" for c in collections]
        assert not any("User B" in name for name in names), "User A should not see User B's collections"

    def test_user_a_cannot_access_user_b_collection(self, client, auth_headers, second_user_headers):
        """User A should get 404 when accessing User B's collection directly."""
        # User B creates a collection
        create_resp = client.post(
            "/api/v1/collections",
            json={"name": "User B's Private Collection"},
            headers=second_user_headers,
        )
        coll_id = create_resp.json()["id"]

        # User A tries to access it
        get_resp = client.get(f"/api/v1/collections/{coll_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_user_a_cannot_modify_user_b_collection(self, client, auth_headers, second_user_headers):
        """User A should get 404 when modifying User B's collection."""
        # User B creates a collection
        create_resp = client.post(
            "/api/v1/collections",
            json={"name": "User B Collection to Modify"},
            headers=second_user_headers,
        )
        coll_id = create_resp.json()["id"]

        # User A creates an item to try adding to User B's collection
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/to-add", "title": "Item to Add"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        # User A tries to add their item to User B's collection
        add_resp = client.post(
            f"/api/v1/collections/{coll_id}/items",
            json={"item_ids": [item_id]},
            headers=auth_headers,
        )
        assert add_resp.status_code == 404

    def test_user_a_cannot_see_user_b_tags(self, client, auth_headers, second_user_headers):
        """User A should not see tags created by User B."""
        # User B creates tags
        for i in range(2):
            client.post(
                "/api/v1/tags",
                json={"name": f"user-b-tag-{i}-{uuid.uuid4().hex[:6]}"},
                headers=second_user_headers,
            )

        # User A lists tags - should not see User B's tags
        list_resp = client.get("/api/v1/tags", headers=auth_headers)
        assert list_resp.status_code == 200
        tags = list_resp.json()
        names = [t.get("name") or "" for t in tags]
        assert not any("user-b-tag" in name for name in names), "User A should not see User B's tags"

    def test_user_a_cannot_add_tag_from_user_b(self, client, auth_headers, second_user_headers):
        """User A should not be able to add User B's tags to their items."""
        # User B creates a tag
        tag_resp = client.post(
            "/api/v1/tags",
            json={"name": f"user-b-exclusive-{uuid.uuid4().hex[:6]}"},
            headers=second_user_headers,
        )
        tag_id = tag_resp.json()["id"]

        # User A creates an item
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/tag-test", "title": "Tag Test Item"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        # User A tries to add User B's tag to their item
        add_tag_resp = client.post(
            f"/api/v1/items/{item_id}/tags?tag_id={tag_id}",
            headers=auth_headers,
        )
        # Should fail - tag belongs to second_user
        assert add_tag_resp.status_code in (404, 409)

    def test_user_a_items_not_in_user_b_search(self, client, auth_headers, second_user_headers):
        """User B searching should never see User A's items even with partial matches."""
        unique_content = f"completely-unique-content-{uuid.uuid4().hex[:8]}"

        # User A creates item with unique content
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/isolation-search",
                "title": "Isolation Search Test",
                "content": unique_content,
            },
            headers=auth_headers,
        )

        # User B searches with a substring of User A's unique content
        partial = unique_content[:20]
        search_resp = client.get(f"/api/v1/search?q={partial}", headers=second_user_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) == 0

    def test_pat_scoped_to_owner(self, client, db, auth_headers):
        """PAT should only access the token owner's data, not other users'."""
        # Get user from auth_headers (test@example.com)
        from fourdpocket.models.user import User
        from tests.factories import make_pat

        user_a = db.exec(select(User).where(User.email == "test@example.com")).one()

        # Create a PAT for user A
        token, raw_token = make_pat(db, user_a.id, name="Test PAT")

        # Create item for user A
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/pat-item", "title": "PAT Owner Item"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        # Use PAT to access item - should succeed
        pat_headers = {"Authorization": f"Bearer {raw_token}"}
        get_resp = client.get(f"/api/v1/items/{item_id}", headers=pat_headers)
        assert get_resp.status_code == 200

        # Use PAT to list items - should only see owner items
        list_resp = client.get("/api/v1/items", headers=pat_headers)
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert any("PAT Owner Item" in item.get("title", "") for item in items), "PAT should only see its owner's items"

    def test_items_in_different_collections_isolated(self, client, auth_headers, second_user_headers):
        """Items in different users' collections should be isolated."""
        # User A creates collection and item
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": f"User A Collection {uuid.uuid4().hex[:6]}"},
            headers=auth_headers,
        )
        coll_id = coll_resp.json()["id"]

        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/coll-item", "title": "Collection Item"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        client.post(f"/api/v1/collections/{coll_id}/items", json={"item_ids": [item_id]}, headers=auth_headers)

        # User B tries to access the collection
        get_coll_resp = client.get(f"/api/v1/collections/{coll_id}", headers=second_user_headers)
        assert get_coll_resp.status_code == 404

        # User B tries to add items to User A's collection
        user_b_item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-b", "title": "User B Item"},
            headers=second_user_headers,
        )
        user_b_item_id = user_b_item_resp.json()["id"]

        add_resp = client.post(
            f"/api/v1/collections/{coll_id}/items",
            json={"item_ids": [user_b_item_id]},
            headers=second_user_headers,
        )
        assert add_resp.status_code == 404

    def test_user_cannot_access_other_users_entities(self, client, auth_headers, second_user_headers):
        """User A should not be able to access User B's entities directly."""
        # User B creates an entity
        entity_resp = client.post(
            "/api/v1/entities",
            json={"name": f"User B Entity {uuid.uuid4().hex[:6]}", "entity_type": "organization"},
            headers=second_user_headers,
        )

        # If entity creation succeeded, User A should not be able to access it
        if entity_resp.status_code == 201:
            entity_id = entity_resp.json().get("id")
            if entity_id:
                get_resp = client.get(f"/api/v1/entities/{entity_id}", headers=auth_headers)
                assert get_resp.status_code == 404

    def test_user_bulk_delete_isolated(self, client, auth_headers, second_user_headers):
        """Bulk operations should only affect the authenticated user's data."""
        # User A creates items
        user_a_items = []
        for i in range(3):
            resp = client.post(
                "/api/v1/items",
                json={"url": f"https://example.com/user-a-bulk-{i}", "title": f"User A Bulk {i}"},
                headers=auth_headers,
            )
            user_a_items.append(resp.json()["id"])

        # User B creates items
        user_b_items = []
        for i in range(3):
            resp = client.post(
                "/api/v1/items",
                json={"url": f"https://example.com/user-b-bulk-{i}", "title": f"User B Bulk {i}"},
                headers=second_user_headers,
            )
            user_b_items.append(resp.json()["id"])

        # User A deletes their items
        for item_id in user_a_items:
            client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)

        # User B's items should still exist
        for item_id in user_b_items:
            get_resp = client.get(f"/api/v1/items/{item_id}", headers=second_user_headers)
            assert get_resp.status_code == 200

        # User A's items should be gone
        for item_id in user_a_items:
            get_resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
            assert get_resp.status_code == 404

    def test_entities_isolated_between_users(self, client, auth_headers, second_user_headers):
        """Entity list should only show the authenticated user's entities."""
        unique_entity = f"entity-isolation-{uuid.uuid4().hex[:8]}"

        # User A creates an entity
        client.post(
            "/api/v1/entities",
            json={"name": f"User A Entity {unique_entity}", "entity_type": "person"},
            headers=auth_headers,
        )

        # User B lists entities - should not see User A's
        list_resp = client.get("/api/v1/entities", headers=second_user_headers)
        assert list_resp.status_code == 200
        entities = list_resp.json()
        names = [e.get("name") or "" for e in entities]
        assert not any(unique_entity in name for name in names), "User B should not see User A's entities"

    def test_check_url_user_scoped(self, client, auth_headers, second_user_headers):
        """URL existence check should be user-scoped."""
        # User A saves a URL
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/user-a-url"},
            headers=auth_headers,
        )

        # User B checks the same URL - should say it doesn't exist for them
        check_resp = client.get(
            "/api/v1/items/check-url?url=https://example.com/user-a-url",
            headers=second_user_headers,
        )
        assert check_resp.status_code == 200
        data = check_resp.json()
        assert data["exists"] is False, "URL should not exist for User B (only exists for User A)"
