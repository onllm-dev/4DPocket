"""add item_chunk section provenance columns

Revision ID: a1b2c3d4e5f6
Revises: 375487e8618a
Create Date: 2026-04-13 13:30:00.000000

Adds nullable section-aware columns to ``item_chunks`` so chunks can
remember which structured section (post, comment, transcript_segment,
page, …) they came from. Enables filtering and snippet rendering.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "375487e8618a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_COLUMNS = (
    ("section_id", sa.String(length=64), True),
    ("section_kind", sa.String(length=32), True),
    ("section_role", sa.String(length=32), True),
    ("parent_section_id", sa.String(length=64), True),
    ("page_no", sa.Integer(), True),
    ("timestamp_start_s", sa.Float(), True),
    ("author", sa.String(length=255), True),
    ("is_accepted_answer", sa.Boolean(), False),
)


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent — skip columns that the metadata-create_all path may have
    # already added on a fresh DB.
    for name, col_type, nullable in _NEW_COLUMNS:
        if _column_exists(bind, "item_chunks", name):
            continue
        default = sa.text("0") if name == "is_accepted_answer" else None
        op.add_column(
            "item_chunks",
            sa.Column(name, col_type, nullable=nullable, server_default=default),
        )

    if not _column_exists(bind, "item_chunks", "heading_path"):
        op.add_column("item_chunks", sa.Column("heading_path", sa.JSON(), nullable=True))

    # Drop the temporary server_default for the boolean — model owns it now.
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("item_chunks") as batch:
            batch.alter_column("is_accepted_answer", server_default=None)

    # Helpful indexes for filter queries (kind:comment, role:main, author:@x)
    inspector = sa.inspect(bind)
    existing = {ix["name"] for ix in inspector.get_indexes("item_chunks")}
    for col in ("section_id", "section_kind", "section_role", "author"):
        ix_name = f"ix_item_chunks_{col}"
        if ix_name not in existing:
            op.create_index(ix_name, "item_chunks", [col])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {ix["name"] for ix in inspector.get_indexes("item_chunks")}
    for col in ("section_id", "section_kind", "section_role", "author"):
        ix_name = f"ix_item_chunks_{col}"
        if ix_name in existing:
            op.drop_index(ix_name, table_name="item_chunks")

    for name, _ct, _nullable in _NEW_COLUMNS:
        if _column_exists(bind, "item_chunks", name):
            op.drop_column("item_chunks", name)
    if _column_exists(bind, "item_chunks", "heading_path"):
        op.drop_column("item_chunks", "heading_path")
