"""add instance_settings.admin_bootstrapped flag

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-22 12:00:00.000000

Adds a boolean flag to the `instance_settings` singleton so we can atomically
claim the "first user becomes admin" slot via a conditional UPDATE. Without
this, two concurrent POST /auth/register calls could both observe
`COUNT(users) == 0` and both become admin (race window is small but real on
fresh deployments). The conditional UPDATE ensures exactly one caller wins.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent — SQLModel.metadata.create_all() on a fresh DB may already
    # have added the column if the model was updated before migration ran.
    if not _column_exists(bind, "instance_settings", "admin_bootstrapped"):
        op.add_column(
            "instance_settings",
            sa.Column(
                "admin_bootstrapped",
                sa.Boolean(),
                nullable=False,
                # sa.false() renders as ``false`` on PostgreSQL and ``0`` on
                # SQLite — using sa.text("0") would fail on PG where Boolean
                # rejects integer literals.
                server_default=sa.false(),
            ),
        )
    # Existing deployments: if any admin already exists, flip the flag so we
    # don't let another registrant claim admin after upgrading. Use the SQL
    # standard ``TRUE``/``FALSE`` values rendered by SQLAlchemy so the
    # statement is portable; both SQLite (which treats TRUE=1) and PostgreSQL
    # accept these.
    bind.execute(
        sa.text(
            "UPDATE instance_settings SET admin_bootstrapped = :t "
            "WHERE EXISTS (SELECT 1 FROM users WHERE role = 'admin')"
        ).bindparams(t=True)
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "instance_settings", "admin_bootstrapped"):
        op.drop_column("instance_settings", "admin_bootstrapped")
