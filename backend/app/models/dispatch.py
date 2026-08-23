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


class SupplyChallan(Base):
    __tablename__ = "supply_challans"
    __table_args__ = (
        CheckConstraint(
            "business_scope IN ('RAILWAY','NON_RAILWAY')", name="ck_challan_business_scope"
        ),
        CheckConstraint(
            "status IN ('DRAFT','READY','DISPATCHED','DELIVERED','ACKNOWLEDGED','CANCELLED')",
            name="ck_challan_status",
        ),
        Index("ix_supply_challans_project", "project_id"),
        Index("ix_supply_challans_loa", "loa_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challan_number: Mapped[str] = mapped_column(String(50), unique=True)
    challan_date: Mapped[date] = mapped_column(Date)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    business_scope: Mapped[str] = mapped_column(String(20))
    customer_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    railway_division_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_divisions.id")
    )
    consignee_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_authorities.id")
    )
    bill_to_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_authorities.id")
    )
    ship_to_railway_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_authority_addresses.id")
    )
    ship_to_party_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("party_addresses.id")
    )
    dispatch_from_address_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_addresses.id")
    )
    transporter: Mapped[str | None] = mapped_column(String(255))
    vehicle_number: Mapped[str | None] = mapped_column(String(50))
    transport_reference: Mapped[str | None] = mapped_column(String(255))
    eway_bill_reference: Mapped[str | None] = mapped_column(String(255))
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    special_instructions: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    division_snapshot: Mapped[dict | None] = mapped_column(JSON)
    consignee_snapshot: Mapped[dict | None] = mapped_column(JSON)
    delivery_address_snapshot: Mapped[dict] = mapped_column(JSON)
    dispatch_from_snapshot: Mapped[dict] = mapped_column(JSON)
    organization_snapshot: Mapped[dict] = mapped_column(JSON)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_date: Mapped[date | None] = mapped_column(Date)
    receiving_authority_text: Mapped[str | None] = mapped_column(String(255))
    acknowledgement_reference: Mapped[str | None] = mapped_column(String(255))
    acknowledgement_remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lines: Mapped[list["SupplyChallanLine"]] = relationship(
        back_populates="challan", cascade="all, delete-orphan"
    )


class SupplyChallanLine(Base):
    __tablename__ = "supply_challan_lines"
    __table_args__ = (
        UniqueConstraint("supply_challan_id", "line_number", name="uq_challan_line_number"),
        CheckConstraint("dispatched_quantity > 0", name="ck_challan_line_quantity"),
        CheckConstraint(
            "NOT (loa_item_id IS NOT NULL AND variation_line_id IS NOT NULL)",
            name="ck_challan_line_single_contract_source",
        ),
        Index("ix_challan_lines_contract", "loa_item_id", "variation_line_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supply_challan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supply_challans.id", ondelete="CASCADE")
    )
    line_number: Mapped[int] = mapped_column()
    loa_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loa_items.id"))
    variation_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("loa_variation_lines.id")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description_snapshot: Mapped[str] = mapped_column(String(2000))
    hsn_snapshot: Mapped[str | None] = mapped_column(String(20))
    unit_snapshot: Mapped[str] = mapped_column(String(100))
    dispatched_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    challan: Mapped[SupplyChallan] = relationship(back_populates="lines")
    allocations: Mapped[list["ChallanReceiptAllocation"]] = relationship(
        back_populates="challan_line", cascade="all, delete-orphan"
    )


class ChallanReceiptAllocation(Base):
    __tablename__ = "challan_receipt_allocations"
    __table_args__ = (
        UniqueConstraint(
            "challan_line_id", "material_receipt_line_id", name="uq_challan_receipt_allocation"
        ),
        CheckConstraint("allocated_quantity > 0", name="ck_challan_allocation_quantity"),
        Index("ix_challan_allocations_receipt_line", "material_receipt_line_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challan_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supply_challan_lines.id", ondelete="CASCADE")
    )
    material_receipt_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("material_receipt_lines.id")
    )
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    challan_line: Mapped[SupplyChallanLine] = relationship(back_populates="allocations")
