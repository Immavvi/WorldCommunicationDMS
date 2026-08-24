"""add commercial GST snapshots

Revision ID: b62a19e7d405
Revises: a12f4d8c91e0
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b62a19e7d405"
down_revision: str | None = "a12f4d8c91e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("organization_gst_snapshot", sa.JSON()))
    op.add_column("proforma_invoices", sa.Column("organization_gst_snapshot", sa.JSON()))
    op.add_column("proforma_invoices", sa.Column("customer_gst_snapshot", sa.JSON()))


def downgrade() -> None:
    op.drop_column("proforma_invoices", "customer_gst_snapshot")
    op.drop_column("proforma_invoices", "organization_gst_snapshot")
    op.drop_column("purchase_orders", "organization_gst_snapshot")
