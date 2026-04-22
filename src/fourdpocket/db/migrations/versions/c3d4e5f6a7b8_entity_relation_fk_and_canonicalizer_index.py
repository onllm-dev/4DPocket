"""entity_relation user_id FK + canonicalizer lower index

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-22 12:00:00.000000

a. Add proper FK + ondelete=CASCADE on entity_relations.user_id → users.id.
   Uses op.batch_alter_table so SQLite (which cannot ALTER FK in-place) works.
b. Create index ix_entities_lower_canonical_name on LOWER(canonical_name) to
   speed up the 3-tier entity canonicalizer's case-insensitive lookups.
   On PostgreSQL a functional index is created directly; on SQLite op.execute
   is used (SQLite supports functional index syntax since 3.9).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "ix_entities_lower_canonical_name"


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    # ── a. entity_relations.user_id FK ──────────────────────────────────────
    with op.batch_alter_table("entity_relations", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_entity_relations_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # ── b. LOWER(canonical_name) index on entities ───────────────────────────
    dialect = _dialect_name()
    if dialect == "postgresql":
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
                "ON entities (LOWER(canonical_name) text_pattern_ops)"
            )
        )
    else:
        # SQLite 3.9+ supports functional indexes via CREATE INDEX
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {_INDEX_NAME} "
                "ON entities (LOWER(canonical_name))"
            )
        )


def downgrade() -> None:
    # ── b. drop LOWER index ──────────────────────────────────────────────────
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_INDEX_NAME}"))

    # ── a. drop entity_relations.user_id FK ─────────────────────────────────
    with op.batch_alter_table("entity_relations", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_entity_relations_user_id_users",
            type_="foreignkey",
        )
