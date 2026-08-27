"""add loa date provenance

Revision ID: h20h7c2d5496
Revises: h20g6b1c4385
"""

import sqlalchemy as sa

from alembic import op

revision = "h20h7c2d5496"
down_revision = "h20g6b1c4385"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("railway_loa_imports", sa.Column("loa_date_provenance", sa.String(30)))
    op.add_column("railway_loa_imports", sa.Column("loa_date_source", sa.String(255)))


def downgrade():
    op.drop_column("railway_loa_imports", "loa_date_source")
    op.drop_column("railway_loa_imports", "loa_date_provenance")
