"""Tags CRUD endpoints."""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select, col

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.tag import ItemTag, Tag, TagCreate, TagRead, TagUpdate
from fourdpocket.models.user import User

router = APIRouter(prefix="/tags", tags=["tags"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s/-]", "", slug)
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
):
    tags = db.exec(
        select(Tag)
        .where(Tag.user_id == current_user.id)
        .order_by(col(Tag.usage_count).desc())
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
