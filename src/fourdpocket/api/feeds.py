"""Knowledge feed API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import ItemRead
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


@router.get("", response_model=list[ItemRead])
def get_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    items = get_feed_items(
        db=db, subscriber_id=current_user.id, limit=limit, offset=offset
    )
    return items
