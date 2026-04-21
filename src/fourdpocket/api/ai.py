"""AI feature endpoints."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

logger = logging.getLogger(__name__)
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.config import get_settings
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.tag import ItemTag
from fourdpocket.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status(_: User = Depends(get_current_user)):
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
    _: None = Depends(require_pat_editor),
):
    """Trigger AI enrichment (re-tag, re-summarize) for an item."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Always run synchronously - Huey silently queues without raising when consumer is down
    from fourdpocket.ai.summarizer import summarize_item
    from fourdpocket.ai.tagger import auto_tag_item

    # Don't pre-sanitize here — auto_tag_item -> generate_tags already sanitizes via sanitize_for_prompt
    tags = auto_tag_item(
        item_id=item.id,
        user_id=current_user.id,
        title=item.title or "",
        content=item.content or "",
        description=item.description or "",
        db=db,
    )
    summary = summarize_item(item.id, db)

    # Also dispatch to Huey for embedding (best-effort, runs if consumer is up)
    try:
        from fourdpocket.workers.enrichment_pipeline import enrich_item_v2
        enrich_item_v2(str(item_id), str(current_user.id))
    except Exception:
        pass

    return {
        "status": "completed",
        "item_id": str(item_id),
        "tags": len(tags),
        "summary": bool(summary),
    }


@router.get("/suggest-collection")
def suggest_collection_for_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suggest which existing collection an item might belong to."""
    item = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id
        )
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Get item's tags
    item_tag_ids = [
        link.tag_id
        for link in db.exec(select(ItemTag).where(ItemTag.item_id == item.id)).all()
    ]

    # Get all collections with their items' tags
    collections = db.exec(
        select(Collection).where(Collection.user_id == current_user.id)
    ).all()
    suggestions = []

    for coll in collections:
        coll_items = db.exec(
            select(CollectionItem).where(CollectionItem.collection_id == coll.id)
        ).all()
        if not coll_items:
            continue
        coll_item_ids = [ci.item_id for ci in coll_items]
        coll_tag_links = db.exec(
            select(ItemTag).where(ItemTag.item_id.in_(coll_item_ids))
        ).all()
        coll_tag_ids = set(link.tag_id for link in coll_tag_links)

        if item_tag_ids and coll_tag_ids:
            overlap = len(set(item_tag_ids) & coll_tag_ids)
            if overlap > 0:
                score = overlap / max(len(item_tag_ids), 1)
                suggestions.append({
                    "collection_id": str(coll.id),
                    "collection_name": coll.name,
                    "score": round(score, 2),
                    "shared_tags": overlap,
                })

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:5]


@router.get("/knowledge-gaps")
def detect_knowledge_gaps(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Detect potential knowledge gaps - topics with few items that could use more."""

    from fourdpocket.models.tag import Tag

    # Get all user's tags with counts
    tags = db.exec(select(Tag).where(Tag.user_id == user.id)).all()

    # Find tags with parent relationships where child has very few items
    gaps = []
    for tag in tags:
        if tag.parent_id and tag.usage_count and tag.usage_count <= 2:
            parent = db.exec(select(Tag).where(Tag.id == tag.parent_id)).first()
            if parent and parent.usage_count and parent.usage_count > 5:
                gaps.append({
                    "tag": tag.name,
                    "count": tag.usage_count,
                    "parent_tag": parent.name,
                    "parent_count": parent.usage_count,
                    "suggestion": f"You have {parent.usage_count} items about {parent.name} but only {tag.usage_count} about {tag.name}",
                })

    # Also find popular tags with no hierarchy
    popular_tags = [t for t in tags if (t.usage_count or 0) >= 5 and not t.parent_id]
    for tag in popular_tags[:10]:
        # Check for subtopics that don't have their own tag
        child_tags = [t for t in tags if t.parent_id == tag.id]
        if not child_tags:
            gaps.append({
                "tag": tag.name,
                "count": tag.usage_count,
                "parent_tag": None,
                "parent_count": None,
                "suggestion": f"You have {tag.usage_count} items tagged '{tag.name}' - consider creating sub-tags for better organization",
            })

    return gaps[:20]


@router.get("/stale-items")
def detect_stale_items(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Find items that may be outdated (old API docs, deprecated libraries, etc.)."""
    from datetime import timedelta

    stale_threshold = datetime.now(timezone.utc) - timedelta(days=365)

    # Items older than 1 year in tech-related tags
    tech_keywords = ["api", "documentation", "tutorial", "guide", "reference", "library", "framework", "sdk"]

    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == user.id,
            KnowledgeItem.is_archived == False,  # noqa: E712
            KnowledgeItem.created_at < stale_threshold,
        ).order_by(KnowledgeItem.created_at.asc()).limit(50)
    ).all()

    stale = []
    for item in items:
        title_lower = (item.title or "").lower()
        is_tech = any(kw in title_lower for kw in tech_keywords)
        age_days = (datetime.now(timezone.utc) - item.created_at).days if item.created_at else 0

        stale.append({
            "id": str(item.id),
            "title": item.title,
            "url": item.url,
            "source_platform": item.source_platform,
            "age_days": age_days,
            "likely_outdated": is_tech,
            "reason": "Technical content over 1 year old" if is_tech else f"Saved {age_days} days ago",
        })

    # Sort: tech items first, then by age
    stale.sort(key=lambda x: (not x["likely_outdated"], -x["age_days"]))
    return stale[:30]


@router.get("/cross-platform")
def find_cross_platform_connections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Find items from different platforms that reference each other."""

    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == user.id,
            KnowledgeItem.content.is_not(None),
        ).limit(500)
    ).all()

    # Build URL -> item index
    url_to_item = {}
    for item in items:
        if item.url:
            url_to_item[item.url] = item

    connections = []
    for item in items:
        if not item.content:
            continue
        # Search for other saved URLs in this item's content
        for other_url, other_item in url_to_item.items():
            if other_item.id == item.id:
                continue
            if other_url in item.content:
                connections.append({
                    "source": {"id": str(item.id), "title": item.title, "platform": item.source_platform},
                    "references": {"id": str(other_item.id), "title": other_item.title, "platform": other_item.source_platform},
                    "type": "content_link",
                })

    return connections[:50]


@router.post("/transcribe")
def transcribe_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Transcribe audio using Groq's Whisper API."""
    import httpx

    from fourdpocket.ai.factory import get_resolved_ai_config

    config = get_resolved_ai_config()
    groq_key = config.get("groq_api_key", "")
    if not groq_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Groq API key not configured. "
            "Set FDP_AI__GROQ_API_KEY or configure in Admin panel.",
        )

    # Validate file type
    allowed_types = {
        "audio/webm", "audio/wav", "audio/mp3", "audio/mpeg",
        "audio/ogg", "audio/mp4", "audio/m4a", "audio/x-m4a",
    }
    content_type = file.content_type or ""
    if content_type not in allowed_types and not content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {content_type}",
        )

    # Read file content (max 25MB - Groq limit)
    audio_bytes = file.file.read()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file too large (max 25MB)",
        )

    # Call Groq Whisper API
    filename = file.filename or "audio.webm"
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_key}"},
            files={"file": (filename, audio_bytes, content_type or "audio/webm")},
            data={"model": "whisper-large-v3-turbo", "response_format": "json"},
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        transcript = result.get("text", "")
    except httpx.HTTPStatusError as e:
        detail = f"Transcription service error (HTTP {e.response.status_code})"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    except Exception as e:
        logger.exception("Transcription failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription failed",
        )

    return {"text": transcript}
