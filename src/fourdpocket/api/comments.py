"""Comment API endpoints."""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.models.comment import Comment
from fourdpocket.models.user import User
from fourdpocket.sharing.permissions import can_view_item

router = APIRouter(prefix="/items/{item_id}/comments", tags=["comments"])


# --- Schemas ---


class CommentCreate(BaseModel):
    content: str

    model_config = {"extra": "forbid"}


class CommentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    item_id: uuid.UUID
    content: str
    created_at: datetime
    user_display_name: str | None = None

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.post("", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(
    item_id: uuid.UUID,
    body: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    if not can_view_item(db, current_user.id, item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    # Strip HTML tags from comment content for defense-in-depth
    clean_content = re.sub(r"<[^>]+>", "", body.content)
    comment = Comment(
        user_id=current_user.id,
        item_id=item_id,
        content=clean_content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("", response_model=list[CommentRead])
def list_comments(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    if not can_view_item(db, current_user.id, item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    rows = db.exec(
        select(Comment, User.display_name, User.username)
        .join(User, User.id == Comment.user_id)
        .where(Comment.item_id == item_id)
        .order_by(col(Comment.created_at).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    result = []
    for comment, display_name, username in rows:
        data = CommentRead.model_validate(comment)
        data.user_display_name = display_name or username or "Unknown"
        result.append(data)
    return result


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    item_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    comment = db.get(Comment, comment_id)
    if not comment or comment.item_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete another user's comment",
        )
    db.delete(comment)
    db.commit()
