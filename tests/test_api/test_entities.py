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


# === PHASE 0C MOPUP ADDITIONS ===

import json


def _get_auth_user(db):
    """Get the user associated with auth_headers (test@example.com)."""
    from sqlmodel import select

    from fourdpocket.models.user import User
    return db.exec(select(User).where(User.email == "test@example.com")).first()


class TestEntitySynthesisPayload:
    """Tests for _synthesis_payload handling of different synthesis column formats."""

    def test_synthesis_payload_dict(self, client, auth_headers, db):
        """entity.synthesis stored as dict is parsed correctly."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Dict Entity",
            canonical_name="Dict Entity",
            entity_type="concept",
            synthesis={"summary": "Dict summary", "themes": ["theme1", "theme2"]},
        )
        db.add(entity)
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["synthesis"]["summary"] == "Dict summary"
        assert data["synthesis"]["themes"] == ["theme1", "theme2"]

    def test_synthesis_payload_json_string(self, client, auth_headers, db):
        """entity.synthesis stored as JSON string is parsed correctly."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="String Entity",
            canonical_name="String Entity",
            entity_type="concept",
            synthesis=json.dumps({"summary": "JSON string summary", "themes": ["themeA"]}),
        )
        db.add(entity)
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["synthesis"]["summary"] == "JSON string summary"

    def test_synthesis_payload_plain_string(self, client, auth_headers, db):
        """entity.synthesis stored as plain string is wrapped in summary."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Plain Entity",
            canonical_name="Plain Entity",
            entity_type="concept",
            synthesis="Just a plain text synthesis",
        )
        db.add(entity)
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["synthesis"]["summary"] == "Just a plain text synthesis"

    def test_synthesis_payload_malformed(self, client, auth_headers, db):
        """Malformed JSON synthesis is gracefully handled."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Malformed Entity",
            canonical_name="Malformed Entity",
            entity_type="concept",
            synthesis="not { json at all",
        )
        db.add(entity)
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Falls back to wrapping plain text in summary
        assert data["synthesis"]["summary"] == "not { json at all"


class TestEntityGraph:
    """Tests for entity graph endpoint."""

    def test_entity_graph(self, client, auth_headers, db):
        """Pre-seeded entities + relations returns nodes + edges."""
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.entity_relation import EntityRelation

        user = _get_auth_user(db)
        entity_a = Entity(user_id=user.id, name="Entity A", canonical_name="Entity A", entity_type="concept")
        entity_b = Entity(user_id=user.id, name="Entity B", canonical_name="Entity B", entity_type="concept")
        db.add(entity_a)
        db.add(entity_b)
        db.commit()
        db.refresh(entity_a)
        db.refresh(entity_b)

        rel = EntityRelation(
            user_id=user.id,
            source_id=entity_a.id,
            target_id=entity_b.id,
            keywords="related",
            weight=0.85,
        )
        db.add(rel)
        db.commit()

        resp = client.get("/api/v1/entities/graph", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["edges"][0]["weight"] == 0.85

    def test_entity_graph_filter_type(self, client, auth_headers, db):
        """Graph filtered by entity_type returns only matching nodes."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        db.add(Entity(user_id=user.id, name="Tool Entity", canonical_name="Tool Entity", entity_type="tool"))
        db.add(Entity(user_id=user.id, name="Person Entity", canonical_name="Person Entity", entity_type="person"))
        db.commit()

        resp = client.get("/api/v1/entities/graph?entity_type=tool", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["entity_type"] == "tool"

    def test_entity_graph_empty(self, client, auth_headers):
        """Empty graph returns empty nodes + edges."""
        resp = client.get("/api/v1/entities/graph", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []


class TestEntitySearch:
    """Tests for entity list search."""

    def test_list_entities_search_q(self, client, auth_headers, db):
        """GET /entities?q= filters by canonical_name."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        db.add(Entity(user_id=user.id, name="Python Language", canonical_name="Python Language", entity_type="tool"))
        db.add(Entity(user_id=user.id, name="JavaScript Language", canonical_name="JavaScript Language", entity_type="tool"))
        db.add(Entity(user_id=user.id, name="Pythonista Blog", canonical_name="Pythonista Blog", entity_type="person"))
        db.commit()

        resp = client.get("/api/v1/entities?q=Python", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all("Python" in e["canonical_name"] for e in data)


class TestRegenerateSynthesis:
    """Tests for POST /entities/{id}/synthesize."""

    def test_regenerate_synthesis_404(self, client, auth_headers):
        """Non-existent entity returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000099"
        resp = client.post(f"/api/v1/entities/{fake_id}/synthesize", headers=auth_headers)
        assert resp.status_code == 404

    def test_regenerate_synthesis_low_items(self, client, auth_headers, db):
        """Entity with item_count below minimum returns 400."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Low Item Entity",
            canonical_name="Low Item Entity",
            entity_type="concept",
            item_count=1,  # below synthesis_min_item_count=3
        )
        db.add(entity)
        db.commit()

        resp = client.post(f"/api/v1/entities/{entity.id}/synthesize", headers=auth_headers)
        assert resp.status_code == 400

    def test_regenerate_synthesis_null_503(self, client, auth_headers, db, monkeypatch):
        """synthesize_entity returns None → 503."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Null Entity",
            canonical_name="Null Entity",
            entity_type="concept",
            item_count=10,
        )
        db.add(entity)
        db.commit()

        # synthesize_entity is imported inside the endpoint, so patch where it's defined
        monkeypatch.setattr("fourdpocket.ai.synthesizer.synthesize_entity", lambda *a: None)
        monkeypatch.setattr("fourdpocket.ai.synthesizer.should_regenerate", lambda *a, **kw: True)

        resp = client.post(f"/api/v1/entities/{entity.id}/synthesize?force=true", headers=auth_headers)
        assert resp.status_code == 503


class TestEntityItems:
    """Tests for GET /entities/{id}/items."""

    def test_get_entity_items(self, client, auth_headers, db):
        """Pre-seeded ItemEntity returns items."""
        from fourdpocket.models.entity import Entity, ItemEntity
        from fourdpocket.models.item import KnowledgeItem

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Entity With Items",
            canonical_name="Entity With Items",
            entity_type="concept",
        )
        db.add(entity)
        db.commit()

        item = KnowledgeItem(
            user_id=user.id,
            url="https://linked.com",
            title="Linked Item",
            content="Content",
        )
        db.add(item)
        db.commit()

        db.add(ItemEntity(entity_id=entity.id, item_id=item.id, salience=0.9))
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity.id}/items", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Linked Item"
        assert data[0]["salience"] == 0.9

    def test_get_entity_items_404(self, client, auth_headers):
        """Non-existent entity returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000098"
        resp = client.get(f"/api/v1/entities/{fake_id}/items", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_entity_items_empty(self, client, auth_headers, db):
        """Entity with no linked items returns empty list."""
        from fourdpocket.models.entity import Entity

        user = _get_auth_user(db)
        entity = Entity(
            user_id=user.id,
            name="Empty Entity",
            canonical_name="Empty Entity",
            entity_type="concept",
        )
        db.add(entity)
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity.id}/items", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestRelatedEntities:
    """Tests for GET /entities/{id}/related."""

    def test_get_related_entities(self, client, auth_headers, db):
        """Pre-seeded EntityRelation returns related entities."""
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.entity_relation import EntityRelation

        user = _get_auth_user(db)
        entity_a = Entity(user_id=user.id, name="Source Entity", canonical_name="Source Entity", entity_type="concept")
        entity_b = Entity(user_id=user.id, name="Target Entity", canonical_name="Target Entity", entity_type="concept")
        db.add(entity_a)
        db.add(entity_b)
        db.commit()

        db.add(EntityRelation(
            user_id=user.id,
            source_id=entity_a.id,
            target_id=entity_b.id,
            keywords="related",
            weight=0.75,
        ))
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity_a.id}/related", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["entity"]["canonical_name"] == "Target Entity"

    def test_get_related_entities_404(self, client, auth_headers):
        """Non-existent entity returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000097"
        resp = client.get(f"/api/v1/entities/{fake_id}/related", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_related_as_source(self, client, auth_headers, db):
        """Entity is source in relation is found."""
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.entity_relation import EntityRelation

        user = _get_auth_user(db)
        entity_a = Entity(user_id=user.id, name="Source Only", canonical_name="Source Only", entity_type="concept")
        entity_b = Entity(user_id=user.id, name="Target Only", canonical_name="Target Only", entity_type="concept")
        db.add(entity_a)
        db.add(entity_b)
        db.commit()

        db.add(EntityRelation(
            user_id=user.id,
            source_id=entity_a.id,
            target_id=entity_b.id,
            weight=0.5,
        ))
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity_a.id}/related", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_related_as_target(self, client, auth_headers, db):
        """Entity is target in relation is found."""
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.entity_relation import EntityRelation

        user = _get_auth_user(db)
        entity_a = Entity(user_id=user.id, name="Target Source", canonical_name="Target Source", entity_type="concept")
        entity_b = Entity(user_id=user.id, name="Target Only", canonical_name="Target Only", entity_type="concept")
        db.add(entity_a)
        db.add(entity_b)
        db.commit()

        db.add(EntityRelation(
            user_id=user.id,
            source_id=entity_a.id,
            target_id=entity_b.id,
            weight=0.6,
        ))
        db.commit()

        resp = client.get(f"/api/v1/entities/{entity_b.id}/related", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
