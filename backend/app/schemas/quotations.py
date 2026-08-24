from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuotationLineInput(BaseModel):
    product_id: UUID | None = None
    product_model_id: UUID | None = None
    oem_party_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    hsn_code: str | None = Field(default=None, max_length=20)
    unit_id: UUID | None = None
    unit_text: str | None = Field(default=None, max_length=100)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    quoted_rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
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
    remarks: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def free_text_requirements(self):
        if not self.product_id and (not self.description or not (self.unit_id or self.unit_text)):
            raise ValueError("Free-text lines require description and UOM.")
        return self


class QuotationCreate(BaseModel):
    quotation_date: date
    validity_date: date | None = None
    customer_party_id: UUID
    business_scope: str = Field(pattern="^(RAILWAY|NON_RAILWAY)$")
    project_id: UUID | None = None
    loa_id: UUID | None = None
    railway_zone_id: UUID | None = None
    railway_division_id: UUID | None = None
    railway_authority_id: UUID | None = None
    bill_to_party_address_id: UUID | None = None
    bill_to_railway_address_id: UUID | None = None
    ship_to_party_address_id: UUID | None = None
    ship_to_railway_address_id: UUID | None = None
    organization_id: UUID
    gst_registration_id: UUID
    payment_term_id: UUID | None = None
    terms_version_id: UUID | None = None
    enquiry_reference: str | None = Field(default=None, max_length=255)
    enquiry_date: date | None = None
    subject: str = Field(min_length=1, max_length=500)
    tax_mode: str | None = Field(default=None, pattern="^(INTRA_STATE|INTER_STATE)$")
    place_of_supply_state: str | None = Field(default=None, max_length=100)
    place_of_supply_state_code: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = Field(default=None, max_length=10000)
    special_instructions: str | None = Field(default=None, max_length=10000)
    round_off: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-0.99"),
        le=Decimal("0.99"),
        max_digits=3,
        decimal_places=2,
    )
    lines: list[QuotationLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates_and_tax(self):
        if self.validity_date and self.validity_date < self.quotation_date:
            raise ValueError("Validity date cannot precede quotation date.")
        for line in self.lines:
            if self.tax_mode == "INTRA_STATE" and line.igst_percent:
                raise ValueError("Intra-state quotation cannot include IGST.")
            if self.tax_mode == "INTER_STATE" and (line.cgst_percent or line.sgst_percent):
                raise ValueError("Inter-state quotation cannot include CGST/SGST.")
        return self


class QuotationHeaderUpdate(BaseModel):
    validity_date: date | None = None
    enquiry_reference: str | None = Field(default=None, max_length=255)
    enquiry_date: date | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    payment_term_id: UUID | None = None
    terms_version_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=10000)
    special_instructions: str | None = Field(default=None, max_length=10000)
    round_off: Decimal | None = Field(default=None, ge=Decimal("-0.99"), le=Decimal("0.99"))


class QuotationLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_number: int
    product_id: UUID | None
    product_model_id: UUID | None
    oem_party_id: UUID | None
    description_snapshot: str
    oem_snapshot: str | None
    model_snapshot: str | None
    hsn_snapshot: str | None
    unit_snapshot: str
    quantity: Decimal
    quoted_rate: Decimal
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
    remarks: str | None


class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    quotation_number: str
    revision_number: int
    previous_revision_id: UUID | None
    is_latest: bool
    quotation_date: date
    validity_date: date | None
    customer_party_id: UUID
    business_scope: str
    project_id: UUID | None
    loa_id: UUID | None
    railway_zone_id: UUID | None
    railway_division_id: UUID | None
    railway_authority_id: UUID | None
    enquiry_reference: str | None
    enquiry_date: date | None
    subject: str
    tax_mode: str
    place_of_supply_state: str
    place_of_supply_state_code: str
    notes: str | None
    special_instructions: str | None
    status: str
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    round_off: Decimal
    grand_total: Decimal
    amount_in_words: str
    organization_snapshot: dict
    organization_gst_snapshot: dict
    customer_snapshot: dict
    customer_gst_snapshot: dict | None
    zone_snapshot: dict | None
    division_snapshot: dict | None
    authority_snapshot: dict | None
    bill_to_snapshot: dict
    ship_to_snapshot: dict | None
    place_of_supply_snapshot: dict
    payment_terms_snapshot: dict | None
    terms_snapshot: dict | None
    project_name_snapshot: str | None
    project_work_reference_snapshot: str | None
    loa_number_snapshot: str | None
    loa_date_snapshot: date | None
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[QuotationLineResponse]


class QuotationAction(BaseModel):
    action: str = Field(pattern="^(SUBMIT|APPROVE|ISSUE|ACCEPT|REJECT|EXPIRE|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class RevisionCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
