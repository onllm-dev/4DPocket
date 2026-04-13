"""End-to-end item lifecycle: create → enrich → search → delete cascade."""

import uuid

from sqlmodel import select

from fourdpocket.models.collection import CollectionItem
from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.tag import ItemTag, Tag


class TestItemLifecycle:
    """Full journey from item creation through enrichment, search, and deletion."""

    def test_create_item_indexes_for_search(self, client, auth_headers):
        """Creating an item should index it in the search backend."""
        response = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/lifecycle-test", "title": "Lifecycle Test Item"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        item_id = response.json()["id"]

        # Search should find the newly created item
        search_resp = client.get("/api/v1/search?q=lifecycle", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        item_ids = [r["id"] for r in results]
        assert item_id in item_ids, "Newly created item should appear in search results"

    def test_create_item_no_error(self, client, auth_headers, mock_chat_provider):
        """Creating an item with AI mocking should succeed without errors."""
        response = client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/enrichment-stages",
                "title": "Enrichment Stages Test",
                "content": "Some content for enrichment",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_add_to_collection_and_verify_membership(self, client, auth_headers, db):
        """Item should become part of a collection when added."""
        # Create item
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/collection-test", "title": "Collection Test"},
            headers=auth_headers,
        )
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Create collection
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "Test Collection"},
            headers=auth_headers,
        )
        assert coll_resp.status_code == 201
        coll_id = coll_resp.json()["id"]

        # Add item to collection
        add_resp = client.post(
            f"/api/v1/collections/{coll_id}/items",
            json={"item_ids": [item_id]},
            headers=auth_headers,
        )
        assert add_resp.status_code == 201
        assert item_id in add_resp.json()["added"]

        # Verify membership via db
        link = db.exec(
            select(CollectionItem).where(
                CollectionItem.collection_id == uuid.UUID(coll_id),
                CollectionItem.item_id == uuid.UUID(item_id),
            )
        ).first()
        assert link is not None, "Item should be linked to collection"

    def test_search_returns_item_with_content_match(self, client, auth_headers):
        """Search should find item by content."""
        unique_content = f"unique-phrase-{uuid.uuid4().hex[:8]}"

        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/search-test",
                "title": "Search Test",
                "content": f"Some content containing {unique_content} for searching.",
            },
            headers=auth_headers,
        )

        search_resp = client.get(f"/api/v1/search?q={unique_content}", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) >= 1
        titles = [r["title"] for r in results]
        assert "Search Test" in titles

    def test_delete_item_cascades_to_chunks(self, client, auth_headers, db):
        """Deleting an item should remove all its chunks."""
        # Create item with content
        item_resp = client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/cascade-chunks",
                "title": "Cascade Chunks Test",
                "content": "Content for cascade test",
            },
            headers=auth_headers,
        )
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Delete the item
        delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # Verify chunks are gone
        remaining_chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == uuid.UUID(item_id))
        ).all()
        assert len(remaining_chunks) == 0, "All chunks should be deleted with item"

    def test_delete_item_cascades_to_tags(self, client, auth_headers, db):
        """Deleting an item should remove all item-tag associations and decrement tag usage."""
        # Create item
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/cascade-tags", "title": "Cascade Tags Test"},
            headers=auth_headers,
        )
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Create and attach a tag
        tag_resp = client.post("/api/v1/tags", json={"name": "cascade-tag"}, headers=auth_headers)
        tag_id = tag_resp.json()["id"]

        client.post(f"/api/v1/items/{item_id}/tags?tag_id={tag_id}", headers=auth_headers)

        # Get initial tag usage
        initial_tag = db.get(Tag, uuid.UUID(tag_id))
        initial_usage = initial_tag.usage_count

        # Delete the item
        delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # Verify item-tag links are removed
        remaining_links = db.exec(
            select(ItemTag).where(ItemTag.item_id == uuid.UUID(item_id))
        ).all()
        assert len(remaining_links) == 0

        # Tag usage should be decremented
        db.refresh(initial_tag)
        assert initial_tag.usage_count == initial_usage - 1

    def test_delete_item_cascades_to_enrichment_stages(self, client, auth_headers, db):
        """Deleting an item should remove all enrichment stage records."""
        # Create item
        item_resp = client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/cascade-stages",
                "title": "Cascade Stages Test",
                "content": "Content for testing enrichment stage cascade",
            },
            headers=auth_headers,
        )
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Delete the item
        delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # Verify enrichment stages are gone
        remaining_stages = db.exec(
            select(EnrichmentStage).where(EnrichmentStage.item_id == uuid.UUID(item_id))
        ).all()
        assert len(remaining_stages) == 0

    def test_delete_item_removes_from_collections(self, client, auth_headers, db):
        """Deleting an item should remove it from all collections."""
        # Create item
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/cascade-coll", "title": "Cascade Collection Test"},
            headers=auth_headers,
        )
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Create collection and add item
        coll_resp = client.post("/api/v1/collections", json={"name": "Cascade Test Coll"}, headers=auth_headers)
        coll_id = coll_resp.json()["id"]
        client.post(f"/api/v1/collections/{coll_id}/items", json={"item_ids": [item_id]}, headers=auth_headers)

        # Verify link exists
        link_before = db.exec(
            select(CollectionItem).where(
                CollectionItem.collection_id == uuid.UUID(coll_id),
                CollectionItem.item_id == uuid.UUID(item_id),
            )
        ).first()
        assert link_before is not None

        # Delete item
        delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # Verify link is gone
        link_after = db.exec(
            select(CollectionItem).where(
                CollectionItem.collection_id == uuid.UUID(coll_id),
                CollectionItem.item_id == uuid.UUID(item_id),
            )
        ).first()
        assert link_after is None

    def test_full_lifecycle_create_enrich_search_delete(self, client, auth_headers, mock_chat_provider, mock_embedding_provider):
        """Complete lifecycle: create → verify in list → verify in search → delete → verify gone."""
        unique_term = f"lifecycle-{uuid.uuid4().hex[:8]}"

        # 1. Create
        create_resp = client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/lifecycle-full",
                "title": f"Full Lifecycle Test {unique_term}",
                "content": f"Content with {unique_term} for search verification.",
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        item_id = create_resp.json()["id"]

        # 2. Verify in item list
        list_resp = client.get("/api/v1/items", headers=auth_headers)
        assert list_resp.status_code == 200
        list_ids = [item["id"] for item in list_resp.json()]
        assert item_id in list_ids

        # 3. Verify in search
        search_resp = client.get(f"/api/v1/search?q={unique_term}", headers=auth_headers)
        assert search_resp.status_code == 200
        search_ids = [r["id"] for r in search_resp.json()]
        assert item_id in search_ids, "Item should be findable by content"

        # 4. Delete
        delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # 5. Verify gone from list
        list_resp2 = client.get("/api/v1/items", headers=auth_headers)
        list_ids2 = [item["id"] for item in list_resp2.json()]
        assert item_id not in list_ids2

        # 6. Verify gone from search
        search_resp2 = client.get(f"/api/v1/search?q={unique_term}", headers=auth_headers)
        search_ids2 = [r["id"] for r in search_resp2.json()]
        assert item_id not in search_ids2

        # 7. Verify 404 on direct fetch
        get_resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert get_resp.status_code == 404
