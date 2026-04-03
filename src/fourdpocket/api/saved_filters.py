"""Saved search filters (smart filters) endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.saved_filter import SavedFilter
from fourdpocket.models.user import User

router = APIRouter(prefix="/filters", tags=["filters"])


class FilterCreate(BaseModel):
    name: str
    query: str
    filters: dict = {}


class FilterUpdate(BaseModel):
    name: str | None = None
    query: str | None = None
    filters: dict | None = None


@router.get("")
def list_filters(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.exec(
        select(SavedFilter).where(SavedFilter.user_id == current_user.id).order_by(SavedFilter.created_at.desc())
    ).all()


@router.post("", status_code=201)
def create_filter(body: FilterCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    f = SavedFilter(user_id=current_user.id, name=body.name, query=body.query, filters=body.filters)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{filter_id}", status_code=204)
def delete_filter(filter_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    f = db.exec(select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.user_id == current_user.id)).first()
    if not f:
        raise HTTPException(status_code=404, detail="Filter not found")
    db.delete(f)
    db.commit()
