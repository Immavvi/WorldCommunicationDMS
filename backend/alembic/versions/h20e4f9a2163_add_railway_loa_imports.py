"""add railway loa imports

Revision ID: h20e4f9a2163
Revises: g17d3e8f1052
"""

import sqlalchemy as sa

from alembic import op

revision = "h20e4f9a2163"
down_revision = "g17d3e8f1052"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("loas", "description", existing_type=sa.String(1000), type_=sa.Text())
    op.alter_column("loa_items", "description", existing_type=sa.String(2000), type_=sa.Text())
    op.create_table(
        "railway_loa_imports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("extension", sa.String(10), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="UPLOADED"),
        sa.Column("extraction_method", sa.String(20)),
        sa.Column("extraction_error", sa.String(1000)),
        sa.Column("extraction_warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("railway_zone_id", sa.Uuid(), sa.ForeignKey("railway_zones.id")),
        sa.Column("railway_division_id", sa.Uuid(), sa.ForeignKey("railway_divisions.id")),
        sa.Column("authority_id", sa.Uuid(), sa.ForeignKey("railway_authorities.id")),
        sa.Column("issuing_party_id", sa.Uuid(), sa.ForeignKey("parties.id")),
        sa.Column("loa_id", sa.Uuid(), sa.ForeignKey("loas.id"), unique=True),
        sa.Column("extracted_zone_text", sa.String(255)),
        sa.Column("extracted_division_text", sa.String(255)),
        sa.Column("authority_text", sa.String(500)),
        sa.Column("loa_number", sa.String(100)),
        sa.Column("tender_reference", sa.String(255)),
        sa.Column("loa_date", sa.Date()),
        sa.Column("completion_period", sa.String(255)),
        sa.Column("completion_date", sa.Date()),
        sa.Column("work_description", sa.Text()),
        sa.Column("contract_value", sa.Numeric(18, 2)),
        sa.Column("duplicate_candidates", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("extracted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('UPLOADED','EXTRACTING','NEEDS_REVIEW',"
            "'READY_FOR_APPROVAL','APPROVED','EXTRACTION_FAILED','CANCELLED')",
            name="ck_railway_loa_import_status",
        ),
        sa.CheckConstraint(
            "extraction_method IS NULL OR extraction_method IN ('XLSX','NATIVE_PDF','OCR')",
            name="ck_railway_loa_import_method",
        ),
    )
    op.create_index("ix_railway_loa_import_status", "railway_loa_imports", ["status"])
    op.create_index("ix_railway_loa_import_loa_number", "railway_loa_imports", ["loa_number"])
    op.create_table(
        "railway_loa_import_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "loa_import_id",
            sa.Uuid(),
            sa.ForeignKey("railway_loa_imports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_number", sa.String(50)),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id")),
        sa.Column("description", sa.Text()),
        sa.Column("hsn_text", sa.String(50)),
        sa.Column("hsn_code_id", sa.Uuid(), sa.ForeignKey("hsn_codes.id")),
        sa.Column("unit_text", sa.String(100)),
        sa.Column("unit_id", sa.Uuid(), sa.ForeignKey("units_of_measure.id")),
        sa.Column("quantity", sa.Numeric(18, 4)),
        sa.Column("rate", sa.Numeric(18, 2)),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("oem_make", sa.String(255)),
        sa.Column("model_number", sa.String(255)),
        sa.Column("tax_text", sa.String(255)),
        sa.Column("remarks", sa.String(1000)),
        sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_loa_import_line_quantity"),
        sa.CheckConstraint("rate IS NULL OR rate >= 0", name="ck_loa_import_line_rate"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_loa_import_line_amount"),
    )
    op.create_index(
        "ix_loa_import_lines_import", "railway_loa_import_lines", ["loa_import_id", "line_number"]
    )


def downgrade():
    op.drop_table("railway_loa_import_lines")
    op.drop_table("railway_loa_imports")
    op.alter_column("loa_items", "description", existing_type=sa.Text(), type_=sa.String(2000))
    op.alter_column("loas", "description", existing_type=sa.Text(), type_=sa.String(1000))
