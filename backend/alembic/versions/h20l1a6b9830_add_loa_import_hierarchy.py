"""add LOA import hierarchy and candidate provenance

Revision ID: h20l1a6b9830
Revises: h20k0f5a8729
"""

import sqlalchemy as sa

from alembic import op

revision = "h20l1a6b9830"
down_revision = "h20k0f5a8729"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "ck_railway_loa_import_method", "railway_loa_imports", type_="check"
    )
    op.create_check_constraint(
        "ck_railway_loa_import_method",
        "railway_loa_imports",
        "extraction_method IS NULL OR extraction_method IN "
        "('XLSX','NATIVE_PDF','OCR','MIXED_PDF')",
    )
    op.create_table(
        "railway_loa_import_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("loa_import_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("title_raw", sa.Text(), nullable=False),
        sa.Column("title_normalized", sa.Text(), nullable=False),
        sa.Column("source_page_start", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("source_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("extracted_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("difference", sa.Numeric(18, 2), nullable=True),
        sa.Column("reconciliation_status", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(
            ["loa_import_id"], ["railway_loa_imports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_railway_loa_import_schedules_loa_import_id",
        "railway_loa_import_schedules",
        ["loa_import_id"],
    )
    op.create_table(
        "railway_loa_import_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("title_raw", sa.Text(), nullable=False),
        sa.Column("title_normalized", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(30), nullable=False),
        sa.Column("source_page_start", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("source_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("extracted_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("difference", sa.Numeric(18, 2), nullable=True),
        sa.Column("reconciliation_status", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["railway_loa_import_schedules.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_railway_loa_import_groups_schedule_id",
        "railway_loa_import_groups",
        ["schedule_id"],
    )
    for name, column in (
        ("candidate_key", sa.String(100)),
        ("source_order", sa.Integer()),
        ("group_id", sa.UUID()),
        ("item_code", sa.String(50)),
        ("description_raw", sa.Text()),
        ("description_normalized", sa.Text()),
        ("uom_raw", sa.String(100)),
        ("uom_normalized", sa.String(100)),
        ("source_page_start", sa.Integer()),
        ("source_page_end", sa.Integer()),
        ("extraction_method", sa.String(20)),
        ("extraction_confidence", sa.Numeric(5, 4)),
        ("extraction_issues", sa.JSON()),
    ):
        op.add_column("railway_loa_import_lines", sa.Column(name, column, nullable=True))
    op.create_foreign_key(
        "fk_railway_loa_import_lines_group_id",
        "railway_loa_import_lines",
        "railway_loa_import_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_railway_loa_import_lines_group_id",
        "railway_loa_import_lines",
        ["group_id"],
    )


def downgrade():
    op.drop_index(
        "ix_railway_loa_import_lines_group_id", table_name="railway_loa_import_lines"
    )
    op.drop_constraint(
        "fk_railway_loa_import_lines_group_id",
        "railway_loa_import_lines",
        type_="foreignkey",
    )
    for name in (
        "extraction_issues",
        "extraction_confidence",
        "extraction_method",
        "source_page_end",
        "source_page_start",
        "uom_normalized",
        "uom_raw",
        "description_normalized",
        "description_raw",
        "item_code",
        "group_id",
        "source_order",
        "candidate_key",
    ):
        op.drop_column("railway_loa_import_lines", name)
    op.drop_index(
        "ix_railway_loa_import_groups_schedule_id",
        table_name="railway_loa_import_groups",
    )
    op.drop_table("railway_loa_import_groups")
    op.drop_index(
        "ix_railway_loa_import_schedules_loa_import_id",
        table_name="railway_loa_import_schedules",
    )
    op.drop_table("railway_loa_import_schedules")
    op.drop_constraint(
        "ck_railway_loa_import_method", "railway_loa_imports", type_="check"
    )
    op.create_check_constraint(
        "ck_railway_loa_import_method",
        "railway_loa_imports",
        "extraction_method IS NULL OR extraction_method IN ('XLSX','NATIVE_PDF','OCR')",
    )
