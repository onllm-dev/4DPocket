"""CRUD tests for notes endpoints."""


def test_create_standalone_note(client, auth_headers):
    response = client.post(
        "/api/v1/notes",
        json={"title": "My Note", "content": "Some content here"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Note"
    assert data["content"] == "Some content here"
    assert data["item_id"] is None
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data


def test_list_notes_returns_users_notes(client, auth_headers, second_user_headers):
    client.post("/api/v1/notes", json={"content": "Note A"}, headers=auth_headers)
    client.post("/api/v1/notes", json={"content": "Note B"}, headers=auth_headers)
    client.post("/api/v1/notes", json={"content": "Note C"}, headers=second_user_headers)

    response = client.get("/api/v1/notes", headers=auth_headers)
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 2
    contents = {note["content"] for note in notes}
    assert "Note A" in contents
    assert "Note B" in contents
    assert "Note C" not in contents


def test_get_note_by_id(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Findable note"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == note_id


def test_get_nonexistent_note_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.get(f"/api/v1/notes/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_update_note_content(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"title": "Original", "content": "Original content"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "Updated content"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Updated content"


def test_delete_note(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "To be deleted"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_attach_note_to_item(client, auth_headers):
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        f"/api/v1/items/{item_id}/notes",
        json={"title": "Attached Note", "content": "Note attached to item"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["content"] == "Note attached to item"


def test_list_item_notes(client, auth_headers):
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    client.post(f"/api/v1/items/{item_id}/notes", json={"content": "First note"}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/notes", json={"content": "Second note"}, headers=auth_headers)

    response = client.get(f"/api/v1/items/{item_id}/notes", headers=auth_headers)
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 2
    assert all(note["item_id"] == item_id for note in notes)


def test_user_scoping_notes_not_visible_to_other_user(client, auth_headers, second_user_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Private note"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/notes/{note_id}", headers=second_user_headers)
    assert response.status_code == 404

    list_resp = client.get("/api/v1/notes", headers=second_user_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


# === PHASE 0B MOPUP ADDITIONS ===


def test_create_note_invalid_item_404(client, auth_headers):
    """item_id points to non-existent item → 404."""
    response = client.post(
        "/api/v1/notes",
        json={"content": "Some content", "item_id": "00000000-0000-0000-0000-000000000002"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_create_note_fts_exception_swallowed(client, auth_headers, monkeypatch):
    """FTS index_note raises → note still created."""
    def raise_exception(*args, **kwargs):
        raise RuntimeError("FTS error")

    monkeypatch.setattr("fourdpocket.search.sqlite_fts.index_note", raise_exception)

    response = client.post(
        "/api/v1/notes",
        json={"content": "Content after FTS failure"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["content"] == "Content after FTS failure"


def test_search_notes_fts(client, auth_headers):
    """GET /notes/search?q=keyword with FTS returns matching note."""
    client.post(
        "/api/v1/notes",
        json={"content": "The quick brown fox"},
        headers=auth_headers,
    )
    response = client.get("/api/v1/notes/search?q=quick", headers=auth_headers)
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 1
    assert notes[0]["content"] == "The quick brown fox"


def test_search_notes_like_fallback(client, auth_headers, monkeypatch):
    """search.backend != 'sqlite' → LIKE fallback path is used."""
    import fourdpocket.config as config_module

    class FakeSettings:
        def __init__(self):
            self.search = self._Search()
            self.database = self._Database()
            self.server = self._Server()
            self.auth = self._Auth()

        class _Search:
            backend = "not_sqlite"
        class _Database:
            url = "sqlite:///./test.db"
        class _Server:
            secure_cookies = False
        class _Auth:
            mode = "multi"
            token_expire_minutes = 30

    monkeypatch.setattr(config_module, "get_settings", lambda: FakeSettings())

    client.post(
        "/api/v1/notes",
        json={"content": "mystery keyword xyz"},
        headers=auth_headers,
    )
    response = client.get("/api/v1/notes/search?q=xyz", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_update_note_404(client, auth_headers):
    """PATCH non-existent note → 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.patch(
        f"/api/v1/notes/{fake_id}",
        json={"content": "Updated"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_note_with_tags(client, auth_headers):
    """PATCH note with tags applies them."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note without tags"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"tags": ["foo", "bar"]},
        headers=auth_headers,
    )
    assert response.status_code == 200

    tags_resp = client.get(f"/api/v1/notes/{note_id}/tags", headers=auth_headers)
    assert tags_resp.status_code == 200
    tag_names = {t["name"] for t in tags_resp.json()}
    assert tag_names == {"foo", "bar"}


def test_delete_note_404(client, auth_headers):
    """DELETE non-existent note → 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.delete(f"/api/v1/notes/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_note_cascade_tags(client, auth_headers, db):
    """Delete note with NoteTag → tag usage_count is decremented."""
    from sqlmodel import select

    from fourdpocket.models.note import Note
    from fourdpocket.models.note_tag import NoteTag
    from fourdpocket.models.tag import Tag
    from fourdpocket.models.user import User

    # Get user UUID from the registered user
    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    user_uuid = user.id

    # Create note and tag directly in DB with correct UUID
    note = Note(user_id=user_uuid, content="Note for cascade test")
    db.add(note)
    db.flush()

    tag = Tag(user_id=user_uuid, name="cascadetag", slug="cascadetag", usage_count=1)
    db.add(tag)
    db.flush()

    db.add(NoteTag(note_id=note.id, tag_id=tag.id))
    db.commit()

    note_id = str(note.id)
    response = client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 204

    db.refresh(tag)
    assert tag.usage_count == 0


def test_delete_note_cascade_highlight(client, auth_headers, db):
    """Pre-create Highlight, delete note → highlight cascade deleted."""
    from sqlmodel import select

    from fourdpocket.models.highlight import Highlight
    from fourdpocket.models.note import Note
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    user_uuid = user.id

    note = Note(user_id=user_uuid, content="Note with highlight")
    db.add(note)
    db.flush()

    highlight = Highlight(user_id=user_uuid, note_id=note.id, text="highlighted text")
    db.add(highlight)
    db.commit()

    highlight_id = highlight.id
    note_id = str(note.id)
    response = client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 204

    # Use exec+select instead of db.get to avoid session identity map issues
    remaining = db.exec(select(Highlight).where(Highlight.id == highlight_id)).first()
    assert remaining is None


def test_delete_note_cascade_collection(client, auth_headers, db):
    """Pre-add note to collection, delete → CollectionNote cascade deleted."""
    from sqlmodel import select

    from fourdpocket.models.collection import Collection
    from fourdpocket.models.collection_note import CollectionNote
    from fourdpocket.models.note import Note
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    user_uuid = user.id

    note = Note(user_id=user_uuid, content="Note in collection")
    db.add(note)
    db.flush()

    collection = Collection(user_id=user_uuid, name="Test Collection")
    db.add(collection)
    db.flush()

    db.add(CollectionNote(collection_id=collection.id, note_id=note.id))
    db.commit()

    note_id = str(note.id)
    response = client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 204

    remaining = db.exec(
        select(CollectionNote).where(CollectionNote.note_id == note.id)
    ).first()
    assert remaining is None


def test_add_tags_to_note(client, auth_headers):
    """POST /notes/{id}/tags adds tags."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note to tag"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.post(
        f"/api/v1/notes/{note_id}/tags",
        json={"tags": ["newtag"]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["tags_added"] == ["newtag"]


def test_add_tags_to_note_404(client, auth_headers):
    """POST /notes/{id}/tags with bad note_id → 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.post(
        f"/api/v1/notes/{fake_id}/tags",
        json={"tags": ["tag"]},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_remove_tag_from_note(client, auth_headers):
    """Remove a tag that is applied to a note."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note for tag removal"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    # Add a tag first
    client.post(
        f"/api/v1/notes/{note_id}/tags",
        json={"tags": ["removeme"]},
        headers=auth_headers,
    )

    # Get tag id
    tags_resp = client.get(f"/api/v1/notes/{note_id}/tags", headers=auth_headers)
    tag_id = tags_resp.json()[0]["id"]

    response = client.delete(
        f"/api/v1/notes/{note_id}/tags/{tag_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


def test_remove_tag_from_note_not_applied(client, auth_headers, db):
    """Tag not on note → 404."""
    from sqlmodel import select

    from fourdpocket.models.tag import Tag
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    user_uuid = user.id

    # Create a tag that is NOT linked to any note
    tag = Tag(user_id=user_uuid, name="orphan", slug="orphan")
    db.add(tag)
    db.commit()

    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note without orphan tag"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.delete(
        f"/api/v1/notes/{note_id}/tags/{tag.id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_list_note_tags(client, auth_headers):
    """GET /notes/{id}/tags returns list of tags."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Note to list tags"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    client.post(
        f"/api/v1/notes/{note_id}/tags",
        json={"tags": ["alpha", "beta"]},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/notes/{note_id}/tags", headers=auth_headers)
    assert response.status_code == 200
    tag_names = {t["name"] for t in response.json()}
    assert tag_names == {"alpha", "beta"}


def test_list_note_tags_404(client, auth_headers):
    """GET /notes/{id}/tags with bad note_id → 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.get(f"/api/v1/notes/{fake_id}/tags", headers=auth_headers)
    assert response.status_code == 404


def test_summarize_note(client, auth_headers, monkeypatch):
    """Patch summarize_note → returns summary."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Content to summarize"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "fourdpocket.ai.summarizer.summarize_note",
        lambda nid, db: "This is the summary",
    )

    response = client.post(f"/api/v1/notes/{note_id}/summarize", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["summary"] == "This is the summary"


def test_summarize_note_import_error(client, auth_headers, monkeypatch):
    """ImportError from summarizer → 501."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Content"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    def raise_import(*args, **kwargs):
        raise ImportError("no module")

    monkeypatch.setattr("fourdpocket.ai.summarizer.summarize_note", raise_import)

    response = client.post(f"/api/v1/notes/{note_id}/summarize", headers=auth_headers)
    assert response.status_code == 501


def test_summarize_note_exception(client, auth_headers, monkeypatch):
    """Exception from summarizer → 500."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Content"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    def raise_err(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr("fourdpocket.ai.summarizer.summarize_note", raise_err)

    response = client.post(f"/api/v1/notes/{note_id}/summarize", headers=auth_headers)
    assert response.status_code == 500


def test_generate_note_title(client, auth_headers, monkeypatch):
    """Patch generate_title → returns generated title."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "The cat sat on the mat and purred loudly"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "fourdpocket.ai.title_generator.generate_title",
        lambda content: "Generated Title",
    )

    response = client.post(f"/api/v1/notes/{note_id}/generate-title", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Generated Title"


def test_generate_note_title_no_content(client, auth_headers):
    """Empty content → 400."""
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": ""},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.post(f"/api/v1/notes/{note_id}/generate-title", headers=auth_headers)
    assert response.status_code == 400


def test_attach_note_item_404(client, auth_headers):
    """POST /items/{fake_id}/notes → 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.post(
        f"/api/v1/items/{fake_id}/notes",
        json={"content": "Attached note"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_list_item_notes_404(client, auth_headers):
    """GET /items/{fake_id}/notes → 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.get(f"/api/v1/items/{fake_id}/notes", headers=auth_headers)
    assert response.status_code == 404
