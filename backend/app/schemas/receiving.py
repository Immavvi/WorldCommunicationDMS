from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReceiptLineCreate(BaseModel):
    purchase_order_line_id: UUID
    quantity_received: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    quantity_accepted: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    quantity_short: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    quantity_damaged: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    quantity_rejected: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    remarks: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def physical_total(self):
        if (
            self.quantity_received
            != self.quantity_accepted + self.quantity_damaged + self.quantity_rejected
        ):
            raise ValueError(
                "Received quantity must equal accepted, damaged, and rejected quantities."
            )
        return self


class ReceiptCreate(BaseModel):
    purchase_order_id: UUID
    receipt_date: date
    vendor_invoice_reference: str | None = Field(default=None, max_length=255)
    delivery_reference: str | None = Field(default=None, max_length=255)
    receiving_location: str = Field(min_length=1, max_length=255)
    remarks: str | None = Field(default=None, max_length=2000)
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class ReceiptUpdate(BaseModel):
    vendor_invoice_reference: str | None = Field(default=None, max_length=255)
    delivery_reference: str | None = Field(default=None, max_length=255)
    receiving_location: str | None = Field(default=None, min_length=1, max_length=255)
    remarks: str | None = Field(default=None, max_length=2000)


class ReceiptLineResponse(ReceiptLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ordered_quantity_snapshot: Decimal
    previously_accepted_snapshot: Decimal
    quantity_excess: Decimal
    product_id: UUID | None
    description_snapshot: str
    unit_snapshot: str


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    receipt_number: str
    purchase_order_id: UUID
    vendor_party_id: UUID
    project_id: UUID
    loa_id: UUID | None
    receipt_date: date
    vendor_invoice_reference: str | None
    delivery_reference: str | None
    receiving_location: str
    received_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    remarks: str | None
    status: str
    po_number_snapshot: str
    vendor_snapshot: dict
    created_at: datetime
    updated_at: datetime
    lines: list[ReceiptLineResponse]


class ReceiptAction(BaseModel):
    action: str = Field(pattern="^(RECEIVE|VERIFY|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class PoReceiptPositionLine(BaseModel):
    purchase_order_line_id: UUID
    line_number: int
    description: str
    unit: str
    ordered_quantity: Decimal
    accepted_to_date: Decimal
    pending_quantity: Decimal
