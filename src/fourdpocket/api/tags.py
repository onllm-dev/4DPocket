"""Tags CRUD endpoints."""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.tag import ItemTag, Tag, TagCreate, TagRead, TagUpdate
from fourdpocket.models.user import User

router = APIRouter(prefix="/tags", tags=["tags"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    tag_data: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slug = _slugify(tag_data.name)

    existing = db.exec(
        select(Tag).where(Tag.user_id == current_user.id, Tag.slug == slug)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")

    if tag_data.parent_id:
        parent = db.get(Tag, tag_data.parent_id)
        if not parent or parent.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Parent tag not found"
            )

    tag = Tag(
        user_id=current_user.id,
        name=tag_data.name,
        slug=slug,
        color=tag_data.color,
        parent_id=tag_data.parent_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.get("", response_model=list[TagRead])
def list_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    tags = db.exec(
        select(Tag)
        .where(Tag.user_id == current_user.id)
        .order_by(col(Tag.usage_count).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return tags


@router.get("/{tag_id}", response_model=TagRead)
def get_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: uuid.UUID,
    tag_data: TagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    update_dict = tag_data.model_dump(exclude_unset=True)
    if "name" in update_dict:
        update_dict["slug"] = _slugify(update_dict["name"])

    for key, value in update_dict.items():
        setattr(tag, key, value)

    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    # Remove all item-tag associations
    links = db.exec(select(ItemTag).where(ItemTag.tag_id == tag_id)).all()
    for link in links:
        db.delete(link)

    # Unparent child tags
    children = db.exec(select(Tag).where(Tag.parent_id == tag_id)).all()
    for child in children:
        child.parent_id = None
        db.add(child)

    db.delete(tag)
    db.commit()


@router.get("/suggestions/merge")
def suggest_tag_merges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest tags that could be merged (similar names)."""
    tags = db.exec(
        select(Tag).where(Tag.user_id == current_user.id).limit(500)
    ).all()
    suggestions = []

    from difflib import SequenceMatcher

    seen = set()
    for i, t1 in enumerate(tags):
        for t2 in tags[i + 1 :]:
            pair_key = (min(str(t1.id), str(t2.id)), max(str(t1.id), str(t2.id)))
            if pair_key in seen:
                continue
            ratio = SequenceMatcher(None, t1.name.lower(), t2.name.lower()).ratio()
            if 0.7 < ratio < 1.0:
                seen.add(pair_key)
                suggestions.append({
                    "tag_a": {"id": str(t1.id), "name": t1.name, "usage_count": t1.usage_count},
                    "tag_b": {"id": str(t2.id), "name": t2.name, "usage_count": t2.usage_count},
                    "similarity": round(ratio, 2),
                })

    suggestions.sort(key=lambda x: x["similarity"], reverse=True)
    return suggestions[:20]


class TagMergeRequest(BaseModel):
    source_tag_id: uuid.UUID
    target_tag_id: uuid.UUID


@router.post("/merge")
def merge_tags(
    body: TagMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge source tag into target tag. All items with source get target instead."""
    source = db.exec(
        select(Tag).where(Tag.id == body.source_tag_id, Tag.user_id == current_user.id)
    ).first()
    target = db.exec(
        select(Tag).where(Tag.id == body.target_tag_id, Tag.user_id == current_user.id)
    ).first()
    if not source or not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    source_links = db.exec(select(ItemTag).where(ItemTag.tag_id == source.id)).all()
    for link in source_links:
        existing = db.exec(
            select(ItemTag).where(ItemTag.item_id == link.item_id, ItemTag.tag_id == target.id)
        ).first()
        if not existing:
            db.add(ItemTag(item_id=link.item_id, tag_id=target.id, confidence=link.confidence))
        db.delete(link)

    target.usage_count = (target.usage_count or 0) + (source.usage_count or 0)
    db.delete(source)
    db.commit()
    return {"status": "merged", "target_tag": target.name, "items_moved": len(source_links)}


@router.get("/{tag_id}/items", response_model=list[ItemRead])
def list_tag_items(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    items = db.exec(
        select(KnowledgeItem)
        .join(ItemTag, ItemTag.item_id == KnowledgeItem.id)
        .where(ItemTag.tag_id == tag_id, KnowledgeItem.user_id == current_user.id)
        .order_by(col(KnowledgeItem.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return items
