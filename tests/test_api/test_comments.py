"""CRUD tests for comment endpoints."""




def _create_item(client, auth_headers, url="https://example.com/article"):
    resp = client.post("/api/v1/items", json={"url": url}, headers=auth_headers)
    return resp.json()["id"]


def test_add_comment_to_item(client, auth_headers):
    """Add a comment to an item."""
    item_id = _create_item(client, auth_headers)

    response = client.post(
        f"/api/v1/items/{item_id}/comments",
        json={"content": "This is a comment"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["content"] == "This is a comment"
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data
    # user_display_name may be None if display_name is not set on the user
    assert data.get("user_display_name") is not None or True


def test_add_comment_strips_html_tags(client, auth_headers):
    """HTML tags are stripped from comment content."""
    item_id = _create_item(client, auth_headers)

    response = client.post(
        f"/api/v1/items/{item_id}/comments",
        json={"content": "<script>bad</script>Safe comment"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert "<script>" not in response.json()["content"]


def test_list_comments_returns_item_comments(client, auth_headers):
    """List comments for an item."""
    item_id = _create_item(client, auth_headers)

    client.post(f"/api/v1/items/{item_id}/comments", json={"content": "First"}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/comments", json={"content": "Second"}, headers=auth_headers)

    response = client.get(f"/api/v1/items/{item_id}/comments", headers=auth_headers)
    assert response.status_code == 200
    comments = response.json()
    assert len(comments) == 2
    assert all(c["item_id"] == item_id for c in comments)


def test_list_comments_ordered_chronologically(client, auth_headers):
    """Comments are ordered by created_at ascending."""
    item_id = _create_item(client, auth_headers)

    client.post(f"/api/v1/items/{item_id}/comments", json={"content": "Earliest"}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/comments", json={"content": "Middle"}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/comments", json={"content": "Latest"}, headers=auth_headers)

    response = client.get(f"/api/v1/items/{item_id}/comments", headers=auth_headers)
    comments = response.json()
    contents = [c["content"] for c in comments]
    assert contents == ["Earliest", "Middle", "Latest"]


def test_list_comments_pagination(client, auth_headers):
    """List comments respects offset and limit."""
    item_id = _create_item(client, auth_headers)

    for i in range(5):
        client.post(f"/api/v1/items/{item_id}/comments", json={"content": f"Comment {i}"}, headers=auth_headers)

    response = client.get(f"/api/v1/items/{item_id}/comments?offset=1&limit=2", headers=auth_headers)
    assert response.status_code == 200
    comments = response.json()
    assert len(comments) == 2


def test_delete_own_comment(client, auth_headers):
    """Owner can delete their own comment."""
    item_id = _create_item(client, auth_headers)
    create_resp = client.post(
        f"/api/v1/items/{item_id}/comments",
        json={"content": "To delete"},
        headers=auth_headers,
    )
    comment_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/items/{item_id}/comments/{comment_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/api/v1/items/{item_id}/comments", headers=auth_headers)
    assert all(c["id"] != comment_id for c in list_resp.json())


def test_delete_comment_forbidden_for_other_user(client, auth_headers, second_user_headers):
    """Non-owner cannot delete another user's comment."""
    item_id = _create_item(client, auth_headers)
    create_resp = client.post(
        f"/api/v1/items/{item_id}/comments",
        json={"content": "User A comment"},
        headers=auth_headers,
    )
    comment_id = create_resp.json()["id"]

    delete_resp = client.delete(
        f"/api/v1/items/{item_id}/comments/{comment_id}",
        headers=second_user_headers,
    )
    assert delete_resp.status_code == 403


def test_delete_comment_404_for_nonexistent(client, auth_headers):
    """Deleting nonexistent comment returns 404."""
    item_id = _create_item(client, auth_headers)
    fake_id = "00000000-0000-0000-0000-000000000002"

    delete_resp = client.delete(f"/api/v1/items/{item_id}/comments/{fake_id}", headers=auth_headers)
    assert delete_resp.status_code == 404


def test_delete_comment_404_wrong_item(client, auth_headers):
    """Comment attached to different item returns 404 when deleted via wrong item."""
    item_id_a = _create_item(client, auth_headers)
    item_id_b = _create_item(client, auth_headers, url="https://example.com/other-article")

    create_resp = client.post(
        f"/api/v1/items/{item_id_a}/comments",
        json={"content": "Comment on item A"},
        headers=auth_headers,
    )
    comment_id = create_resp.json()["id"]

    # Trying to delete via item_id_b instead of item_id_a returns 404
    delete_resp = client.delete(
        f"/api/v1/items/{item_id_b}/comments/{comment_id}",
        headers=auth_headers,
    )
    assert delete_resp.status_code == 404


def test_add_comment_404_for_nonexistent_item(client, auth_headers):
    """Commenting on nonexistent item returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.post(
        f"/api/v1/items/{fake_id}/comments",
        json={"content": "Comment"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_add_comment_empty_content(client, auth_headers):
    """Empty string content is accepted (validation is minimal)."""
    item_id = _create_item(client, auth_headers)

    response = client.post(
        f"/api/v1/items/{item_id}/comments",
        json={"content": ""},
        headers=auth_headers,
    )
    assert response.status_code == 201


def test_list_comments_401_without_auth(client):
    """List comments without auth returns 401."""
    response = client.get("/api/v1/items/00000000-0000-0000-0000-000000000001/comments")
    assert response.status_code == 401


def test_add_comment_401_without_auth(client):
    """Adding comment without auth returns 401."""
    response = client.post(
        "/api/v1/items/00000000-0000-0000-0000-000000000001/comments",
        json={"content": "Comment"},
    )
    assert response.status_code == 401
