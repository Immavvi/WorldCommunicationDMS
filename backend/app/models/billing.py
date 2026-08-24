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


class ProformaInvoice(Base):
    __tablename__ = "proforma_invoices"
    __table_args__ = (
        CheckConstraint("business_scope IN ('RAILWAY','NON_RAILWAY')", name="ck_pi_business_scope"),
        CheckConstraint("tax_mode IN ('INTRA_STATE','INTER_STATE')", name="ck_pi_tax_mode"),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','ISSUED','CANCELLED')", name="ck_pi_status"
        ),
        Index("ix_proforma_invoices_project", "project_id"),
        Index("ix_proforma_invoices_loa", "loa_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pi_number: Mapped[str] = mapped_column(String(50), unique=True)
    pi_date: Mapped[date] = mapped_column(Date)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    customer_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    business_scope: Mapped[str] = mapped_column(String(20))
    railway_division_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_divisions.id")
    )
    railway_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_authorities.id")
    )
    bill_to_party_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("party_addresses.id")
    )
    bill_to_railway_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_authority_addresses.id")
    )
    ship_to_party_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("party_addresses.id")
    )
    ship_to_railway_address_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_authority_addresses.id")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"))
    payment_term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_terms.id"))
    terms_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms_condition_versions.id")
    )
    tax_mode: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    special_instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    round_off: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    amount_in_words: Mapped[str] = mapped_column(String(1000))
    organization_snapshot: Mapped[dict] = mapped_column(JSON)
    organization_gst_snapshot: Mapped[dict | None] = mapped_column(JSON)
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    customer_gst_snapshot: Mapped[dict | None] = mapped_column(JSON)
    division_snapshot: Mapped[dict | None] = mapped_column(JSON)
    authority_snapshot: Mapped[dict | None] = mapped_column(JSON)
    bill_to_snapshot: Mapped[dict] = mapped_column(JSON)
    ship_to_snapshot: Mapped[dict] = mapped_column(JSON)
    bank_snapshot: Mapped[dict] = mapped_column(JSON)
    payment_terms_snapshot: Mapped[dict | None] = mapped_column(JSON)
    terms_snapshot: Mapped[dict | None] = mapped_column(JSON)
    project_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    project_work_reference_snapshot: Mapped[str | None] = mapped_column(String(255))
    loa_number_snapshot: Mapped[str | None] = mapped_column(String(100))
    loa_date_snapshot: Mapped[date | None] = mapped_column(Date)
    railway_zone_snapshot: Mapped[str | None] = mapped_column(String(300))
    railway_division_snapshot: Mapped[str | None] = mapped_column(String(300))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lines: Mapped[list["ProformaInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class ProformaInvoiceLine(Base):
    __tablename__ = "proforma_invoice_lines"
    __table_args__ = (
        UniqueConstraint("proforma_invoice_id", "line_number", name="uq_pi_line_number"),
        CheckConstraint("billable_quantity > 0", name="ck_pi_line_quantity"),
        CheckConstraint(
            "sales_rate >= 0 AND discount_percent >= 0 AND discount_percent <= 100",
            name="ck_pi_line_rates",
        ),
        CheckConstraint(
            "NOT (loa_item_id IS NOT NULL AND variation_line_id IS NOT NULL)",
            name="ck_pi_line_single_contract_source",
        ),
        Index("ix_pi_lines_challan_line", "supply_challan_line_id"),
        Index("ix_pi_lines_contract", "loa_item_id", "variation_line_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proforma_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proforma_invoices.id", ondelete="CASCADE")
    )
    line_number: Mapped[int] = mapped_column()
    supply_challan_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supply_challan_lines.id")
    )
    loa_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loa_items.id"))
    variation_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("loa_variation_lines.id")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description_snapshot: Mapped[str] = mapped_column(String(2000))
    hsn_snapshot: Mapped[str | None] = mapped_column(String(20))
    unit_snapshot: Mapped[str] = mapped_column(String(100))
    oem_snapshot: Mapped[str | None] = mapped_column(String(255))
    model_snapshot: Mapped[str | None] = mapped_column(String(255))
    challan_number_snapshot: Mapped[str | None] = mapped_column(String(50))
    challan_date_snapshot: Mapped[date | None] = mapped_column(Date)
    billable_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    sales_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
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
    remarks: Mapped[str | None] = mapped_column(String(1000))
    invoice: Mapped[ProformaInvoice] = relationship(back_populates="lines")
