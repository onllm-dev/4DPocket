"""Admin management endpoints."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from fourdpocket.api.deps import (
    get_db,
    get_or_create_settings,
    require_admin,
    require_jwt_session,
)
from fourdpocket.models.base import UserRole
from fourdpocket.models.collection import Collection
from fourdpocket.models.entity import Entity
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.tag import Tag
from fourdpocket.models.user import User, UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def instance_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """System-wide analytics: counts of key entities, storage on disk, worker queue status."""
    def _count(model) -> int:
        return db.exec(select(func.count()).select_from(model)).one()

    user_total = _count(User)
    active_users = db.exec(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    ).one()

    # Huey queue depth (SQLite backend). Failure = 0, not fatal.
    queue_depth = 0
    worker_alive = False
    try:
        import sqlite3

        db_path = os.path.join(os.getcwd(), "data", "huey_tasks.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            try:
                cur = conn.execute("SELECT COUNT(*) FROM task")
                queue_depth = cur.fetchone()[0] or 0
            finally:
                conn.close()
    except Exception:
        pass

    try:
        import subprocess

        out = subprocess.run(
            ["pgrep", "-f", "fourdpocket.workers.huey_worker"],
            capture_output=True, text=True, timeout=2,
        )
        worker_alive = bool(out.stdout.strip())
    except Exception:
        pass

    # Best-effort storage usage (data directory).
    storage_bytes = 0
    try:
        data_dir = os.path.join(os.getcwd(), "data")
        for root, _dirs, files in os.walk(data_dir):
            for fname in files:
                try:
                    storage_bytes += os.path.getsize(os.path.join(root, fname))
                except OSError:
                    pass
    except Exception:
        pass

    return {
        "users_total": user_total,
        "users_active": active_users,
        "items_total": _count(KnowledgeItem),
        "collections_total": _count(Collection),
        "tags_total": _count(Tag),
        "entities_total": _count(Entity),
        "storage_bytes": storage_bytes,
        "queue_depth": queue_depth,
        "worker_alive": worker_alive,
    }


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    users = db.exec(select(User).offset(offset).limit(limit)).all()
    return users


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    display_name: str | None = None


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    _: None = Depends(require_jwt_session),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and data.role and data.role != UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    _: None = Depends(require_jwt_session),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Cascade delete ALL user-owned data (GDPR-compliant full removal)
    from fourdpocket.models.collection import Collection, CollectionItem
    from fourdpocket.models.collection_note import CollectionNote
    from fourdpocket.models.comment import Comment
    from fourdpocket.models.embedding import Embedding
    from fourdpocket.models.feed import KnowledgeFeed
    from fourdpocket.models.feed_entry import FeedEntry
    from fourdpocket.models.highlight import Highlight
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.models.item_link import ItemLink
    from fourdpocket.models.note import Note
    from fourdpocket.models.note_tag import NoteTag
    from fourdpocket.models.rss_feed import RSSFeed
    from fourdpocket.models.rule import Rule
    from fourdpocket.models.saved_filter import SavedFilter
    from fourdpocket.models.share import Share, ShareRecipient
    from fourdpocket.models.tag import ItemTag, Tag

    uid = user_id

    # 1. Delete share recipients (both sent and received)
    user_shares = db.exec(select(Share).where(Share.owner_id == uid)).all()
    for share in user_shares:
        for sr in db.exec(select(ShareRecipient).where(ShareRecipient.share_id == share.id)).all():
            db.delete(sr)
        db.delete(share)
    # Remove as recipient from others' shares
    for sr in db.exec(select(ShareRecipient).where(ShareRecipient.user_id == uid)).all():
        db.delete(sr)

    # 2. Delete item-level data
    user_items = db.exec(select(KnowledgeItem).where(KnowledgeItem.user_id == uid)).all()
    item_ids = [i.id for i in user_items]
    if item_ids:
        for row in db.exec(select(ItemTag).where(ItemTag.item_id.in_(item_ids))).all():
            db.delete(row)
        for row in db.exec(select(Highlight).where(Highlight.item_id.in_(item_ids))).all():
            db.delete(row)
        for row in db.exec(select(Comment).where(Comment.item_id.in_(item_ids))).all():
            db.delete(row)
        for row in db.exec(select(Embedding).where(Embedding.item_id.in_(item_ids))).all():
            db.delete(row)
        for row in db.exec(select(CollectionItem).where(CollectionItem.item_id.in_(item_ids))).all():
            db.delete(row)
        for row in db.exec(select(ItemLink).where(ItemLink.item_id.in_(item_ids))).all():
            db.delete(row)

    # 3. Delete note-level data
    user_notes = db.exec(select(Note).where(Note.user_id == uid)).all()
    note_ids = [n.id for n in user_notes]
    if note_ids:
        for row in db.exec(select(NoteTag).where(NoteTag.note_id.in_(note_ids))).all():
            db.delete(row)
        for row in db.exec(select(Highlight).where(Highlight.note_id.in_(note_ids))).all():
            db.delete(row)
        for row in db.exec(select(CollectionNote).where(CollectionNote.note_id.in_(note_ids))).all():
            db.delete(row)

    # 4. Delete collections
    for coll in db.exec(select(Collection).where(Collection.user_id == uid)).all():
        for ci in db.exec(select(CollectionItem).where(CollectionItem.collection_id == coll.id)).all():
            db.delete(ci)
        for cn in db.exec(select(CollectionNote).where(CollectionNote.collection_id == coll.id)).all():
            db.delete(cn)
        db.delete(coll)

    # 5. Delete tags (with ItemTag cleanup), notes, items
    for tag in db.exec(select(Tag).where(Tag.user_id == uid)).all():
        for it_row in db.exec(select(ItemTag).where(ItemTag.tag_id == tag.id)).all():
            db.delete(it_row)
        for nt_row in db.exec(select(NoteTag).where(NoteTag.tag_id == tag.id)).all():
            db.delete(nt_row)
        db.delete(tag)
    for note in user_notes:
        db.delete(note)
    for item in user_items:
        db.delete(item)

    # 6. Delete RSS feeds, feed entries, rules, saved filters, knowledge feeds
    for feed in db.exec(select(RSSFeed).where(RSSFeed.user_id == uid)).all():
        for entry in db.exec(select(FeedEntry).where(FeedEntry.feed_id == feed.id)).all():
            db.delete(entry)
        db.delete(feed)
    for row in db.exec(select(Rule).where(Rule.user_id == uid)).all():
        db.delete(row)
    for row in db.exec(select(SavedFilter).where(SavedFilter.user_id == uid)).all():
        db.delete(row)
    for row in db.exec(select(KnowledgeFeed).where(KnowledgeFeed.user_id == uid)).all():
        db.delete(row)
    # Also delete comments on others' items
    for row in db.exec(select(Comment).where(Comment.user_id == uid)).all():
        db.delete(row)

    # 7. Clean up FTS indexes
    try:
        from fourdpocket.config import get_settings as _get_settings
        _s = _get_settings()
        if _s.search.backend == "sqlite" and _s.database.url.startswith("sqlite"):
            from sqlalchemy import text as _text
            db.exec(_text("DELETE FROM items_fts WHERE user_id = :uid"), params={"uid": str(uid)})
            db.exec(_text("DELETE FROM notes_fts WHERE user_id = :uid"), params={"uid": str(uid)})
    except Exception:
        pass

    db.delete(user)
    db.commit()


# ─── AI Settings (admin-controlled) ─────────────────────────────

AI_CONFIG_KEYS = {
    "chat_provider", "ollama_url", "ollama_model",
    "groq_api_key", "nvidia_api_key",
    "custom_base_url", "custom_api_key", "custom_model", "custom_api_type",
    "embedding_provider", "embedding_model",
    "auto_tag", "auto_summarize",
    "tag_confidence_threshold", "tag_suggestion_threshold",
    "sync_enrichment",
}


def _mask_key(value: str) -> str:
    """Mask API keys for display: show first 4 and last 4 chars."""
    if not value or len(value) < 12:
        return "***" if value else ""
    return f"{value[:4]}...{value[-4:]}"


@router.get("/ai-settings")
def get_ai_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Get resolved AI configuration (env defaults + admin overrides)."""
    from fourdpocket.ai.factory import get_resolved_ai_config

    config = get_resolved_ai_config()
    # Mask sensitive keys in response
    masked = {**config}
    for key in ("groq_api_key", "nvidia_api_key", "custom_api_key"):
        if key in masked and masked[key]:
            masked[key] = _mask_key(masked[key])
    return masked


class AISettingsUpdate(BaseModel):
    chat_provider: str | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    groq_api_key: str | None = None
    nvidia_api_key: str | None = None
    custom_base_url: str | None = None
    custom_api_key: str | None = None
    custom_model: str | None = None
    custom_api_type: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    auto_tag: bool | None = None
    auto_summarize: bool | None = None
    tag_confidence_threshold: float | None = None
    tag_suggestion_threshold: float | None = None
    sync_enrichment: bool | None = None


@router.patch("/ai-settings")
def update_ai_settings(
    data: AISettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    _: None = Depends(require_jwt_session),
):
    """Update AI settings (stored in InstanceSettings.extra['ai_config']).

    Admin panel settings take precedence over .env values.
    """
    settings = get_or_create_settings(db)
    extra = dict(settings.extra) if settings.extra else {}
    ai_config = extra.get("ai_config", {})

    update_dict = data.model_dump(exclude_unset=True)
    # Only accept known AI config keys
    for key, value in update_dict.items():
        if key in AI_CONFIG_KEYS:
            # Don't overwrite secrets with masked value
            if (key.endswith("_key") or key.endswith("_url")) and value and "..." in value:
                continue
            # Validate URL fields point to valid http(s) endpoints
            if key.endswith("_url") and value:
                if not value.startswith(("http://", "https://")):
                    continue
            ai_config[key] = value

    extra["ai_config"] = ai_config
    settings.extra = extra
    db.add(settings)
    db.commit()
    db.refresh(settings)

    # Return resolved config with masked keys
    from fourdpocket.ai.factory import get_resolved_ai_config

    config = get_resolved_ai_config()
    masked = {**config}
    for key in ("groq_api_key", "nvidia_api_key", "custom_api_key"):
        if key in masked and masked[key]:
            masked[key] = _mask_key(masked[key])
    return masked


# ─── Search Settings (admin-controlled) ─────────────────────────

SEARCH_CONFIG_KEYS = {
    "graph_ranker_enabled",
    "graph_ranker_hop_decay",
    "graph_ranker_top_k",
}


@router.get("/search-settings")
def get_search_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Get resolved search configuration (env defaults + admin overrides)."""
    from fourdpocket.search.admin_config import get_resolved_search_config

    return get_resolved_search_config()


class SearchSettingsUpdate(BaseModel):
    graph_ranker_enabled: bool | None = None
    graph_ranker_hop_decay: float | None = None
    graph_ranker_top_k: int | None = None


@router.patch("/search-settings")
def update_search_settings(
    data: SearchSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    _: None = Depends(require_jwt_session),
):
    """Update search settings (stored in InstanceSettings.extra['search_config']).

    Admin panel settings take precedence over .env values.
    """
    settings = get_or_create_settings(db)
    # Deep copy both layers so SQLAlchemy detects the JSON-column change.
    extra = dict(settings.extra) if settings.extra else {}
    search_config = dict(extra.get("search_config", {}))

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if key in SEARCH_CONFIG_KEYS:
            # Light validation on numeric bounds
            if key == "graph_ranker_hop_decay" and value is not None:
                value = max(0.0, min(1.0, float(value)))
            if key == "graph_ranker_top_k" and value is not None:
                value = max(1, min(500, int(value)))
            search_config[key] = value

    extra["search_config"] = search_config
    settings.extra = extra
    db.add(settings)
    db.commit()
    db.refresh(settings)

    from fourdpocket.search.admin_config import get_resolved_search_config

    return get_resolved_search_config()


# ─── Instance Settings ──────────────────────────────────────────

class InstanceSettingsRead(BaseModel):
    instance_name: str
    registration_enabled: bool
    registration_mode: str
    default_user_role: str
    max_users: int | None
    model_config = {"from_attributes": True}


class InstanceSettingsUpdate(BaseModel):
    instance_name: str | None = None
    registration_enabled: bool | None = None
    registration_mode: str | None = None
    default_user_role: str | None = None
    max_users: int | None = None


@router.get("/settings", response_model=InstanceSettingsRead)
def get_instance_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return get_or_create_settings(db)


@router.patch("/settings", response_model=InstanceSettingsRead)
def update_instance_settings(
    data: InstanceSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    _: None = Depends(require_jwt_session),
):
    settings = get_or_create_settings(db)
    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
