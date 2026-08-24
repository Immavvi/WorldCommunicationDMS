"""add user administration metadata

Revision ID: g17d3e8f1052
Revises: f15c2d7e9041
"""

import sqlalchemy as sa

from alembic import op

revision = "g17d3e8f1052"
down_revision = "f15c2d7e9041"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("display_name", sa.String(255)))
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")))


def downgrade():
    op.drop_column("users", "created_by_user_id")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "display_name")
