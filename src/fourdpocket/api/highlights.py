"""Highlights & annotations endpoints."""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.models.highlight import Highlight
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.note import Note
from fourdpocket.models.user import User

router = APIRouter(prefix="/highlights", tags=["highlights"])


_ALLOWED_POSITION_KEYS = {"start", "end", "paragraph", "sentence"}


class HighlightCreate(BaseModel):
    item_id: uuid.UUID | None = None
    note_id: uuid.UUID | None = None
    text: str
    note: str | None = None
    color: str = "yellow"
    position: dict | None = None

    model_config = {"extra": "forbid"}

    def model_post_init(self, __context):
        if not self.item_id and not self.note_id:
            raise ValueError("Either item_id or note_id must be provided")
        if self.item_id and self.note_id:
            raise ValueError("Only one of item_id or note_id should be provided")
        if self.position is not None:
            for key in self.position:
                if key not in _ALLOWED_POSITION_KEYS:
                    raise ValueError(f"position key '{key}' not allowed")
                if not isinstance(self.position[key], (int, float)):
                    raise ValueError(f"position['{key}'] must be a number")


class HighlightUpdate(BaseModel):
    note: str | None = None
    color: str | None = None


@router.get("")
def list_highlights(
    item_id: uuid.UUID | None = None,
    note_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all highlights, optionally filtered by item or note."""
    query = select(Highlight).where(Highlight.user_id == current_user.id)
    if item_id:
        query = query.where(Highlight.item_id == item_id)
    if note_id:
        query = query.where(Highlight.note_id == note_id)
    query = query.order_by(Highlight.created_at.desc()).limit(limit).offset(offset)
    return db.exec(query).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_highlight(
    body: HighlightCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    # Verify ownership of the target item/note
    if body.item_id:
        item = db.get(KnowledgeItem, body.item_id)
        if not item or item.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Item not found")
    if body.note_id:
        note = db.get(Note, body.note_id)
        if not note or note.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Note not found")

    def _strip(s):
        return re.sub(r"<[^>]+>", "", s) if s else s

    highlight = Highlight(
        user_id=current_user.id,
        item_id=body.item_id,
        note_id=body.note_id,
        text=_strip(body.text),
        note=_strip(body.note),
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
    _: None = Depends(require_pat_editor),
):
    h = db.exec(select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == current_user.id)).first()
    if not h:
        raise HTTPException(status_code=404, detail="Highlight not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "note" and value:
            value = re.sub(r"<[^>]+>", "", value)
        setattr(h, field, value)
    db.commit()
    db.refresh(h)
    return h


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_highlight(
    highlight_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    h = db.exec(select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == current_user.id)).first()
    if not h:
        raise HTTPException(status_code=404, detail="Highlight not found")
    db.delete(h)
    db.commit()


@router.get("/search")
def search_highlights(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search within highlights text and notes."""
    query = select(Highlight).where(
        Highlight.user_id == current_user.id,
        (Highlight.text.contains(q)) | (Highlight.note.contains(q)),
    ).limit(limit).offset(offset)
    return db.exec(query).all()
