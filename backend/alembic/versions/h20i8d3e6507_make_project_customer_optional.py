"""make project customer optional for railway projects

Revision ID: h20i8d3e6507
Revises: h20h7c2d5496
"""

import sqlalchemy as sa

from alembic import op

revision = "h20i8d3e6507"
down_revision = "h20h7c2d5496"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "projects",
        "customer_party_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "projects",
        "customer_party_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
