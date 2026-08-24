from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaymentCreate(BaseModel):
    receipt_date: date
    customer_party_id: UUID
    organization_id: UUID
    bank_account_id: UUID | None = None
    payment_mode: str = Field(pattern="^(BANK_TRANSFER|NEFT|RTGS|IMPS|UPI|CHEQUE|CASH|OTHER)$")
    transaction_reference: str | None = Field(default=None, max_length=255)
    transaction_date: date | None = None
    amount_received: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_reference(self):
        if self.payment_mode in {"BANK_TRANSFER", "NEFT", "RTGS", "IMPS", "UPI", "CHEQUE"}:
            if not self.transaction_reference:
                raise ValueError("Transaction/reference number is required for this payment mode.")
        return self


class PaymentUpdate(BaseModel):
    receipt_date: date | None = None
    bank_account_id: UUID | None = None
    payment_mode: str | None = Field(
        default=None, pattern="^(BANK_TRANSFER|NEFT|RTGS|IMPS|UPI|CHEQUE|CASH|OTHER)$"
    )
    transaction_reference: str | None = Field(default=None, max_length=255)
    transaction_date: date | None = None
    amount_received: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    notes: str | None = Field(default=None, max_length=5000)


class AllocationCreate(BaseModel):
    tax_invoice_id: UUID
    allocated_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    allocation_date: date
    remarks: str | None = Field(default=None, max_length=1000)


class PaymentAction(BaseModel):
    action: str = Field(pattern="^(CONFIRM|CANCEL|REVERSE)$")
    reason: str = Field(min_length=1, max_length=1000)


class AllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    payment_id: UUID
    tax_invoice_id: UUID
    allocated_amount: Decimal
    allocation_date: date
    actor_user_id: UUID
    remarks: str | None
    invoice_number_snapshot: str
    project_snapshot: str | None
    loa_snapshot: str | None
    created_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    receipt_number: str
    receipt_date: date
    customer_party_id: UUID
    organization_id: UUID
    bank_account_id: UUID | None
    payment_mode: str
    transaction_reference: str | None
    transaction_date: date | None
    amount_received: Decimal
    currency: str
    notes: str | None
    status: str
    customer_snapshot: dict
    organization_snapshot: dict
    bank_snapshot: dict | None
    created_by_user_id: UUID
    confirmed_by_user_id: UUID | None
    confirmed_at: datetime | None
    reversed_by_user_id: UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime
    allocations: list[AllocationResponse]
    allocated_amount: Decimal
    unallocated_amount: Decimal


class ReceivablePosition(BaseModel):
    tax_invoice_id: UUID
    invoice_number: str
    invoice_date: date
    customer_party_id: UUID
    customer_name: str
    project_id: UUID
    project_name: str | None
    loa_id: UUID | None
    loa_number: str | None
    railway_division_id: UUID | None
    due_date: date | None
    invoice_total: Decimal
    received_amount: Decimal
    outstanding_amount: Decimal
    payment_status: str
    days_overdue: int


class EligibleInvoice(BaseModel):
    tax_invoice_id: UUID
    invoice_number: str
    invoice_date: date
    due_date: date | None
    invoice_total: Decimal
    received_amount: Decimal
    outstanding_amount: Decimal
    project_name: str | None
    loa_number: str | None


class InvoicePaymentHistory(BaseModel):
    payment_id: UUID
    receipt_number: str
    receipt_date: date
    payment_status: str
    allocated_amount: Decimal
    allocation_date: date
    remarks: str | None
