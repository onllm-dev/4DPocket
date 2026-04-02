"""Notes CRUD endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select, col

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.note import Note, NoteCreate, NoteRead, NoteUpdate
from fourdpocket.models.user import User

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if note_data.item_id:
        item = db.get(KnowledgeItem, note_data.item_id)
        if not item or item.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    note = Note(
        user_id=current_user.id,
        item_id=note_data.item_id,
        title=note_data.title,
        content=note_data.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=list[NoteRead])
def list_notes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = (
        select(Note)
        .where(Note.user_id == current_user.id)
        .order_by(col(Note.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return db.exec(query).all()


@router.get("/{note_id}", response_model=NoteRead)
def get_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    note_id: uuid.UUID,
    note_data: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    update_dict = note_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(note, key, value)
    note.updated_at = datetime.now(timezone.utc)

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    db.delete(note)
    db.commit()


# Item-attached notes endpoints
item_notes_router = APIRouter(tags=["notes"])


@item_notes_router.post(
    "/items/{item_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED
)
def attach_note_to_item(
    item_id: uuid.UUID,
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    note = Note(
        user_id=current_user.id,
        item_id=item_id,
        title=note_data.title,
        content=note_data.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@item_notes_router.get("/items/{item_id}/notes", response_model=list[NoteRead])
def list_item_notes(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    notes = db.exec(
        select(Note)
        .where(Note.item_id == item_id, Note.user_id == current_user.id)
        .order_by(col(Note.created_at).desc())
    ).all()
    return notes
