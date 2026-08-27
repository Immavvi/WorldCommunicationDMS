from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MasterDataWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    business_scope: str | None = Field(default=None, max_length=20)
    tracking_class: str | None = Field(
        default=None, pattern="^(SERIALIZED|QUANTITY_TRACKED|NON_STOCK)$"
    )
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    pan: str | None = Field(default=None, max_length=10)
    symbol: str | None = Field(default=None, max_length=20)
    decimal_places: int | None = Field(default=None, ge=0, le=6)
    due_days: int | None = Field(default=None, ge=0)
    context: str | None = Field(default=None, max_length=30)
    customer_party_id: UUID | None = None
    organization_id: UUID | None = None
    party_id: UUID | None = None
    zone_id: UUID | None = None
    division_id: UUID | None = None
    location_id: UUID | None = None
    oem_profile_id: UUID | None = None
    project_id: UUID | None = None
    railway_division_id: UUID | None = None
    authority_id: UUID | None = None
    category_id: UUID | None = None
    product_model_id: UUID | None = None
    unit_id: UUID | None = None
    hsn_code_id: UUID | None = None
    default_tax_rate_set_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, max_length=30)
    manufacturer_code: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    model_number: str | None = Field(default=None, max_length=100)
    location_type: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=255)
    effective_from: date | None = None
    effective_to: date | None = None
    account_name: str | None = Field(default=None, max_length=255)
    bank_name: str | None = Field(default=None, max_length=255)
    branch_name: str | None = Field(default=None, max_length=255)
    account_number: str | None = Field(default=None, max_length=50)
    account_type: str | None = Field(default=None, max_length=50)
    ifsc: str | None = Field(default=None, max_length=11)
    swift: str | None = Field(default=None, max_length=11)
    is_default: bool | None = None
    gstin: str | None = Field(default=None, max_length=15)
    registered_name: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, max_length=2)
    loa_number: str | None = Field(default=None, max_length=100)
    loa_date: date | None = None
    customer_reference: str | None = Field(default=None, max_length=255)
    specifications: dict[str, Any] | None = None
    roles: list[str] | None = None
    aliases: list[str] | None = None
    components: dict[str, float] | None = None
    address_type: str | None = Field(default=None, max_length=20)
    label: str | None = Field(default=None, max_length=100)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=10)
    country: str | None = Field(default=None, max_length=100)
    contact_name: str | None = Field(default=None, max_length=150)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({alias.strip() for alias in value if alias.strip()}, key=str.casefold)


class MasterDataResponse(BaseModel):
    id: UUID
    resource: str
    data: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MasterDataListResponse(BaseModel):
    items: list[MasterDataResponse]
    total: int
    offset: int
    limit: int


class TermsVersionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=50000)
    effective_from: date


class TermsVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    terms_set_id: UUID
    version: int
    content: str
    effective_from: date
    created_by_user_id: UUID
    created_at: datetime
