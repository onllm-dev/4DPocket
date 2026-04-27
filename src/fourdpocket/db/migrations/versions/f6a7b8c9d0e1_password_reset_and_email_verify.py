"""password_reset_and_email_verify

Adds password_reset_tokens and email_verification_tokens tables and extends
the users table with email_verified, email_verified_at columns.

The initial_schema migration calls SQLModel.metadata.create_all(), which means
on a fresh database these tables already exist by the time this migration runs.
All DDL operations are therefore guarded with existence checks (idempotent).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-23 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    try:
        return column_name in {c["name"] for c in inspector.get_columns(table_name)}
    except Exception:
        return False


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    try:
        return index_name in {i["name"] for i in inspector.get_indexes(table_name)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. users: add email verification columns (idempotent) ────────────────
    with op.batch_alter_table("users", schema=None) as batch_op:
        if not _column_exists(bind, "users", "email_verified"):
            batch_op.add_column(
                sa.Column(
                    "email_verified",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if not _column_exists(bind, "users", "email_verified_at"):
            batch_op.add_column(
                sa.Column(
                    "email_verified_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )
        # password_changed_at was introduced in a previous wave; add idempotently
        if not _column_exists(bind, "users", "password_changed_at"):
            batch_op.add_column(
                sa.Column(
                    "password_changed_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )

    # ── 2. password_reset_tokens (idempotent) ─────────────────────────────────
    if not _table_exists(bind, "password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("token_hash", name="uq_prt_token_hash"),
        )
    if not _index_exists(bind, "password_reset_tokens", "ix_prt_token_hash"):
        op.create_index("ix_prt_token_hash", "password_reset_tokens", ["token_hash"])
    if not _index_exists(bind, "password_reset_tokens", "ix_prt_user_id"):
        op.create_index("ix_prt_user_id", "password_reset_tokens", ["user_id"])
    if not _index_exists(bind, "password_reset_tokens", "ix_prt_expires_at"):
        op.create_index("ix_prt_expires_at", "password_reset_tokens", ["expires_at"])

    # ── 3. email_verification_tokens (idempotent) ─────────────────────────────
    if not _table_exists(bind, "email_verification_tokens"):
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("token_hash", name="uq_evt_token_hash"),
        )
    if not _index_exists(bind, "email_verification_tokens", "ix_evt_token_hash"):
        op.create_index("ix_evt_token_hash", "email_verification_tokens", ["token_hash"])
    if not _index_exists(bind, "email_verification_tokens", "ix_evt_user_id"):
        op.create_index("ix_evt_user_id", "email_verification_tokens", ["user_id"])
    if not _index_exists(bind, "email_verification_tokens", "ix_evt_expires_at"):
        op.create_index("ix_evt_expires_at", "email_verification_tokens", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "email_verification_tokens", "ix_evt_expires_at"):
        op.drop_index("ix_evt_expires_at", table_name="email_verification_tokens")
    if _index_exists(bind, "email_verification_tokens", "ix_evt_user_id"):
        op.drop_index("ix_evt_user_id", table_name="email_verification_tokens")
    if _index_exists(bind, "email_verification_tokens", "ix_evt_token_hash"):
        op.drop_index("ix_evt_token_hash", table_name="email_verification_tokens")
    if _table_exists(bind, "email_verification_tokens"):
        op.drop_table("email_verification_tokens")

    if _index_exists(bind, "password_reset_tokens", "ix_prt_expires_at"):
        op.drop_index("ix_prt_expires_at", table_name="password_reset_tokens")
    if _index_exists(bind, "password_reset_tokens", "ix_prt_user_id"):
        op.drop_index("ix_prt_user_id", table_name="password_reset_tokens")
    if _index_exists(bind, "password_reset_tokens", "ix_prt_token_hash"):
        op.drop_index("ix_prt_token_hash", table_name="password_reset_tokens")
    if _table_exists(bind, "password_reset_tokens"):
        op.drop_table("password_reset_tokens")

    with op.batch_alter_table("users", schema=None) as batch_op:
        if _column_exists(bind, "users", "email_verified_at"):
            batch_op.drop_column("email_verified_at")
        if _column_exists(bind, "users", "email_verified"):
            batch_op.drop_column("email_verified")
