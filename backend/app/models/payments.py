import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CustomerPayment(Base):
    __tablename__ = "customer_payments"
    __table_args__ = (
        CheckConstraint("amount_received > 0", name="ck_customer_payments_amount"),
        CheckConstraint(
            "payment_mode IN ('BANK_TRANSFER','NEFT','RTGS','IMPS','UPI','CHEQUE','CASH','OTHER')",
            name="ck_customer_payments_mode",
        ),
        CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','CANCELLED','REVERSED')",
            name="ck_customer_payments_status",
        ),
        Index("ix_customer_payments_customer_date", "customer_party_id", "receipt_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True)
    receipt_date: Mapped[date] = mapped_column(Date)
    customer_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_accounts.id"))
    payment_mode: Mapped[str] = mapped_column(String(30))
    transaction_reference: Mapped[str | None] = mapped_column(String(255))
    transaction_date: Mapped[date | None] = mapped_column(Date)
    amount_received: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    organization_snapshot: Mapped[dict] = mapped_column(JSON)
    bank_snapshot: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="ck_payment_allocations_amount"),
        UniqueConstraint("payment_id", "tax_invoice_id", name="uq_payment_invoice_allocation"),
        Index("ix_payment_allocations_invoice", "tax_invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_payments.id", ondelete="CASCADE")
    )
    tax_invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tax_invoices.id"))
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    allocation_date: Mapped[date] = mapped_column(Date)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    invoice_number_snapshot: Mapped[str] = mapped_column(String(50))
    project_snapshot: Mapped[str | None] = mapped_column(String(255))
    loa_snapshot: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payment: Mapped[CustomerPayment] = relationship(back_populates="allocations")
