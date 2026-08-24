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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NumberingSeries(Base):
    __tablename__ = "numbering_series"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_type: Mapped[str] = mapped_column(String(30), unique=True)
    prefix: Mapped[str] = mapped_column(String(20))
    next_number: Mapped[int] = mapped_column(Integer, default=1)
    padding: Mapped[int] = mapped_column(Integer, default=6)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcurementRequirement(Base):
    __tablename__ = "procurement_requirements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED','CANCELLED')",
            name="ck_procurement_requirement_status",
        ),
        Index("ix_procurement_requirements_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    requirement_number: Mapped[str] = mapped_column(String(50), unique=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    requirement_date: Mapped[date] = mapped_column(Date)
    required_by_date: Mapped[date | None] = mapped_column(Date)
    remarks: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lines: Mapped[list["ProcurementRequirementLine"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )


class ProcurementRequirementLine(Base):
    __tablename__ = "procurement_requirement_lines"
    __table_args__ = (
        CheckConstraint("required_quantity > 0", name="ck_procurement_requirement_line_quantity"),
        CheckConstraint(
            "NOT (loa_item_id IS NOT NULL AND variation_line_id IS NOT NULL)",
            name="ck_procurement_requirement_single_contract_source",
        ),
        Index("ix_procurement_requirement_lines_requirement", "requirement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procurement_requirements.id", ondelete="CASCADE")
    )
    line_number: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_models.id"))
    description: Mapped[str] = mapped_column(String(2000))
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hsn_codes.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units_of_measure.id"))
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    loa_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loa_items.id"))
    variation_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("loa_variation_lines.id")
    )
    remarks: Mapped[str | None] = mapped_column(String(1000))
    requirement: Mapped[ProcurementRequirement] = relationship(back_populates="lines")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','ISSUED',"
            "'PARTIALLY_FULFILLED','FULFILLED','REJECTED','CANCELLED')",
            name="ck_purchase_order_status",
        ),
        CheckConstraint(
            "tax_mode IN ('INTRA_STATE','INTER_STATE')", name="ck_purchase_order_tax_mode"
        ),
        CheckConstraint(
            "(ship_to_organization_address_id IS NOT NULL) <> "
            "(ship_to_party_address_id IS NOT NULL)",
            name="ck_purchase_order_single_ship_to",
        ),
        Index("ix_purchase_orders_project", "project_id"),
        Index("ix_purchase_orders_loa", "loa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(String(50), unique=True)
    po_date: Mapped[date] = mapped_column(Date)
    vendor_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    procurement_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("procurement_requirements.id")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    billing_organization_address_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization_addresses.id")
    )
    ship_to_organization_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_addresses.id")
    )
    ship_to_party_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("party_addresses.id")
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    payment_term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_terms.id"))
    terms_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms_condition_versions.id")
    )
    tax_mode: Mapped[str] = mapped_column(String(20))
    delivery_date: Mapped[date | None] = mapped_column(Date)
    special_instructions: Mapped[str | None] = mapped_column(Text)
    terms_override_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", server_default="DRAFT")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    round_off: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    vendor_snapshot: Mapped[dict] = mapped_column(JSON)
    organization_snapshot: Mapped[dict] = mapped_column(JSON)
    organization_gst_snapshot: Mapped[dict | None] = mapped_column(JSON)
    billing_address_snapshot: Mapped[dict] = mapped_column(JSON)
    shipping_address_snapshot: Mapped[dict] = mapped_column(JSON)
    payment_terms_snapshot: Mapped[dict | None] = mapped_column(JSON)
    terms_snapshot: Mapped[dict | None] = mapped_column(JSON)
    project_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    project_work_reference_snapshot: Mapped[str | None] = mapped_column(String(255))
    loa_number_snapshot: Mapped[str | None] = mapped_column(String(100))
    loa_date_snapshot: Mapped[date | None] = mapped_column(Date)
    railway_zone_snapshot: Mapped[str | None] = mapped_column(String(300))
    railway_division_snapshot: Mapped[str | None] = mapped_column(String(300))
    procurement_requirement_number_snapshot: Mapped[str | None] = mapped_column(String(50))
    vendor_gstin_snapshot: Mapped[str | None] = mapped_column(String(15))
    vendor_address_snapshot: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "line_number", name="uq_purchase_order_line_number"),
        CheckConstraint("ordered_quantity > 0", name="ck_purchase_order_line_quantity"),
        CheckConstraint(
            "unit_rate >= 0 AND discount_percent >= 0 AND discount_percent <= 100",
            name="ck_purchase_order_line_rates",
        ),
        CheckConstraint(
            "NOT (loa_item_id IS NOT NULL AND variation_line_id IS NOT NULL)",
            name="ck_purchase_order_line_single_contract_source",
        ),
        Index("ix_purchase_order_lines_contract", "loa_item_id", "variation_line_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE")
    )
    line_number: Mapped[int] = mapped_column(Integer)
    requirement_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("procurement_requirement_lines.id")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_models.id"))
    description: Mapped[str] = mapped_column(String(2000))
    hsn_code: Mapped[str | None] = mapped_column(String(20))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units_of_measure.id"))
    unit_snapshot: Mapped[str] = mapped_column(String(100))
    oem_snapshot: Mapped[str | None] = mapped_column(String(255))
    model_snapshot: Mapped[str | None] = mapped_column(String(255))
    ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cgst_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    sgst_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    igst_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    loa_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loa_items.id"))
    variation_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("loa_variation_lines.id")
    )
    remarks: Mapped[str | None] = mapped_column(String(1000))
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
