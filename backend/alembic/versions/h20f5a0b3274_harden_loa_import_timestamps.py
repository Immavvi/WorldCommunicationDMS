"""harden loa import timestamps

Revision ID: h20f5a0b3274
Revises: h20e4f9a2163
"""

import sqlalchemy as sa

from alembic import op

revision = "h20f5a0b3274"
down_revision = "h20e4f9a2163"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "railway_loa_imports",
        "uploaded_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "railway_loa_imports",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "railway_loa_imports",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "railway_loa_imports",
        "uploaded_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
