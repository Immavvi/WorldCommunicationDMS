"""harden railway master data

Revision ID: h20j9e4f7618
Revises: h20i8d3e6507
"""

import sqlalchemy as sa

from alembic import op

revision = "h20j9e4f7618"
down_revision = "h20i8d3e6507"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("railway_zones", "railway_divisions", "railway_locations", "railway_authorities"):
        op.add_column(
            table,
            sa.Column("aliases", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        )
    op.drop_constraint(
        "ck_railway_authority_roles_role", "railway_authority_roles", type_="check"
    )
    op.create_check_constraint(
        "ck_railway_authority_roles_role",
        "railway_authority_roles",
        "role IN ('ISSUING_AUTHORITY','EXECUTION_AUTHORITY','CONSIGNEE','BILL_TO','SHIP_TO')",
    )


def downgrade():
    op.drop_constraint(
        "ck_railway_authority_roles_role", "railway_authority_roles", type_="check"
    )
    op.create_check_constraint(
        "ck_railway_authority_roles_role",
        "railway_authority_roles",
        "role IN ('CONSIGNEE','BILL_TO','SHIP_TO')",
    )
    for table in ("railway_authorities", "railway_locations", "railway_divisions", "railway_zones"):
        op.drop_column(table, "aliases")
