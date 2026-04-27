"""Highlights & annotations endpoints."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.ai.sanitizer import strip_html
from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.models.highlight import Highlight
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.note import Note
from fourdpocket.models.user import User
from fourdpocket.sharing.permissions import can_view_item

router = APIRouter(prefix="/highlights", tags=["Highlights"])


_ALLOWED_POSITION_KEYS = {"start", "end", "paragraph", "sentence"}


class HighlightCreate(BaseModel):
    item_id: uuid.UUID | None = None
    note_id: uuid.UUID | None = None
    text: str
    note: str | None = None
    color: Literal["yellow", "green", "blue", "red", "purple"] = "yellow"
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
            if "start" in self.position and self.position["start"] < 0:
                raise ValueError("position['start'] must be >= 0")
            if "start" in self.position and "end" in self.position:
                if self.position["start"] > self.position["end"]:
                    raise ValueError("position['start'] must be <= position['end']")


class HighlightUpdate(BaseModel):
    note: str | None = None
    color: Literal["yellow", "green", "blue", "red", "purple"] | None = None


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
    if item_id and not can_view_item(db, current_user.id, item_id):
        raise HTTPException(status_code=404, detail="Item not found")
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

    highlight = Highlight(
        user_id=current_user.id,
        item_id=body.item_id,
        note_id=body.note_id,
        text=strip_html(body.text),
        note=strip_html(body.note),
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
            value = strip_html(value)
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
    """Search within highlights text and notes.

    Uses tokenized LIKE: splits query on whitespace and ANDs each token so that
    multi-word queries and partial matches (e.g. "server" matching "servers") work.
    TODO: replace with FTS5 virtual table (highlights_fts) for full parity with notes search.
    """
    tokens = q.split()
    filters = [Highlight.user_id == current_user.id]
    for token in tokens:
        filters.append(
            (Highlight.text.contains(token)) | (Highlight.note.contains(token))
        )
    query = select(Highlight).where(*filters).limit(limit).offset(offset)
    return db.exec(query).all()
