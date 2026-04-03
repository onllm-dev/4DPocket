"""Dashboard statistics endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, func, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.collection import Collection
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.note import Note
from fourdpocket.models.tag import Tag
from fourdpocket.models.user import User

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_items = db.exec(
        select(func.count()).select_from(KnowledgeItem).where(KnowledgeItem.user_id == uid)
    ).one()

    items_this_week = db.exec(
        select(func.count()).select_from(KnowledgeItem).where(
            KnowledgeItem.user_id == uid,
            KnowledgeItem.created_at >= week_ago,
        )
    ).one()

    total_tags = db.exec(
        select(func.count()).select_from(Tag).where(Tag.user_id == uid)
    ).one()

    total_notes = db.exec(
        select(func.count()).select_from(Note).where(Note.user_id == uid)
    ).one()

    total_collections = db.exec(
        select(func.count()).select_from(Collection).where(Collection.user_id == uid)
    ).one()

    # Items by platform
    platform_counts = db.exec(
        select(KnowledgeItem.source_platform, func.count()).where(
            KnowledgeItem.user_id == uid
        ).group_by(KnowledgeItem.source_platform)
    ).all()

    # Top tags
    top_tags = db.exec(
        select(Tag.name, Tag.usage_count).where(
            Tag.user_id == uid
        ).order_by(col(Tag.usage_count).desc()).limit(10)
    ).all()

    return {
        "total_items": total_items,
        "items_this_week": items_this_week,
        "total_tags": total_tags,
        "total_notes": total_notes,
        "total_collections": total_collections,
        "items_by_platform": {str(p): c for p, c in platform_counts},
        "top_tags": [{"name": n, "count": c} for n, c in top_tags],
    }


@router.get("/users/{user_id}/public")
def get_public_profile(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
    }
