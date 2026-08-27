import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RailwayLoaImport(Base):
    __tablename__ = "railway_loa_imports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADED','EXTRACTING','NEEDS_REVIEW','READY_FOR_APPROVAL',"
            "'APPROVED','EXTRACTION_FAILED','CANCELLED')",
            name="ck_railway_loa_import_status",
        ),
        CheckConstraint(
            "extraction_method IS NULL OR extraction_method IN "
            "('XLSX','NATIVE_PDF','OCR','MIXED_PDF')",
            name="ck_railway_loa_import_method",
        ),
        Index("ix_railway_loa_import_status", "status"),
        Index("ix_railway_loa_import_loa_number", "loa_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    extension: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="UPLOADED", server_default="UPLOADED")
    extraction_method: Mapped[str | None] = mapped_column(String(20))
    extraction_error: Mapped[str | None] = mapped_column(String(1000))
    extraction_warnings: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    project_candidates: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    authority_candidates: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    boq_reconciliation: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    completion_date_provenance: Mapped[str | None] = mapped_column(String(30))
    loa_date_provenance: Mapped[str | None] = mapped_column(String(30))
    loa_date_source: Mapped[str | None] = mapped_column(String(255))

    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    railway_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("railway_zones.id"))
    railway_division_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_divisions.id")
    )
    authority_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("railway_authorities.id"))
    issuing_party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"), unique=True)

    extracted_zone_text: Mapped[str | None] = mapped_column(String(255))
    extracted_division_text: Mapped[str | None] = mapped_column(String(255))
    authority_text: Mapped[str | None] = mapped_column(String(500))
    loa_number: Mapped[str | None] = mapped_column(String(100))
    tender_reference: Mapped[str | None] = mapped_column(String(255))
    loa_date: Mapped[date | None] = mapped_column(Date)
    completion_period: Mapped[str | None] = mapped_column(String(255))
    completion_date: Mapped[date | None] = mapped_column(Date)
    work_description: Mapped[str | None] = mapped_column(Text)
    contract_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    duplicate_candidates: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["RailwayLoaImportLine"]] = relationship(
        back_populates="loa_import",
        cascade="all, delete-orphan",
        order_by="RailwayLoaImportLine.line_number",
    )
    schedules: Mapped[list["RailwayLoaImportSchedule"]] = relationship(
        back_populates="loa_import",
        cascade="all, delete-orphan",
        order_by="RailwayLoaImportSchedule.sequence",
    )


class RailwayLoaImportSchedule(Base):
    __tablename__ = "railway_loa_import_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    loa_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("railway_loa_imports.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int]
    source_key: Mapped[str] = mapped_column(String(255))
    title_raw: Mapped[str] = mapped_column(Text)
    title_normalized: Mapped[str] = mapped_column(Text)
    source_page_start: Mapped[int | None]
    source_page_end: Mapped[int | None]
    source_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    extracted_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    reconciliation_status: Mapped[str] = mapped_column(String(30), default="NEEDS_REVIEW")

    loa_import: Mapped[RailwayLoaImport] = relationship(back_populates="schedules")
    groups: Mapped[list["RailwayLoaImportGroup"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="RailwayLoaImportGroup.sequence",
    )


class RailwayLoaImportGroup(Base):
    __tablename__ = "railway_loa_import_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("railway_loa_import_schedules.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int]
    source_key: Mapped[str] = mapped_column(String(255))
    title_raw: Mapped[str] = mapped_column(Text)
    title_normalized: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String(30))
    source_page_start: Mapped[int | None]
    source_page_end: Mapped[int | None]
    source_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    extracted_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    reconciliation_status: Mapped[str] = mapped_column(String(30), default="NEEDS_REVIEW")

    schedule: Mapped[RailwayLoaImportSchedule] = relationship(back_populates="groups")
    lines: Mapped[list["RailwayLoaImportLine"]] = relationship(back_populates="group")


class RailwayLoaImportLine(Base):
    __tablename__ = "railway_loa_import_lines"
    __table_args__ = (
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_loa_import_line_quantity"),
        CheckConstraint("rate IS NULL OR rate >= 0", name="ck_loa_import_line_rate"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_loa_import_line_amount"),
        CheckConstraint(
            "extraction_outcome IN ('EXTRACTED','NEEDS_REVIEW','REJECTED_WITH_REASON',"
            "'EXPLICITLY_IGNORED_BY_OWNER')",
            name="ck_loa_import_line_outcome",
        ),
        Index("ix_loa_import_lines_import", "loa_import_id", "line_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    loa_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("railway_loa_imports.id", ondelete="CASCADE")
    )
    line_number: Mapped[int]
    candidate_key: Mapped[str | None] = mapped_column(String(100))
    source_order: Mapped[int | None]
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_loa_import_groups.id", ondelete="SET NULL"), index=True
    )
    item_number: Mapped[str | None] = mapped_column(String(50))
    item_code: Mapped[str | None] = mapped_column(String(50))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str | None] = mapped_column(Text)
    description_raw: Mapped[str | None] = mapped_column(Text)
    description_normalized: Mapped[str | None] = mapped_column(Text)
    hsn_text: Mapped[str | None] = mapped_column(String(50))
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hsn_codes.id"))
    unit_text: Mapped[str | None] = mapped_column(String(100))
    uom_raw: Mapped[str | None] = mapped_column(String(100))
    uom_normalized: Mapped[str | None] = mapped_column(String(100))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units_of_measure.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    oem_make: Mapped[str | None] = mapped_column(String(255))
    model_number: Mapped[str | None] = mapped_column(String(255))
    tax_text: Mapped[str | None] = mapped_column(String(255))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    source_page: Mapped[int | None]
    source_page_start: Mapped[int | None]
    source_page_end: Mapped[int | None]
    source_serial: Mapped[str | None] = mapped_column(String(50))
    source_raw_text: Mapped[str | None] = mapped_column(Text)
    extraction_outcome: Mapped[str] = mapped_column(
        String(30), default="EXTRACTED", server_default="EXTRACTED"
    )
    extraction_issue: Mapped[str | None] = mapped_column(String(1000))
    extraction_method: Mapped[str | None] = mapped_column(String(20))
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    extraction_issues: Mapped[list | None] = mapped_column(JSON, default=list)

    loa_import: Mapped[RailwayLoaImport] = relationship(back_populates="lines")
    group: Mapped[RailwayLoaImportGroup | None] = relationship(back_populates="lines")
