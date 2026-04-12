"""Tool-level tests — exercise the pure Python functions in fourdpocket.mcp.tools."""

import uuid

import pytest
from sqlmodel import Session

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
