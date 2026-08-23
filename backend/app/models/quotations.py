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


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint("quotation_number", "revision_number", name="uq_quotation_revision"),
        CheckConstraint("business_scope IN ('RAILWAY','NON_RAILWAY')", name="ck_quotation_scope"),
        CheckConstraint("tax_mode IN ('INTRA_STATE','INTER_STATE')", name="ck_quotation_tax_mode"),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','ISSUED','ACCEPTED',"
            "'REJECTED','EXPIRED','CANCELLED')",
            name="ck_quotation_status",
        ),
        CheckConstraint("revision_number >= 0", name="ck_quotation_revision"),
        CheckConstraint(
            "validity_date IS NULL OR validity_date >= quotation_date", name="ck_quotation_validity"
        ),
        Index("ix_quotations_customer", "customer_party_id"),
        Index("ix_quotations_project", "project_id"),
        Index("ix_quotations_number_latest", "quotation_number", "is_latest"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quotation_number: Mapped[str] = mapped_column(String(50))
    revision_number: Mapped[int] = mapped_column(default=0)
    previous_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id"))
    is_latest: Mapped[bool] = mapped_column(default=True, server_default="true")
    quotation_date: Mapped[date] = mapped_column(Date)
    validity_date: Mapped[date | None] = mapped_column(Date)
    customer_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    business_scope: Mapped[str] = mapped_column(String(20))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    railway_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("railway_zones.id"))
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
    gst_registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gst_registrations.id"))
    payment_term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_terms.id"))
    terms_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms_condition_versions.id")
    )
    enquiry_reference: Mapped[str | None] = mapped_column(String(255))
    enquiry_date: Mapped[date | None] = mapped_column(Date)
    subject: Mapped[str] = mapped_column(String(500))
    tax_mode: Mapped[str] = mapped_column(String(20))
    place_of_supply_state: Mapped[str] = mapped_column(String(100))
    place_of_supply_state_code: Mapped[str] = mapped_column(String(2))
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
    organization_gst_snapshot: Mapped[dict] = mapped_column(JSON)
    customer_snapshot: Mapped[dict] = mapped_column(JSON)
    customer_gst_snapshot: Mapped[dict | None] = mapped_column(JSON)
    zone_snapshot: Mapped[dict | None] = mapped_column(JSON)
    division_snapshot: Mapped[dict | None] = mapped_column(JSON)
    authority_snapshot: Mapped[dict | None] = mapped_column(JSON)
    bill_to_snapshot: Mapped[dict] = mapped_column(JSON)
    ship_to_snapshot: Mapped[dict | None] = mapped_column(JSON)
    place_of_supply_snapshot: Mapped[dict] = mapped_column(JSON)
    payment_terms_snapshot: Mapped[dict | None] = mapped_column(JSON)
    terms_snapshot: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationLine(Base):
    __tablename__ = "quotation_lines"
    __table_args__ = (
        UniqueConstraint("quotation_id", "line_number", name="uq_quotation_line_number"),
        CheckConstraint("quantity > 0", name="ck_quotation_line_quantity"),
        CheckConstraint("quoted_rate >= 0", name="ck_quotation_line_rate"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"))
    line_number: Mapped[int] = mapped_column()
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_models.id"))
    oem_party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    description_snapshot: Mapped[str] = mapped_column(String(2000))
    oem_snapshot: Mapped[str | None] = mapped_column(String(255))
    model_snapshot: Mapped[str | None] = mapped_column(String(255))
    hsn_snapshot: Mapped[str | None] = mapped_column(String(20))
    unit_snapshot: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quoted_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cgst_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    sgst_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    igst_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    quotation: Mapped[Quotation] = relationship(back_populates="lines")
