"""add customer payments and receivable allocations

Revision ID: e14a7b92c301
Revises: c13d7a42e890
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e14a7b92c301"
down_revision: str | None = "c13d7a42e890"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("receipt_number", sa.String(50), nullable=False, unique=True),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("customer_party_id", sa.Uuid(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), sa.ForeignKey("bank_accounts.id")),
        sa.Column("payment_mode", sa.String(30), nullable=False),
        sa.Column("transaction_reference", sa.String(255)),
        sa.Column("transaction_date", sa.Date()),
        sa.Column("amount_received", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("customer_snapshot", sa.JSON(), nullable=False),
        sa.Column("organization_snapshot", sa.JSON(), nullable=False),
        sa.Column("bank_snapshot", sa.JSON()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversal_reason", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount_received > 0", name="ck_customer_payments_amount"),
        sa.CheckConstraint(
            "payment_mode IN ('BANK_TRANSFER','NEFT','RTGS','IMPS','UPI','CHEQUE','CASH','OTHER')",
            name="ck_customer_payments_mode",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','CANCELLED','REVERSED')",
            name="ck_customer_payments_status",
        ),
    )
    op.create_index(
        "ix_customer_payments_customer_date",
        "customer_payments",
        ["customer_party_id", "receipt_date"],
    )
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Uuid(),
            sa.ForeignKey("customer_payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tax_invoice_id", sa.Uuid(), sa.ForeignKey("tax_invoices.id"), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocation_date", sa.Date(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("remarks", sa.String(1000)),
        sa.Column("invoice_number_snapshot", sa.String(50), nullable=False),
        sa.Column("project_snapshot", sa.String(255)),
        sa.Column("loa_snapshot", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("allocated_amount > 0", name="ck_payment_allocations_amount"),
        sa.UniqueConstraint("payment_id", "tax_invoice_id", name="uq_payment_invoice_allocation"),
    )
    op.create_index("ix_payment_allocations_invoice", "payment_allocations", ["tax_invoice_id"])
    op.execute(
        sa.text(
            "INSERT INTO numbering_series "
            "(id, document_type, prefix, next_number, padding) "
            "VALUES (:id, 'CUSTOMER_RECEIPT', 'RCT-', 1, 6)"
        ).bindparams(id=uuid.uuid4())
    )


def downgrade() -> None:
    op.execute("DELETE FROM numbering_series WHERE document_type = 'CUSTOMER_RECEIPT'")
    op.drop_table("payment_allocations")
    op.drop_table("customer_payments")
