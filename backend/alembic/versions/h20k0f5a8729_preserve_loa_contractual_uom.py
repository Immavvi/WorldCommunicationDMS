"""preserve LOA contractual UOM and source provenance

Revision ID: h20k0f5a8729
Revises: h20j9e4f7618
"""

import sqlalchemy as sa

from alembic import op

revision = "h20k0f5a8729"
down_revision = "h20j9e4f7618"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("loa_items", "unit_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("loa_items", sa.Column("unit_text", sa.String(100), nullable=True))
    op.add_column("loa_items", sa.Column("source_page", sa.Integer(), nullable=True))
    op.add_column("loa_items", sa.Column("source_serial", sa.String(50), nullable=True))
    op.add_column("loa_items", sa.Column("source_raw_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("loa_items", "source_raw_text")
    op.drop_column("loa_items", "source_serial")
    op.drop_column("loa_items", "source_page")
    op.drop_column("loa_items", "unit_text")
    op.alter_column("loa_items", "unit_id", existing_type=sa.UUID(), nullable=False)
