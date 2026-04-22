"""Tests for filter-only search (empty q with type:/tag: filters).

When q is empty and only filter directives are provided, the search API routes
to _filter_only_search (direct SQL SELECT) rather than the FTS/vector backend.
"""
import pytest


class TestFilterOnlySearch:
    """GET /api/v1/search with empty q and filter directives."""

    def _create_item(self, client, auth_headers, *, title, url, item_type="article", source_platform="generic"):
        """Helper: POST an item with minimal metadata."""
        resp = client.post(
            "/api/v1/items",
            json={"url": url, "title": title},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201), resp.text
        return resp.json()

    def test_type_filter_returns_matching_items(self, client, auth_headers):
        """type:youtube with empty q returns items whose source_platform=youtube.

        The search endpoint returns a plain list (not a dict with 'results' key).
        """
        resp = client.get(
            "/api/v1/search",
            params={"q": "type:youtube"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # All returned items must be youtube type
        for item in data:
            assert item.get("source_platform") == "youtube" or item.get("item_type") == "youtube"

    def test_tag_filter_with_empty_q_returns_matching_items(self, client, auth_headers, db):
        """tag:foo with empty q returns only items tagged 'foo'."""
        from sqlmodel import select

        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.tag import ItemTag, Tag
        from fourdpocket.models.user import User

        # Resolve the logged-in user
        user = db.exec(
            select(User).where(User.email == "test@example.com")
        ).first()
        assert user is not None

        # Create two items directly in DB
        tagged_item = KnowledgeItem(
            user_id=user.id,
            title="Tagged Item",
            url="https://example.com/tagged",
            source_platform="generic",
        )
        untagged_item = KnowledgeItem(
            user_id=user.id,
            title="Untagged Item",
            url="https://example.com/untagged",
            source_platform="generic",
        )
        db.add(tagged_item)
        db.add(untagged_item)
        db.commit()
        db.refresh(tagged_item)

        tag = Tag(user_id=user.id, name="foo", slug="foo")
        db.add(tag)
        db.commit()
        db.refresh(tag)

        db.add(ItemTag(item_id=tagged_item.id, tag_id=tag.id))
        db.commit()

        resp = client.get(
            "/api/v1/search",
            params={"q": "tag:foo"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        result_ids = {r["id"] for r in data}
        assert str(tagged_item.id) in result_ids
        assert str(untagged_item.id) not in result_ids

    def test_filter_only_does_not_return_other_users_items(self, client, auth_headers, second_user_headers, db):
        """Filter-only search is user-scoped — other users' items never appear.

        Uses type:generic to trigger the filter-only code path with a non-empty filter.
        """
        from sqlmodel import select

        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.user import User

        other_user = db.exec(
            select(User).where(User.email == "user2@example.com")
        ).first()
        if other_user is None:
            pytest.skip("second_user_headers fixture did not create second user")

        other_item = KnowledgeItem(
            user_id=other_user.id,
            title="Other User Generic Item",
            url="https://example.com/other",
            source_platform="generic",
        )
        db.add(other_item)
        db.commit()

        # type:generic triggers filter-only path (has_filters=True, no free-text)
        resp = client.get(
            "/api/v1/search",
            params={"q": "type:generic"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        result_ids = {r["id"] for r in data}
        assert str(other_item.id) not in result_ids

    def test_empty_q_with_no_filters_returns_400(self, client, auth_headers):
        """Pure empty q with no filters returns 400 (API requires query or filter)."""
        resp = client.get(
            "/api/v1/search",
            params={"q": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_filter_only_q_returns_200(self, client, auth_headers):
        """Filter directive with empty free-text returns 200 (filter-only path)."""
        resp = client.get(
            "/api/v1/search",
            params={"q": "type:article"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
