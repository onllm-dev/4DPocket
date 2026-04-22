"""Collections CRUD endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from fourdpocket.api.deps import (
    get_current_user,
    get_current_user_pat_aware,
    get_db,
    require_pat_editor,
)
from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.collection import (
    Collection,
    CollectionCreate,
    CollectionItem,
    CollectionRead,
    CollectionUpdate,
)
from fourdpocket.models.collection_note import CollectionNote
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.note import Note, NoteRead
from fourdpocket.models.user import User

router = APIRouter(prefix="/collections", tags=["collections"])


def _check_pat_collection_scope(
    db: Session,
    pat: ApiToken | None,
    collection_id: uuid.UUID,
) -> None:
    """If the request is PAT-authenticated, verify the PAT covers this collection."""
    if pat is None:
        return
    from fourdpocket.api.api_token_utils import token_can_access_collection

    if not token_can_access_collection(db, pat, collection_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PAT does not have access to this collection",
        )


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(
    data: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    collection = Collection(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        icon=data.icon,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


@router.get("", response_model=list[CollectionRead])
def list_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    collections = db.exec(
        select(Collection)
        .where(Collection.user_id == current_user.id)
        .order_by(col(Collection.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return collections


@router.get("/{collection_id}", response_model=CollectionRead)
def get_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )
    return collection


@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(
    collection_id: uuid.UUID,
    data: CollectionUpdate,
    db: Session = Depends(get_db),
    auth: tuple[User, ApiToken | None] = Depends(get_current_user_pat_aware),
    _: None = Depends(require_pat_editor),
):
    current_user, pat = auth
    _check_pat_collection_scope(db, pat, collection_id)
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(collection, key, value)
    collection.updated_at = datetime.now(timezone.utc)

    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: tuple[User, ApiToken | None] = Depends(get_current_user_pat_aware),
    _: None = Depends(require_pat_editor),
):
    current_user, pat = auth
    _check_pat_collection_scope(db, pat, collection_id)
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    # Cascade: remove CollectionItem, CollectionNote, and Share references
    from fourdpocket.models.collection_note import CollectionNote
    from fourdpocket.models.share import Share, ShareRecipient

    for link in db.exec(select(CollectionItem).where(CollectionItem.collection_id == collection_id)).all():
        db.delete(link)
    for link in db.exec(select(CollectionNote).where(CollectionNote.collection_id == collection_id)).all():
        db.delete(link)
    for share in db.exec(select(Share).where(Share.collection_id == collection_id)).all():
        for sr in db.exec(select(ShareRecipient).where(ShareRecipient.share_id == share.id)).all():
            db.delete(sr)
        db.delete(share)

    db.delete(collection)
    db.commit()


class AddItemsRequest(BaseModel):
    item_ids: list[uuid.UUID]


@router.post("/{collection_id}/items", status_code=status.HTTP_201_CREATED)
def add_items_to_collection(
    collection_id: uuid.UUID,
    data: AddItemsRequest,
    db: Session = Depends(get_db),
    auth: tuple[User, ApiToken | None] = Depends(get_current_user_pat_aware),
    _: None = Depends(require_pat_editor),
):
    current_user, pat = auth
    _check_pat_collection_scope(db, pat, collection_id)
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    # Get current max position
    existing = db.exec(
        select(CollectionItem)
        .where(CollectionItem.collection_id == collection_id)
        .order_by(col(CollectionItem.position).desc())
    ).first()
    position = (existing.position + 1) if existing else 0

    added = []
    for item_id in data.item_ids:
        item = db.get(KnowledgeItem, item_id)
        if not item or item.user_id != current_user.id:
            continue

        exists = db.exec(
            select(CollectionItem).where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.item_id == item_id,
            )
        ).first()
        if exists:
            continue

        link = CollectionItem(
            collection_id=collection_id,
            item_id=item_id,
            position=position,
        )
        db.add(link)
        added.append(str(item_id))
        position += 1

    db.commit()
    return {"added": added}


@router.delete(
    "/{collection_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_item_from_collection(
    collection_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: tuple[User, ApiToken | None] = Depends(get_current_user_pat_aware),
    _: None = Depends(require_pat_editor),
):
    current_user, pat = auth
    _check_pat_collection_scope(db, pat, collection_id)
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    link = db.exec(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.item_id == item_id,
        )
    ).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not in collection"
        )

    db.delete(link)
    db.commit()


class ReorderItem(BaseModel):
    item_id: uuid.UUID
    position: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


@router.put("/{collection_id}/items/reorder")
def reorder_collection_items(
    collection_id: uuid.UUID,
    data: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    for reorder_item in data.items:
        link = db.exec(
            select(CollectionItem).where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.item_id == reorder_item.item_id,
            )
        ).first()
        if link:
            link.position = reorder_item.position
            db.add(link)

    db.commit()
    return {"status": "reordered"}


@router.get("/{collection_id}/smart-items")
def get_smart_collection_items(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get items matching a smart collection's query."""
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    if not collection.is_smart or not collection.smart_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not a smart collection"
        )

    from fourdpocket.search import get_search_service

    service = get_search_service()
    results = service.search(
        db, collection.smart_query, current_user.id, limit=limit, offset=offset,
    )
    return [r.to_dict() if hasattr(r, "to_dict") else r for r in results]


@router.get("/{collection_id}/items", response_model=list[ItemRead])
def list_collection_items(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    items = db.exec(
        select(KnowledgeItem)
        .join(CollectionItem, CollectionItem.item_id == KnowledgeItem.id)
        .where(CollectionItem.collection_id == collection_id)
        .order_by(col(CollectionItem.position).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return items


@router.get("/{collection_id}/rss")
def get_collection_rss(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an RSS feed XML for a collection."""
    from fastapi.responses import Response

    collection = db.exec(
        select(Collection).where(
            Collection.id == collection_id, Collection.user_id == current_user.id
        )
    ).first()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    # Get collection items
    coll_items = db.exec(
        select(CollectionItem).where(CollectionItem.collection_id == collection.id)
        .order_by(CollectionItem.position)
    ).all()
    item_ids = [ci.item_id for ci in coll_items]
    items = (
        db.exec(select(KnowledgeItem).where(KnowledgeItem.id.in_(item_ids))).all()
        if item_ids
        else []
    )

    # Build RSS XML
    rss_items = ""
    for item in items:
        pub_date = (
            item.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
            if item.created_at
            else ""
        )
        rss_items += f"""    <item>
      <title><![CDATA[{item.title or "Untitled"}]]></title>
      <link>{item.url or ""}</link>
      <description><![CDATA[{item.summary or item.description or ""}]]></description>
      <pubDate>{pub_date}</pubDate>
      <guid>{item.id}</guid>
    </item>\n"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{collection.name}</title>
    <description>{collection.description or ""}</description>
    <lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}
</lastBuildDate>
{rss_items}  </channel>
</rss>"""

    return Response(content=xml, media_type="application/rss+xml")


# --- Collection Notes endpoints ---


class AddNotesRequest(BaseModel):
    note_ids: list[uuid.UUID]


@router.post("/{collection_id}/notes", status_code=status.HTTP_201_CREATED)
def add_notes_to_collection(
    collection_id: uuid.UUID,
    data: AddNotesRequest,
    db: Session = Depends(get_db),
    auth: tuple[User, ApiToken | None] = Depends(get_current_user_pat_aware),
    _: None = Depends(require_pat_editor),
):
    """Add notes to a collection."""
    current_user, pat = auth
    _check_pat_collection_scope(db, pat, collection_id)
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    # Get current max position
    existing = db.exec(
        select(CollectionNote)
        .where(CollectionNote.collection_id == collection_id)
        .order_by(col(CollectionNote.position).desc())
    ).first()
    position = (existing.position + 1) if existing else 0

    added = []
    for note_id in data.note_ids:
        note = db.get(Note, note_id)
        if not note or note.user_id != current_user.id:
            continue

        exists = db.exec(
            select(CollectionNote).where(
                CollectionNote.collection_id == collection_id,
                CollectionNote.note_id == note_id,
            )
        ).first()
        if exists:
            continue

        link = CollectionNote(
            collection_id=collection_id,
            note_id=note_id,
            position=position,
        )
        db.add(link)
        added.append(str(note_id))
        position += 1

    db.commit()
    return {"added": added}


@router.delete(
    "/{collection_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_note_from_collection(
    collection_id: uuid.UUID,
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: tuple[User, ApiToken | None] = Depends(get_current_user_pat_aware),
    _: None = Depends(require_pat_editor),
):
    """Remove a note from a collection."""
    current_user, pat = auth
    _check_pat_collection_scope(db, pat, collection_id)
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    link = db.exec(
        select(CollectionNote).where(
            CollectionNote.collection_id == collection_id,
            CollectionNote.note_id == note_id,
        )
    ).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not in collection"
        )

    db.delete(link)
    db.commit()


@router.get("/{collection_id}/notes", response_model=list[NoteRead])
def list_collection_notes(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List notes in a collection, ordered by position."""
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    notes = db.exec(
        select(Note)
        .join(CollectionNote, CollectionNote.note_id == Note.id)
        .where(CollectionNote.collection_id == collection_id)
        .order_by(col(CollectionNote.position).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return notes


# --- Item collections convenience endpoint ---

item_collections_router = APIRouter(tags=["collections"])


@item_collections_router.get("/items/{item_id}/collections", response_model=list[CollectionRead])
def list_item_collections(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List collections an item belongs to."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    collections = db.exec(
        select(Collection)
        .join(CollectionItem, CollectionItem.collection_id == Collection.id)
        .where(CollectionItem.item_id == item_id)
    ).all()
    return collections
