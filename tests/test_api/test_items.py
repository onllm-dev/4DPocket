"""CRUD tests for knowledge items endpoints."""


def test_create_item_with_url(client, auth_headers):
    response = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/article", "title": "Example Article"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://example.com/article"
    assert data["title"] == "Example Article"
    assert data["item_type"] == "url"
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data


def test_create_item_with_content(client, auth_headers):
    response = client.post(
        "/api/v1/items",
        json={
            "title": "My Note",
            "content": "Some note content here",
            "item_type": "note",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Note"
    assert data["content"] == "Some note content here"
    assert data["item_type"] == "note"


def test_list_items_returns_users_items(client, auth_headers, second_user_headers):
    # Create items for user 1
    client.post("/api/v1/items", json={"url": "https://a.com"}, headers=auth_headers)
    client.post("/api/v1/items", json={"url": "https://b.com"}, headers=auth_headers)
    # Create item for user 2
    client.post("/api/v1/items", json={"url": "https://c.com"}, headers=second_user_headers)

    response = client.get("/api/v1/items", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    urls = {item["url"] for item in items}
    assert "https://a.com" in urls
    assert "https://b.com" in urls
    assert "https://c.com" not in urls


def test_list_items_pagination(client, auth_headers):
    for i in range(5):
        client.post("/api/v1/items", json={"url": f"https://example.com/{i}"}, headers=auth_headers)

    response = client.get("/api/v1/items?offset=0&limit=3", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 3

    response = client.get("/api/v1/items?offset=3&limit=3", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_item_by_id(client, auth_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com", "title": "Test"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_get_nonexistent_item_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = client.get(f"/api/v1/items/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_update_item(client, auth_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com", "title": "Original Title"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/items/{item_id}",
        json={"title": "Updated Title", "is_favorite": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["is_favorite"] is True


def test_delete_item(client, auth_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_user_scoping_other_user_cannot_get_item(client, auth_headers, second_user_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://private.com"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/items/{item_id}", headers=second_user_headers)
    assert response.status_code == 404


def test_filter_by_item_type(client, auth_headers):
    client.post("/api/v1/items", json={"url": "https://example.com", "item_type": "url"}, headers=auth_headers)
    client.post("/api/v1/items", json={"title": "Note", "content": "text", "item_type": "note"}, headers=auth_headers)

    response = client.get("/api/v1/items?item_type=note", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert all(item["item_type"] == "note" for item in items)


def test_filter_by_source_platform(client, auth_headers):
    client.post(
        "/api/v1/items",
        json={"url": "https://github.com/user/repo", "source_platform": "github"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/items?source_platform=github", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert all(item["source_platform"] == "github" for item in items)


def test_filter_by_is_favorite(client, auth_headers):
    create_resp = client.post("/api/v1/items", json={"url": "https://example.com"}, headers=auth_headers)
    item_id = create_resp.json()["id"]
    client.patch(f"/api/v1/items/{item_id}", json={"is_favorite": True}, headers=auth_headers)

    client.post("/api/v1/items", json={"url": "https://other.com"}, headers=auth_headers)

    response = client.get("/api/v1/items?is_favorite=true", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["is_favorite"] is True


def test_add_tag_to_item(client, auth_headers):
    item_resp = client.post("/api/v1/items", json={"url": "https://example.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    tag_resp = client.post("/api/v1/tags", json={"name": "Python"}, headers=auth_headers)
    tag_id = tag_resp.json()["id"]

    response = client.post(
        f"/api/v1/items/{item_id}/tags?tag_id={tag_id}",
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["tag_id"] == tag_id


def test_remove_tag_from_item(client, auth_headers):
    item_resp = client.post("/api/v1/items", json={"url": "https://example.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    tag_resp = client.post("/api/v1/tags", json={"name": "RemoveMe"}, headers=auth_headers)
    tag_id = tag_resp.json()["id"]

    client.post(f"/api/v1/items/{item_id}/tags?tag_id={tag_id}", headers=auth_headers)

    response = client.delete(f"/api/v1/items/{item_id}/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 204


def test_check_url_exists(client, auth_headers):
    """Should return exists=True with item details when URL is already saved."""
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/saved", "title": "Saved Article"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    response = client.get(
        "/api/v1/items/check-url?url=https://example.com/saved",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["item_id"] == item_id
    assert data["title"] == "Saved Article"


def test_check_url_not_exists(client, auth_headers):
    """Should return exists=False when URL is not saved."""
    response = client.get(
        "/api/v1/items/check-url?url=https://example.com/not-saved",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False


def test_check_url_user_scoped(client, auth_headers, second_user_headers):
    """Should not find URLs saved by other users."""
    client.post(
        "/api/v1/items",
        json={"url": "https://example.com/user1-only"},
        headers=auth_headers,
    )

    response = client.get(
        "/api/v1/items/check-url?url=https://example.com/user1-only",
        headers=second_user_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False


def test_check_url_requires_auth(client):
    """Should return 401 when no auth headers provided."""
    response = client.get("/api/v1/items/check-url?url=https://example.com")
    assert response.status_code == 401


# === PHASE 0A MOPUP ADDITIONS ===  # noqa: E266


def test_get_timeline(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    _ = make_item(db, user.id, title="Timeline Item", item_type="url")
    response = client.get("/api/v1/items/timeline", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(i["title"] == "Timeline Item" for d in data for i in d["items"])


def test_get_timeline_empty(client, auth_headers):
    response = client.get("/api/v1/items/timeline", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_reading_queue(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    make_item(db, user.id, content="Some content", reading_progress=30, item_type="url")
    response = client.get("/api/v1/items/reading-queue", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1


def test_get_reading_queue_excludes_completed(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    make_item(db, user.id, content="Full content", reading_progress=100, item_type="url")
    response = client.get("/api/v1/items/reading-queue", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert all(item["reading_progress"] < 100 for item in items)


def test_get_reading_list(client, auth_headers, db):
    from fourdpocket.models.base import ReadingStatus
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    _ = make_item(db, user.id, reading_status=ReadingStatus.reading_list, item_type="url")
    response = client.get("/api/v1/items/reading-list", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert all(item["reading_status"] == "reading_list" for item in items)


def test_get_read_items(client, auth_headers, db):
    from fourdpocket.models.base import ReadingStatus
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    make_item(db, user.id, reading_status=ReadingStatus.read, item_type="url")
    response = client.get("/api/v1/items/read", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert all(item["reading_status"] == "read" for item in items)


def test_get_queue_stats(client, auth_headers, db):
    response = client.get("/api/v1/items/queue-stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_archive_item(client, auth_headers, db, monkeypatch):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, url="https://example.com/article", item_type="url")
    monkeypatch.setattr("fourdpocket.api.items.logger", __import__("logging").getLogger("test"))
    monkeypatch.setattr("fourdpocket.workers.archiver.archive_page", lambda *a, **k: None)
    response = client.post(f"/api/v1/items/{item.id}/archive", headers=auth_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_archive_item_no_url(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, url=None, item_type="note")
    response = client.post(f"/api/v1/items/{item.id}/archive", headers=auth_headers)
    assert response.status_code == 400


def test_reprocess_item(client, auth_headers, db, monkeypatch):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, url="https://example.com/article", item_type="url")
    monkeypatch.setattr("fourdpocket.workers.fetcher.fetch_and_process_url", lambda *a, **k: None)
    response = client.post(f"/api/v1/items/{item.id}/reprocess", headers=auth_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_reprocess_item_no_url(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, url=None, item_type="note")
    response = client.post(f"/api/v1/items/{item.id}/reprocess", headers=auth_headers)
    assert response.status_code == 400


def test_get_related_items(client, auth_headers, db, monkeypatch):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    monkeypatch.setattr("fourdpocket.ai.connector.find_related", lambda *a, **k: [])
    response = client.get(f"/api/v1/items/{item.id}/related", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_update_reading_progress(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.patch(
        f"/api/v1/items/{item.id}/reading-progress",
        json={"progress": 75},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reading_progress"] == 75


def test_bulk_archive(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item1 = make_item(db, user.id, item_type="url")
    item2 = make_item(db, user.id, item_type="url")
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "archive", "item_ids": [str(item1.id), str(item2.id)]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 2


def test_bulk_delete(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item1 = make_item(db, user.id, item_type="url")
    item2 = make_item(db, user.id, item_type="url")
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "delete", "item_ids": [str(item1.id), str(item2.id)]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 2


def test_bulk_favorite(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "favorite", "item_ids": [str(item.id)]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1


def test_bulk_unfavorite(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, is_favorite=True, item_type="url")
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "unfavorite", "item_ids": [str(item.id)]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1


def test_bulk_tag_by_id(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    from tests.factories import make_item, make_tag
    user = db.exec(select(User)).first()
    item = make_item(db, user.id, item_type="url")
    tag = make_tag(db, user.id, name="BulkTag")
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "tag", "item_ids": [str(item.id)], "tag_id": str(tag.id)},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1


def test_bulk_tag_by_name(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    from tests.factories import make_item
    user = db.exec(select(User)).first()
    item = make_item(db, user.id, item_type="url")
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "tag", "item_ids": [str(item.id)], "tag_name": "NewTagByName"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1


def test_bulk_enrich(client, auth_headers, db, monkeypatch):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    # Just ensure no exception propagates — the function may do nothing if AI is unconfigured
    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "enrich", "item_ids": [str(item.id)]},
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_media_proxy_unsafe_localhost(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.get(
        f"/api/v1/items/{item.id}/media-proxy?url=http://localhost/foo.jpg",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_media_proxy_unsafe_10_network(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.get(
        f"/api/v1/items/{item.id}/media-proxy?url=http://10.0.0.1/foo.jpg",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_media_proxy_unsafe_172_network(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.get(
        f"/api/v1/items/{item.id}/media-proxy?url=http://172.16.0.1/foo.jpg",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_media_proxy_unsafe_dot_local(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.get(
        f"/api/v1/items/{item.id}/media-proxy?url=http://evil.local/image.jpg",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_media_proxy_unsafe_ftp_scheme(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")
    response = client.get(
        f"/api/v1/items/{item.id}/media-proxy?url=ftp://example.com/file",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_media_proxy_cache_hit(client, auth_headers, db, monkeypatch):
    import tempfile

    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")

    # Create a real temp file so FileResponse doesn't complain
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        temp_path = f.name

    def fake_exists(self, path):
        return True

    def fake_get_abs(self, path):
        from pathlib import Path
        return Path(temp_path)

    monkeypatch.setattr("fourdpocket.storage.local.LocalStorage.file_exists", fake_exists)
    monkeypatch.setattr("fourdpocket.storage.local.LocalStorage.get_absolute_path", fake_get_abs)

    response = client.get(
        f"/api/v1/items/{item.id}/media-proxy?url=https://example.com/img.jpg",
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_serve_media(client, auth_headers, db, monkeypatch):
    import tempfile
    from pathlib import Path

    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        temp_path = f.name

    def fake_get_abs(self, path):
        return Path(temp_path)

    def fake_get_file(self, path):
        pass

    monkeypatch.setattr("fourdpocket.storage.local.LocalStorage.get_absolute_path", fake_get_abs)
    monkeypatch.setattr("fourdpocket.storage.local.LocalStorage.get_file", fake_get_file)

    # Path must start with user id prefix
    user_path = f"{user.id}/media/test.jpg"
    response = client.get(f"/api/v1/items/{item.id}/media/{user_path}", headers=auth_headers)
    assert response.status_code == 200


def test_serve_media_wrong_user_path(client, auth_headers, db):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, item_type="url")

    # Path does not start with this user's id prefix — should be rejected
    response = client.get(f"/api/v1/items/{item.id}/media/00000000-0000-0000-0000-000000000001/file.jpg", headers=auth_headers)
    assert response.status_code == 403


def test_download_video(client, auth_headers, db, monkeypatch):
    from fourdpocket.models.base import SourcePlatform
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, url="https://youtube.com/watch?v=abc", source_platform=SourcePlatform.youtube, item_type="url")
    monkeypatch.setattr("fourdpocket.workers.media_downloader.download_video", lambda *a, **k: "/path/video.mp4")
    response = client.post(f"/api/v1/items/{item.id}/download-video", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "downloaded"


def test_download_video_unsupported_platform(client, auth_headers, db):
    from fourdpocket.models.base import SourcePlatform
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_item
    item = make_item(db, user.id, url="https://example.com/article", source_platform=SourcePlatform.generic, item_type="url")
    response = client.post(f"/api/v1/items/{item.id}/download-video", headers=auth_headers)
    assert response.status_code == 400


def test_is_safe_proxy_url_valid(client, auth_headers):
    from fourdpocket.api.items import _is_safe_proxy_url
    assert _is_safe_proxy_url("http://example.com/image.jpg") is True
    assert _is_safe_proxy_url("https://cdn.example.com/photo.png") is True


def test_is_safe_proxy_url_localhost(client, auth_headers):
    from fourdpocket.api.items import _is_safe_proxy_url
    assert _is_safe_proxy_url("http://localhost/foo") is False
    assert _is_safe_proxy_url("http://localhost:8080/bar") is False


def test_is_safe_proxy_url_private_networks(client, auth_headers):
    from fourdpocket.api.items import _is_safe_proxy_url
    assert _is_safe_proxy_url("http://10.0.0.1/bar") is False
    assert _is_safe_proxy_url("http://10.255.255.1/bar") is False
    assert _is_safe_proxy_url("http://172.16.0.1/baz") is False
    assert _is_safe_proxy_url("http://172.31.255.1/baz") is False


def test_is_safe_proxy_url_internal_tlds(client, auth_headers):
    from fourdpocket.api.items import _is_safe_proxy_url
    assert _is_safe_proxy_url("http://evil.local/internal") is False
    assert _is_safe_proxy_url("http://evil.internal/page") is False


def test_is_safe_proxy_url_ftp(client, auth_headers):
    from fourdpocket.api.items import _is_safe_proxy_url
    assert _is_safe_proxy_url("ftp://example.com/file") is False


def test_try_sync_enrich_noop_when_tags_exist(client, auth_headers, db, monkeypatch):
    from fourdpocket.models.user import User
    from sqlmodel import select
    user = db.exec(select(User)).first()
    from tests.factories import make_enrichment_stage, make_item, make_tag

    item = make_item(db, user.id, item_type="url")
    _ = make_tag(db, user.id, name="ExistingTag")
    make_enrichment_stage(db, item.id, "tagged", status="completed")

    # If existing tags are present, sync enrichment should skip tagging
    # (function should return early — no exception means success)
    from fourdpocket.api.items import _try_sync_enrich
    _try_sync_enrich(item, db, user.id)  # should not raise


def test_create_item_duplicate_url_returns_409(client, auth_headers):
    url = "https://example.com/duplicate-test"
    client.post(
        "/api/v1/items",
        json={"url": url, "title": "First"},
        headers=auth_headers,
    )
    response = client.post(
        "/api/v1/items",
        json={"url": url, "title": "Second"},
        headers=auth_headers,
    )
    assert response.status_code == 409


class TestListItemsSortAndFilter:
    """Test sort_by, sort_order, tag_id, and is_archived list filters."""

    def test_list_items_sort_by_title_asc(self, client, auth_headers):
        """sort_by=title&sort_order=asc returns items alphabetically."""
        client.post("/api/v1/items", json={"url": "https://z.com", "title": "Zulu Article"}, headers=auth_headers)
        client.post("/api/v1/items", json={"url": "https://a.com", "title": "Alpha Article"}, headers=auth_headers)
        client.post("/api/v1/items", json={"url": "https://m.com", "title": "Mid Article"}, headers=auth_headers)

        response = client.get("/api/v1/items?sort_by=title&sort_order=asc", headers=auth_headers)
        assert response.status_code == 200
        titles = [item["title"] for item in response.json()]
        assert titles == sorted(titles), f"Expected alphabetical order, got {titles}"

    def test_list_items_sort_by_title_desc(self, client, auth_headers):
        """sort_by=title&sort_order=desc returns reverse alphabetical."""
        client.post("/api/v1/items", json={"url": "https://z2.com", "title": "Zulu"}, headers=auth_headers)
        client.post("/api/v1/items", json={"url": "https://a2.com", "title": "Alpha"}, headers=auth_headers)

        response = client.get("/api/v1/items?sort_by=title&sort_order=desc", headers=auth_headers)
        assert response.status_code == 200
        titles = [item["title"] for item in response.json()]
        assert titles == sorted(titles, reverse=True), f"Expected reverse order, got {titles}"

    def test_list_items_sort_by_invalid_field_returns_422(self, client, auth_headers):
        """sort_by with an invalid field name is rejected by the regex pattern."""
        response = client.get("/api/v1/items?sort_by=email", headers=auth_headers)
        assert response.status_code == 422

    def test_list_items_filter_by_tag_id(self, client, auth_headers):
        """tag_id filter returns only items with that tag."""
        # Create two items
        r1 = client.post("/api/v1/items", json={"url": "https://tagged.com", "title": "Tagged"}, headers=auth_headers)
        r2 = client.post("/api/v1/items", json={"url": "https://untagged.com", "title": "Untagged"}, headers=auth_headers)
        item1_id = r1.json()["id"]
        item2_id = r2.json()["id"]

        # Create a tag and add it to the first item via tag_id query param
        tag_resp = client.post("/api/v1/tags", json={"name": "filter-test-tag"}, headers=auth_headers)
        assert tag_resp.status_code in (200, 201)
        tag_id = tag_resp.json()["id"]

        # Add tag to item 1
        add_resp = client.post(f"/api/v1/items/{item1_id}/tags?tag_id={tag_id}", headers=auth_headers)
        assert add_resp.status_code in (200, 201)

        # Filter by tag_id
        response = client.get(f"/api/v1/items?tag_id={tag_id}", headers=auth_headers)
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 1
        returned_ids = {i["id"] for i in items}
        assert item1_id in returned_ids
        assert item2_id not in returned_ids

    def test_list_items_filter_is_archived(self, client, auth_headers):
        """is_archived=true returns only archived items."""
        r = client.post("/api/v1/items", json={"url": "https://archive-me.com", "title": "Archive Me"}, headers=auth_headers)
        item_id = r.json()["id"]

        # Use bulk action to archive (sets is_archived=True directly)
        archive_resp = client.post("/api/v1/items/bulk", json={"action": "archive", "item_ids": [item_id]}, headers=auth_headers)
        assert archive_resp.status_code == 200

        # Create a non-archived item
        client.post("/api/v1/items", json={"url": "https://keep-active.com", "title": "Active"}, headers=auth_headers)

        response = client.get("/api/v1/items?is_archived=true", headers=auth_headers)
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 1
        assert all(i.get("is_archived") for i in items)
