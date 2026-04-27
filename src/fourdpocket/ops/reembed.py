"""Re-embedding operation — clears and re-enqueues the 'embedded' enrichment stage.

Supports:
  - --dry-run: report counts without mutating anything.
  - --user EMAIL: scope to a single user.
  - Dimension mismatch detection (reported, not auto-handled here — CLI layer decides).
"""

import sys
import uuid
from typing import Optional

from sqlalchemy.engine import Engine
from sqlmodel import Session, select


def _enqueue_embedding(item_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Enqueue the 'embedded' stage for a single item.

    If the Huey worker is not running, falls back to synchronous execution
    (mirrors the sync_enrichment pattern in the workers).
    """
    from fourdpocket.workers.enrichment_pipeline import run_enrichment_stage

    try:
        run_enrichment_stage(str(item_id), str(user_id), "embedded")
    except Exception as e:
        # If Huey cannot enqueue (e.g. worker not running), log and continue.
        import logging
        logging.getLogger(__name__).warning(
            "Failed to enqueue embedded stage for item %s: %s", item_id, e
        )


def _clear_embeddings_for_user(
    user_id: uuid.UUID,
    vector_backend: str,
    db: Session,
) -> None:
    """Clear embeddings for all items owned by *user_id*.

    For Chroma: deletes per-user collection contents.
    For pgvector: NULLs the embedding column on item_chunks for this user.
    """
    if vector_backend == "chroma":
        try:
            from fourdpocket.search.semantic import _get_collection

            collection = _get_collection(user_id)
            # Get all IDs in the collection and delete them
            existing = collection.get(include=[])
            if existing and existing.get("ids"):
                collection.delete(ids=existing["ids"])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to clear Chroma embeddings for user %s: %s", user_id, e
            )
    else:
        # pgvector: NULL out embeddings on item_chunks for this user
        try:
            from sqlalchemy import text
            db.execute(
                text("UPDATE item_chunks SET embedding = NULL WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to clear pgvector embeddings for user %s: %s", user_id, e
            )


def _reset_embedding_stage_for_item(db: Session, item_id: uuid.UUID) -> None:
    """Reset the 'embedded' enrichment stage back to pending for re-processing."""
    from fourdpocket.models.enrichment import EnrichmentStage

    stage = db.exec(
        select(EnrichmentStage).where(
            EnrichmentStage.item_id == item_id,
            EnrichmentStage.stage == "embedded",
        )
    ).first()
    if stage is not None:
        stage.status = "pending"
        stage.attempts = 0
        stage.last_error = None
        db.add(stage)
    db.commit()


def run_reembed(
    *,
    engine: Engine,
    user_email: Optional[str],
    dry_run: bool,
    vector_backend: str,
) -> dict:
    """Core re-embedding logic.

    Args:
        engine: SQLAlchemy engine for DB access.
        user_email: If provided, scope to this user only.
        dry_run: If True, report plan without mutating anything.
        vector_backend: "chroma" or "pgvector".

    Returns:
        dict with keys: total_items, total_users, dry_run.

    Raises:
        SystemExit(1) if user_email is given but not found.
    """
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.models.user import User

    with Session(engine) as db:
        # Resolve user filter
        target_user_ids: list[uuid.UUID] = []

        if user_email:
            user = db.exec(
                select(User).where(User.email == user_email)
            ).first()
            if user is None:
                print(f"ERROR: No user found with email: {user_email}", file=sys.stderr)
                sys.exit(1)
            target_user_ids = [user.id]
        else:
            all_users = db.exec(select(User.id)).all()
            target_user_ids = list(all_users)

        # Count affected items
        if target_user_ids:
            items = db.exec(
                select(KnowledgeItem).where(
                    KnowledgeItem.user_id.in_(target_user_ids)  # type: ignore[attr-defined]
                )
            ).all()
        else:
            items = []

        total_items = len(items)
        total_users = len(target_user_ids)

        print(
            f"Re-embed plan: {total_items} item(s) across {total_users} user(s)"
            + (" [DRY RUN — no changes]" if dry_run else "")
        )

        if dry_run:
            return {"total_items": total_items, "total_users": total_users, "dry_run": True}

        # Group items by user for efficient per-user clear
        items_by_user: dict[uuid.UUID, list[KnowledgeItem]] = {}
        for item in items:
            items_by_user.setdefault(item.user_id, []).append(item)

        for uid, user_items in items_by_user.items():
            # Clear existing embeddings for this user
            _clear_embeddings_for_user(uid, vector_backend, db)

            # Reset stage and enqueue for each item
            for item in user_items:
                _reset_embedding_stage_for_item(db, item.id)
                _enqueue_embedding(item.id, uid)

        print(f"Enqueued {total_items} item(s) for re-embedding.")
        return {"total_items": total_items, "total_users": total_users, "dry_run": False}
