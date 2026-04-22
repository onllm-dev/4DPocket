"""wave3_cleanup: cascade FKs, tz-aware datetimes, collection unique constraint

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-23 12:00:00.000000

Changes:
a. entity_relations.user_id, source_id, target_id — drop + recreate FKs with ondelete=CASCADE
b. embeddings.item_id — drop + recreate FK with ondelete=CASCADE
c. llm_cache.created_at — alter column to DateTime(timezone=True)
d. rate_limits.locked_until, last_attempt — alter columns to DateTime(timezone=True)
e. collections — add UniqueConstraint(user_id, name)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── a. entity_relations: cascade FKs for user_id, source_id, target_id ────
    with op.batch_alter_table("entity_relations", schema=None) as batch_op:
        # Drop existing FKs if present (the previous migration added user_id FK)
        try:
            batch_op.drop_constraint("fk_entity_relations_user_id_users", type_="foreignkey")
        except Exception:
            pass
        batch_op.create_foreign_key(
            "fk_entity_relations_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_entity_relations_source_id_entities",
            "entities",
            ["source_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_entity_relations_target_id_entities",
            "entities",
            ["target_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # ── b. embeddings.item_id: cascade FK ────────────────────────────────────
    with op.batch_alter_table("embeddings", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_embeddings_item_id_knowledge_items",
            "knowledge_items",
            ["item_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # ── c. llm_cache.created_at: timezone-aware ───────────────────────────────
    with op.batch_alter_table("llm_cache", schema=None) as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

    # ── d. rate_limits: timezone-aware datetime columns ───────────────────────
    with op.batch_alter_table("rate_limits", schema=None) as batch_op:
        batch_op.alter_column(
            "locked_until",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "last_attempt",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

    # ── e. collections: unique constraint on (user_id, name) ─────────────────
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_collection_user_name", ["user_id", "name"])


def downgrade() -> None:
    # ── e. drop collections unique constraint ─────────────────────────────────
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.drop_constraint("uq_collection_user_name", type_="unique")

    # ── d. rate_limits: revert to non-timezone-aware ──────────────────────────
    # Note: SQLite will silently accept DateTime() columns regardless; the
    # timezone flag is effectively a Postgres-only semantic difference.
    with op.batch_alter_table("rate_limits", schema=None) as batch_op:
        batch_op.alter_column(
            "last_attempt",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "locked_until",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    # ── c. llm_cache: revert timezone ────────────────────────────────────────
    with op.batch_alter_table("llm_cache", schema=None) as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    # ── b. drop embeddings cascade FK ────────────────────────────────────────
    with op.batch_alter_table("embeddings", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_embeddings_item_id_knowledge_items", type_="foreignkey"
        )

    # ── a. entity_relations: drop cascade FKs, restore plain user_id FK ──────
    with op.batch_alter_table("entity_relations", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_entity_relations_target_id_entities", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_entity_relations_source_id_entities", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_entity_relations_user_id_users", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_entity_relations_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
