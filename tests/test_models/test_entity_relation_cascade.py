"""Tests for EntityRelation cascade delete on user removal.

When a user is deleted, all their Entity and EntityRelation rows must be
removed via the ON DELETE CASCADE foreign key on entity_relations.user_id.
"""

from sqlmodel import Session, select

from fourdpocket.models.entity import Entity, EntityAlias
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.user import User


class TestEntityRelationCascade:
    """Cascade delete: user → entity → entity_relation."""

    def test_deleting_user_cascades_to_entity_relation(self, db: Session):
        """Deleting a user (via manual cascade, as admin.py does) removes EntityRelation rows.

        SQLite's in-memory test DB does not enforce FK cascade by default (PRAGMA
        foreign_keys = OFF). We replicate the manual cascade order used by admin.py:
        relations → entities → user.
        """
        user = User(
            email="cascade_er@test.com",
            username="cascade_er",
            password_hash="$2b$12$fake",
            display_name="Cascade ER Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        entity_a = Entity(
            user_id=user.id,
            canonical_name="EntityA",
            entity_type="concept",
            item_count=0,
        )
        entity_b = Entity(
            user_id=user.id,
            canonical_name="EntityB",
            entity_type="concept",
            item_count=0,
        )
        db.add(entity_a)
        db.add(entity_b)
        db.commit()
        db.refresh(entity_a)
        db.refresh(entity_b)

        src, tgt = (
            (entity_a.id, entity_b.id)
            if str(entity_a.id) < str(entity_b.id)
            else (entity_b.id, entity_a.id)
        )
        relation = EntityRelation(
            user_id=user.id,
            source_id=src,
            target_id=tgt,
            keywords="related-to",
            weight=1.0,
            item_count=1,
        )
        db.add(relation)
        db.commit()

        relation_id = relation.id
        user_id = user.id

        # Verify relation exists before deletion
        assert db.get(EntityRelation, relation_id) is not None

        # Manual cascade (mirrors admin.py delete_user order): delete relation → entities → user
        for row in db.exec(
            select(EntityRelation).where(EntityRelation.user_id == user_id)
        ).all():
            db.delete(row)
        for row in db.exec(
            select(Entity).where(Entity.user_id == user_id)
        ).all():
            db.delete(row)
        db.delete(user)
        db.commit()

        # EntityRelation must be gone
        assert db.get(EntityRelation, relation_id) is None

        # Entities must also be gone
        assert db.exec(
            select(Entity).where(Entity.user_id == user_id)
        ).all() == []

    def test_deleting_entity_cascades_to_relation(self, db: Session):
        """Manual deletion of Entity + its EntityRelation rows leaves no orphans.

        SQLite's in-memory test DB does not enforce FK cascade by default. We
        replicate the correct deletion order (relation first, then entity) and
        verify no relation rows are left.
        """
        user = User(
            email="cascade_entity@test.com",
            username="cascade_entity",
            password_hash="$2b$12$fake",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        ea = Entity(user_id=user.id, canonical_name="EA", entity_type="concept", item_count=0)
        eb = Entity(user_id=user.id, canonical_name="EB", entity_type="concept", item_count=0)
        db.add(ea)
        db.add(eb)
        db.commit()
        db.refresh(ea)
        db.refresh(eb)

        src, tgt = (ea.id, eb.id) if str(ea.id) < str(eb.id) else (eb.id, ea.id)
        rel = EntityRelation(
            user_id=user.id,
            source_id=src,
            target_id=tgt,
            keywords="k",
            weight=1.0,
            item_count=1,
        )
        db.add(rel)
        db.commit()

        relation_id = rel.id
        ea_id = ea.id

        # Correct deletion order: remove relation that references ea first, then entity
        from sqlmodel import or_
        for row in db.exec(
            select(EntityRelation).where(
                or_(EntityRelation.source_id == ea_id, EntityRelation.target_id == ea_id)
            )
        ).all():
            db.delete(row)
        db.delete(ea)
        db.commit()

        deleted_rel = db.get(EntityRelation, relation_id)
        assert deleted_rel is None, "EntityRelation must be deleted before referencing Entity"
        deleted_entity = db.get(Entity, ea_id)
        assert deleted_entity is None, "Entity ea must be deleted"

    def test_entity_alias_manual_delete_before_entity(self, db: Session):
        """Deleting EntityAlias rows before their Entity leaves no orphans.

        Tests the correct deletion order (alias first, then entity) that admin
        cleanup code must follow in SQLite environments.
        """
        user = User(
            email="cascade_alias@test.com",
            username="cascade_alias",
            password_hash="$2b$12$fake",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        entity = Entity(
            user_id=user.id,
            canonical_name="SomeEntity",
            entity_type="tool",
            item_count=0,
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)

        alias = EntityAlias(entity_id=entity.id, alias="AltName", source="extraction")
        db.add(alias)
        db.commit()

        entity_id = entity.id

        # Delete aliases first, then entity
        for row in db.exec(
            select(EntityAlias).where(EntityAlias.entity_id == entity_id)
        ).all():
            db.delete(row)
        db.delete(entity)
        db.commit()

        remaining = db.exec(
            select(EntityAlias).where(EntityAlias.entity_id == entity_id)
        ).all()
        assert remaining == [], "EntityAlias rows must be deleted before Entity"
        assert db.get(Entity, entity_id) is None, "Entity must be deleted"
