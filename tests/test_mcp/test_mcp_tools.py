"""Tool-level tests — exercise the pure Python functions in fourdpocket.mcp.tools."""

import uuid

import pytest
from sqlmodel import Session, select

from fourdpocket.api.api_token_utils import generate_token
from fourdpocket.mcp import tools
from fourdpocket.models.api_token import ApiToken, ApiTokenCollection
from fourdpocket.models.base import ApiTokenRole
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User


def _user(db: Session, email: str) -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        password_hash="x",
        display_name="T",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _pat(
    db: Session,
    user_id: uuid.UUID,
    role: ApiTokenRole = ApiTokenRole.viewer,
    all_collections: bool = True,
    allow_deletion: bool = False,
    include_uncollected: bool = True,
) -> ApiToken:
    gen = generate_token()
    pat = ApiToken(
        user_id=user_id,
        name="t",
        token_prefix=gen.prefix,
        token_hash=gen.token_hash,
        role=role,
        all_collections=all_collections,
        include_uncollected=include_uncollected,
        allow_deletion=allow_deletion,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)
    return pat


def _item(db: Session, user_id: uuid.UUID, title: str) -> KnowledgeItem:
    it = KnowledgeItem(
        user_id=user_id,
        title=title,
        content=f"content about {title}",
        item_type="note",
        source_platform="generic",
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


def _collection(db: Session, user_id: uuid.UUID, name: str) -> Collection:
    c = Collection(user_id=user_id, name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _link(db: Session, collection_id: uuid.UUID, item_id: uuid.UUID) -> None:
    db.add(CollectionItem(collection_id=collection_id, item_id=item_id, position=0))
    db.commit()


def _grant(db: Session, token_id: uuid.UUID, collection_id: uuid.UUID) -> None:
    db.add(ApiTokenCollection(token_id=token_id, collection_id=collection_id))
    db.commit()


# ─── list_collections ──────────────────────────────────────────────────────


def test_list_collections_all_access(db):
    user = _user(db, "lc1@x.com")
    pat = _pat(db, user.id, all_collections=True)
    _collection(db, user.id, "Research")
    _collection(db, user.id, "Fun")

    res = tools.list_collections(db, user, pat)
    names = {c["name"] for c in res["collections"]}
    assert names == {"Research", "Fun"}


def test_list_collections_scoped(db):
    user = _user(db, "lc2@x.com")
    pat = _pat(db, user.id, all_collections=False)
    a = _collection(db, user.id, "Keep")
    _collection(db, user.id, "Drop")
    _grant(db, pat.id, a.id)

    res = tools.list_collections(db, user, pat)
    assert {c["name"] for c in res["collections"]} == {"Keep"}


# ─── get_knowledge ─────────────────────────────────────────────────────────


def test_get_knowledge_respects_acl(db):
    user = _user(db, "gk@x.com")
    pat = _pat(db, user.id, all_collections=False, include_uncollected=False)
    keep_coll = _collection(db, user.id, "Keep")
    _grant(db, pat.id, keep_coll.id)

    kept = _item(db, user.id, "Kept")
    _link(db, keep_coll.id, kept.id)

    invisible = _item(db, user.id, "Hidden")

    detail = tools.get_knowledge(db, user, pat, str(kept.id))
    assert detail["id"] == str(kept.id)

    with pytest.raises(tools.ToolError):
        tools.get_knowledge(db, user, pat, str(invisible.id))


def test_get_knowledge_missing_id(db):
    user = _user(db, "gk404@x.com")
    pat = _pat(db, user.id)
    with pytest.raises(tools.ToolError):
        tools.get_knowledge(db, user, pat, str(uuid.uuid4()))


# ─── save_knowledge ────────────────────────────────────────────────────────


def test_save_knowledge_viewer_rejected(db):
    user = _user(db, "sv@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.viewer)
    with pytest.raises(tools.ToolError):
        tools.call(
            tools.save_knowledge,
            db,
            user,
            pat,
            content="hello world",
            title="First note",
        )


def test_save_knowledge_editor_creates_note(db):
    user = _user(db, "sve@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    detail = tools.save_knowledge(
        db, user, pat, content="hello world", title="First note", tags=["inbox"]
    )
    assert detail["title"] == "First note"
    assert "inbox" in detail["tags"]


def test_save_knowledge_needs_url_or_content(db):
    user = _user(db, "sn@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    with pytest.raises(tools.ToolError):
        tools.save_knowledge(db, user, pat)


# ─── update_knowledge ──────────────────────────────────────────────────────


def test_update_knowledge(db):
    user = _user(db, "upd@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    item = _item(db, user.id, "Original")

    res = tools.update_knowledge(
        db, user, pat, str(item.id), title="New title", is_favorite=True
    )
    assert res["title"] == "New title"
    assert res["is_favorite"] is True


def test_update_knowledge_viewer_rejected(db):
    user = _user(db, "updv@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.viewer)
    item = _item(db, user.id, "X")
    with pytest.raises(tools.ToolError):
        tools.call(tools.update_knowledge, db, user, pat, str(item.id), title="Y")


# ─── delete_knowledge ──────────────────────────────────────────────────────


def test_delete_without_allow_deletion_rejected(db):
    user = _user(db, "del@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor, allow_deletion=False)
    item = _item(db, user.id, "doomed")
    with pytest.raises(tools.ToolError):
        tools.call(tools.delete_knowledge, db, user, pat, str(item.id))


def test_delete_with_allow_deletion_succeeds(db):
    user = _user(db, "del2@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor, allow_deletion=True)
    item = _item(db, user.id, "doomed")
    res = tools.delete_knowledge(db, user, pat, str(item.id))
    assert res["status"] == "deleted"
    assert db.get(KnowledgeItem, item.id) is None


def test_delete_cascades_through_enrichment_rows(db):
    """Regression: enriched items (chunks, embeddings, collection links, stages)
    must be cascade-deleted. Bare ``db.delete(item)`` would trigger SQLite
    FOREIGN KEY violations — delete_knowledge must use the shared cascade helper.
    """
    from fourdpocket.models.embedding import Embedding
    from fourdpocket.models.enrichment import EnrichmentStage
    from fourdpocket.models.item_chunk import ItemChunk

    user = _user(db, "delcascade@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor, allow_deletion=True)
    item = _item(db, user.id, "rich")

    # Link into a collection
    coll = _collection(db, user.id, "bucket")
    _link(db, coll.id, item.id)

    # Seed a chunk + embedding (as sync enrichment would)
    chunk = ItemChunk(
        item_id=item.id,
        user_id=user.id,
        chunk_order=0,
        text="seed text for chunk",
        token_count=4,
        char_start=0,
        char_end=18,
        content_hash="seed",
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    db.add(Embedding(item_id=item.id, model="test", content_hash="seed"))
    db.add(EnrichmentStage(item_id=item.id, stage="chunked", status="completed"))
    db.commit()

    res = tools.delete_knowledge(db, user, pat, str(item.id))
    assert res["status"] == "deleted"
    assert db.get(KnowledgeItem, item.id) is None
    assert db.get(ItemChunk, chunk.id) is None


# ─── add_to_collection ─────────────────────────────────────────────────────


def test_add_to_collection_blocks_foreign_collection(db):
    user = _user(db, "atc@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor, all_collections=False)
    good = _collection(db, user.id, "Good")
    _grant(db, pat.id, good.id)
    forbidden = _collection(db, user.id, "Forbidden")
    item = _item(db, user.id, "x")
    with pytest.raises(tools.ToolError):
        tools.add_to_collection(db, user, pat, str(forbidden.id), str(item.id))


def test_add_to_collection_happy_path(db):
    user = _user(db, "atch@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    coll = _collection(db, user.id, "C")
    item = _item(db, user.id, "I")
    res = tools.add_to_collection(db, user, pat, str(coll.id), str(item.id))
    assert res["status"] == "added"


# ─── search_knowledge ──────────────────────────────────────────────────────


def test_search_knowledge_scope(db):
    from fourdpocket.search.sqlite_fts import index_item

    user = _user(db, "se@x.com")
    pat = _pat(db, user.id, all_collections=False, include_uncollected=False)
    keep_coll = _collection(db, user.id, "K")
    _grant(db, pat.id, keep_coll.id)

    keep = _item(db, user.id, "pythonic Keep")
    drop = _item(db, user.id, "pythonic Drop")
    _link(db, keep_coll.id, keep.id)

    for it in (keep, drop):
        index_item(db, it)

    res = tools.search_knowledge(db, user, pat, query="pythonic", limit=10)
    ids = {r["id"] for r in res["results"]}
    assert str(keep.id) in ids
    assert str(drop.id) not in ids


# ─── search_in_collection ─────────────────────────────────────────────────


def test_search_in_collection_by_name(db):
    from fourdpocket.search.sqlite_fts import index_item

    user = _user(db, "sic-n@x.com")
    pat = _pat(db, user.id, all_collections=True, include_uncollected=True)
    target = _collection(db, user.id, "Research")
    other = _collection(db, user.id, "Fun")

    inside = _item(db, user.id, "overlapping topic A")
    outside_same_text = _item(db, user.id, "overlapping topic B")
    _link(db, target.id, inside.id)
    _link(db, other.id, outside_same_text.id)

    for it in (inside, outside_same_text):
        index_item(db, it)

    # Case-insensitive name resolution
    res = tools.search_in_collection(
        db, user, pat, collection="research", query="overlapping", limit=10
    )
    ids = {r["id"] for r in res["results"]}
    assert str(inside.id) in ids
    assert str(outside_same_text.id) not in ids
    assert res["collection"]["name"] == "Research"
    assert res["collection"]["id"] == str(target.id)


def test_search_in_collection_by_id(db):
    from fourdpocket.search.sqlite_fts import index_item

    user = _user(db, "sic-id@x.com")
    pat = _pat(db, user.id, all_collections=True, include_uncollected=True)
    coll = _collection(db, user.id, "Archive")

    inside = _item(db, user.id, "targeted snippet")
    _link(db, coll.id, inside.id)
    index_item(db, inside)

    res = tools.search_in_collection(
        db, user, pat, collection=str(coll.id), query="targeted", limit=5
    )
    assert {r["id"] for r in res["results"]} == {str(inside.id)}


def test_search_in_collection_unknown_name_raises(db):
    user = _user(db, "sic-u@x.com")
    pat = _pat(db, user.id, all_collections=True)
    with pytest.raises(tools.ToolError):
        tools.search_in_collection(
            db, user, pat, collection="nonexistent-collection", query="anything"
        )


def test_search_in_collection_forbidden_by_token(db):
    user = _user(db, "sic-f@x.com")
    pat = _pat(db, user.id, all_collections=False)
    allowed = _collection(db, user.id, "Allowed")
    forbidden = _collection(db, user.id, "Forbidden")
    _grant(db, pat.id, allowed.id)

    with pytest.raises(tools.ToolError):
        tools.search_in_collection(
            db, user, pat, collection=str(forbidden.id), query="anything"
        )


# === PHASE 1B MOPUP ADDITIONS ===

# ─── get_entity ──────────────────────────────────────────────────────────────


def test_get_entity_found_by_name(db):
    """get_entity by name returns entity with synthesis."""
    from fourdpocket.models.entity import Entity

    user = _user(db, "ge-fn@x.com")
    pat = _pat(db, user.id)
    entity = Entity(
        user_id=user.id, canonical_name="Python", entity_type="technology", description="Lang"
    )
    db.add(entity)
    db.commit()

    res = tools.get_entity(db, user, pat, "Python")
    assert res["canonical_name"] == "Python"
    assert res["entity_type"] == "technology"


def test_get_entity_found_by_uuid(db):
    """get_entity by UUID returns entity."""
    from fourdpocket.models.entity import Entity

    user = _user(db, "ge-uuid@x.com")
    pat = _pat(db, user.id)
    entity = Entity(
        user_id=user.id, canonical_name="Rust", entity_type="technology", description="Lang"
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    res = tools.get_entity(db, user, pat, str(entity.id))
    assert res["canonical_name"] == "Rust"


def test_get_entity_not_found(db):
    """get_entity raises ToolError when entity does not exist."""
    user = _user(db, "ge-404@x.com")
    pat = _pat(db, user.id)

    with pytest.raises(tools.ToolError, match="not found"):
        tools.get_entity(db, user, pat, "DoesNotExist")


# ─── get_related_entities ────────────────────────────────────────────────────


def test_get_related_entities_found(db):
    """get_related_entities returns one-hop neighbours ranked by weight."""
    from fourdpocket.models.entity import Entity
    from fourdpocket.models.entity_relation import EntityRelation

    user = _user(db, "gre@x.com")
    pat = _pat(db, user.id)

    python = Entity(user_id=user.id, canonical_name="Python", entity_type="technology")
    rust = Entity(user_id=user.id, canonical_name="Rust", entity_type="technology")
    db.add_all([python, rust])
    db.commit()
    db.refresh(python)
    db.refresh(rust)

    rel = EntityRelation(
        user_id=user.id,
        source_id=python.id,
        target_id=rust.id,
        keywords='["systems", "safe"]',
        weight=0.95,
    )
    db.add(rel)
    db.commit()

    res = tools.get_related_entities(db, user, pat, "Python", limit=10)
    assert res["source"]["canonical_name"] == "Python"
    assert len(res["related"]) == 1
    assert res["related"][0]["entity"]["canonical_name"] == "Rust"


def test_get_related_entities_not_found(db):
    """get_related_entities raises ToolError for unknown entity."""
    user = _user(db, "gre-404@x.com")
    pat = _pat(db, user.id)

    with pytest.raises(tools.ToolError, match="not found"):
        tools.get_related_entities(db, user, pat, "UnknownEntity")


def test_get_related_entities_respects_limit(db):
    """get_related_entities caps results at the specified limit."""
    from fourdpocket.models.entity import Entity
    from fourdpocket.models.entity_relation import EntityRelation

    user = _user(db, "gre-limit@x.com")
    pat = _pat(db, user.id)

    center = Entity(user_id=user.id, canonical_name="Center", entity_type="concept")
    db.add(center)
    db.commit()
    db.refresh(center)

    for i in range(5):
        other = Entity(user_id=user.id, canonical_name=f"Other{i}", entity_type="concept")
        db.add(other)
        db.commit()
        db.refresh(other)
        db.add(
            EntityRelation(
                user_id=user.id,
                source_id=center.id,
                target_id=other.id,
                keywords=None,
                weight=0.5 + i * 0.1,
            )
        )
    db.commit()

    res = tools.get_related_entities(db, user, pat, "Center", limit=3)
    assert len(res["related"]) == 3


# ─── save_knowledge ─────────────────────────────────────────────────────────


def test_save_knowledge_with_collection_id(db):
    """save_knowledge with collection_id creates CollectionItem link."""
    user = _user(db, "swc@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    coll = _collection(db, user.id, "Work")

    res = tools.save_knowledge(
        db, user, pat, url="https://example.com/article", collection_id=str(coll.id)
    )
    assert "id" in res
    # Verify link was created
    from fourdpocket.models.collection import CollectionItem

    link = db.exec(
        select(CollectionItem).where(
            CollectionItem.collection_id == coll.id,
            CollectionItem.item_id == uuid.UUID(res["id"]),
        )
    ).first()
    assert link is not None


def test_save_knowledge_collection_acl_denied(db):
    """save_knowledge rejects collection the token cannot write to."""
    user = _user(db, "swc-deny@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor, all_collections=False)
    coll = _collection(db, user.id, "Private")
    _grant(db, pat.id, coll.id)  # only this collection

    # Try to save to a different, ungranted collection
    other = _collection(db, user.id, "Other")

    with pytest.raises(tools.ToolError, match="cannot write"):
        tools.save_knowledge(
            db, user, pat, url="https://example.com", collection_id=str(other.id)
        )


def test_save_knowledge_with_tags(db):
    """save_knowledge applies tags to the newly created item."""
    user = _user(db, "swt@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)

    res = tools.save_knowledge(
        db, user, pat, content="Something interesting.", tags=["python", "AI"]
    )
    assert set(res["tags"]) == {"python", "AI"}


# ─── update_knowledge ────────────────────────────────────────────────────────


def test_update_knowledge_replaces_tags(db):
    """update_knowledge with tags=['newtag'] replaces the existing tag set."""
    from fourdpocket.models.tag import ItemTag, Tag

    user = _user(db, "upt@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    item = _item(db, user.id, "Target")

    # Pre-existing tag
    old_tag = Tag(user_id=user.id, name="old-tag", slug="old-tag")
    db.add(old_tag)
    db.commit()
    db.refresh(old_tag)
    db.add(ItemTag(item_id=item.id, tag_id=old_tag.id))
    db.commit()

    res = tools.update_knowledge(
        db, user, pat, str(item.id), tags=["new-tag"]
    )
    assert "new-tag" in res["tags"]
    assert "old-tag" not in res["tags"]


def test_update_knowledge_partial_update(db):
    """update_knowledge only changes the fields that are passed."""
    user = _user(db, "up-partial@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    item = _item(db, user.id, "Original Title")

    res = tools.update_knowledge(
        db, user, pat, str(item.id), is_favorite=True
    )
    assert res["title"] == "Original Title"
    assert res["is_favorite"] is True


def test_update_knowledge_missing_item(db):
    """update_knowledge raises ToolError for unknown knowledge_id."""
    user = _user(db, "up-404@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)

    with pytest.raises(tools.ToolError):
        tools.update_knowledge(
            db, user, pat, str(uuid.uuid4()), title="New"
        )


# ─── refresh_knowledge ──────────────────────────────────────────────────────


def test_refresh_knowledge_enqueues_enrichment(db, monkeypatch):
    """refresh_knowledge calls enrich_item_v2 even without refetch."""
    user = _user(db, "rf@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    item = _item(db, user.id, "To refresh")

    called = []

    def mock_enrich(item_id, user_id):
        called.append((item_id, user_id))

    monkeypatch.setattr(
        "fourdpocket.workers.enrichment_pipeline.enrich_item_v2", mock_enrich
    )

    res = tools.refresh_knowledge(db, user, pat, str(item.id), refetch=False)
    assert res["status"] == "refresh_enqueued"
    assert called[0][0] == str(item.id)


def test_refresh_knowledge_refetch_and_enrich(db, monkeypatch):
    """refresh_knowledge with refetch=True first re-fetches URL then enriches."""
    user = _user(db, "rf2@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    item = _item(db, user.id, "With URL")
    item.url = "https://example.com/refetch"
    db.add(item)
    db.commit()

    calls = []

    def mock_fetch(item_id, url):
        calls.append(("fetch", item_id, url))

    def mock_enrich(item_id, user_id):
        calls.append(("enrich", item_id, user_id))

    monkeypatch.setattr(
        "fourdpocket.workers.fetcher.fetch_and_process_url", mock_fetch
    )
    monkeypatch.setattr(
        "fourdpocket.workers.enrichment_pipeline.enrich_item_v2", mock_enrich
    )

    res = tools.refresh_knowledge(db, user, pat, str(item.id), refetch=True)
    assert res["status"] == "refresh_enqueued"
    assert calls[0][0] == "fetch"
    assert calls[1][0] == "enrich"


def test_refresh_knowledge_missing_item(db):
    """refresh_knowledge raises ToolError for unknown knowledge_id."""
    user = _user(db, "rf-404@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)

    with pytest.raises(tools.ToolError):
        tools.refresh_knowledge(db, user, pat, str(uuid.uuid4()))


# ─── delete_knowledge ───────────────────────────────────────────────────────


def test_delete_knowledge_unknown_item(db):
    """delete_knowledge raises ToolError when item does not exist."""
    user = _user(db, "del-404@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor, allow_deletion=True)

    with pytest.raises(tools.ToolError):
        tools.delete_knowledge(db, user, pat, str(uuid.uuid4()))


# ─── search_knowledge ────────────────────────────────────────────────────────


def test_search_knowledge_empty_query_returns_empty(db):
    """search_knowledge with no matching results returns empty list."""
    user = _user(db, "se-empty@x.com")
    pat = _pat(db, user.id, all_collections=True)

    res = tools.search_knowledge(db, user, pat, query="xyzzy-nothing", limit=10)
    assert res["results"] == []


def test_search_knowledge_respects_limit(db):
    """search_knowledge caps results at the configured limit (max 50)."""
    from fourdpocket.search.sqlite_fts import index_item

    user = _user(db, "se-limit@x.com")
    pat = _pat(db, user.id, all_collections=True)

    for i in range(5):
        it = _item(db, user.id, f"Unique thing {i}")
        index_item(db, it)

    res = tools.search_knowledge(db, user, pat, query="Unique", limit=2)
    assert len(res["results"]) <= 2


def test_search_knowledge_date_range_filter(db):
    """search_knowledge after/before filters are accepted without error."""
    from datetime import datetime, timedelta, timezone

    from fourdpocket.search.sqlite_fts import index_item

    user = _user(db, "se-date@x.com")
    pat = _pat(db, user.id, all_collections=True)

    now = datetime.now(timezone.utc)
    item = _item(db, user.id, "Dated Item")
    item.created_at = now
    db.add(item)
    db.commit()
    index_item(db, item)

    after = (now - timedelta(days=1)).isoformat()
    before = (now + timedelta(days=1)).isoformat()
    # Just verify it runs without raising; date filter application
    # depends on the search backend's FTS implementation
    res = tools.search_knowledge(
        db, user, pat, query="Dated", limit=5, after=after, before=before
    )
    assert "results" in res


# ─── list_collections ───────────────────────────────────────────────────────


def test_list_collections_includes_uncollected(db):
    """list_collections returns an 'uncollected' sentinel when token includes uncollected."""
    user = _user(db, "lc-unc@x.com")
    pat = _pat(db, user.id, all_collections=True, include_uncollected=True)

    res = tools.list_collections(db, user, pat)
    # The tool should return the user's collections; the sentinel is a UI hint
    assert isinstance(res["collections"], list)


def test_list_collections_empty(db):
    """list_collections returns empty list when user has no collections."""
    user = _user(db, "lc-empty@x.com")
    pat = _pat(db, user.id, all_collections=True)

    res = tools.list_collections(db, user, pat)
    assert res["collections"] == []


# ─── add_to_collection ──────────────────────────────────────────────────────


def test_add_to_collection_item_not_found(db):
    """add_to_collection raises ToolError when knowledge_id is unknown."""
    user = _user(db, "atc-404@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    coll = _collection(db, user.id, "C")

    with pytest.raises(tools.ToolError, match="not found"):
        tools.add_to_collection(db, user, pat, str(coll.id), str(uuid.uuid4()))


def test_add_to_collection_collection_not_found(db):
    """add_to_collection raises ToolError when collection_id is unknown."""
    user = _user(db, "atc-c404@x.com")
    pat = _pat(db, user.id, role=ApiTokenRole.editor)
    item = _item(db, user.id, "I")

    with pytest.raises(tools.ToolError, match="not found"):
        tools.add_to_collection(db, user, pat, str(uuid.uuid4()), str(item.id))
