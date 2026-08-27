"""add loa reconciliation metadata

Revision ID: h20g6b1c4385
Revises: h20f5a0b3274
"""

import sqlalchemy as sa

from alembic import op

revision = "h20g6b1c4385"
down_revision = "h20f5a0b3274"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "railway_divisions",
        sa.Column("customer_party_id", sa.Uuid(), sa.ForeignKey("parties.id")),
    )
    op.add_column(
        "railway_loa_imports",
        sa.Column("project_candidates", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "railway_loa_imports",
        sa.Column("authority_candidates", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "railway_loa_imports",
        sa.Column("boq_reconciliation", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("railway_loa_imports", sa.Column("completion_date_provenance", sa.String(30)))
    op.add_column("railway_loa_import_lines", sa.Column("source_page", sa.Integer()))
    op.add_column("railway_loa_import_lines", sa.Column("source_serial", sa.String(50)))
    op.add_column("railway_loa_import_lines", sa.Column("source_raw_text", sa.Text()))
    op.add_column(
        "railway_loa_import_lines",
        sa.Column(
            "extraction_outcome",
            sa.String(30),
            nullable=False,
            server_default="EXTRACTED",
        ),
    )
    op.add_column("railway_loa_import_lines", sa.Column("extraction_issue", sa.String(1000)))
    op.create_check_constraint(
        "ck_loa_import_line_outcome",
        "railway_loa_import_lines",
        "extraction_outcome IN ('EXTRACTED','NEEDS_REVIEW','REJECTED_WITH_REASON',"
        "'EXPLICITLY_IGNORED_BY_OWNER')",
    )


def downgrade():
    op.drop_constraint("ck_loa_import_line_outcome", "railway_loa_import_lines")
    for column in (
        "extraction_issue",
        "extraction_outcome",
        "source_raw_text",
        "source_serial",
        "source_page",
    ):
        op.drop_column("railway_loa_import_lines", column)
    for column in (
        "completion_date_provenance",
        "boq_reconciliation",
        "authority_candidates",
        "project_candidates",
    ):
        op.drop_column("railway_loa_imports", column)
    op.drop_column("railway_divisions", "customer_party_id")
