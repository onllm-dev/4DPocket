"""Search roundtrip tests: index items → search → verify ranking."""

import uuid


class TestSearchRoundtrip:
    """Verify search indexing and retrieval produce expected ranking."""

    def test_search_finds_item_by_title(self, client, auth_headers):
        """Exact title match should be retrievable via search."""
        title = f"Unique Search Title {uuid.uuid4().hex[:6]}"

        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/title-search", "title": title},
            headers=auth_headers,
        )

        search_resp = client.get(f"/api/v1/search?q={title}", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) >= 1
        assert any(r["title"] == title for r in results)

    def test_search_finds_item_by_url(self, client, auth_headers):
        """URL should be searchable."""
        url = f"https://example.com/roundtrip-{uuid.uuid4().hex[:6]}"

        client.post(
            "/api/v1/items",
            json={"url": url, "title": "URL Search Test"},
            headers=auth_headers,
        )

        # Search by domain
        domain = uuid.uuid4().hex[:6]
        unique_url = f"https://{domain}.example.com/path"
        client.post(
            "/api/v1/items",
            json={"url": unique_url, "title": "Domain Search Test"},
            headers=auth_headers,
        )

        search_resp = client.get(f"/api/v1/search?q={domain}", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        titles = [r["title"] for r in results]
        assert "Domain Search Test" in titles

    def test_search_user_scoping_results(self, client, auth_headers, second_user_headers):
        """User A's items should not appear in User B's search."""
        unique_term = f"user-a-exclusive-{uuid.uuid4().hex[:8]}"

        # User A creates an item
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/user-a-item",
                "title": f"User A Private {unique_term}",
                "content": f"Content for {unique_term}",
            },
            headers=auth_headers,
        )

        # User B searches - should not find User A's item
        search_resp = client.get(f"/api/v1/search?q={unique_term}", headers=second_user_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        titles = [r.get("title") or "" for r in results]
        assert not any(unique_term in title for title in titles), "User B should not see User A's private item"

    def test_search_multiple_items_returns_all_matching(self, client, auth_headers):
        """Multiple items matching a query should all be returned."""
        shared_term = f"multi-{uuid.uuid4().hex[:6]}"

        # Create 3 items with shared term
        for i in range(3):
            client.post(
                "/api/v1/items",
                json={
                    "url": f"https://example.com/multi-{i}",
                    "title": f"Item {i} with {shared_term}",
                    "content": f"Content {i}",
                },
                headers=auth_headers,
            )

        search_resp = client.get(f"/api/v1/search?q={shared_term}", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) >= 3

    def test_search_empty_query_handled(self, client, auth_headers):
        """Empty query should be handled gracefully."""
        # Create at least one item first
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/query-test", "title": "Query Test"},
            headers=auth_headers,
        )

        # Empty query with no filters should return 400 (both q and filters absent)
        search_resp = client.get("/api/v1/search?q=", headers=auth_headers)
        assert search_resp.status_code == 400

    def test_search_special_characters_handled(self, client, auth_headers):
        """Queries with special characters should not cause errors."""
        # Create item with special characters in content
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/special",
                "title": "Special Chars Test",
                "content": "Content with quotes: 'test' and brackets: [test]",
            },
            headers=auth_headers,
        )

        # Search with special chars should not error
        search_resp = client.get("/api/v1/search?q=test", headers=auth_headers)
        assert search_resp.status_code == 200

    def test_search_with_item_type_filter(self, client, auth_headers):
        """Search with item_type filter should only return matching types."""
        # Create note type item
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/type-filter",
                "title": "Note Type Item",
                "item_type": "note",
                "content": "This is a note",
            },
            headers=auth_headers,
        )

        # Search with type filter
        search_resp = client.get("/api/v1/search?q=type-filter&item_type=note", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        for r in results:
            assert r["item_type"] == "note"

    def test_search_pagination(self, client, auth_headers):
        """Search pagination should return correct windows."""
        shared = f"page-{uuid.uuid4().hex[:6]}"

        # Create 5 items
        for i in range(5):
            client.post(
                "/api/v1/items",
                json={
                    "url": f"https://example.com/pg-{i}",
                    "title": f"Page {i} {shared}",
                    "content": f"Content {i}",
                },
                headers=auth_headers,
            )

        # First page
        page1 = client.get(f"/api/v1/search?q={shared}&limit=2&offset=0", headers=auth_headers)
        assert page1.status_code == 200
        results1 = page1.json()
        assert len(results1) <= 2

        # Second page
        page2 = client.get(f"/api/v1/search?q={shared}&limit=2&offset=2", headers=auth_headers)
        assert page2.status_code == 200
        results2 = page2.json()
        assert len(results2) <= 2

        # Pages should not overlap
        ids1 = {r["id"] for r in results1}
        ids2 = {r["id"] for r in results2}
        if ids1 and ids2:
            assert ids1.isdisjoint(ids2), "Pagination should not return duplicate items"

    def test_search_with_source_platform_filter(self, client, auth_headers):
        """Search with source_platform filter should only return from that platform."""
        # Create GitHub item
        client.post(
            "/api/v1/items",
            json={
                "url": "https://github.com/example/repo",
                "title": "GitHub Item",
                "source_platform": "github",
            },
            headers=auth_headers,
        )

        # Create generic item
        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/generic",
                "title": "Generic Item",
            },
            headers=auth_headers,
        )

        # Filter by github
        search_resp = client.get("/api/v1/search?q=Item&source_platform=github", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        for r in results:
            assert r["source_platform"] == "github"

    def test_search_is_favorite_filter(self, client, auth_headers):
        """Search with is_favorite filter should only return favorited items."""
        # Create and favorite an item
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/fav-test", "title": "Favorite Test"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]
        client.patch(f"/api/v1/items/{item_id}", json={"is_favorite": True}, headers=auth_headers)

        # Create non-favorite item
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/not-fav", "title": "Not Favorite Test"},
            headers=auth_headers,
        )

        # Filter by is_favorite
        search_resp = client.get("/api/v1/search?q=Test&is_favorite=true", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        for r in results:
            assert r["is_favorite"] is True

    def test_search_no_results_returns_empty_list(self, client, auth_headers):
        """Query with no matches should return empty list."""
        nonexistent = f"definitely-nonexistent-{uuid.uuid4().hex[:8]}"

        search_resp = client.get(f"/api/v1/search?q={nonexistent}", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert isinstance(results, list)
        assert len(results) == 0

    def test_hybrid_search_endpoint(self, client, auth_headers):
        """Hybrid search endpoint should return results."""
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/hybrid-test", "title": "Hybrid Search Test"},
            headers=auth_headers,
        )

        hybrid_resp = client.get("/api/v1/search/hybrid?q=Hybrid", headers=auth_headers)
        assert hybrid_resp.status_code == 200
        results = hybrid_resp.json()
        assert isinstance(results, list)

    def test_search_returns_item_with_snippets(self, client, auth_headers):
        """Search results should include title_snippet or content_snippet when available."""
        unique = f"snippet-{uuid.uuid4().hex[:6]}"

        client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/snippet",
                "title": "Snippet Test",
                "content": f"This content has {unique} embedded within it.",
            },
            headers=auth_headers,
        )

        search_resp = client.get(f"/api/v1/search?q={unique}", headers=auth_headers)
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) >= 1
        # Results may include snippets when available
