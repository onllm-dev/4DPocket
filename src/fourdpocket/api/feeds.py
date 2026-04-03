"""Knowledge feed API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.user import User
from fourdpocket.sharing.feed_manager import get_feed_items, subscribe, unsubscribe

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.post("/subscribe/{user_id}", status_code=status.HTTP_201_CREATED)
def subscribe_to_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot subscribe to yourself",
        )
    publisher = db.get(User, user_id)
    if not publisher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    feed = subscribe(db=db, subscriber_id=current_user.id, publisher_id=user_id)
    return {"subscriber_id": str(current_user.id), "publisher_id": str(user_id), "id": str(feed.id)}


@router.delete("/unsubscribe/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_from_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = unsubscribe(db=db, subscriber_id=current_user.id, publisher_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )


@router.get("")
def get_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    items = get_feed_items(
        db=db, subscriber_id=current_user.id, limit=limit, offset=offset
    )
    # Enrich with owner display name
    result = []
    for item in items:
        owner = db.get(User, item.user_id)
        owner_name = (owner.display_name or owner.username) if owner else "Unknown"
        result.append({
            "id": str(item.id),
            "title": item.title,
            "url": item.url,
            "source_platform": item.source_platform,
            "item_type": item.item_type,
            "summary": item.summary,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "owner_display_name": owner_name,
        })
    return result
