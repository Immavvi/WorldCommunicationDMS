import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
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


class MasterRecord:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AddressFields:
    label: Mapped[str] = mapped_column(String(100))
    address_line_1: Mapped[str] = mapped_column(String(255))
    address_line_2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    state_code: Mapped[str | None] = mapped_column(String(2))
    postal_code: Mapped[str] = mapped_column(String(10))
    country: Mapped[str] = mapped_column(String(100), default="India", server_default="India")
    contact_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(320))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Organization(MasterRecord, Base):
    __tablename__ = "organizations"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    pan: Mapped[str | None] = mapped_column(String(10), unique=True)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(30))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    addresses: Mapped[list["OrganizationAddress"]] = relationship(back_populates="organization")


class OrganizationAddress(AddressFields, MasterRecord, Base):
    __tablename__ = "organization_addresses"
    __table_args__ = (
        CheckConstraint(
            "address_type IN ('REGISTERED','OFFICE','BILL_TO','SHIP_TO')",
            name="ck_organization_addresses_type",
        ),
        Index("ix_organization_addresses_organization", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    address_type: Mapped[str] = mapped_column(String(20))
    organization: Mapped[Organization] = relationship(back_populates="addresses")


class Party(MasterRecord, Base):
    __tablename__ = "parties"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    pan: Mapped[str | None] = mapped_column(String(10))
    business_scope: Mapped[str] = mapped_column(
        String(20), default="NON_RAILWAY", server_default="NON_RAILWAY"
    )
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(30))

    roles: Mapped[list["PartyRole"]] = relationship(
        back_populates="party", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["PartyAddress"]] = relationship(back_populates="party")


class PartyRole(Base):
    __tablename__ = "party_roles"
    __table_args__ = (
        CheckConstraint("role IN ('CUSTOMER','VENDOR','OEM')", name="ck_party_roles_role"),
    )

    party_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parties.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    party: Mapped[Party] = relationship(back_populates="roles")


class PartyAddress(AddressFields, MasterRecord, Base):
    __tablename__ = "party_addresses"
    __table_args__ = (
        CheckConstraint(
            "address_type IN ('REGISTERED','BILL_TO','SHIP_TO','CONSIGNEE','OTHER')",
            name="ck_party_addresses_type",
        ),
        Index("ix_party_addresses_party", "party_id"),
    )

    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    address_type: Mapped[str] = mapped_column(String(20))
    party: Mapped[Party] = relationship(back_populates="addresses")


class GstRegistration(MasterRecord, Base):
    __tablename__ = "gst_registrations"
    __table_args__ = (
        CheckConstraint(
            "(organization_id IS NOT NULL AND party_id IS NULL) OR "
            "(organization_id IS NULL AND party_id IS NOT NULL)",
            name="ck_gst_registrations_single_owner",
        ),
        UniqueConstraint("gstin", name="uq_gst_registrations_gstin"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    gstin: Mapped[str] = mapped_column(String(15))
    registered_name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(100))
    state_code: Mapped[str] = mapped_column(String(2))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class BankAccount(MasterRecord, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "account_number", name="uq_bank_account"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    account_name: Mapped[str] = mapped_column(String(255))
    bank_name: Mapped[str] = mapped_column(String(255))
    branch_name: Mapped[str | None] = mapped_column(String(255))
    account_number: Mapped[str] = mapped_column(String(50))
    account_type: Mapped[str | None] = mapped_column(String(50))
    ifsc: Mapped[str] = mapped_column(String(11))
    swift: Mapped[str | None] = mapped_column(String(11))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class RailwayZone(MasterRecord, Base):
    __tablename__ = "railway_zones"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class RailwayDivision(MasterRecord, Base):
    __tablename__ = "railway_divisions"
    __table_args__ = (UniqueConstraint("zone_id", "code", name="uq_railway_division_code"),)

    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("railway_zones.id"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))


class RailwayLocation(MasterRecord, Base):
    __tablename__ = "railway_locations"
    __table_args__ = (UniqueConstraint("division_id", "code", name="uq_railway_location_code"),)

    division_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("railway_divisions.id"))
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(255))
    location_type: Mapped[str | None] = mapped_column(String(50))


class RailwayAuthority(MasterRecord, Base):
    __tablename__ = "railway_authorities"

    division_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("railway_divisions.id"))
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("railway_locations.id"))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    designation: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(30))
    roles: Mapped[list["RailwayAuthorityRole"]] = relationship(
        back_populates="authority", cascade="all, delete-orphan"
    )


class RailwayAuthorityRole(Base):
    __tablename__ = "railway_authority_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('CONSIGNEE','BILL_TO','SHIP_TO')", name="ck_railway_authority_roles_role"
        ),
    )

    authority_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("railway_authorities.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    authority: Mapped[RailwayAuthority] = relationship(back_populates="roles")


class RailwayAuthorityAddress(AddressFields, MasterRecord, Base):
    __tablename__ = "railway_authority_addresses"

    authority_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("railway_authorities.id"))


class UnitOfMeasure(MasterRecord, Base):
    __tablename__ = "units_of_measure"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    symbol: Mapped[str] = mapped_column(String(20))
    decimal_places: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class HsnCode(MasterRecord, Base):
    __tablename__ = "hsn_codes"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str] = mapped_column(String(500))


class TaxRateSet(MasterRecord, Base):
    __tablename__ = "tax_rate_sets"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_tax_dates"
        ),
    )

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    components: Mapped[list["TaxRateComponent"]] = relationship(
        back_populates="tax_rate_set", cascade="all, delete-orphan"
    )


class TaxRateComponent(Base):
    __tablename__ = "tax_rate_components"
    __table_args__ = (
        CheckConstraint("component IN ('CGST','SGST','IGST')", name="ck_tax_component"),
        CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_component_rate"),
    )

    tax_rate_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tax_rate_sets.id", ondelete="CASCADE"), primary_key=True
    )
    component: Mapped[str] = mapped_column(String(10), primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    tax_rate_set: Mapped[TaxRateSet] = relationship(back_populates="components")


class ProductCategory(MasterRecord, Base):
    __tablename__ = "product_categories"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String(500))


class OemProfile(MasterRecord, Base):
    __tablename__ = "oem_profiles"

    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"), unique=True)
    manufacturer_code: Mapped[str | None] = mapped_column(String(50), unique=True)
    website: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(1000))


class ProductModel(MasterRecord, Base):
    __tablename__ = "product_models"
    __table_args__ = (UniqueConstraint("oem_profile_id", "model_number", name="uq_product_model"),)

    oem_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oem_profiles.id"))
    model_number: Mapped[str] = mapped_column(String(100))
    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000))


class Product(MasterRecord, Base):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    business_scope: Mapped[str] = mapped_column(String(20), default="BOTH", server_default="BOTH")
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_categories.id"))
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_models.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units_of_measure.id"))
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hsn_codes.id"))
    default_tax_rate_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tax_rate_sets.id")
    )
    specifications: Mapped[dict | None] = mapped_column(JSON)


class PaymentTerm(MasterRecord, Base):
    __tablename__ = "payment_terms"
    __table_args__ = (CheckConstraint("due_days IS NULL OR due_days >= 0", name="ck_due_days"),)

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    due_days: Mapped[int | None] = mapped_column(Integer)


class TermsConditionSet(MasterRecord, Base):
    __tablename__ = "terms_condition_sets"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    context: Mapped[str] = mapped_column(String(30))
    versions: Mapped[list["TermsConditionVersion"]] = relationship(back_populates="terms_set")


class TermsConditionVersion(Base):
    __tablename__ = "terms_condition_versions"
    __table_args__ = (UniqueConstraint("terms_set_id", "version", name="uq_terms_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    terms_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms_condition_sets.id"))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    terms_set: Mapped[TermsConditionSet] = relationship(back_populates="versions")


class Project(MasterRecord, Base):
    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    customer_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    business_scope: Mapped[str] = mapped_column(String(20))
    railway_division_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_divisions.id")
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class Loa(MasterRecord, Base):
    __tablename__ = "loas"
    __table_args__ = (UniqueConstraint("project_id", "loa_number", name="uq_project_loa_number"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    loa_number: Mapped[str] = mapped_column(String(100))
    loa_date: Mapped[date] = mapped_column(Date)
    customer_reference: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")
