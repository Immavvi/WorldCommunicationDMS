from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AllocationCreate(BaseModel):
    material_receipt_line_id: UUID
    allocated_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class ChallanLineCreate(BaseModel):
    dispatched_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    allocations: list[AllocationCreate] = Field(min_length=1)
    remarks: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def allocations_equal_dispatch(self):
        ids = [item.material_receipt_line_id for item in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("A receipt line may only be allocated once per Challan line.")
        if (
            sum((item.allocated_quantity for item in self.allocations), Decimal("0"))
            != self.dispatched_quantity
        ):
            raise ValueError("Receipt allocations must equal dispatched quantity.")
        return self


class ChallanCreate(BaseModel):
    challan_date: date
    project_id: UUID
    loa_id: UUID | None = None
    business_scope: str = Field(pattern="^(RAILWAY|NON_RAILWAY)$")
    customer_party_id: UUID
    railway_division_id: UUID | None = None
    consignee_authority_id: UUID | None = None
    bill_to_authority_id: UUID | None = None
    ship_to_railway_address_id: UUID | None = None
    ship_to_party_address_id: UUID | None = None
    dispatch_from_address_id: UUID
    transporter: str | None = Field(default=None, max_length=255)
    vehicle_number: str | None = Field(default=None, max_length=50)
    transport_reference: str | None = Field(default=None, max_length=255)
    eway_bill_reference: str | None = Field(default=None, max_length=255)
    delivery_notes: str | None = Field(default=None, max_length=10000)
    special_instructions: str | None = Field(default=None, max_length=10000)
    remarks: str | None = Field(default=None, max_length=10000)
    lines: list[ChallanLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_destination(self):
        if self.business_scope == "RAILWAY":
            if (
                not self.railway_division_id
                or not self.consignee_authority_id
                or not self.ship_to_railway_address_id
            ):
                raise ValueError(
                    "Railway challans require division, consignee, and Railway ship-to address."
                )
        elif not self.ship_to_party_address_id:
            raise ValueError("Non-Railway challans require a party ship-to address.")
        return self


class AllocationResponse(AllocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class ChallanLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_number: int
    loa_item_id: UUID | None
    variation_line_id: UUID | None
    product_id: UUID | None
    description_snapshot: str
    hsn_snapshot: str | None
    unit_snapshot: str
    dispatched_quantity: Decimal
    remarks: str | None
    allocations: list[AllocationResponse]


class ChallanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    challan_number: str
    challan_date: date
    project_id: UUID
    loa_id: UUID | None
    business_scope: str
    customer_party_id: UUID
    railway_division_id: UUID | None
    consignee_authority_id: UUID | None
    bill_to_authority_id: UUID | None
    status: str
    transporter: str | None
    vehicle_number: str | None
    transport_reference: str | None
    eway_bill_reference: str | None
    delivery_notes: str | None
    special_instructions: str | None
    remarks: str | None
    customer_snapshot: dict
    division_snapshot: dict | None
    consignee_snapshot: dict | None
    delivery_address_snapshot: dict
    dispatch_from_snapshot: dict
    organization_snapshot: dict
    acknowledged_date: date | None
    receiving_authority_text: str | None
    acknowledgement_reference: str | None
    acknowledgement_remarks: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    lines: list[ChallanLineResponse]


class ChallanAction(BaseModel):
    action: str = Field(pattern="^(READY|DISPATCH|DELIVER|CANCEL)$")
    reason: str = Field(min_length=1, max_length=500)


class AcknowledgementCreate(BaseModel):
    acknowledged_date: date
    receiving_authority_text: str = Field(min_length=1, max_length=255)
    acknowledgement_reference: str | None = Field(default=None, max_length=255)
    acknowledgement_remarks: str | None = Field(default=None, max_length=10000)


class DispatchAvailability(BaseModel):
    material_receipt_line_id: UUID
    description: str
    unit: str
    contractual_item_id: UUID | None
    contract_origin: str | None
    verified_accepted_quantity: Decimal
    allocated_dispatched_quantity: Decimal
    available_quantity: Decimal
    approved_contract_quantity: Decimal | None
    previously_dispatched_contract_quantity: Decimal
    remaining_contract_quantity: Decimal | None
