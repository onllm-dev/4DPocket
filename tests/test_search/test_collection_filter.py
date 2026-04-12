"""Search ACL — collection-scoped filtering."""

import uuid

from sqlmodel import Session

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.base import SearchFilters


def _add_item(db: Session, user_id: uuid.UUID, title: str, content: str) -> KnowledgeItem:
    item = KnowledgeItem(
        user_id=user_id,
        title=title,
        content=content,
        item_type="note",
        source_platform="generic",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _make_user(db: Session, email: str = "u@example.com") -> User:
    user = User(
        email=email,
        username=email.split("@")[0],
        password_hash="x",
        display_name="Test",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_search_applies_allowed_item_ids(db):
    from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend
    from fourdpocket.search.service import SearchService
    from fourdpocket.search.sqlite_fts import index_item

    user = _make_user(db)
    keep = _add_item(db, user.id, "Keep", "python programming")
    drop = _add_item(db, user.id, "Drop", "python programming")

    index_item(db, keep)
    index_item(db, drop)

    class _Nil:
        def upsert_item(self, *a, **k): pass
        def upsert_chunk(self, *a, **k): pass
        def delete_item(self, *a, **k): pass
        def search(self, *a, **k): return []

    service = SearchService(keyword=SqliteFtsBackend(), vector=_Nil())

    # No filter — both hit
    unfiltered = service.search(db, "python", user.id)
    ids_unfiltered = {str(r.item_id) for r in unfiltered}
    assert str(keep.id) in ids_unfiltered
    assert str(drop.id) in ids_unfiltered

    # ACL — only keep
    filters = SearchFilters(allowed_item_ids={keep.id})
    filtered = service.search(db, "python", user.id, filters=filters)
    ids_filtered = {str(r.item_id) for r in filtered}
    assert ids_filtered == {str(keep.id)}


def test_search_applies_collection_id(db):
    from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend
    from fourdpocket.search.service import SearchService
    from fourdpocket.search.sqlite_fts import index_item

    user = _make_user(db, email="c@example.com")
    a = _add_item(db, user.id, "Alpha", "shared keyword")
    b = _add_item(db, user.id, "Beta", "shared keyword")

    for it in (a, b):
        index_item(db, it)

    coll = Collection(user_id=user.id, name="My Coll")
    db.add(coll)
    db.commit()
    db.refresh(coll)

    db.add(CollectionItem(collection_id=coll.id, item_id=a.id, position=0))
    db.commit()

    class _Nil:
        def upsert_item(self, *a, **k): pass
        def upsert_chunk(self, *a, **k): pass
        def delete_item(self, *a, **k): pass
        def search(self, *a, **k): return []

    service = SearchService(keyword=SqliteFtsBackend(), vector=_Nil())

    filters = SearchFilters(collection_id=coll.id)
    results = service.search(db, "shared", user.id, filters=filters)
    ids = {str(r.item_id) for r in results}
    assert ids == {str(a.id)}
