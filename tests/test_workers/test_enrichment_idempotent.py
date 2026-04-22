"""Regression test: re-enriching the same item must not double-increment
entity relation weight/item_count.

Root cause: _store_extraction() incremented weight+item_count on every call
when the EntityRelation already existed, regardless of whether a
RelationEvidence row for (relation_id, item_id) was already present.

Fixed in: src/fourdpocket/workers/enrichment_pipeline.py (_store_extraction)
"""


import pytest
from sqlmodel import Session, select

from fourdpocket.models.entity_relation import EntityRelation, RelationEvidence
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.workers.enrichment_pipeline import _store_extraction

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _make_extraction_result(source_name: str, target_name: str):
    """Build a minimal ExtractionResult with one entity pair and one relation."""
    from fourdpocket.ai.extractor import ExtractedEntity, ExtractedRelation, ExtractionResult

    return ExtractionResult(
        entities=[
            ExtractedEntity(name=source_name, entity_type="concept", description=""),
            ExtractedEntity(name=target_name, entity_type="concept", description=""),
        ],
        relations=[
            ExtractedRelation(
                source=source_name,
                target=target_name,
                keywords="test",
                description="test relation",
            )
        ],
    )


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def idem_user(db: Session):
    user = User(
        email="idem_enrich@example.com",
        username="idemuseridem",
        password_hash="$2b$12$fakehash",
        display_name="Idempotent Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def idem_item(db: Session, idem_user):
    item = KnowledgeItem(
        user_id=idem_user.id,
        title="Idempotency Test Article",
        content="Alpha and Beta are related concepts.",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ─── Tests ─────────────────────────────────────────────────────────────────────

class TestRelationIncrementIdempotency:
    def test_first_enrichment_creates_relation_with_weight_one(
        self, db: Session, idem_user, idem_item
    ):
        """Initial _store_extraction sets weight=1, item_count=1."""
        result = _make_extraction_result("Alpha", "Beta")
        _store_extraction(db, idem_item.id, idem_user.id, None, result)
        db.commit()

        rel = db.exec(select(EntityRelation).where(EntityRelation.user_id == idem_user.id)).first()
        assert rel is not None
        assert rel.weight == 1.0
        assert rel.item_count == 1

    def test_re_enrichment_does_not_double_increment(
        self, db: Session, idem_user, idem_item
    ):
        """Re-running _store_extraction for the same item must NOT increase
        weight or item_count beyond their initial values.

        Regression for: entity relation double-increment on re-enrichment.
        """
        result = _make_extraction_result("Alpha", "Beta")

        # First enrichment
        _store_extraction(db, idem_item.id, idem_user.id, None, result)
        db.commit()

        # Second enrichment (same item, same entities/relations — simulates replay)
        _store_extraction(db, idem_item.id, idem_user.id, None, result)
        db.commit()

        rel = db.exec(select(EntityRelation).where(EntityRelation.user_id == idem_user.id)).first()
        assert rel is not None, "Relation should still exist after re-enrichment"
        assert rel.weight == 1.0, f"Expected weight=1.0, got {rel.weight} (double-increment bug)"
        assert rel.item_count == 1, f"Expected item_count=1, got {rel.item_count} (double-increment bug)"

    def test_re_enrichment_does_not_create_duplicate_evidence(
        self, db: Session, idem_user, idem_item
    ):
        """RelationEvidence rows must remain exactly one per (relation, item)
        even after multiple _store_extraction calls."""
        result = _make_extraction_result("Alpha", "Beta")

        _store_extraction(db, idem_item.id, idem_user.id, None, result)
        db.commit()
        _store_extraction(db, idem_item.id, idem_user.id, None, result)
        db.commit()

        rel = db.exec(select(EntityRelation).where(EntityRelation.user_id == idem_user.id)).first()
        evidence_rows = db.exec(
            select(RelationEvidence).where(RelationEvidence.relation_id == rel.id)
        ).all()
        assert len(evidence_rows) == 1, (
            f"Expected 1 RelationEvidence row, got {len(evidence_rows)}"
        )

    def test_different_item_still_increments(
        self, db: Session, idem_user, idem_item
    ):
        """A second *different* item contributing the same relation SHOULD
        increment weight and item_count."""
        second_item = KnowledgeItem(
            user_id=idem_user.id,
            title="Second Article",
            content="Alpha and Beta appear here too.",
        )
        db.add(second_item)
        db.commit()
        db.refresh(second_item)

        result = _make_extraction_result("Alpha", "Beta")

        _store_extraction(db, idem_item.id, idem_user.id, None, result)
        db.commit()
        _store_extraction(db, second_item.id, idem_user.id, None, result)
        db.commit()

        rel = db.exec(select(EntityRelation).where(EntityRelation.user_id == idem_user.id)).first()
        assert rel is not None
        assert rel.weight == 2.0, f"Expected weight=2.0 for two distinct items, got {rel.weight}"
        assert rel.item_count == 2, f"Expected item_count=2 for two distinct items, got {rel.item_count}"
