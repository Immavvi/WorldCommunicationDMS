from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    work_reference: str | None = Field(default=None, max_length=255)
    customer_party_id: UUID
    business_scope: str = Field(pattern="^(RAILWAY|NON_RAILWAY)$")
    railway_zone_id: UUID | None = None
    railway_division_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = Field(default="ACTIVE", pattern="^(DRAFT|ACTIVE|COMPLETED|CLOSED)$")


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    work_reference: str | None = Field(default=None, max_length=255)
    customer_party_id: UUID | None = None
    railway_zone_id: UUID | None = None
    railway_division_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, pattern="^(DRAFT|ACTIVE|COMPLETED|CLOSED)$")


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LoaCreate(BaseModel):
    project_id: UUID
    loa_number: str = Field(min_length=1, max_length=100)
    loa_date: date
    issuing_party_id: UUID | None = None
    railway_division_id: UUID | None = None
    customer_reference: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    original_contract_value: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2
    )
    validity_date: date | None = None
    completion_date: date | None = None
    remarks: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="DRAFT", pattern="^(DRAFT|ACTIVE|COMPLETED|CLOSED)$")


class LoaUpdate(BaseModel):
    issuing_party_id: UUID | None = None
    railway_division_id: UUID | None = None
    customer_reference: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    original_contract_value: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    validity_date: date | None = None
    completion_date: date | None = None
    remarks: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(DRAFT|ACTIVE|COMPLETED|CLOSED)$")


class LoaResponse(LoaCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LoaItemCreate(BaseModel):
    item_number: str = Field(min_length=1, max_length=50)
    product_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    hsn_code_id: UUID | None = None
    unit_id: UUID
    original_approved_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    contractual_rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    remarks: str | None = Field(default=None, max_length=1000)


class LoaItemResponse(LoaItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loa_id: UUID
    original_line_value: Decimal
    created_at: datetime
    updated_at: datetime


class VariationLineCreate(BaseModel):
    loa_item_id: UUID | None = None
    product_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    hsn_code_id: UUID | None = None
    unit_id: UUID
    direction: str = Field(pattern="^(POSITIVE|NEGATIVE)$")
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    remarks: str | None = Field(default=None, max_length=1000)


class VariationLineResponse(VariationLineCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variation_id: UUID
    line_value: Decimal


class VariationCreate(BaseModel):
    reference_number: str = Field(min_length=1, max_length=100)
    variation_date: date
    remarks: str | None = Field(default=None, max_length=2000)
    lines: list[VariationLineCreate] = Field(min_length=1)


class VariationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loa_id: UUID
    reference_number: str
    variation_date: date
    status: str
    remarks: str | None
    created_by_user_id: UUID
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[VariationLineResponse]


class VariationAction(BaseModel):
    action: str = Field(pattern="^(APPROVE|APPLY|REJECT|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class ApprovedPositionLine(BaseModel):
    contractual_item_id: UUID
    origin: str = Field(pattern="^(ORIGINAL_LOA|VARIATION)$")
    loa_item_id: UUID | None
    originating_variation_id: UUID | None = None
    originating_variation_reference: str | None = None
    item_number: str
    product_id: UUID | None = None
    description: str
    hsn_code_id: UUID | None = None
    unit_id: UUID
    original_quantity: Decimal
    positive_variation_quantity: Decimal
    negative_variation_quantity: Decimal
    current_approved_quantity: Decimal
    contractual_rate: Decimal
    original_value: Decimal
    variation_value: Decimal
    current_approved_value: Decimal


class ApprovedPositionResponse(BaseModel):
    loa_id: UUID
    lines: list[ApprovedPositionLine]
    original_total: Decimal
    variation_total: Decimal
    current_approved_total: Decimal
