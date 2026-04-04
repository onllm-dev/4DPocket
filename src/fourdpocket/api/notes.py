"""Notes CRUD endpoints."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlmodel import Session, col, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.note import Note, NoteCreate, NoteRead, NoteUpdate
from fourdpocket.models.note_tag import NoteTag
from fourdpocket.models.tag import Tag, TagRead
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
    try:
        from fourdpocket.search.sqlite_fts import index_note
        index_note(db, note)
    except Exception:
        pass  # Non-critical
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


@router.get("/search", response_model=list[NoteRead])
def search_notes(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Search notes using FTS5 full-text search with LIKE fallback."""
    from fourdpocket.config import get_settings
    from fourdpocket.search.sqlite_fts import search_notes as fts_search_notes

    settings = get_settings()
    if settings.search.backend == "sqlite" and settings.database.url.startswith("sqlite"):
        results = fts_search_notes(db, q, current_user.id, limit=limit, offset=offset)
        if results:
            note_ids = [uuid.UUID(r["note_id"]) for r in results]
            notes = db.exec(
                select(Note).where(Note.id.in_(note_ids), Note.user_id == current_user.id)
            ).all()
            note_map = {n.id: n for n in notes}
            return [note_map[nid] for nid in note_ids if nid in note_map]

    # Fallback to LIKE for non-SQLite backends or empty FTS results
    query = (
        select(Note)
        .where(
            Note.user_id == current_user.id,
            (Note.title.contains(q)) | (Note.content.contains(q)),
        )
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
    tags = update_dict.pop("tags", None)
    for key, value in update_dict.items():
        setattr(note, key, value)
    note.updated_at = datetime.now(timezone.utc)

    db.add(note)
    db.commit()
    db.refresh(note)

    # Handle tags if provided
    if tags is not None:
        _sync_note_tags(note.id, tags, current_user.id, db)

    try:
        from fourdpocket.search.sqlite_fts import index_note
        index_note(db, note)
    except Exception:
        pass  # Non-critical

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

    # Cascade delete associated data and decrement tag usage counts
    from fourdpocket.models.note_tag import NoteTag
    from fourdpocket.models.highlight import Highlight
    from fourdpocket.models.collection_note import CollectionNote
    from fourdpocket.models.tag import Tag

    for row in db.exec(select(NoteTag).where(NoteTag.note_id == note_id)).all():
        tag = db.get(Tag, row.tag_id)
        if tag and tag.usage_count > 0:
            tag.usage_count = tag.usage_count - 1
            db.add(tag)
        db.delete(row)
    for row in db.exec(select(Highlight).where(Highlight.note_id == note_id)).all():
        db.delete(row)
    for row in db.exec(select(CollectionNote).where(CollectionNote.note_id == note_id)).all():
        db.delete(row)

    # Remove from FTS index
    try:
        from fourdpocket.config import get_settings as _get_settings
        _s = _get_settings()
        if _s.search.backend == "sqlite" and _s.database.url.startswith("sqlite"):
            from sqlalchemy import text as _text
            db.exec(_text("DELETE FROM notes_fts WHERE note_id = :nid"), params={"nid": str(note_id)})
    except Exception:
        pass

    db.delete(note)
    db.commit()


def _slugify(text: str) -> str:
    """Simple slugify for tag names."""
    return text.strip().lower().replace(" ", "-")


def _sync_note_tags(
    note_id: uuid.UUID,
    tag_names: list[str],
    user_id: uuid.UUID,
    db: Session,
) -> None:
    """Find-or-create tags and link them to a note."""
    for name in tag_names:
        slug = _slugify(name)
        tag = db.exec(
            select(Tag).where(Tag.user_id == user_id, Tag.slug == slug)
        ).first()
        if not tag:
            tag = Tag(user_id=user_id, name=name.strip(), slug=slug)
            db.add(tag)
            db.flush()

        existing = db.exec(
            select(NoteTag).where(NoteTag.note_id == note_id, NoteTag.tag_id == tag.id)
        ).first()
        if not existing:
            db.add(NoteTag(note_id=note_id, tag_id=tag.id))
            tag.usage_count += 1
            db.add(tag)

    db.commit()


class AddTagsRequest(BaseModel):
    tags: list[str]


@router.post("/{note_id}/tags", status_code=status.HTTP_201_CREATED)
def add_tags_to_note(
    note_id: uuid.UUID,
    body: AddTagsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add tags to a note. Creates tags if they don't exist."""
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    _sync_note_tags(note_id, body.tags, current_user.id, db)
    return {"status": "ok", "tags_added": body.tags}


@router.delete("/{note_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_note(
    note_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a tag link from a note."""
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    link = db.exec(
        select(NoteTag).where(NoteTag.note_id == note_id, NoteTag.tag_id == tag_id)
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not applied")

    tag = db.get(Tag, tag_id)
    if tag and tag.usage_count > 0:
        tag.usage_count -= 1
        db.add(tag)

    db.delete(link)
    db.commit()


@router.get("/{note_id}/tags", response_model=list[TagRead])
def list_note_tags(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tags for a note."""
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    tags = db.exec(
        select(Tag)
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .where(NoteTag.note_id == note_id)
    ).all()
    return tags


@router.post("/{note_id}/summarize")
def summarize_note_endpoint(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger AI summarization for a note."""
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    try:
        from fourdpocket.ai.summarizer import summarize_note

        summary = summarize_note(note_id, db)
        return {"status": "ok", "summary": summary}
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="AI summarizer not available",
        )
    except Exception as e:
        logger.exception("Summarization failed for note %s: %s", note_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Summarization failed",
        )


@router.post("/{note_id}/generate-title")
def generate_note_title(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an AI title for a note based on its content."""
    note = db.get(Note, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if not note.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note has no content to generate title from",
        )

    try:
        from fourdpocket.ai.title_generator import generate_title

        title = generate_title(note.content)
        note.title = title
        note.updated_at = datetime.now(timezone.utc)
        db.add(note)
        db.commit()
        db.refresh(note)
        return {"status": "ok", "title": title}
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="AI title generator not available",
        )
    except Exception as e:
        logger.exception("Title generation failed for note %s: %s", note_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Title generation failed",
        )


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
