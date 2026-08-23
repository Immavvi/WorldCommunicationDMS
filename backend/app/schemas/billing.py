from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PiLineCreate(BaseModel):
    supply_challan_line_id: UUID | None = None
    loa_item_id: UUID | None = None
    variation_line_id: UUID | None = None
    product_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    hsn_code: str | None = Field(default=None, max_length=20)
    unit_id: UUID | None = None
    billable_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    sales_rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
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
    def source_and_rate(self):
        if self.loa_item_id and self.variation_line_id:
            raise ValueError("Only one contractual source may be selected.")
        if not self.supply_challan_line_id and self.sales_rate is None:
            raise ValueError("A sales rate is required for a non-Challan line.")
        return self


class PiCreate(BaseModel):
    pi_date: date
    project_id: UUID
    loa_id: UUID | None = None
    customer_party_id: UUID
    business_scope: str = Field(pattern="^(RAILWAY|NON_RAILWAY)$")
    railway_division_id: UUID | None = None
    railway_authority_id: UUID | None = None
    bill_to_party_address_id: UUID | None = None
    bill_to_railway_address_id: UUID | None = None
    ship_to_party_address_id: UUID | None = None
    ship_to_railway_address_id: UUID | None = None
    organization_id: UUID
    bank_account_id: UUID
    payment_term_id: UUID | None = None
    terms_version_id: UUID | None = None
    tax_mode: str = Field(pattern="^(INTRA_STATE|INTER_STATE)$")
    notes: str | None = Field(default=None, max_length=10000)
    special_instructions: str | None = Field(default=None, max_length=10000)
    round_off: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-0.99"),
        le=Decimal("0.99"),
        max_digits=3,
        decimal_places=2,
    )
    lines: list[PiLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def addresses_and_tax(self):
        if self.business_scope == "RAILWAY":
            if not all(
                (
                    self.railway_division_id,
                    self.railway_authority_id,
                    self.bill_to_railway_address_id,
                    self.ship_to_railway_address_id,
                )
            ):
                raise ValueError(
                    "Railway PI requires division, authority, bill-to and ship-to addresses."
                )
        elif not self.bill_to_party_address_id or not self.ship_to_party_address_id:
            raise ValueError("Non-Railway PI requires bill-to and ship-to addresses.")
        for line in self.lines:
            if self.tax_mode == "INTRA_STATE" and line.igst_percent:
                raise ValueError("Intra-state PI cannot include IGST.")
            if self.tax_mode == "INTER_STATE" and (line.cgst_percent or line.sgst_percent):
                raise ValueError("Inter-state PI cannot include CGST/SGST.")
        return self


class PiLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_number: int
    supply_challan_line_id: UUID | None
    loa_item_id: UUID | None
    variation_line_id: UUID | None
    product_id: UUID | None
    description_snapshot: str
    hsn_snapshot: str | None
    unit_snapshot: str
    billable_quantity: Decimal
    sales_rate: Decimal
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


class PiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pi_number: str
    pi_date: date
    project_id: UUID
    loa_id: UUID | None
    customer_party_id: UUID
    business_scope: str
    railway_division_id: UUID | None
    railway_authority_id: UUID | None
    status: str
    tax_mode: str
    notes: str | None
    special_instructions: str | None
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
    customer_snapshot: dict
    division_snapshot: dict | None
    authority_snapshot: dict | None
    bill_to_snapshot: dict
    ship_to_snapshot: dict
    bank_snapshot: dict
    payment_terms_snapshot: dict | None
    terms_snapshot: dict | None
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[PiLineResponse]


class PiAction(BaseModel):
    action: str = Field(pattern="^(SUBMIT|APPROVE|ISSUE|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class BillablePosition(BaseModel):
    supply_challan_line_id: UUID
    challan_number: str
    description: str
    unit: str
    contract_origin: str | None
    contractual_item_id: UUID | None
    eligible_dispatched_quantity: Decimal
    previously_committed_pi_quantity: Decimal
    remaining_billable_quantity: Decimal
    contractual_sales_rate: Decimal | None
