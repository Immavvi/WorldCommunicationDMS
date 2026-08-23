from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementLineCreate(BaseModel):
    product_id: UUID | None = None
    product_model_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    hsn_code_id: UUID | None = None
    unit_id: UUID
    required_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    loa_item_id: UUID | None = None
    variation_line_id: UUID | None = None
    remarks: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def one_contract_source(self):
        if self.loa_item_id and self.variation_line_id:
            raise ValueError("Only one contractual source may be selected.")
        return self


class RequirementCreate(BaseModel):
    project_id: UUID
    loa_id: UUID | None = None
    requirement_date: date
    required_by_date: date | None = None
    remarks: str | None = Field(default=None, max_length=2000)
    lines: list[RequirementLineCreate] = Field(min_length=1)


class RequirementUpdate(BaseModel):
    required_by_date: date | None = None
    remarks: str | None = Field(default=None, max_length=2000)


class RequirementLineResponse(RequirementLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_number: int


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    requirement_number: str
    project_id: UUID
    loa_id: UUID | None
    requested_by_user_id: UUID
    requirement_date: date
    required_by_date: date | None
    remarks: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    lines: list[RequirementLineResponse]


class PoLineCreate(BaseModel):
    requirement_line_id: UUID | None = None
    product_id: UUID | None = None
    product_model_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    hsn_code_id: UUID | None = None
    unit_id: UUID
    ordered_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=7, decimal_places=4
    )
    cgst_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=7, decimal_places=4
    )
    sgst_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=7, decimal_places=4
    )
    igst_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=7, decimal_places=4
    )
    loa_item_id: UUID | None = None
    variation_line_id: UUID | None = None
    remarks: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def one_contract_source(self):
        if self.loa_item_id and self.variation_line_id:
            raise ValueError("Only one contractual source may be selected.")
        return self


class PurchaseOrderCreate(BaseModel):
    po_date: date
    vendor_party_id: UUID
    project_id: UUID
    loa_id: UUID | None = None
    procurement_requirement_id: UUID | None = None
    organization_id: UUID
    billing_organization_address_id: UUID
    ship_to_organization_address_id: UUID | None = None
    ship_to_party_address_id: UUID | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    payment_term_id: UUID | None = None
    terms_version_id: UUID | None = None
    tax_mode: str = Field(pattern="^(INTRA_STATE|INTER_STATE)$")
    delivery_date: date | None = None
    special_instructions: str | None = Field(default=None, max_length=10000)
    terms_override_text: str | None = Field(default=None, max_length=50000)
    round_off: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-0.99"),
        le=Decimal("0.99"),
        max_digits=3,
        decimal_places=2,
    )
    lines: list[PoLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def one_ship_to(self):
        selected = bool(self.ship_to_organization_address_id) + bool(self.ship_to_party_address_id)
        if selected != 1:
            raise ValueError("Select exactly one saved ship-to address.")
        return self


class PoLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_number: int
    requirement_line_id: UUID | None
    product_id: UUID | None
    product_model_id: UUID | None
    description: str
    hsn_code: str | None
    unit_id: UUID
    unit_snapshot: str
    ordered_quantity: Decimal
    unit_rate: Decimal
    discount_percent: Decimal
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_percent: Decimal
    sgst_percent: Decimal
    igst_percent: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    line_total: Decimal
    loa_item_id: UUID | None
    variation_line_id: UUID | None
    remarks: str | None


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    po_number: str
    po_date: date
    vendor_party_id: UUID
    project_id: UUID
    loa_id: UUID | None
    procurement_requirement_id: UUID | None
    organization_id: UUID
    billing_organization_address_id: UUID
    ship_to_organization_address_id: UUID | None
    ship_to_party_address_id: UUID | None
    currency: str
    payment_term_id: UUID | None
    terms_version_id: UUID | None
    tax_mode: str
    delivery_date: date | None
    special_instructions: str | None
    terms_override_text: str | None
    status: str
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    round_off: Decimal
    grand_total: Decimal
    vendor_snapshot: dict
    organization_snapshot: dict
    billing_address_snapshot: dict
    shipping_address_snapshot: dict
    payment_terms_snapshot: dict | None
    terms_snapshot: dict | None
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[PoLineResponse]


class WorkflowAction(BaseModel):
    action: str = Field(pattern="^(SUBMIT|APPROVE|ISSUE|REJECT|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class CommitmentResponse(BaseModel):
    contractual_item_id: UUID
    origin: str
    approved_quantity: Decimal
    committed_quantity: Decimal
    remaining_quantity: Decimal
