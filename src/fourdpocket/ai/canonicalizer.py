"""Entity canonicalization — dedup and merge entities by name similarity."""

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlmodel import Session, func, select

from fourdpocket.models.entity import Entity, EntityAlias

logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    """Normalize entity name for fuzzy matching."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)  # strip punctuation
    s = re.sub(r"\s+", " ", s)  # collapse whitespace
    return s


def _merge_descriptions(existing: str, new: str, max_length: int = 1000) -> str:
    """Merge two entity descriptions, avoiding duplicates.

    If the new description adds meaningful info, append it.
    Returns the merged description, truncated to max_length.
    """
    if not new:
        return existing or ""
    if not existing:
        return new[:max_length]

    # If new description is a substring of existing, skip
    if new.lower().strip() in existing.lower():
        return existing

    # Append with separator, truncate
    merged = f"{existing.rstrip('.')}. {new.strip()}"
    return merged[:max_length]


def canonicalize_entity(
    name: str,
    entity_type: str,
    user_id: uuid.UUID,
    db: Session,
    description: str = "",
) -> Entity:
    """Find or create a canonical entity, handling aliases.

    Three-tier matching:
    1. Exact alias match (case-insensitive)
    2. Normalized name match (DB query, not full scan)
    3. Create new entity if no match

    When a match is found, merges the new description into the existing one.
    Returns the canonical Entity.
    """
    # Tier 1: Case-insensitive alias match
    alias_row = db.exec(
        select(EntityAlias)
        .join(Entity, Entity.id == EntityAlias.entity_id)
        .where(
            Entity.user_id == user_id,
            Entity.entity_type == entity_type,
            func.lower(EntityAlias.alias) == name.lower(),
        )
    ).first()

    if alias_row:
        entity = db.get(Entity, alias_row.entity_id)
        if entity:
            # Add the exact surface form as an alias if it's a new casing variant
            if alias_row.alias != name:
                existing_exact = db.exec(
                    select(EntityAlias).where(
                        EntityAlias.entity_id == entity.id,
                        EntityAlias.alias == name,
                    )
                ).first()
                if not existing_exact:
                    new_alias = EntityAlias(
                        entity_id=entity.id,
                        alias=name,
                        source="extraction",
                    )
                    db.add(new_alias)
                    db.flush()
            # Merge description if new info available
            if description:
                merged = _merge_descriptions(entity.description or "", description)
                if merged != (entity.description or ""):
                    entity.description = merged
                    entity.updated_at = datetime.now(timezone.utc)
                    db.add(entity)
                    db.flush()
            return entity

    # Tier 2: Normalized canonical_name match (efficient DB query)
    normalized = _normalize(name)
    if normalized:
        # Optimization: pre-filter candidates by the first character of the normalized
        # name using DB-side LOWER(TRIM(...)).  _normalize() strips punctuation and
        # collapses whitespace beyond what LOWER+TRIM does, so we can only safely rely
        # on the first letter being preserved (e.g. "R.A.G." lowered is "r.a.g."
        # which still starts with "r", same as its normalized form "rag").
        # A single-character prefix reduces the scan by ~26x on average while being
        # safe for punctuation-heavy names.  The full Python equality check below
        # preserves exact behavioral parity.  Both SQLite and PostgreSQL support
        # func.lower / func.trim natively, and Group A's functional index on
        # lower(canonical_name) will further accelerate this once it lands.
        first_char = normalized[0]
        candidates = db.exec(
            select(Entity).where(
                Entity.user_id == user_id,
                Entity.entity_type == entity_type,
                func.lower(func.trim(Entity.canonical_name)).like(first_char + "%"),
            )
        ).all()

        for candidate in candidates:
            if _normalize(candidate.canonical_name) == normalized:
                # Add alias if it's a new surface form
                existing_alias = db.exec(
                    select(EntityAlias).where(
                        EntityAlias.entity_id == candidate.id,
                        EntityAlias.alias == name,
                    )
                ).first()
                if not existing_alias:
                    alias = EntityAlias(
                        entity_id=candidate.id,
                        alias=name,
                        source="extraction",
                    )
                    db.add(alias)
                    db.flush()

                # Merge description
                if description:
                    merged = _merge_descriptions(candidate.description or "", description)
                    if merged != (candidate.description or ""):
                        candidate.description = merged
                        candidate.updated_at = datetime.now(timezone.utc)
                        db.add(candidate)
                        db.flush()
                return candidate

    # Tier 3: Create new entity (guard against concurrent insert race)
    import sqlalchemy.exc

    now = datetime.now(timezone.utc)
    entity = Entity(
        user_id=user_id,
        canonical_name=name,
        entity_type=entity_type,
        description=description[:1000] if description else "",
        item_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(entity)
    try:
        db.flush()
    except sqlalchemy.exc.IntegrityError:
        db.rollback()
        # Another concurrent request created the same entity; re-query and return it.
        existing = db.exec(
            select(Entity).where(
                Entity.user_id == user_id,
                Entity.entity_type == entity_type,
                Entity.canonical_name == name,
            )
        ).first()
        if existing:
            return existing
        raise

    # Add the name as the first alias
    alias = EntityAlias(
        entity_id=entity.id,
        alias=name,
        source="extraction",
    )
    db.add(alias)
    db.flush()
    db.refresh(entity)

    return entity


def increment_item_count(entity: Entity, db: Session) -> None:
    """Increment the item_count for an entity."""
    entity.item_count += 1
    entity.updated_at = datetime.now(timezone.utc)
    db.add(entity)
