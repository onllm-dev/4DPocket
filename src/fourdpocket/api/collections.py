"""Collections CRUD endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.collection import (
    Collection,
    CollectionCreate,
    CollectionItem,
    CollectionRead,
    CollectionUpdate,
)
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.user import User

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(
    data: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
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
    current_user: User = Depends(get_current_user),
):
    collection = db.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )

    links = db.exec(
        select(CollectionItem).where(CollectionItem.collection_id == collection_id)
    ).all()
    for link in links:
        db.delete(link)

    db.delete(collection)
    db.commit()


class AddItemsRequest(BaseModel):
    item_ids: list[uuid.UUID]


@router.post("/{collection_id}/items", status_code=status.HTTP_201_CREATED)
def add_items_to_collection(
    collection_id: uuid.UUID,
    data: AddItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    current_user: User = Depends(get_current_user),
):
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

    from fourdpocket.search.sqlite_fts import search

    results = search(
        db, collection.smart_query, user_id=current_user.id, limit=limit, offset=offset
    )
    return results


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
