from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contracts import ProjectCreate


class LoaImportLineReview(BaseModel):
    id: UUID | None = None
    candidate_key: str | None = Field(default=None, max_length=100)
    source_order: int | None = Field(default=None, ge=1)
    group_id: UUID | None = None
    product_id: UUID | None = None
    description: str | None = Field(default=None, max_length=10000)
    description_raw: str | None = Field(default=None, max_length=50000)
    description_normalized: str | None = Field(default=None, max_length=50000)
    hsn_text: str | None = Field(default=None, max_length=50)
    hsn_code_id: UUID | None = None
    unit_text: str | None = Field(default=None, max_length=100)
    uom_raw: str | None = Field(default=None, max_length=100)
    uom_normalized: str | None = Field(default=None, max_length=100)
    unit_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    oem_make: str | None = Field(default=None, max_length=255)
    model_number: str | None = Field(default=None, max_length=255)
    tax_text: str | None = Field(default=None, max_length=255)
    remarks: str | None = Field(default=None, max_length=1000)
    source_page: int | None = Field(default=None, ge=1)
    source_page_start: int | None = Field(default=None, ge=1)
    source_page_end: int | None = Field(default=None, ge=1)
    source_serial: str | None = Field(default=None, max_length=50)
    source_raw_text: str | None = Field(default=None, max_length=10000)
    extraction_outcome: str = Field(
        default="EXTRACTED",
        pattern="^(EXTRACTED|NEEDS_REVIEW|REJECTED_WITH_REASON|EXPLICITLY_IGNORED_BY_OWNER)$",
    )
    extraction_issue: str | None = Field(default=None, max_length=1000)
    extraction_method: str | None = Field(default=None, max_length=20)
    extraction_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    extraction_issues: list[str] = Field(default_factory=list)


class LoaImportReview(BaseModel):
    project_id: UUID | None = None
    railway_zone_id: UUID | None = None
    railway_division_id: UUID | None = None
    authority_id: UUID | None = None
    issuing_party_id: UUID | None = None
    loa_number: str | None = Field(default=None, max_length=100)
    tender_reference: str | None = Field(default=None, max_length=255)
    loa_date: date | None = None
    completion_period: str | None = Field(default=None, max_length=255)
    completion_date: date | None = None
    work_description: str | None = Field(default=None, max_length=10000)
    contract_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    authority_text: str | None = Field(default=None, max_length=500)
    lines: list[LoaImportLineReview] | None = None


class LoaImportApproval(BaseModel):
    new_project: ProjectCreate | None = None
    confirm_duplicate: bool = False


class RailwayCustomerMapping(BaseModel):
    customer_party_id: UUID


class LoaImportLineResponse(LoaImportLineReview):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    line_number: int


class LoaImportGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    source_key: str
    title_raw: str
    title_normalized: str
    source_kind: str
    source_page_start: int | None
    source_page_end: int | None
    source_total: Decimal | None
    extracted_total: Decimal | None
    difference: Decimal | None
    reconciliation_status: str


class LoaImportScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    source_key: str
    title_raw: str
    title_normalized: str
    source_page_start: int | None
    source_page_end: int | None
    source_total: Decimal | None
    extracted_total: Decimal | None
    difference: Decimal | None
    reconciliation_status: str
    groups: list[LoaImportGroupResponse]


class LoaImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    uploaded_by_user_id: UUID
    status: str
    extraction_method: str | None
    extraction_error: str | None
    extraction_warnings: list
    project_id: UUID | None
    railway_zone_id: UUID | None
    railway_division_id: UUID | None
    authority_id: UUID | None
    issuing_party_id: UUID | None
    loa_id: UUID | None
    extracted_zone_text: str | None
    extracted_division_text: str | None
    authority_text: str | None
    loa_number: str | None
    tender_reference: str | None
    loa_date: date | None
    completion_period: str | None
    completion_date: date | None
    work_description: str | None
    contract_value: Decimal | None
    duplicate_candidates: list
    project_candidates: list
    authority_candidates: list
    boq_reconciliation: dict
    boq_readiness_issues: list[dict] = Field(default_factory=list)
    completion_date_provenance: str | None
    loa_date_provenance: str | None
    loa_date_source: str | None
    uploaded_at: datetime
    extracted_at: datetime | None
    approved_at: datetime | None
    updated_at: datetime
    lines: list[LoaImportLineResponse]
    schedules: list[LoaImportScheduleResponse] = Field(default_factory=list)
