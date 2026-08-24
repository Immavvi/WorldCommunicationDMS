"""harden historical document snapshots

Revision ID: a12f4d8c91e0
Revises: 555bdb93d194
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a12f4d8c91e0"
down_revision: str | None = "555bdb93d194"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HEADER_TABLES = (
    "purchase_orders",
    "proforma_invoices",
    "tax_invoices",
    "supply_challans",
)


def upgrade() -> None:
    for table in HEADER_TABLES:
        op.add_column(table, sa.Column("project_name_snapshot", sa.String(255)))
        op.add_column(table, sa.Column("project_work_reference_snapshot", sa.String(255)))
        op.add_column(table, sa.Column("loa_number_snapshot", sa.String(100)))
        op.add_column(table, sa.Column("loa_date_snapshot", sa.Date()))
        op.add_column(table, sa.Column("railway_zone_snapshot", sa.String(300)))
        op.add_column(table, sa.Column("railway_division_snapshot", sa.String(300)))
    for name in (
        "project_name_snapshot",
        "project_work_reference_snapshot",
        "loa_number_snapshot",
    ):
        length = 100 if name == "loa_number_snapshot" else 255
        op.add_column("quotations", sa.Column(name, sa.String(length)))
    op.add_column("quotations", sa.Column("loa_date_snapshot", sa.Date()))

    op.add_column(
        "purchase_orders", sa.Column("procurement_requirement_number_snapshot", sa.String(50))
    )
    op.add_column("purchase_orders", sa.Column("vendor_gstin_snapshot", sa.String(15)))
    op.add_column("purchase_orders", sa.Column("vendor_address_snapshot", sa.JSON()))

    for table in (
        "purchase_order_lines",
        "proforma_invoice_lines",
        "tax_invoice_lines",
        "supply_challan_lines",
    ):
        op.add_column(table, sa.Column("oem_snapshot", sa.String(255)))
        op.add_column(table, sa.Column("model_snapshot", sa.String(255)))
    op.add_column("proforma_invoice_lines", sa.Column("challan_number_snapshot", sa.String(50)))
    op.add_column("proforma_invoice_lines", sa.Column("challan_date_snapshot", sa.Date()))
    op.add_column("tax_invoice_lines", sa.Column("pi_number_snapshot", sa.String(50)))
    op.add_column("tax_invoice_lines", sa.Column("pi_date_snapshot", sa.Date()))
    op.add_column("tax_invoice_lines", sa.Column("challan_number_snapshot", sa.String(50)))
    op.add_column("tax_invoice_lines", sa.Column("challan_date_snapshot", sa.Date()))


def downgrade() -> None:
    for name in (
        "challan_date_snapshot",
        "challan_number_snapshot",
        "pi_date_snapshot",
        "pi_number_snapshot",
    ):
        op.drop_column("tax_invoice_lines", name)
    for name in ("challan_date_snapshot", "challan_number_snapshot"):
        op.drop_column("proforma_invoice_lines", name)
    for table in (
        "supply_challan_lines",
        "tax_invoice_lines",
        "proforma_invoice_lines",
        "purchase_order_lines",
    ):
        op.drop_column(table, "model_snapshot")
        op.drop_column(table, "oem_snapshot")
    for name in (
        "vendor_address_snapshot",
        "vendor_gstin_snapshot",
        "procurement_requirement_number_snapshot",
    ):
        op.drop_column("purchase_orders", name)
    for name in (
        "loa_date_snapshot",
        "loa_number_snapshot",
        "project_work_reference_snapshot",
        "project_name_snapshot",
    ):
        op.drop_column("quotations", name)
    for table in reversed(HEADER_TABLES):
        for name in (
            "railway_division_snapshot",
            "railway_zone_snapshot",
            "loa_date_snapshot",
            "loa_number_snapshot",
            "project_work_reference_snapshot",
            "project_name_snapshot",
        ):
            op.drop_column(table, name)
