"""Tests for entity API endpoints."""

import uuid

from fourdpocket.ai.canonicalizer import canonicalize_entity
from fourdpocket.models.item import KnowledgeItem


class TestEntitiesEndpoints:
    def test_list_entities_empty(self, client, auth_headers):
        resp = client.get("/api/v1/entities", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_entities_with_data(self, client, auth_headers, db):
        # Create item first to get user
        resp = client.post(
            "/api/v1/items",
            json={"title": "Entity Test Item", "content": "Test content"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

        # Get user from DB via the item
        from sqlmodel import select
        item = db.exec(select(KnowledgeItem)).first()
        user_id = item.user_id

        # Create entities directly in DB
        canonicalize_entity("FastAPI", "tool", user_id, db, "Web framework")
        canonicalize_entity("Python", "tool", user_id, db, "Language")

        resp = client.get("/api/v1/entities", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {e["canonical_name"] for e in data}
        assert "FastAPI" in names
        assert "Python" in names

    def test_list_entities_filter_by_type(self, client, auth_headers, db):
        resp = client.post(
            "/api/v1/items",
            json={"title": "Type Filter Item", "content": "Content"},
            headers=auth_headers,
        )
        item = db.exec(
            __import__("sqlmodel", fromlist=["select"]).select(KnowledgeItem)
        ).first()

        canonicalize_entity("Docker", "tool", item.user_id, db)
        canonicalize_entity("Kubernetes", "tool", item.user_id, db)
        canonicalize_entity("Elon Musk", "person", item.user_id, db)

        resp = client.get("/api/v1/entities?entity_type=tool", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(e["entity_type"] == "tool" for e in data)

    def test_get_entity_detail(self, client, auth_headers, db):
        resp = client.post(
            "/api/v1/items",
            json={"title": "Detail Item", "content": "Content"},
            headers=auth_headers,
        )
        item = db.exec(
            __import__("sqlmodel", fromlist=["select"]).select(KnowledgeItem)
        ).first()

        entity = canonicalize_entity("React", "tool", item.user_id, db, "UI library")

        resp = client.get(f"/api/v1/entities/{entity.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["canonical_name"] == "React"
        assert data["entity_type"] == "tool"
        assert data["description"] == "UI library"
        assert len(data["aliases"]) >= 1

    def test_get_entity_not_found(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/entities/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_entity_user_scoping(self, client, auth_headers, second_user_headers, db):
        # Create entity as first user
        resp = client.post(
            "/api/v1/items",
            json={"title": "Scoped Entity Item", "content": "Content"},
            headers=auth_headers,
        )
        item = db.exec(
            __import__("sqlmodel", fromlist=["select"]).select(KnowledgeItem)
        ).first()
        entity = canonicalize_entity("Secret Tool", "tool", item.user_id, db)

        # Second user should not see it
        resp = client.get(f"/api/v1/entities/{entity.id}", headers=second_user_headers)
        assert resp.status_code == 404

        # Second user's list should be empty
        resp = client.get("/api/v1/entities", headers=second_user_headers)
        assert resp.status_code == 200
        assert resp.json() == []
