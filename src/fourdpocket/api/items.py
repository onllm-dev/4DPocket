"""Knowledge item CRUD endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlmodel import Session, select, func, col

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.base import ItemType, SourcePlatform
from fourdpocket.models.item import ItemCreate, ItemRead, ItemUpdate, KnowledgeItem
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.models.user import User

router = APIRouter(prefix="/items", tags=["items"])


def _detect_platform(url: str) -> SourcePlatform:
    """Detect source platform from URL."""
    url_lower = url.lower()
    patterns = {
        SourcePlatform.youtube: ["youtube.com", "youtu.be"],
        SourcePlatform.reddit: ["reddit.com", "redd.it"],
        SourcePlatform.github: ["github.com", "gist.github.com"],
        SourcePlatform.twitter: ["twitter.com", "x.com"],
        SourcePlatform.instagram: ["instagram.com"],
        SourcePlatform.threads: ["threads.net"],
        SourcePlatform.tiktok: ["tiktok.com"],
        SourcePlatform.hackernews: ["news.ycombinator.com"],
        SourcePlatform.stackoverflow: ["stackoverflow.com"],
        SourcePlatform.mastodon: [],  # detected by ActivityPub patterns
        SourcePlatform.substack: ["substack.com"],
        SourcePlatform.medium: ["medium.com"],
        SourcePlatform.linkedin: ["linkedin.com"],
        SourcePlatform.spotify: ["open.spotify.com"],
    }
    for platform, domains in patterns.items():
        if any(domain in url_lower for domain in domains):
            return platform
    return SourcePlatform.generic


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    item_data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    platform = item_data.source_platform
    if item_data.url and platform == SourcePlatform.generic:
        platform = _detect_platform(item_data.url)

    item = KnowledgeItem(
        user_id=current_user.id,
        url=item_data.url,
        title=item_data.title,
        description=item_data.description,
        content=item_data.content,
        item_type=item_data.item_type,
        source_platform=platform,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Index for search
    try:
        from fourdpocket.search.indexer import SearchIndexer

        indexer = SearchIndexer(db)
        indexer.index_item(item)
    except Exception:
        pass  # Search indexing is best-effort

    return item


@router.get("", response_model=list[ItemRead])
def list_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    item_type: ItemType | None = None,
    source_platform: SourcePlatform | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    tag_id: uuid.UUID | None = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|title|updated_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    query = select(KnowledgeItem).where(KnowledgeItem.user_id == current_user.id)

    if item_type is not None:
        query = query.where(KnowledgeItem.item_type == item_type)
    if source_platform is not None:
        query = query.where(KnowledgeItem.source_platform == source_platform)
    if is_favorite is not None:
        query = query.where(KnowledgeItem.is_favorite == is_favorite)
    if is_archived is not None:
        query = query.where(KnowledgeItem.is_archived == is_archived)
    if tag_id is not None:
        query = query.join(ItemTag, ItemTag.item_id == KnowledgeItem.id).where(
            ItemTag.tag_id == tag_id
        )

    sort_col = getattr(KnowledgeItem, sort_by)
    if sort_order == "desc":
        query = query.order_by(col(sort_col).desc())
    else:
        query = query.order_by(col(sort_col).asc())

    query = query.offset(offset).limit(limit)
    items = db.exec(query).all()
    return items


@router.get("/{item_id}", response_model=ItemRead)
def get_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: uuid.UUID,
    item_data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    update_dict = item_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Delete associated tags
    tags = db.exec(select(ItemTag).where(ItemTag.item_id == item_id)).all()
    for tag_link in tags:
        db.delete(tag_link)

    db.delete(item)
    db.commit()


@router.post("/{item_id}/tags", status_code=status.HTTP_201_CREATED)
def add_tag_to_item(
    item_id: uuid.UUID,
    tag_id: uuid.UUID = Query(...),
    confidence: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    existing = db.exec(
        select(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id == tag_id)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already applied")

    link = ItemTag(item_id=item_id, tag_id=tag_id, confidence=confidence)
    db.add(link)

    tag.usage_count += 1
    db.add(tag)

    db.commit()
    return {"item_id": str(item_id), "tag_id": str(tag_id), "confidence": confidence}


@router.delete("/{item_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_item(
    item_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    link = db.exec(
        select(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id == tag_id)
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not applied")

    tag = db.get(Tag, tag_id)
    if tag and tag.usage_count > 0:
        tag.usage_count -= 1
        db.add(tag)

    db.delete(link)
    db.commit()
