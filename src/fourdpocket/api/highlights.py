"""Highlights & annotations endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.highlight import Highlight
from fourdpocket.models.user import User

router = APIRouter(prefix="/highlights", tags=["highlights"])


class HighlightCreate(BaseModel):
    item_id: uuid.UUID
    text: str
    note: str | None = None
    color: str = "yellow"
    position: dict | None = None


class HighlightUpdate(BaseModel):
    note: str | None = None
    color: str | None = None


@router.get("")
def list_highlights(
    item_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all highlights, optionally filtered by item."""
    query = select(Highlight).where(Highlight.user_id == current_user.id)
    if item_id:
        query = query.where(Highlight.item_id == item_id)
    query = query.order_by(Highlight.created_at.desc())
    return db.exec(query).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_highlight(
    body: HighlightCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    highlight = Highlight(
        user_id=current_user.id,
        item_id=body.item_id,
        text=body.text,
        note=body.note,
        color=body.color,
        position=body.position,
    )
    db.add(highlight)
    db.commit()
    db.refresh(highlight)
    return highlight


@router.patch("/{highlight_id}")
def update_highlight(
    highlight_id: uuid.UUID,
    body: HighlightUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    h = db.exec(select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == current_user.id)).first()
    if not h:
        raise HTTPException(status_code=404, detail="Highlight not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(h, field, value)
    db.commit()
    db.refresh(h)
    return h


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_highlight(
    highlight_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    h = db.exec(select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == current_user.id)).first()
    if not h:
        raise HTTPException(status_code=404, detail="Highlight not found")
    db.delete(h)
    db.commit()


@router.get("/search")
def search_highlights(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search within highlights text and notes."""
    query = select(Highlight).where(
        Highlight.user_id == current_user.id,
        (Highlight.text.contains(q)) | (Highlight.note.contains(q)),
    )
    return db.exec(query).all()
