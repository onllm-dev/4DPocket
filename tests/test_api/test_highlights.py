"""CRUD tests for highlights endpoints."""




def test_create_highlight_attached_to_item(client, auth_headers):
    """Create a highlight attached to an item."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/article"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={
            "item_id": item_id,
            "text": "This is highlighted text",
            "note": "My annotation",
            "color": "yellow",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["text"] == "This is highlighted text"
    assert data["note"] == "My annotation"
    assert data["color"] == "yellow"
    assert "id" in data
    assert "user_id" in data


def test_create_highlight_attached_to_note(client, auth_headers):
    """Create a highlight attached to a note."""
    note_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note content"},
        headers=auth_headers,
    )
    note_id = note_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={
            "note_id": note_id,
            "text": "Highlighted from note",
            "color": "green",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["note_id"] == note_id
    assert data["text"] == "Highlighted from note"
    assert data["color"] == "green"


def test_create_highlight_rejects_neither_item_nor_note(client, auth_headers):
    """Must provide either item_id or note_id."""
    response = client.post(
        "/api/v1/highlights",
        json={"text": "Some text"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_highlight_rejects_both_item_and_note(client, auth_headers):
    """Cannot provide both item_id and note_id."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    note_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note"},
        headers=auth_headers,
    )
    response = client.post(
        "/api/v1/highlights",
        json={
            "item_id": item_resp.json()["id"],
            "note_id": note_resp.json()["id"],
            "text": "Conflicting",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_highlight_with_position_dict(client, auth_headers):
    """Position dict is stored when provided with valid keys."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/article"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={
            "item_id": item_id,
            "text": "Text with position",
            "position": {"start": 100, "end": 250, "paragraph": 3},
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["position"]["start"] == 100
    assert data["position"]["end"] == 250
    assert data["position"]["paragraph"] == 3


def test_create_highlight_rejects_invalid_position_key(client, auth_headers):
    """position dict keys must be from allowed set."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={
            "item_id": item_id,
            "text": "Bad key",
            "position": {"invalid_key": 10},
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_highlight_rejects_html_tags_stripped(client, auth_headers):
    """HTML tags are stripped from text and note."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={
            "item_id": item_id,
            "text": "<script>bad</script>Good text",
            "note": "<b>Annotated</b>",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "<script>" not in data["text"]
    assert "<b>" not in data["note"]


def test_list_highlights_returns_users_highlights(client, auth_headers, second_user_headers):
    """List returns only the authenticated user's highlights."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "User A highlight"}, headers=auth_headers)
    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "User A highlight 2"}, headers=auth_headers)
    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "User B highlight"}, headers=second_user_headers)

    response = client.get("/api/v1/highlights", headers=auth_headers)
    assert response.status_code == 200
    highlights = response.json()
    texts = {h["text"] for h in highlights}
    assert "User A highlight" in texts
    assert "User A highlight 2" in texts
    assert "User B highlight" not in texts


def test_list_highlights_filtered_by_item(client, auth_headers):
    """List highlights filtered by item_id."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/article"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]
    other_item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/other"},
        headers=auth_headers,
    )
    other_item_id = other_item_resp.json()["id"]

    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "From item A"}, headers=auth_headers)
    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "From item A 2"}, headers=auth_headers)
    client.post("/api/v1/highlights", json={"item_id": other_item_id, "text": "From item B"}, headers=auth_headers)

    response = client.get(f"/api/v1/highlights?item_id={item_id}", headers=auth_headers)
    assert response.status_code == 200
    highlights = response.json()
    assert len(highlights) == 2
    assert all(h["item_id"] == item_id for h in highlights)


def test_list_highlights_pagination(client, auth_headers):
    """List highlights respects limit and offset."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    for i in range(5):
        client.post("/api/v1/highlights", json={"item_id": item_id, "text": f"Highlight {i}"}, headers=auth_headers)

    response = client.get("/api/v1/highlights?limit=2&offset=1", headers=auth_headers)
    assert response.status_code == 200
    highlights = response.json()
    assert len(highlights) == 2


def test_update_highlight(client, auth_headers):
    """Update note and color of an existing highlight."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Original", "note": "Original note", "color": "yellow"},
        headers=auth_headers,
    )
    highlight_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/highlights/{highlight_id}",
        json={"note": "Updated note", "color": "blue"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["note"] == "Updated note"
    assert data["color"] == "blue"
    assert data["text"] == "Original"


def test_update_highlight_strips_html(client, auth_headers):
    """Update strips HTML from note field."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Text"},
        headers=auth_headers,
    )
    highlight_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/highlights/{highlight_id}",
        json={"note": "<script>bad</script>Safe"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "<script>" not in response.json()["note"]


def test_delete_highlight(client, auth_headers):
    """Delete a highlight."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "To delete"},
        headers=auth_headers,
    )
    highlight_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/highlights/{highlight_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    # Verify via list - the deleted highlight should not appear
    list_resp = client.get("/api/v1/highlights", headers=auth_headers)
    assert all(h["id"] != highlight_id for h in list_resp.json())


def test_user_scoping_highlight_not_visible_to_other_user(client, auth_headers, second_user_headers):
    """A user's highlight is not visible to another user."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Private highlight"},
        headers=auth_headers,
    )
    highlight_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/highlights", headers=second_user_headers)
    assert all(h["id"] != highlight_id for h in list_resp.json())


def test_highlight_404_for_nonexistent_id(client, auth_headers):
    """Update/delete on nonexistent highlight returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.patch(f"/api/v1/highlights/{fake_id}", json={}, headers=auth_headers)
    assert response.status_code == 404
    delete_resp = client.delete(f"/api/v1/highlights/{fake_id}", headers=auth_headers)
    assert delete_resp.status_code == 404


def test_search_highlights(client, auth_headers):
    """Search highlights by text content."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "Python is great"}, headers=auth_headers)
    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "JavaScript vs Python"}, headers=auth_headers)
    client.post("/api/v1/highlights", json={"item_id": item_id, "text": "Rust performance"}, headers=auth_headers)

    response = client.get("/api/v1/highlights/search?q=Python", headers=auth_headers)
    assert response.status_code == 200
    highlights = response.json()
    assert len(highlights) >= 2
    texts = [h["text"] for h in highlights]
    assert all("Python" in t for t in texts)


def test_search_highlights_requires_min_length(client, auth_headers):
    """Search query must be at least 2 characters."""
    response = client.get("/api/v1/highlights/search?q=a", headers=auth_headers)
    assert response.status_code == 422


def test_highlight_401_without_auth(client):
    """All endpoints require authentication."""
    response = client.get("/api/v1/highlights")
    assert response.status_code == 401


# === BUG REGRESSION TESTS ===


def test_create_highlight_invalid_color_returns_422(client, auth_headers):
    """color must be one of the allowed Literal values.

    Regression test: color was free-form str, allowing arbitrary values.
    Fixed in: src/fourdpocket/api/highlights.py HighlightCreate
    """
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Colored highlight", "color": "pink"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_highlight_invalid_color_returns_422(client, auth_headers):
    """color update must also be constrained to allowed Literal values.

    Regression test: HighlightUpdate.color was free-form str.
    Fixed in: src/fourdpocket/api/highlights.py HighlightUpdate
    """
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Text"},
        headers=auth_headers,
    )
    highlight_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/highlights/{highlight_id}",
        json={"color": "magenta"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_highlight_negative_start_position_returns_422(client, auth_headers):
    """position['start'] must be >= 0.

    Regression test: no validation existed for negative start values.
    Fixed in: src/fourdpocket/api/highlights.py HighlightCreate.model_post_init
    """
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Bad pos", "position": {"start": -1}},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_highlight_start_greater_than_end_returns_422(client, auth_headers):
    """position['start'] must be <= position['end'].

    Regression test: no ordering check existed.
    Fixed in: src/fourdpocket/api/highlights.py HighlightCreate.model_post_init
    """
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        "/api/v1/highlights",
        json={"item_id": item_id, "text": "Bad range", "position": {"start": 100, "end": 50}},
        headers=auth_headers,
    )
    assert response.status_code == 422
