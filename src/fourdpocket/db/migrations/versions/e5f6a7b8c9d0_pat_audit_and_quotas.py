"""pat_audit_and_quotas: add pat_events and user_quotas tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-23 13:00:00.000000

Changes:
a. create table pat_events  (audit trail per PAT action)
b. create table user_quotas (per-user resource caps)

Note: The project's initial-schema migration uses SQLModel.metadata.create_all
so that a fresh install of the latest code already has all tables. This migration
is the idempotent incremental form for existing installations that were deployed
before these tables were added.  Each CREATE is guarded by _table_exists().
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(bind, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    for table in inspector.get_table_names():
        for idx in inspector.get_indexes(table):
            if idx["name"] == index_name:
                return True
    return False


def upgrade() -> None:
    bind = op.get_bind()

    # ── a. pat_events ─────────────────────────────────────────────────────────
    if not _table_exists(bind, "pat_events"):
        op.create_table(
            "pat_events",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column(
                "pat_id",
                sa.Uuid(),
                sa.ForeignKey("api_tokens.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("resource", sa.String(), nullable=True),
            sa.Column("ip", sa.String(), nullable=True),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
        )

    if not _index_exists(bind, "ix_pat_events_pat_id"):
        op.create_index("ix_pat_events_pat_id", "pat_events", ["pat_id"])
    if not _index_exists(bind, "ix_pat_events_user_id"):
        op.create_index("ix_pat_events_user_id", "pat_events", ["user_id"])
    if not _index_exists(bind, "ix_pat_events_created_at"):
        op.create_index("ix_pat_events_created_at", "pat_events", ["created_at"])

    # ── b. user_quotas ────────────────────────────────────────────────────────
    if not _table_exists(bind, "user_quotas"):
        op.create_table(
            "user_quotas",
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("items_max", sa.Integer(), nullable=True),
            sa.Column("storage_bytes_max", sa.Integer(), nullable=True),
            sa.Column("daily_api_calls_max", sa.Integer(), nullable=True),
            sa.Column("daily_api_calls_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "daily_window_start",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column("items_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("storage_bytes_used", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "user_quotas"):
        op.drop_table("user_quotas")

    if _index_exists(bind, "ix_pat_events_created_at"):
        op.drop_index("ix_pat_events_created_at", table_name="pat_events")
    if _index_exists(bind, "ix_pat_events_user_id"):
        op.drop_index("ix_pat_events_user_id", table_name="pat_events")
    if _index_exists(bind, "ix_pat_events_pat_id"):
        op.drop_index("ix_pat_events_pat_id", table_name="pat_events")

    if _table_exists(bind, "pat_events"):
        op.drop_table("pat_events")
