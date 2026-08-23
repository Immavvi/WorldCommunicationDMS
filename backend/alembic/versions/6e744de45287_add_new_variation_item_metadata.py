"""add new variation item metadata

Revision ID: 6e744de45287
Revises: 09d2dfe5b375
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "6e744de45287"
down_revision: Union[str, Sequence[str], None] = "09d2dfe5b375"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loa_variation_lines", sa.Column("product_id", sa.Uuid(), nullable=True))
    op.add_column("loa_variation_lines", sa.Column("hsn_code_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_variation_lines_product",
        "loa_variation_lines",
        "products",
        ["product_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_variation_lines_hsn_code",
        "loa_variation_lines",
        "hsn_codes",
        ["hsn_code_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_variation_lines_hsn_code", "loa_variation_lines", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_variation_lines_product", "loa_variation_lines", type_="foreignkey"
    )
    op.drop_column("loa_variation_lines", "hsn_code_id")
    op.drop_column("loa_variation_lines", "product_id")
