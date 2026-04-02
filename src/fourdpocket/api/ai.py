"""AI feature endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.config import get_settings
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status():
    """Check AI provider availability."""
    settings = get_settings()
    return {
        "chat_provider": settings.ai.chat_provider,
        "embedding_provider": settings.ai.embedding_provider,
        "auto_tag": settings.ai.auto_tag,
        "auto_summarize": settings.ai.auto_summarize,
        "tag_confidence_threshold": settings.ai.tag_confidence_threshold,
        "tag_suggestion_threshold": settings.ai.tag_suggestion_threshold,
    }


@router.post("/items/{item_id}/enrich")
def enrich_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger AI enrichment (re-tag, re-summarize) for an item."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    try:
        from fourdpocket.workers.ai_enrichment import enrich_item as enrich_task

        enrich_task(str(item_id), str(current_user.id))
        return {"status": "queued", "item_id": str(item_id)}
    except Exception:
        # Run synchronously if Huey isn't available
        from fourdpocket.ai.summarizer import summarize_item
        from fourdpocket.ai.tagger import auto_tag_item

        tags = auto_tag_item(
            item_id=item.id,
            user_id=current_user.id,
            title=item.title or "",
            content=item.content,
            description=item.description,
            db=db,
        )
        summary = summarize_item(item.id, db)

        return {
            "status": "completed",
            "item_id": str(item_id),
            "tags": len(tags),
            "summary": bool(summary),
        }
