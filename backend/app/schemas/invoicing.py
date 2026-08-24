from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineCreate(BaseModel):
    proforma_invoice_line_id: UUID
    invoiced_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    remarks: str | None = Field(default=None, max_length=1000)


class InvoiceCreate(BaseModel):
    invoice_date: date
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
    gst_registration_id: UUID
    bank_account_id: UUID
    payment_term_id: UUID | None = None
    terms_version_id: UUID | None = None
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
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_number: int
    proforma_invoice_line_id: UUID
    supply_challan_line_id: UUID | None
    loa_item_id: UUID | None
    variation_line_id: UUID | None
    product_id: UUID | None
    description_snapshot: str
    hsn_snapshot: str | None
    unit_snapshot: str
    oem_snapshot: str | None
    model_snapshot: str | None
    pi_number_snapshot: str | None
    pi_date_snapshot: date | None
    challan_number_snapshot: str | None
    challan_date_snapshot: date | None
    invoiced_quantity: Decimal
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


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    invoice_number: str
    invoice_date: date
    project_id: UUID
    loa_id: UUID | None
    customer_party_id: UUID
    business_scope: str
    status: str
    tax_mode: str
    place_of_supply_state: str
    place_of_supply_state_code: str
    due_date: date | None
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
    division_snapshot: dict | None
    authority_snapshot: dict | None
    bill_to_snapshot: dict
    ship_to_snapshot: dict
    place_of_supply_snapshot: dict
    bank_snapshot: dict
    payment_terms_snapshot: dict | None
    terms_snapshot: dict | None
    project_name_snapshot: str | None
    project_work_reference_snapshot: str | None
    loa_number_snapshot: str | None
    loa_date_snapshot: date | None
    railway_zone_snapshot: str | None
    railway_division_snapshot: str | None
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    issued_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineResponse]


class InvoiceAction(BaseModel):
    action: str = Field(pattern="^(SUBMIT|APPROVE|ISSUE|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class InvoiceablePosition(BaseModel):
    proforma_invoice_line_id: UUID
    pi_number: str
    description: str
    unit: str
    contract_origin: str | None
    contractual_item_id: UUID | None
    challan_line_id: UUID | None
    eligible_pi_quantity: Decimal
    previously_invoiced_quantity: Decimal
    remaining_invoiceable_quantity: Decimal
    sales_rate: Decimal
