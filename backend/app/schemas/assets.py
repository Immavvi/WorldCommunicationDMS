from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetRegistrationPosition(BaseModel):
    material_receipt_line_id: UUID
    receipt_number: str
    product_id: UUID
    product_snapshot: str
    tracking_class: str
    accepted_quantity: int
    already_registered: int
    remaining_quantity: int


class SerialRegistrationItem(BaseModel):
    manufacturer_serial_number: str = Field(min_length=1, max_length=255)
    internal_tag: str | None = Field(default=None, max_length=100)

    @field_validator("manufacturer_serial_number")
    @classmethod
    def trim_serial(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Manufacturer serial number cannot be blank.")
        return value


class AssetRegistrationCreate(BaseModel):
    material_receipt_line_id: UUID
    assets: list[SerialRegistrationItem] = Field(min_length=1, max_length=500)


class AssetLocationInput(BaseModel):
    project_id: UUID | None = None
    railway_zone_id: UUID | None = None
    railway_division_id: UUID | None = None
    railway_location_id: UUID | None = None
    site: str | None = Field(default=None, max_length=255)
    building: str | None = Field(default=None, max_length=255)
    room: str | None = Field(default=None, max_length=255)
    rack: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)


class AssetAction(AssetLocationInput):
    action: str = Field(
        pattern="^(MAKE_AVAILABLE|ALLOCATE|MARK_DELIVERED|MOVE|SEND_FOR_REPAIR|"
        "RETURN_FROM_REPAIR|MARK_DAMAGED|MARK_LOST|RETIRE|DISPOSE|CANCEL)$"
    )
    reason: str = Field(min_length=1, max_length=1000)
    remarks: str | None = Field(default=None, max_length=2000)


class AssetInstallation(AssetLocationInput):
    installation_date: date
    reason: str = Field(min_length=1, max_length=1000)
    remarks: str | None = Field(default=None, max_length=2000)


class WarrantyUpdate(BaseModel):
    warranty_type: str | None = Field(default=None, max_length=100)
    warranty_reference: str | None = Field(default=None, max_length=255)
    warranty_start_date: date | None = None
    warranty_duration_months: int | None = Field(default=None, ge=0, le=1200)
    warranty_expiry_date: date | None = None
    warranty_provider_party_id: UUID | None = None
    warranty_remarks: str | None = Field(default=None, max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_warranty_dates(self):
        if self.warranty_duration_months is not None and self.warranty_start_date is None:
            raise ValueError("Warranty start date is required when duration is provided.")
        return self


class ReplacementCreate(BaseModel):
    replacement_asset_id: UUID
    reason: str = Field(min_length=1, max_length=1000)


class ChallanAssetAssign(BaseModel):
    asset_ids: list[UUID] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=1000)


class AssetEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    from_status: str | None
    to_status: str
    from_location_snapshot: str | None
    to_location_snapshot: str | None
    project_id: UUID | None
    railway_zone_id: UUID | None
    railway_division_id: UUID | None
    railway_location_id: UUID | None
    supply_challan_id: UUID | None
    event_at: datetime
    actor_user_id: UUID
    reason: str
    remarks: str | None
    created_at: datetime


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    asset_number: str
    manufacturer_serial_number: str
    internal_tag: str | None
    product_id: UUID
    product_snapshot: str
    oem_party_id: UUID | None
    oem_snapshot: str | None
    product_model_id: UUID | None
    model_snapshot: str | None
    vendor_party_id: UUID
    purchase_order_id: UUID
    purchase_order_line_id: UUID
    material_receipt_id: UUID
    material_receipt_line_id: UUID
    receipt_date_snapshot: date
    source_project_id: UUID
    source_loa_id: UUID | None
    project_snapshot: str
    loa_snapshot: str | None
    status: str
    current_project_id: UUID | None
    current_railway_zone_id: UUID | None
    current_railway_division_id: UUID | None
    current_railway_location_id: UUID | None
    current_site: str | None
    current_building: str | None
    current_room: str | None
    current_rack: str | None
    current_position: str | None
    installation_date: date | None
    warranty_type: str | None
    warranty_reference: str | None
    warranty_start_date: date | None
    warranty_duration_months: int | None
    warranty_expiry_date: date | None
    warranty_provider_party_id: UUID | None
    warranty_remarks: str | None
    replacement_asset_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    events: list[AssetEventResponse]
