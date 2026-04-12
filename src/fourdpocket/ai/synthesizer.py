"""LLM-authored entity synthesis — structured JSON wiki pages per entity.

Input: entity + its top-salient item mentions + top-weighted related entities.
Output: a structured JSON synthesis stored on ``entities.synthesis``::

    {
      "summary": str,                  # 2-4 sentence grounded description
      "themes": [str, ...],            # recurring-context phrases
      "key_contexts": [{context, source_item_id}, ...],
      "relationships": [{entity_name, nature}, ...],
      "confidence": "low|medium|high",
      "last_updated": iso8601,
      "source_item_count": int
    }

Regeneration rules live in :mod:`fourdpocket.workers.enrichment_pipeline`:
only eligible entities are sent here (``item_count - synthesis_item_count >= N``,
``min_item_count`` reached, ``min_interval_hours`` elapsed).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, col, select

from fourdpocket.ai.factory import get_chat_provider
from fourdpocket.ai.llm_cache import get_cached_response, store_cached_response
from fourdpocket.ai.sanitizer import sanitize_for_prompt
from fourdpocket.config import get_settings
from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.item import KnowledgeItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a knowledge-base synthesis assistant.

Given an entity and evidence from a user's personal knowledge base, write a
neutral, encyclopedia-style synthesis in JSON form. Ground every claim in the
provided evidence — do NOT invent facts beyond it.

Return valid JSON with this exact shape:
{
  "summary": "2-4 sentence description of what this entity is, grounded in the evidence.",
  "themes": ["short phrase", "short phrase"],
  "key_contexts": [
    {"context": "1-2 sentence excerpt or paraphrase of a key mention.", "source_item_id": "uuid-or-null"}
  ],
  "relationships": [
    {"entity_name": "Related Entity", "nature": "how they relate based on evidence"}
  ],
  "confidence": "low|medium|high"
}

Rules:
- If evidence is thin or contradictory, set confidence="low".
- Max 5 themes, max 5 key_contexts, max 6 relationships.
- Use neutral voice. Do not use first person.
- Do NOT add fields beyond those listed."""


_CONFIDENCE_VALUES = {"low", "medium", "high"}


def _evidence_hash(entity: Entity, contexts: list[dict], rels: list[dict]) -> str:
    """Content hash used for the LLM cache lookup."""
    payload = json.dumps(
        {
            "name": entity.canonical_name,
            "type": entity.entity_type,
            "description": entity.description or "",
            "contexts": contexts,
            "relationships": rels,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _collect_evidence(
    db: Session, entity: Entity, max_items: int
) -> tuple[list[dict], list[dict]]:
    """Gather the most-salient mentions and the top related entities."""
    # Top-salient ItemEntity mentions → contexts
    mentions = db.exec(
        select(ItemEntity, KnowledgeItem)
        .join(KnowledgeItem, KnowledgeItem.id == ItemEntity.item_id)
        .where(ItemEntity.entity_id == entity.id)
        .order_by(col(ItemEntity.salience).desc())
        .limit(max_items)
    ).all()

    contexts: list[dict] = []
    for mention, item in mentions:
        snippet = mention.context or item.summary or item.description or ""
        snippet = sanitize_for_prompt(snippet, max_length=400)
        if not snippet.strip():
            continue
        contexts.append(
            {
                "context": snippet,
                "source_item_id": str(item.id),
                "source_title": item.title[:120] if item.title else None,
            }
        )

    # Top related entities (by relation weight)
    rels = db.exec(
        select(EntityRelation)
        .where(
            EntityRelation.user_id == entity.user_id,
            (EntityRelation.source_id == entity.id)
            | (EntityRelation.target_id == entity.id),
        )
        .order_by(col(EntityRelation.weight).desc())
        .limit(6)
    ).all()

    relationship_hints: list[dict] = []
    for r in rels:
        other_id = r.target_id if r.source_id == entity.id else r.source_id
        other = db.get(Entity, other_id)
        if other is None:
            continue
        relationship_hints.append(
            {
                "entity_name": other.canonical_name,
                "keywords": r.keywords or "",
                "description": sanitize_for_prompt(r.description or "", max_length=200),
                "weight": r.weight,
            }
        )

    return contexts, relationship_hints


def _validate_synthesis(raw: Any) -> dict[str, Any] | None:
    """Shape-check the LLM output before persisting."""
    if not isinstance(raw, dict):
        return None

    summary = (raw.get("summary") or "").strip()
    if not summary:
        return None

    themes = raw.get("themes") or []
    if not isinstance(themes, list):
        themes = []
    themes = [str(t).strip()[:80] for t in themes[:5] if str(t).strip()]

    key_contexts = raw.get("key_contexts") or []
    if not isinstance(key_contexts, list):
        key_contexts = []
    cleaned_contexts: list[dict] = []
    for c in key_contexts[:5]:
        if not isinstance(c, dict):
            continue
        text = str(c.get("context") or "").strip()
        if not text:
            continue
        source = c.get("source_item_id")
        if source is not None:
            try:
                uuid.UUID(str(source))
                source = str(source)
            except (ValueError, TypeError):
                source = None
        cleaned_contexts.append({"context": text[:400], "source_item_id": source})

    relationships = raw.get("relationships") or []
    if not isinstance(relationships, list):
        relationships = []
    cleaned_rels: list[dict] = []
    for r in relationships[:6]:
        if not isinstance(r, dict):
            continue
        name = str(r.get("entity_name") or "").strip()
        if not name:
            continue
        nature = str(r.get("nature") or "").strip()[:200]
        cleaned_rels.append({"entity_name": name[:120], "nature": nature})

    confidence = str(raw.get("confidence") or "low").strip().lower()
    if confidence not in _CONFIDENCE_VALUES:
        confidence = "low"

    return {
        "summary": summary[:800],
        "themes": themes,
        "key_contexts": cleaned_contexts,
        "relationships": cleaned_rels,
        "confidence": confidence,
    }


def synthesize_entity(entity_id: uuid.UUID, db: Session) -> dict[str, Any] | None:
    """Generate (or refresh) the synthesis for a single entity.

    Returns the structured synthesis payload (also persisted on the entity)
    or ``None`` when the entity has insufficient evidence or the LLM is offline.
    """
    settings = get_settings()
    enrichment = settings.enrichment
    if not enrichment.synthesis_enabled:
        return None

    entity = db.get(Entity, entity_id)
    if entity is None:
        return None

    if entity.item_count < enrichment.synthesis_min_item_count:
        return None

    contexts, rels = _collect_evidence(db, entity, enrichment.synthesis_max_context_items)
    if not contexts:
        return None

    aliases = db.exec(
        select(EntityAlias.alias).where(EntityAlias.entity_id == entity.id)
    ).all()

    cache_key = _evidence_hash(entity, contexts, rels)
    cached = get_cached_response(db, cache_key, "synthesis")
    result_payload = cached if isinstance(cached, dict) else None

    if result_payload is None:
        chat = get_chat_provider()
        prompt = _build_prompt(entity, list(aliases), contexts, rels)
        try:
            raw = chat.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
        except Exception as e:  # nosec - any provider failure is tolerated
            logger.debug("Synthesis LLM call failed for %s: %s", entity.id, e)
            return None

        result_payload = _validate_synthesis(raw)
        if result_payload is None:
            return None

        store_cached_response(db, cache_key, "synthesis", result_payload)

    now = datetime.now(timezone.utc)
    result_payload = {
        **result_payload,
        "last_updated": now.isoformat(),
        "source_item_count": entity.item_count,
    }
    entity.synthesis = result_payload
    entity.synthesis_generated_at = now
    entity.synthesis_item_count = entity.item_count
    entity.synthesis_confidence = result_payload.get("confidence")
    entity.updated_at = now
    db.add(entity)
    db.commit()
    db.refresh(entity)

    return result_payload


def _build_prompt(
    entity: Entity,
    aliases: list[str],
    contexts: list[dict],
    rels: list[dict],
) -> str:
    """Assemble the user prompt from evidence. Sanitises all user-origin text."""
    parts = [
        f"Entity: {entity.canonical_name}",
        f"Type: {entity.entity_type}",
    ]
    if aliases:
        parts.append(f"Aliases: {', '.join(aliases[:10])}")
    if entity.description:
        parts.append(
            "Existing description: "
            + sanitize_for_prompt(entity.description, max_length=300)
        )
    parts.append(f"Mentioned in {entity.item_count} items.")

    parts.append("\nKey mentions (most-salient first):")
    for i, c in enumerate(contexts, start=1):
        title = c.get("source_title") or ""
        parts.append(
            f"{i}. [{title}] {c['context']}"
        )

    if rels:
        parts.append("\nRelated entities in the user's graph:")
        for r in rels:
            parts.append(
                f"- {r['entity_name']} ({r.get('keywords', '')}): "
                f"{r.get('description', '')[:200]}"
            )

    parts.append(
        "\nWrite the synthesis now, returning ONLY valid JSON matching the schema."
    )
    return "\n".join(parts)


def should_regenerate(entity: Entity) -> bool:
    """Decide whether an entity is due for synthesis regeneration."""
    settings = get_settings().enrichment
    if not settings.synthesis_enabled:
        return False
    if entity.item_count < settings.synthesis_min_item_count:
        return False

    # First-ever synthesis — eligible once min_item_count is reached
    if entity.synthesis is None or entity.synthesis_generated_at is None:
        return True

    delta = (entity.item_count or 0) - (entity.synthesis_item_count or 0)
    if delta < settings.synthesis_threshold:
        return False

    last = entity.synthesis_generated_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    hours_since = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
    return hours_since >= settings.synthesis_min_interval_hours
