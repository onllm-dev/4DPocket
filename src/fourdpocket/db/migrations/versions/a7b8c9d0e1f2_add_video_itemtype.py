"""add 'video' value to the itemtype enum

The YouTube processor produces item_type="video", but the Postgres `itemtype`
enum was created without it, so writing a YouTube item failed with
InvalidTextRepresentation and the extraction was silently dropped. SQLite does
not enforce enums, which is why this only surfaced on Postgres.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (and others) store enums as plain text — no type to alter.
        return
    # Postgres forbids ALTER TYPE ... ADD VALUE inside a transaction block,
    # so run it in an autocommit block. IF NOT EXISTS keeps it idempotent.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE itemtype ADD VALUE IF NOT EXISTS 'video'")


def downgrade() -> None:
    # Postgres has no supported way to drop an enum value; intentionally a no-op.
    pass
