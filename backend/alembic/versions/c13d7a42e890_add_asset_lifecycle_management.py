"""add asset lifecycle management

Revision ID: c13d7a42e890
Revises: b62a19e7d405
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c13d7a42e890"
down_revision: str | None = "b62a19e7d405"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "tracking_class",
            sa.String(20),
            nullable=False,
            server_default="QUANTITY_TRACKED",
        ),
    )
    op.create_check_constraint(
        "ck_products_tracking_class",
        "products",
        "tracking_class IN ('SERIALIZED','QUANTITY_TRACKED','NON_STOCK')",
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_number", sa.String(50), nullable=False, unique=True),
        sa.Column("manufacturer_serial_number", sa.String(255), nullable=False),
        sa.Column("normalized_serial", sa.String(255), nullable=False),
        sa.Column("internal_tag", sa.String(100), unique=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_snapshot", sa.String(2000), nullable=False),
        sa.Column("oem_party_id", sa.Uuid(), sa.ForeignKey("parties.id")),
        sa.Column("oem_snapshot", sa.String(255)),
        sa.Column("product_model_id", sa.Uuid(), sa.ForeignKey("product_models.id")),
        sa.Column("model_snapshot", sa.String(255)),
        sa.Column("vendor_party_id", sa.Uuid(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column(
            "purchase_order_id", sa.Uuid(), sa.ForeignKey("purchase_orders.id"), nullable=False
        ),
        sa.Column(
            "purchase_order_line_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_order_lines.id"),
            nullable=False,
        ),
        sa.Column(
            "material_receipt_id", sa.Uuid(), sa.ForeignKey("material_receipts.id"), nullable=False
        ),
        sa.Column(
            "material_receipt_line_id",
            sa.Uuid(),
            sa.ForeignKey("material_receipt_lines.id"),
            nullable=False,
        ),
        sa.Column("receipt_date_snapshot", sa.Date(), nullable=False),
        sa.Column("source_project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_loa_id", sa.Uuid(), sa.ForeignKey("loas.id")),
        sa.Column("project_snapshot", sa.String(255), nullable=False),
        sa.Column("loa_snapshot", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False, server_default="REGISTERED"),
        sa.Column("current_project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("current_railway_zone_id", sa.Uuid(), sa.ForeignKey("railway_zones.id")),
        sa.Column("current_railway_division_id", sa.Uuid(), sa.ForeignKey("railway_divisions.id")),
        sa.Column("current_railway_location_id", sa.Uuid(), sa.ForeignKey("railway_locations.id")),
        sa.Column("current_site", sa.String(255)),
        sa.Column("current_building", sa.String(255)),
        sa.Column("current_room", sa.String(255)),
        sa.Column("current_rack", sa.String(100)),
        sa.Column("current_position", sa.String(100)),
        sa.Column("installation_date", sa.Date()),
        sa.Column("warranty_type", sa.String(100)),
        sa.Column("warranty_reference", sa.String(255)),
        sa.Column("warranty_start_date", sa.Date()),
        sa.Column("warranty_duration_months", sa.Integer()),
        sa.Column("warranty_expiry_date", sa.Date()),
        sa.Column("warranty_provider_party_id", sa.Uuid(), sa.ForeignKey("parties.id")),
        sa.Column("warranty_remarks", sa.Text()),
        sa.Column("replacement_asset_id", sa.Uuid(), sa.ForeignKey("assets.id")),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('REGISTERED','AVAILABLE','ALLOCATED','DISPATCHED','DELIVERED',"
            "'INSTALLED','IN_SERVICE','UNDER_REPAIR','RETURNED','REPLACED','RETIRED',"
            "'DISPOSED','LOST','DAMAGED','CANCELLED')",
            name="ck_assets_status",
        ),
        sa.UniqueConstraint("normalized_serial", name="uq_assets_normalized_serial"),
    )
    op.create_index("ix_assets_product", "assets", ["product_id"])
    op.create_index("ix_assets_project_status", "assets", ["current_project_id", "status"])
    op.create_index("ix_assets_warranty_expiry", "assets", ["warranty_expiry_date"])
    op.create_table(
        "asset_lifecycle_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "asset_id", sa.Uuid(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("from_location_snapshot", sa.Text()),
        sa.Column("to_location_snapshot", sa.Text()),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("railway_zone_id", sa.Uuid(), sa.ForeignKey("railway_zones.id")),
        sa.Column("railway_division_id", sa.Uuid(), sa.ForeignKey("railway_divisions.id")),
        sa.Column("railway_location_id", sa.Uuid(), sa.ForeignKey("railway_locations.id")),
        sa.Column("supply_challan_id", sa.Uuid(), sa.ForeignKey("supply_challans.id")),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("remarks", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_asset_events_asset_date", "asset_lifecycle_events", ["asset_id", "event_at"]
    )
    op.create_table(
        "challan_asset_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "supply_challan_line_id",
            sa.Uuid(),
            sa.ForeignKey("supply_challan_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("asset_id", name="uq_challan_asset_assignment_asset"),
        sa.UniqueConstraint("supply_challan_line_id", "asset_id", name="uq_challan_line_asset"),
    )
    op.create_index(
        "ix_challan_asset_assignments_line", "challan_asset_assignments", ["supply_challan_line_id"]
    )
    op.execute(
        sa.text(
            "INSERT INTO numbering_series (id, document_type, prefix, next_number, padding) "
            "VALUES (:id, 'ASSET', 'AST-', 1, 6)"
        ).bindparams(id=uuid.uuid4())
    )


def downgrade() -> None:
    op.execute("DELETE FROM numbering_series WHERE document_type = 'ASSET'")
    op.drop_table("challan_asset_assignments")
    op.drop_table("asset_lifecycle_events")
    op.drop_table("assets")
    op.drop_constraint("ck_products_tracking_class", "products", type_="check")
    op.drop_column("products", "tracking_class")
