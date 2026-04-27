"""ItemLink endpoints for multi-link topic node items."""

import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_link import ItemLink, ItemLinkCreate, ItemLinkRead
from fourdpocket.models.user import User

router = APIRouter(prefix="/items", tags=["Item Links"])


@router.get("/{item_id}/links", response_model=list[ItemLinkRead])
def list_item_links(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List links for an item, ordered by position."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    links = db.exec(
        select(ItemLink)
        .where(ItemLink.item_id == item_id)
        .order_by(col(ItemLink.position).asc())
    ).all()
    return links


@router.post("/{item_id}/links", response_model=ItemLinkRead, status_code=status.HTTP_201_CREATED)
def create_item_link(
    item_id: uuid.UUID,
    body: ItemLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Add a link to an item. Auto-extracts domain from URL."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    domain = body.domain
    if not domain:
        parsed = urlparse(body.url)
        domain = parsed.netloc or None

    link = ItemLink(
        item_id=item_id,
        url=body.url,
        title=body.title,
        domain=domain,
        position=body.position,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{item_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_link(
    item_id: uuid.UUID,
    link_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Remove a link from an item."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    link = db.exec(
        select(ItemLink).where(ItemLink.id == link_id, ItemLink.item_id == item_id)
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()


class ReorderLinksRequest(BaseModel):
    link_ids: list[uuid.UUID]


@router.put("/{item_id}/links/reorder")
def reorder_item_links(
    item_id: uuid.UUID,
    data: ReorderLinksRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Reorder links by providing link_ids in desired order."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    for position, link_id in enumerate(data.link_ids):
        link = db.exec(
            select(ItemLink).where(ItemLink.id == link_id, ItemLink.item_id == item_id)
        ).first()
        if link:
            link.position = position
            db.add(link)

    db.commit()
    return {"status": "reordered"}
