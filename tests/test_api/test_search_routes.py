"""Tests for search API endpoints."""
import uuid

from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.search.sqlite_fts import index_item


def _seed_item(client, auth_headers, url="https://example.com", title="Test Item", content="Searchable content here"):
    """Create an item and index it in FTS."""
    resp = client.post(
        "/api/v1/items",
        json={"url": url, "title": title, "content": content},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    return item_id


class TestSearchItems:
    """Test the main /search endpoint."""

    def test_search_basic_query_returns_results(self, client, auth_headers, db: Session):
        """A simple text query returns matching items."""
        item_id = _seed_item(client, auth_headers, title="Python Tutorial", content="Learn Python programming")
        item = db.get(KnowledgeItem, uuid.UUID(item_id))
        index_item(db, item)

        response = client.get("/api/v1/search?q=python", headers=auth_headers)
        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 1
        assert any(r["id"] == item_id for r in results)

    def test_search_empty_query_returns_422(self, client, auth_headers):
        """An empty query string is rejected (min_length=1)."""
        response = client.get("/api/v1/search?q=", headers=auth_headers)
        assert response.status_code == 422

    def test_search_no_query_returns_422(self, client, auth_headers):
        """Query parameter is required."""
        response = client.get("/api/v1/search", headers=auth_headers)
        assert response.status_code == 422

    def test_search_user_scoping(self, client, auth_headers, second_user_headers, db: Session):
        """User A's search never returns User B's items."""
        # User A item
        uid_a = _seed_item(client, auth_headers, url="https://user-a-private.com", title="Private Doc", content="Secret content")
        item_a = db.get(KnowledgeItem, uuid.UUID(uid_a))
        index_item(db, item_a)

        # User B item
        uid_b = _seed_item(client, second_user_headers, url="https://user-b.info", title="Other Doc", content="Other content")
        item_b = db.get(KnowledgeItem, uuid.UUID(uid_b))
        index_item(db, item_b)

        # User A searches
        response = client.get("/api/v1/search?q=private", headers=auth_headers)
        assert response.status_code == 200
        results = response.json()
        ids = {r["id"] for r in results}
        assert uid_a in ids
        assert uid_b not in ids

        # User B searches
        response = client.get("/api/v1/search?q=other", headers=second_user_headers)
        assert response.status_code == 200
        results = response.json()
        ids = {r["id"] for r in results}
        assert uid_b in ids
        assert uid_a not in ids

    def test_search_with_item_type_filter(self, client, auth_headers, db: Session):
        """item_type query parameter filters results."""
        # Article item
        aid = _seed_item(client, auth_headers, url="https://article.com", title="An Article", content="article content")
        a_item = db.get(KnowledgeItem, uuid.UUID(aid))
        index_item(db, a_item)

        # Note item
        nid = client.post(
            "/api/v1/items",
            json={"title": "A Note", "content": "note content", "item_type": "note"},
            headers=auth_headers,
        ).json()["id"]
        n_item = db.get(KnowledgeItem, uuid.UUID(nid))
        index_item(db, n_item)

        response = client.get("/api/v1/search?q=content&item_type=article", headers=auth_headers)
        assert response.status_code == 200
        results = response.json()
        assert all(r["item_type"] == "article" for r in results)

    def test_search_with_platform_filter(self, client, auth_headers, db: Session):
        """source_platform query parameter filters results."""
        aid = _seed_item(client, auth_headers, url="https://github.com/user/repo", title="GitHub Repo", content="code here")
        a_item = db.get(KnowledgeItem, uuid.UUID(aid))
        index_item(db, a_item)

        response = client.get("/api/v1/search?q=code&source_platform=github", headers=auth_headers)
        assert response.status_code == 200
        results = response.json()
        assert all(r["source_platform"] == "github" for r in results)

    def test_search_pagination_offset_limit(self, client, auth_headers, db: Session):
        """offset and limit produce correct result windows."""
        # Create and index 5 items
        ids = []
        for i in range(5):
            iid = _seed_item(client, auth_headers, url=f"https://page{i}.com", title=f"Page {i}", content=f"Content number {i}")
            item = db.get(KnowledgeItem, uuid.UUID(iid))
            index_item(db, item)
            ids.append(iid)

        # First page
        response = client.get("/api/v1/search?q=page&limit=2&offset=0", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

        # Second page
        response = client.get("/api/v1/search?q=page&limit=2&offset=2", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

        # Beyond available
        response = client.get("/api/v1/search?q=page&limit=2&offset=4", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_search_no_results(self, client, auth_headers, db: Session):
        """Query with no matches returns empty list."""
        aid = _seed_item(client, auth_headers, url="https://example.com", title="Unique Title XYZ123", content="Unique content")
        item = db.get(KnowledgeItem, uuid.UUID(aid))
        index_item(db, item)

        response = client.get("/api/v1/search?q=nonexistentquerythatmatchesnothing", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_search_special_characters(self, client, auth_headers, db: Session):
        """Queries with quotes and brackets are handled gracefully."""
        aid = _seed_item(client, auth_headers, url="https://example.com", title="Test [brackets]", content='Content with "quotes"')
        item = db.get(KnowledgeItem, uuid.UUID(aid))
        index_item(db, item)

        response = client.get('/api/v1/search?q=test [brackets]"quotes"', headers=auth_headers)
        assert response.status_code == 200
        # Should not error, may or may not return results

    def test_search_requires_auth(self, client):
        """Unauthenticated requests return 401."""
        response = client.get("/api/v1/search?q=test")
        assert response.status_code == 401


class TestUnifiedSearch:
    """Test /search/unified endpoint."""

    def test_unified_search_returns_items_and_notes(self, client, auth_headers, db: Session):
        """Unified search returns both items and notes."""
        # Create an item
        iid = _seed_item(client, auth_headers, title="Docker Tutorial", content="Docker container guide")
        item = db.get(KnowledgeItem, uuid.UUID(iid))
        index_item(db, item)

        # Create a note
        note_resp = client.post("/api/v1/notes", json={"title": "Note about Docker", "content": "Docker notes"}, headers=auth_headers)
        assert note_resp.status_code == 201

        response = client.get("/api/v1/search/unified?q=docker", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "notes" in data
        assert "total" in data

    def test_unified_search_user_scoping(self, client, auth_headers, second_user_headers, db: Session):
        """Unified search respects user boundaries."""
        # User A item
        aid = _seed_item(client, auth_headers, title="Alpha Item", content="alpha private")
        item_a = db.get(KnowledgeItem, uuid.UUID(aid))
        index_item(db, item_a)

        # User B item
        bid = _seed_item(client, second_user_headers, title="Beta Item", content="beta private")
        item_b = db.get(KnowledgeItem, uuid.UUID(bid))
        index_item(db, item_b)

        response = client.get("/api/v1/search/unified?q=alpha", headers=auth_headers)
        assert response.status_code == 200
        item_ids = {r["id"] for r in response.json()["items"]}
        assert aid in item_ids
        assert bid not in item_ids

    def test_unified_search_requires_auth(self, client):
        """Unified search requires authentication."""
        response = client.get("/api/v1/search/unified?q=test")
        assert response.status_code == 401


class TestHybridSearch:
    """Test /search/hybrid endpoint."""

    def test_hybrid_search_basic(self, client, auth_headers, db: Session):
        """Hybrid search returns results."""
        aid = _seed_item(client, auth_headers, title="React Guide", content="React JS tutorial")
        item = db.get(KnowledgeItem, uuid.UUID(aid))
        index_item(db, item)

        response = client.get("/api/v1/search/hybrid?q=react", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_hybrid_search_requires_auth(self, client):
        """Hybrid search requires authentication."""
        response = client.get("/api/v1/search/hybrid?q=test")
        assert response.status_code == 401


class TestSemanticSearch:
    """Test /search/semantic endpoint."""

    def test_semantic_search_returns_list(self, client, auth_headers):
        """Semantic search returns a list (may be empty without embeddings)."""
        response = client.get("/api/v1/search/semantic?q=test", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_semantic_search_requires_auth(self, client):
        """Semantic search requires authentication."""
        response = client.get("/api/v1/search/semantic?q=test")
        assert response.status_code == 401


class TestGetSearchFilters:
    """Test /search/filters endpoint."""

    def test_get_filters_returns_platforms_and_tags(self, client, auth_headers):
        """Filters endpoint returns available platforms and tags."""
        response = client.get("/api/v1/search/filters", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "platforms" in data
        assert "types" in data
        assert "tags" in data

    def test_get_filters_user_scoped(self, client, auth_headers, second_user_headers):
        """Each user sees only their own data in filters."""
        # User A creates a tagged item
        aid = _seed_item(client, auth_headers, title="User A Doc", content="content")
        client.post("/api/v1/tags", json={"name": "alpha-tag"}, headers=auth_headers)

        # User B creates different content
        _seed_item(client, second_user_headers, title="User B Doc", content="content")
        client.post("/api/v1/tags", json={"name": "beta-tag"}, headers=second_user_headers)

        response_a = client.get("/api/v1/search/filters", headers=auth_headers)
        assert response_a.status_code == 200
        tag_names = {t["name"] for t in response_a.json()["tags"]}
        assert "alpha-tag" in tag_names
        assert "beta-tag" not in tag_names

    def test_get_filters_requires_auth(self, client):
        """Filters endpoint requires authentication."""
        response = client.get("/api/v1/search/filters")
        assert response.status_code == 401
