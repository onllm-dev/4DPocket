"""MCP tool implementations.

Each tool is a sync Python function that takes the current ``User`` + ``ApiToken``
+ ``Session`` and returns a JSON-serialisable dict. This keeps the logic
independent of the MCP transport and trivially unit-testable.

Shared access-control rules:
- Every tool consults the PAT's collection ACL via
  ``token_allowed_item_ids`` to produce an item-id allow-set.
- Write tools require the PAT role be ``editor``.
- ``delete_knowledge`` additionally requires the PAT ``allow_deletion`` flag.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from fourdpocket.api.api_token_utils import (
    require_deletion,
    require_editor,
    token_allowed_item_ids,
    token_can_access_collection,
    token_can_access_item,
)
from fourdpocket.mcp.serializers import (
    collection_brief,
    entity_brief,
    entity_with_synthesis,
    knowledge_brief,
    knowledge_detail,
    related_entity,
    resolve_entity_ref,
)
from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.base import ItemType, SourcePlatform
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.entity import Entity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.base import SearchFilters


class ToolError(RuntimeError):
    """Raised when a tool call is denied or invalid — surfaced to MCP clients."""


def _raise(msg: str) -> None:
    raise ToolError(msg)


def _item_visible(
    db: Session, token: ApiToken, user: User, item_id: uuid.UUID
) -> KnowledgeItem:
    item = db.get(KnowledgeItem, item_id)
    if item is None or item.user_id != user.id:
        _raise("Knowledge item not found.")
    if not token_can_access_item(db, token, item_id, user.id):
        _raise("Token does not have access to this item.")
    return item


# ─── Read tools ────────────────────────────────────────────────────────────


def search_knowledge(
    db: Session,
    user: User,
    token: ApiToken,
    query: str,
    limit: int = 20,
    item_type: str | None = None,
    tags: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    collection_id: str | None = None,
) -> dict[str, Any]:
    """Hybrid search across the user's knowledge base, scoped by token ACL."""
    from fourdpocket.search import get_search_service

    service = get_search_service()

    filters = SearchFilters(
        item_type=item_type,
        tags=tags,
        after=after,
        before=before,
        collection_id=uuid.UUID(collection_id) if collection_id else None,
        allowed_item_ids=token_allowed_item_ids(db, token, user.id),
    )

    if collection_id is not None and not token_can_access_collection(
        db, token, uuid.UUID(collection_id)
    ):
        _raise("Token cannot access the requested collection.")

    results = service.search(
        db, query, user.id, filters=filters, limit=max(1, min(limit, 50))
    )
    # Fetch full brief for each result
    if not results:
        return {"results": []}

    ids = [uuid.UUID(str(r.item_id)) for r in results]
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id.in_(ids), KnowledgeItem.user_id == user.id
        )
    ).all()
    by_id = {i.id: i for i in items}
    briefs = []
    for r in results:
        item = by_id.get(uuid.UUID(str(r.item_id)))
        if item is None:
            continue
        payload = knowledge_brief(item)
        payload["score"] = round(r.score, 4)
        payload["snippet"] = r.content_snippet or r.title_snippet
        briefs.append(payload)
    return {"results": briefs}


def get_knowledge(
    db: Session, user: User, token: ApiToken, knowledge_id: str
) -> dict[str, Any]:
    """Fetch full detail for a single knowledge item."""
    item = _item_visible(db, token, user, uuid.UUID(knowledge_id))
    return knowledge_detail(db, item)


def _resolve_collection(
    db: Session, user: User, token: ApiToken, ref: str
) -> Collection:
    """Resolve a collection reference (UUID or case-insensitive name) for this user + token.

    LLMs usually know the collection *name*, not its id — so accept either.
    Raises ``ToolError`` if the collection is missing or the PAT can't access it.
    """
    coll: Collection | None = None
    try:
        coll = db.get(Collection, uuid.UUID(ref))
    except (ValueError, TypeError):
        coll = None

    if coll is None:
        coll = db.exec(
            select(Collection).where(
                Collection.user_id == user.id,
                col(Collection.name).ilike(ref),
            )
        ).first()

    if coll is None or coll.user_id != user.id:
        _raise(f"Collection not found: {ref!r}.")
    if not token_can_access_collection(db, token, coll.id):
        _raise("Token cannot access the requested collection.")
    return coll


def search_in_collection(
    db: Session,
    user: User,
    token: ApiToken,
    collection: str,
    query: str,
    limit: int = 20,
    item_type: str | None = None,
    tags: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
) -> dict[str, Any]:
    """Search scoped to a single collection, identified by UUID or name."""
    coll = _resolve_collection(db, user, token, collection)
    payload = search_knowledge(
        db,
        user,
        token,
        query=query,
        limit=limit,
        item_type=item_type,
        tags=tags,
        after=after,
        before=before,
        collection_id=str(coll.id),
    )
    payload["collection"] = {"id": str(coll.id), "name": coll.name}
    return payload


def list_collections(
    db: Session, user: User, token: ApiToken
) -> dict[str, Any]:
    """List collections the token has access to (includes a virtual 'uncollected' bucket when applicable)."""
    query = select(Collection).where(Collection.user_id == user.id)
    if not token.all_collections:
        from fourdpocket.models.api_token import ApiTokenCollection

        allowed = db.exec(
            select(ApiTokenCollection.collection_id).where(
                ApiTokenCollection.token_id == token.id
            )
        ).all()
        if not allowed:
            return {"collections": []}
        query = query.where(col(Collection.id).in_(list(allowed)))

    rows = db.exec(query.order_by(col(Collection.created_at).desc())).all()
    return {"collections": [collection_brief(db, c) for c in rows]}


def get_entity(
    db: Session, user: User, token: ApiToken, id_or_name: str
) -> dict[str, Any]:
    """Fetch entity detail including synthesis and aliases."""
    entity = resolve_entity_ref(db, user.id, id_or_name)
    if entity is None:
        _raise("Entity not found.")
    return entity_with_synthesis(db, entity)


def get_related_entities(
    db: Session,
    user: User,
    token: ApiToken,
    id_or_name: str,
    limit: int = 10,
) -> dict[str, Any]:
    """One-hop associative trail from the entity graph."""
    entity = resolve_entity_ref(db, user.id, id_or_name)
    if entity is None:
        _raise("Entity not found.")

    rels = db.exec(
        select(EntityRelation)
        .where(
            EntityRelation.user_id == user.id,
            (EntityRelation.source_id == entity.id)
            | (EntityRelation.target_id == entity.id),
        )
        .order_by(col(EntityRelation.weight).desc())
        .limit(max(1, min(limit, 50)))
    ).all()

    items = []
    for r in rels:
        other_id = r.target_id if r.source_id == entity.id else r.source_id
        other = db.get(Entity, other_id)
        if other is None:
            continue
        items.append(related_entity(other, r))
    return {"source": entity_brief(entity), "related": items}


# ─── Write tools (editor role) ─────────────────────────────────────────────


def save_knowledge(
    db: Session,
    user: User,
    token: ApiToken,
    url: str | None = None,
    content: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    collection_id: str | None = None,
) -> dict[str, Any]:
    """Persist a new knowledge item. Either ``url`` or ``content`` must be provided.

    URLs trigger the fetcher pipeline; content creates a note immediately.
    """
    require_editor(token)

    if not url and not content:
        _raise("Provide either url or content.")

    if collection_id is not None and not token_can_access_collection(
        db, token, uuid.UUID(collection_id)
    ):
        _raise("Token cannot write to the requested collection.")

    item = KnowledgeItem(
        user_id=user.id,
        url=url,
        content=content,
        title=title,
        item_type=ItemType.url if url else ItemType.note,
        source_platform=SourcePlatform.generic,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Link to collection if requested
    if collection_id:
        cid = uuid.UUID(collection_id)
        if db.get(Collection, cid) and db.exec(
            select(Collection).where(
                Collection.id == cid, Collection.user_id == user.id
            )
        ).first():
            existing = db.exec(
                select(CollectionItem).where(
                    CollectionItem.collection_id == cid,
                    CollectionItem.item_id == item.id,
                )
            ).first()
            if existing is None:
                db.add(
                    CollectionItem(
                        collection_id=cid, item_id=item.id, position=0
                    )
                )
                db.commit()

    # Apply tags inline
    if tags:
        from fourdpocket.models.tag import ItemTag, Tag

        for raw in tags[:30]:
            name = str(raw).strip()[:64]
            if not name:
                continue
            slug = name.lower().replace(" ", "-")
            tag = db.exec(
                select(Tag).where(Tag.user_id == user.id, Tag.slug == slug)
            ).first()
            if tag is None:
                tag = Tag(user_id=user.id, name=name, slug=slug, usage_count=1)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            else:
                tag.usage_count = (tag.usage_count or 0) + 1
                db.add(tag)
            link = db.exec(
                select(ItemTag).where(
                    ItemTag.item_id == item.id, ItemTag.tag_id == tag.id
                )
            ).first()
            if link is None:
                db.add(ItemTag(item_id=item.id, tag_id=tag.id))
        db.commit()

    # Trigger enrichment (sync fallback if Huey off)
    try:
        from fourdpocket.workers.enrichment_pipeline import enrich_item_v2

        enrich_item_v2(str(item.id), str(user.id))
    except Exception:  # nosec - enrichment is best-effort
        pass

    return knowledge_detail(db, item)


def update_knowledge(
    db: Session,
    user: User,
    token: ApiToken,
    knowledge_id: str,
    title: str | None = None,
    content: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
) -> dict[str, Any]:
    """Edit an existing item. Only provided fields are changed."""
    require_editor(token)

    item = _item_visible(db, token, user, uuid.UUID(knowledge_id))

    if title is not None:
        item.title = title
    if content is not None:
        item.content = content
    if description is not None:
        item.description = description
    if is_favorite is not None:
        item.is_favorite = bool(is_favorite)
    if is_archived is not None:
        item.is_archived = bool(is_archived)

    db.add(item)
    db.commit()
    db.refresh(item)

    if tags is not None:
        from fourdpocket.models.tag import ItemTag, Tag

        # Replace tags entirely when caller passes a tags array.
        existing_links = db.exec(
            select(ItemTag).where(ItemTag.item_id == item.id)
        ).all()
        for link in existing_links:
            db.delete(link)
        for raw in tags[:30]:
            name = str(raw).strip()[:64]
            if not name:
                continue
            slug = name.lower().replace(" ", "-")
            tag = db.exec(
                select(Tag).where(Tag.user_id == user.id, Tag.slug == slug)
            ).first()
            if tag is None:
                tag = Tag(user_id=user.id, name=name, slug=slug, usage_count=1)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            db.add(ItemTag(item_id=item.id, tag_id=tag.id))
        db.commit()

    return knowledge_detail(db, item)


def refresh_knowledge(
    db: Session,
    user: User,
    token: ApiToken,
    knowledge_id: str,
    refetch: bool = False,
) -> dict[str, Any]:
    """Re-run enrichment on an item. Pass ``refetch=True`` to also re-download URL content."""
    require_editor(token)

    item = _item_visible(db, token, user, uuid.UUID(knowledge_id))

    if refetch and item.url:
        try:
            from fourdpocket.workers.fetcher import fetch_and_process_url

            fetch_and_process_url(str(item.id), item.url)
        except Exception:  # nosec - best-effort
            pass

    try:
        from fourdpocket.workers.enrichment_pipeline import enrich_item_v2

        enrich_item_v2(str(item.id), str(user.id))
    except Exception:  # nosec
        pass

    return {"status": "refresh_enqueued", "knowledge_id": str(item.id)}


def delete_knowledge(
    db: Session, user: User, token: ApiToken, knowledge_id: str
) -> dict[str, Any]:
    """Hard-delete an item. Requires PAT ``allow_deletion`` flag."""
    from fourdpocket.api.items import cascade_delete_item

    require_deletion(token)

    item = _item_visible(db, token, user, uuid.UUID(knowledge_id))
    deleted_id = str(item.id)
    cascade_delete_item(db, item)
    db.commit()
    return {"status": "deleted", "knowledge_id": deleted_id}


def add_to_collection(
    db: Session,
    user: User,
    token: ApiToken,
    collection_id: str,
    knowledge_id: str,
) -> dict[str, Any]:
    """Link an existing knowledge item into a collection."""
    require_editor(token)

    cid = uuid.UUID(collection_id)
    item = _item_visible(db, token, user, uuid.UUID(knowledge_id))

    coll = db.get(Collection, cid)
    if coll is None or coll.user_id != user.id:
        _raise("Collection not found.")
    if not token_can_access_collection(db, token, cid):
        _raise("Token cannot write to the requested collection.")

    existing = db.exec(
        select(CollectionItem).where(
            CollectionItem.collection_id == cid,
            CollectionItem.item_id == item.id,
        )
    ).first()
    if existing is None:
        # Append at the tail
        max_pos_row = db.exec(
            select(CollectionItem)
            .where(CollectionItem.collection_id == cid)
            .order_by(col(CollectionItem.position).desc())
        ).first()
        position = (max_pos_row.position + 1) if max_pos_row else 0
        db.add(
            CollectionItem(
                collection_id=cid, item_id=item.id, position=position
            )
        )
        db.commit()

    return {
        "status": "added",
        "collection_id": collection_id,
        "knowledge_id": knowledge_id,
    }


# ─── HTTPException → ToolError adapter ────────────────────────────────────


def call(fn, *args, **kwargs):
    """Invoke a tool function, converting FastAPI HTTPExceptions to ToolErrors.

    Keeps error surface consistent from the MCP perspective regardless of
    whether the underlying auth helper raises ``HTTPException`` or ``ToolError``.
    """
    try:
        return fn(*args, **kwargs)
    except HTTPException as e:
        raise ToolError(str(e.detail)) from e
