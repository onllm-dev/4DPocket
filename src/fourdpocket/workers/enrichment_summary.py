"""Helpers for collapsing per-stage enrichment rows into a compact summary.

Lists like ``/items`` need a single-badge status per item; showing all
five stages on a card is noise. This module converts a set of
``EnrichmentStage`` rows into ``EnrichmentSummary`` objects and does the
batching efficiently for list views.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlmodel import Session, select

from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.item import EnrichmentSummary

# User-visible stages. Skip "synthesized" because it fires on entity
# synthesis and isn't really an item-level concern — it would keep the
# overall badge "processing" for items that are otherwise fully done.
USER_VISIBLE_STAGES = ("chunked", "embedded", "tagged", "summarized", "entities_extracted")


def summarize_stages(stages: Iterable[EnrichmentStage]) -> EnrichmentSummary:
    """Collapse one item's stage rows into a single-badge summary.

    Overall priority (first match wins):
      * ``failed`` — any user-visible stage failed (even if some succeeded)
      * ``processing`` — any user-visible stage is running or pending
      * ``done`` — every user-visible stage is done or skipped
      * ``none`` — no stage rows exist yet (item just created / legacy)
    """
    stage_map: dict[str, EnrichmentStage] = {
        s.stage: s for s in stages if s.stage in USER_VISIBLE_STAGES
    }

    if not stage_map:
        return EnrichmentSummary(
            overall="none",
            stages={},
            failed_stages=[],
            last_error=None,
        )

    status_by_stage = {k: v.status for k, v in stage_map.items()}
    failed_stages = [s for s, status in status_by_stage.items() if status == "failed"]
    last_error = None

    if failed_stages:
        # Surface the most recent failure's message
        latest_failed = max(
            (stage_map[s] for s in failed_stages),
            key=lambda r: r.updated_at,
        )
        last_error = latest_failed.last_error
        overall = "failed"
    elif any(status in ("pending", "running") for status in status_by_stage.values()):
        overall = "processing"
    elif all(status in ("done", "skipped") for status in status_by_stage.values()):
        overall = "done"
    else:
        overall = "processing"  # defensive — unknown status counts as in-flight

    return EnrichmentSummary(
        overall=overall,
        stages=status_by_stage,
        failed_stages=failed_stages,
        last_error=last_error,
    )


def batch_enrichment_summary(
    db: Session, item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, EnrichmentSummary]:
    """Return ``{item_id: summary}`` for a batch of items.

    Executes a single query regardless of batch size.
    """
    if not item_ids:
        return {}

    rows = db.exec(
        select(EnrichmentStage).where(EnrichmentStage.item_id.in_(item_ids))
    ).all()

    by_item: dict[uuid.UUID, list[EnrichmentStage]] = {}
    for row in rows:
        by_item.setdefault(row.item_id, []).append(row)

    return {iid: summarize_stages(by_item.get(iid, [])) for iid in item_ids}


def queue_stats(db: Session, user_id: uuid.UUID) -> dict:
    """Cheap snapshot of how much enrichment work is still in flight.

    Used for the "~N items ahead" hint on pending items. Scoped to the
    user so one user's big import doesn't show up on another user's UI.
    """
    from fourdpocket.models.item import KnowledgeItem

    rows = db.exec(
        select(EnrichmentStage)
        .join(KnowledgeItem, KnowledgeItem.id == EnrichmentStage.item_id)
        .where(KnowledgeItem.user_id == user_id)
        .where(EnrichmentStage.status.in_(("pending", "running")))
    ).all()

    pending_items: set[uuid.UUID] = set()
    running_items: set[uuid.UUID] = set()
    for row in rows:
        if row.status == "running":
            running_items.add(row.item_id)
        else:
            pending_items.add(row.item_id)

    # An item being "running" also has "pending" siblings — de-dup.
    total_in_flight = len(pending_items | running_items)

    return {
        "items_in_flight": total_in_flight,
        "running_items": len(running_items),
        "pending_items": len(pending_items - running_items),
    }
