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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaterialReceipt(Base):
    __tablename__ = "material_receipts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','RECEIVED','VERIFIED','CANCELLED')",
            name="ck_material_receipt_status",
        ),
        Index("ix_material_receipts_po", "purchase_order_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"))
    vendor_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    receipt_date: Mapped[date] = mapped_column(Date)
    vendor_invoice_reference: Mapped[str | None] = mapped_column(String(255))
    delivery_reference: Mapped[str | None] = mapped_column(String(255))
    receiving_location: Mapped[str] = mapped_column(String(255))
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remarks: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    po_number_snapshot: Mapped[str] = mapped_column(String(50))
    vendor_snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lines: Mapped[list["MaterialReceiptLine"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class MaterialReceiptLine(Base):
    __tablename__ = "material_receipt_lines"
    __table_args__ = (
        UniqueConstraint(
            "material_receipt_id", "purchase_order_line_id", name="uq_receipt_po_line"
        ),
        CheckConstraint(
            "quantity_received >= 0 AND quantity_accepted >= 0 AND quantity_short >= 0 AND "
            "quantity_damaged >= 0 AND quantity_rejected >= 0 AND quantity_excess >= 0",
            name="ck_receipt_line_quantities",
        ),
        CheckConstraint(
            "quantity_received = quantity_accepted + quantity_damaged + quantity_rejected",
            name="ck_receipt_line_physical_total",
        ),
        Index("ix_material_receipt_lines_po_line", "purchase_order_line_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("material_receipts.id", ondelete="CASCADE")
    )
    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_order_lines.id"))
    ordered_quantity_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    previously_accepted_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantity_accepted: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantity_short: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    quantity_damaged: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    quantity_rejected: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    quantity_excess: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description_snapshot: Mapped[str] = mapped_column(String(2000))
    unit_snapshot: Mapped[str] = mapped_column(String(100))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    receipt: Mapped[MaterialReceipt] = relationship(back_populates="lines")
