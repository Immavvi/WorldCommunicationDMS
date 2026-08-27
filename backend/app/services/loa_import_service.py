import hashlib
import re
import shutil
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import AppError
from app.models.loa_imports import (
    RailwayLoaImport,
    RailwayLoaImportGroup,
    RailwayLoaImportLine,
    RailwayLoaImportSchedule,
)
from app.repositories.contract_repository import ContractRepository
from app.repositories.loa_import_repository import RailwayLoaImportRepository
from app.schemas.contracts import LoaCreate, LoaItemCreate
from app.schemas.loa_imports import LoaImportApproval, LoaImportReview
from app.services.contract_service import ContractService
from app.services.loa_extraction import (
    ExcelLoaExtractor,
    ExtractedLoa,
    PdfLoaExtractor,
    derive_completion_date,
)

MONEY = Decimal("0.01")
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def normalized(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(
        r"\b(?:railway|rly|division|zone|authority|consignee)\b|[^a-z0-9]",
        "",
        value.lower(),
    )


def master_terms(record, *fields: str) -> set[str]:
    terms = {
        normalized(str(getattr(record, field, "")))
        for field in fields
        if getattr(record, field, None)
    }
    terms.update(normalized(str(alias)) for alias in getattr(record, "aliases", []) or [])
    return {term for term in terms if term}


class RailwayLoaImportService:
    def __init__(self, repository: RailwayLoaImportRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.storage_root = settings.document_storage_root / "loa"

    async def upload(self, file: UploadFile, actor_id: UUID) -> RailwayLoaImport:
        filename = file.filename or ""
        if (
            not filename
            or Path(filename).name != filename
            or any(char in filename for char in ("/", "\\", "\x00"))
        ):
            raise AppError(422, "unsafe_filename", "The uploaded filename is invalid.")
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise AppError(
                415, "unsupported_loa_source", "Only PDF and XLSX Railway LOAs are supported."
            )
        import_id = uuid.uuid4()
        directory = self.storage_root / str(import_id)
        destination = directory / f"original{extension}"
        directory.mkdir(parents=True, exist_ok=False)
        digest = hashlib.sha256()
        size = 0
        try:
            with destination.open("xb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.loa_upload_max_bytes:
                        raise AppError(
                            413,
                            "loa_file_too_large",
                            "The Railway LOA exceeds the upload size limit.",
                        )
                    digest.update(chunk)
                    output.write(chunk)
            self._validate_signature(destination, extension)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        record = RailwayLoaImport(
            id=import_id,
            original_filename=filename,
            storage_key=f"loa/{import_id}/original{extension}",
            mime_type=ALLOWED_EXTENSIONS[extension],
            extension=extension.lstrip("."),
            size_bytes=size,
            sha256=digest.hexdigest(),
            uploaded_by_user_id=actor_id,
            lines=[],
            schedules=[],
        )
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            "upload",
            record.id,
            None,
            {
                "original_filename": filename,
                "mime_type": record.mime_type,
                "size_bytes": size,
            },
        )
        await self.extract(record, actor_id)
        return await self.get(record.id)

    def _validate_signature(self, path: Path, extension: str) -> None:
        signature = path.read_bytes()[:8]
        valid = (
            signature.startswith(b"%PDF-")
            if extension == ".pdf"
            else signature.startswith(b"PK\x03\x04")
        )
        if not valid:
            raise AppError(415, "invalid_loa_file", "File content does not match its extension.")

    def file_path(self, record: RailwayLoaImport) -> Path:
        root = self.settings.document_storage_root.resolve()
        path = (root / record.storage_key).resolve()
        if not path.is_relative_to(root):
            raise AppError(
                500, "invalid_storage_reference", "Stored document reference is invalid."
            )
        return path

    async def get(self, import_id: UUID) -> RailwayLoaImport:
        record = await self.repository.get(import_id)
        if record is None:
            raise AppError(404, "loa_import_not_found", "Railway LOA import does not exist.")
        record.boq_readiness_issues = self.boq_readiness_issues(record)
        return record

    async def list(self) -> list[RailwayLoaImport]:
        records = await self.repository.list()
        for record in records:
            record.boq_readiness_issues = self.boq_readiness_issues(record)
        return records

    async def extract(self, record: RailwayLoaImport, actor_id: UUID) -> RailwayLoaImport:
        if record.status in {"APPROVED", "CANCELLED"}:
            raise AppError(
                409, "loa_import_locked", "This Railway LOA import cannot be extracted again."
            )
        record.status = "EXTRACTING"
        record.extraction_error = None
        await self.repository.save(record)
        try:
            path = self.file_path(record)
            result = (
                ExcelLoaExtractor().extract(path)
                if record.extension == "xlsx"
                else PdfLoaExtractor().extract(path)
            )
            await self._apply_extraction(record, result)
            record.status = "NEEDS_REVIEW"
            record.extracted_at = datetime.now(UTC)
            self.repository.audit(
                actor_id,
                "extract",
                record.id,
                None,
                {
                    "method": result.method,
                    "warnings": len(result.warnings),
                    "boq_lines": len(result.lines),
                },
            )
        except Exception as exc:
            record.status = "EXTRACTION_FAILED"
            record.extraction_error = str(exc)[:1000]
            self.repository.audit(
                actor_id,
                "extraction_failed",
                record.id,
                None,
                {
                    "error_type": type(exc).__name__,
                },
            )
        await self.repository.save(record)
        return record

    async def retry(self, import_id: UUID, actor_id: UUID) -> RailwayLoaImport:
        record = await self.get(import_id)
        self.repository.audit(
            actor_id, "retry_extraction", record.id, {"status": record.status}, None
        )
        await self.extract(record, actor_id)
        return await self.get(import_id)

    async def _apply_extraction(self, record: RailwayLoaImport, result: ExtractedLoa) -> None:
        record.extraction_method = result.method
        record.extraction_warnings = result.warnings
        record.loa_number = result.loa_number
        record.tender_reference = result.tender_reference
        record.loa_date = result.loa_date.date() if result.loa_date else None
        record.loa_date_provenance = result.loa_date_provenance
        record.loa_date_source = result.loa_date_source
        record.completion_period = result.completion_period
        record.completion_date = result.completion_date.date() if result.completion_date else None
        record.completion_date_provenance = result.completion_date_provenance
        record.work_description = result.work_description
        record.contract_value = result.contract_value
        record.extracted_division_text = result.division_text
        record.extracted_zone_text = result.zone_text
        record.authority_text = result.authority_text
        record.authority_candidates = result.authority_candidates
        record.boq_reconciliation = result.boq_reconciliation
        divisions, zones, authorities, units, hsn_codes = await self._masters()
        division = self._resolve_railway_masters(record, divisions, zones, authorities)
        if division and division.customer_party_id:
            record.issuing_party_id = division.customer_party_id
        projects = await self.repository.projects(record.railway_division_id)
        record.project_candidates = [
            {
                "id": str(project.id),
                "code": project.code,
                "name": project.name,
                "reason": (
                    "Same Railway Division and tender/work reference"
                    if normalized(record.tender_reference)
                    and normalized(record.tender_reference) == normalized(project.work_reference)
                    else "Same Railway Division and similar work description"
                )
                + "; owner confirmation required",
            }
            for project in projects
            if (
                normalized(record.work_description) in normalized(project.name)
                or normalized(project.name) in normalized(record.work_description)
                or (
                    normalized(record.tender_reference)
                    and normalized(record.tender_reference) == normalized(project.work_reference)
                )
            )
        ]
        record.lines = []
        record.schedules = []
        groups_by_key: dict[str, RailwayLoaImportGroup] = {}
        for schedule_data in result.schedules:
            schedule = RailwayLoaImportSchedule(
                sequence=schedule_data["sequence"],
                source_key=schedule_data["source_key"],
                title_raw=schedule_data["title_raw"],
                title_normalized=schedule_data["title_normalized"],
                source_page_start=schedule_data.get("source_page_start"),
                source_page_end=schedule_data.get("source_page_end"),
                source_total=schedule_data.get("source_total"),
                extracted_total=schedule_data.get("extracted_total"),
                difference=schedule_data.get("difference"),
                reconciliation_status=schedule_data["reconciliation_status"],
                groups=[],
            )
            for group_data in schedule_data["groups"]:
                group = RailwayLoaImportGroup(
                    sequence=group_data["sequence"],
                    source_key=group_data["source_key"],
                    title_raw=group_data["title_raw"],
                    title_normalized=group_data["title_normalized"],
                    source_kind=group_data["source_kind"],
                    source_page_start=group_data.get("source_page_start"),
                    source_page_end=group_data.get("source_page_end"),
                    source_total=group_data.get("source_total"),
                    extracted_total=group_data.get("extracted_total"),
                    difference=group_data.get("difference"),
                    reconciliation_status=group_data["reconciliation_status"],
                )
                schedule.groups.append(group)
                groups_by_key[group.source_key] = group
            record.schedules.append(schedule)
        for index, line in enumerate(result.lines, 1):
            unit = self._match(line.unit_text, units, "code", "name", "symbol")
            hsn = self._match(line.hsn_text, hsn_codes, "code")
            record.lines.append(
                RailwayLoaImportLine(
                    line_number=index,
                    candidate_key=line.candidate_key,
                    source_order=line.source_order,
                    group=groups_by_key.get(line.group_key or ""),
                    item_number=None,
                    item_code=None,
                    description=line.description,
                    description_raw=line.description_raw,
                    description_normalized=line.description_normalized,
                    unit_text=line.unit_text,
                    uom_raw=line.uom_raw,
                    uom_normalized=line.uom_normalized,
                    unit_id=unit.id if unit else None,
                    hsn_text=line.hsn_text,
                    hsn_code_id=hsn.id if hsn else None,
                    quantity=line.quantity,
                    rate=line.rate,
                    amount=line.amount.quantize(MONEY, rounding=ROUND_HALF_UP)
                    if line.amount is not None
                    else None,
                    oem_make=line.oem_make,
                    model_number=line.model_number,
                    tax_text=line.tax_text,
                    remarks=line.remarks,
                    source_page=line.source_page,
                    source_page_start=line.source_page_start,
                    source_page_end=line.source_page_end,
                    source_serial=line.source_serial,
                    source_raw_text=line.source_raw_text,
                    extraction_outcome=line.extraction_outcome,
                    extraction_issue=line.extraction_issue,
                    extraction_method=line.extraction_method,
                    extraction_confidence=line.extraction_confidence,
                    extraction_issues=line.extraction_issues,
                )
            )
        duplicates = await self.repository.duplicate_loas(
            record.loa_number, record.railway_division_id, record.tender_reference
        )
        record.duplicate_candidates = [
            {"id": str(item.id), "loa_number": item.loa_number, "project_id": str(item.project_id)}
            for item in duplicates
        ]

    def _resolve_railway_masters(self, record, divisions, zones, authorities):
        zone = self._match(record.extracted_zone_text, zones, "code", "name")
        division = self._match(
            record.extracted_division_text,
            [item for item in divisions if zone is None or item.zone_id == zone.id],
            "code",
            "name",
        )
        record.railway_division_id = division.id if division else None
        record.railway_zone_id = zone.id if zone else division.zone_id if division else None
        record.authority_id = None
        resolved_candidates = []
        for stored_candidate in record.authority_candidates:
            candidate = dict(stored_candidate)
            compatible = [
                item
                for item in authorities
                if item.is_active
                and division is not None
                and item.division_id == division.id
                and (
                    candidate.get("role") not in {
                        "ISSUING_AUTHORITY",
                        "EXECUTION_AUTHORITY",
                        "CONSIGNEE",
                    }
                    or candidate.get("role") in {role.role for role in item.roles}
                )
            ]
            authority, resolution = self._match_with_status(
                candidate.get("text"), compatible, "code", "name", "designation"
            )
            candidate["master_id"] = str(authority.id) if authority else None
            candidate["master_status"] = resolution
            candidate["master_detail"] = self._authority_resolution_detail(
                candidate, authorities, division, resolution
            )
            resolved_candidates.append(candidate)
            if authority and candidate.get("role") == "CONSIGNEE":
                record.authority_id = authority.id
        # JSON values must be replaced, not mutated in place, so SQLAlchemy persists
        # refreshed resolution metadata for an existing import.
        record.authority_candidates = resolved_candidates
        return division

    @staticmethod
    def _authority_resolution_detail(candidate, authorities, division, resolution: str) -> str:
        if resolution == "MATCHED":
            return "Exactly one active authority matched the Division and contextual role."
        if resolution == "AMBIGUOUS":
            return (
                "More than one active authority matched; select the intended master deliberately."
            )
        needle = normalized(candidate.get("text"))
        textual = [
            item
            for item in authorities
            if needle
            and any(
                needle in term or term in needle
                for term in master_terms(item, "code", "name", "designation")
            )
        ]
        if textual and all(not item.is_active for item in textual):
            return "A matching Railway Authority exists but is inactive."
        if (
            division is not None
            and textual
            and all(item.division_id != division.id for item in textual)
        ):
            return "Matching Railway Authority records belong to another Railway Division."
        role = candidate.get("role")
        in_division = [
            item for item in textual if division is None or item.division_id == division.id
        ]
        if in_division and all(
            role not in {entry.role for entry in item.roles} for item in in_division
        ):
            return f"Matching Railway Authority records do not support the {role} role."
        return "No compatible active Railway Authority is configured for this Division and role."

    async def resolve_masters(self, import_id: UUID, actor_id: UUID) -> RailwayLoaImport:
        record = await self.repository.get(import_id, lock=True)
        if record is None:
            raise AppError(404, "loa_import_not_found", "Railway LOA import does not exist.")
        if record.status in {"APPROVED", "CANCELLED"}:
            raise AppError(409, "loa_import_locked", "The import can no longer be edited.")
        divisions, zones, authorities, _, _ = await self._masters()
        self._resolve_railway_masters(record, divisions, zones, authorities)
        record.status = "READY_FOR_APPROVAL" if self._ready(record) else "NEEDS_REVIEW"
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            "resolve_railway_masters",
            record.id,
            None,
            {
                "railway_zone_id": str(record.railway_zone_id) if record.railway_zone_id else None,
                "railway_division_id": str(record.railway_division_id)
                if record.railway_division_id
                else None,
            },
        )
        return await self.get(record.id)

    async def _masters(self):
        return (
            await self.repository.divisions(),
            await self.repository.zones(),
            await self.repository.authorities(),
            await self.repository.units(),
            await self.repository.hsn_codes(),
        )

    @staticmethod
    def _match(value: str | None, records: list, *fields: str):
        return RailwayLoaImportService._match_with_status(value, records, *fields)[0]

    @staticmethod
    def _match_with_status(value: str | None, records: list, *fields: str):
        needle = normalized(value)
        if not needle:
            return None, "NOT_CONFIGURED"
        exact = [
            record
            for record in records
            if needle in master_terms(record, *fields)
        ]
        if len(exact) == 1:
            return exact[0], "MATCHED"
        if len(exact) > 1:
            return None, "AMBIGUOUS"
        contained = [
            record
            for record in records
            if any(
                needle in term or term in needle for term in master_terms(record, *fields)
            )
        ]
        if len(contained) == 1:
            return contained[0], "MATCHED"
        return None, "AMBIGUOUS" if contained else "NOT_CONFIGURED"

    async def review(
        self, import_id: UUID, payload: LoaImportReview, actor_id: UUID
    ) -> RailwayLoaImport:
        record = await self.repository.get(import_id, lock=True)
        if record is None:
            raise AppError(404, "loa_import_not_found", "Railway LOA import does not exist.")
        if record.status in {"APPROVED", "CANCELLED"}:
            raise AppError(409, "loa_import_locked", "The import can no longer be edited.")
        old_status = record.status
        values = payload.model_dump(exclude_unset=True)
        lines = values.pop("lines", None)
        if {"railway_zone_id", "railway_division_id", "authority_id"}.intersection(values):
            divisions, zones, authorities, _, _ = await self._masters()
            zone_id = values.get("railway_zone_id", record.railway_zone_id)
            division_id = values.get("railway_division_id", record.railway_division_id)
            authority_id = values.get("authority_id", record.authority_id)
            zone = next((item for item in zones if item.id == zone_id), None)
            division = next((item for item in divisions if item.id == division_id), None)
            if zone_id and zone is None:
                raise AppError(422, "invalid_railway_zone", "Select an active Railway Zone.")
            if division_id and division is None:
                raise AppError(
                    422, "invalid_railway_division", "Select an active Railway Division."
                )
            if zone and division and division.zone_id != zone.id:
                raise AppError(
                    422,
                    "railway_hierarchy_mismatch",
                    "The Railway Division does not belong to the selected Railway Zone.",
                )
            if authority_id:
                authority = next((item for item in authorities if item.id == authority_id), None)
                if authority is None or (division and authority.division_id != division.id):
                    raise AppError(
                        422,
                        "invalid_railway_authority",
                        "Select an active Railway Authority from the resolved Division.",
                    )
                if "CONSIGNEE" not in {role.role for role in authority.roles}:
                    raise AppError(
                        422,
                        "incompatible_railway_authority_role",
                        "The selected Railway Authority is not configured as a Consignee.",
                    )
                candidates = [dict(candidate) for candidate in record.authority_candidates]
                for candidate in candidates:
                    if candidate.get("role") == "CONSIGNEE":
                        candidate["master_id"] = str(authority.id)
                        candidate["master_status"] = "OWNER_MAPPED"
                record.authority_candidates = candidates
        if "completion_date" in values and values["completion_date"] != record.completion_date:
            record.completion_date_provenance = "OWNER_CORRECTED"
        if "loa_date" in values and values["loa_date"] != record.loa_date:
            record.loa_date_provenance = "OWNER_CORRECTED"
            record.loa_date_source = "Owner correction during import review"
            if (
                values["loa_date"]
                and record.completion_period
                and record.completion_date is None
                and record.completion_date_provenance == "WAITING_FOR_LOA_DATE"
            ):
                record.completion_date = derive_completion_date(
                    values["loa_date"], record.completion_period
                )
                record.completion_date_provenance = "DERIVED"
        for field, value in values.items():
            setattr(record, field, value)
        if lines is not None:
            existing_by_id = {str(line.id): line for line in record.lines}
            immutable_fields = {
                "candidate_key",
                "source_order",
                "group_id",
                "description_raw",
                "uom_raw",
                "source_page",
                "source_page_start",
                "source_page_end",
                "source_raw_text",
                "extraction_method",
                "extraction_confidence",
                "extraction_issues",
            }
            reviewed_lines = []
            for index, line in enumerate(lines, 1):
                existing = existing_by_id.get(str(line.get("id")))
                values_for_line = {key: value for key, value in line.items() if key != "id"}
                if existing:
                    for field in immutable_fields:
                        values_for_line[field] = getattr(existing, field)
                values_for_line["item_code"] = None
                values_for_line["item_number"] = None
                values_for_line["description_normalized"] = values_for_line.get("description")
                values_for_line["uom_normalized"] = values_for_line.get("unit_text")
                reviewed_lines.append(
                    RailwayLoaImportLine(line_number=index, **values_for_line)
                )
            record.lines = reviewed_lines
            self._refresh_reconciliation(record)
        duplicates = await self.repository.duplicate_loas(
            record.loa_number, record.railway_division_id, record.tender_reference
        )
        record.duplicate_candidates = [
            {"id": str(item.id), "loa_number": item.loa_number, "project_id": str(item.project_id)}
            for item in duplicates
        ]
        record.status = "READY_FOR_APPROVAL" if self._ready(record) else "NEEDS_REVIEW"
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            "review",
            record.id,
            {"status": old_status},
            {
                "status": record.status,
                "line_count": len(record.lines),
                "explicitly_ignored_source_rows": [
                    line.source_serial
                    for line in record.lines
                    if line.extraction_outcome == "EXPLICITLY_IGNORED_BY_OWNER"
                ],
            },
        )
        return await self.get(record.id)

    async def map_customer(
        self, import_id: UUID, customer_party_id: UUID, actor_id: UUID
    ) -> RailwayLoaImport:
        record = await self.repository.get(import_id, lock=True)
        if record is None:
            raise AppError(404, "loa_import_not_found", "Railway LOA import does not exist.")
        if record.status in {"APPROVED", "CANCELLED"}:
            raise AppError(409, "loa_import_locked", "The import can no longer be edited.")
        if record.railway_division_id is None:
            raise AppError(
                422,
                "railway_division_required",
                "Resolve the Railway Division before mapping a Customer.",
            )
        party = await self.repository.party(customer_party_id)
        if (
            party is None
            or not party.is_active
            or "CUSTOMER" not in {role.role for role in party.roles}
        ):
            raise AppError(
                422,
                "invalid_railway_customer",
                "Select an active Customer record for the Railway mapping.",
            )
        division = await self.repository.division(record.railway_division_id, lock=True)
        if division is None or not division.is_active:
            raise AppError(
                422,
                "invalid_railway_division",
                "The selected Railway Division is unavailable.",
            )
        old_party_id = division.customer_party_id
        division.customer_party_id = party.id
        record.issuing_party_id = party.id
        await self.repository.save(division)
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            "map_railway_customer",
            record.id,
            {"customer_party_id": str(old_party_id) if old_party_id else None},
            {
                "railway_division_id": str(division.id),
                "customer_party_id": str(party.id),
            },
        )
        return await self.get(record.id)

    @staticmethod
    def _ready(record: RailwayLoaImport) -> bool:
        return bool(
            record.project_id
            and record.railway_division_id
            and record.loa_number
            and record.loa_date
            and record.work_description
            and record.contract_value is not None
            and record.lines
            and not RailwayLoaImportService.boq_readiness_issues(record)
        )

    @staticmethod
    def boq_readiness_issues(record: RailwayLoaImport) -> list[dict]:
        issues: list[dict] = []
        schedule_by_group = {
            group.id: schedule.title_normalized
            for schedule in getattr(record, "schedules", [])
            for group in schedule.groups
        }
        reconciliation = record.boq_reconciliation or {}
        if reconciliation.get("document_coverage_status") != "COMPLETE":
            issues.append(
                {
                    "scope": "RECONCILIATION",
                    "field": "document_coverage",
                    "message": "Source-document BOQ coverage is incomplete.",
                }
            )
        if reconciliation.get("complete") is not True:
            issues.append(
                {
                    "scope": "RECONCILIATION",
                    "field": "complete",
                    "message": "BOQ reconciliation is not complete.",
                }
            )
        if reconciliation.get("total_discrepancies", 0) != 0:
            issues.append(
                {
                    "scope": "RECONCILIATION",
                    "field": "totals",
                    "message": "One or more BOQ schedule/group totals do not reconcile.",
                }
            )
        for line in record.lines:
            if line.extraction_outcome == "EXPLICITLY_IGNORED_BY_OWNER":
                continue
            schedule = schedule_by_group.get(getattr(line, "group_id", None))
            label = RailwayLoaImportService._line_identity(
                schedule, line.source_serial, getattr(line, "candidate_key", None)
            )
            if line.extraction_outcome != "EXTRACTED":
                outcome = line.extraction_outcome.replace("_", " ").lower()
                issues.append(
                    {
                        "scope": "LINE",
                        "line_number": line.line_number,
                        "field": "outcome",
                        "message": f"{label}: source item remains {outcome}.",
                    }
                )
                continue
            required = {
                "Sn. No.": bool(line.source_serial and line.source_serial.strip()),
                "description": bool(line.description and line.description.strip()),
                "UOM": bool(line.unit_text or line.unit_id),
                "quantity": line.quantity is not None and line.quantity > 0,
                "rate": line.rate is not None and line.rate >= 0,
                "amount": line.amount is not None and line.amount >= 0,
            }
            for field, valid in required.items():
                if not valid:
                    issues.append(
                        {
                            "scope": "LINE",
                            "line_number": line.line_number,
                            "field": field,
                            "message": f"{label}: {field} is required.",
                        }
                    )
        return issues

    @staticmethod
    def _line_identity(
        schedule: str | None, source_serial: str | None, candidate_key: str | None
    ) -> str:
        schedule_label = schedule or "Unresolved schedule"
        if source_serial:
            return f"{schedule_label} - Sn. {source_serial}"
        suffix = candidate_key[:8] if candidate_key else "unresolved"
        return f"{schedule_label} - unresolved Sn. No. ({suffix})"

    @staticmethod
    def _refresh_reconciliation(record: RailwayLoaImport) -> None:
        reconciliation = dict(record.boq_reconciliation or {})
        extracted = sum(line.extraction_outcome == "EXTRACTED" for line in record.lines)
        ignored = sum(
            line.extraction_outcome == "EXPLICITLY_IGNORED_BY_OWNER" for line in record.lines
        )
        unresolved = len(record.lines) - extracted - ignored
        reconciliation.update(
            {
                "source_rows_detected": len(record.lines),
                "extracted_successfully": extracted,
                "needs_review": unresolved,
                "explicitly_ignored": ignored,
                "complete": (
                    reconciliation.get("document_coverage_status") == "COMPLETE"
                    and unresolved == 0
                    and reconciliation.get("total_discrepancies", 0) == 0
                ),
            }
        )
        record.boq_reconciliation = reconciliation

    async def approve(
        self, import_id: UUID, payload: LoaImportApproval, actor_id: UUID
    ) -> RailwayLoaImport:
        record = await self.repository.get(import_id, lock=True)
        if record is None:
            raise AppError(404, "loa_import_not_found", "Railway LOA import does not exist.")
        if record.status == "APPROVED":
            return record
        if record.duplicate_candidates and not payload.confirm_duplicate:
            raise AppError(
                409,
                "possible_duplicate_loa",
                "Possible existing LOA found. Confirm after owner review.",
            )
        contract_service = ContractService(ContractRepository(self.repository.session))
        project_id = record.project_id
        if project_id is None and payload.new_project:
            project = await contract_service.create_project(payload.new_project, actor_id)
            project_id = project.id
            record.project_id = project.id
            self.repository.audit(
                actor_id,
                "create_project_from_import",
                record.id,
                None,
                {"project_id": str(project.id)},
            )
        if not project_id:
            raise AppError(
                422,
                "project_required",
                "Select an existing Project or provide a reviewed new Project.",
            )
        if not self._ready(record):
            raise AppError(
                422, "loa_import_unresolved", "Mandatory LOA or BOQ fields still need review."
            )
        loa = await contract_service.create_loa(
            LoaCreate(
                project_id=project_id,
                loa_number=record.loa_number,
                loa_date=record.loa_date,
                issuing_party_id=record.issuing_party_id,
                railway_division_id=record.railway_division_id,
                customer_reference=record.tender_reference,
                description=record.work_description,
                original_contract_value=record.contract_value,
                completion_date=record.completion_date,
                remarks=f"Completion period: {record.completion_period}"
                if record.completion_period
                else None,
                status="ACTIVE",
            ),
            actor_id,
        )
        for line in record.lines:
            if line.extraction_outcome == "EXPLICITLY_IGNORED_BY_OWNER":
                continue
            if not line.source_serial:
                raise AppError(
                    422,
                    "loa_item_serial_required",
                    "Every registered contractual item requires an owner-confirmed Sn. No.",
                )
            await contract_service.create_item(
                loa.id,
                LoaItemCreate(
                    item_number=line.source_serial,
                    product_id=line.product_id,
                    description=line.description,
                    hsn_code_id=line.hsn_code_id,
                    unit_id=line.unit_id,
                    unit_text=line.unit_text,
                    original_approved_quantity=line.quantity,
                    contractual_rate=line.rate,
                    remarks=line.remarks,
                    source_page=line.source_page,
                    source_serial=line.source_serial,
                    source_raw_text=line.source_raw_text,
                ),
                actor_id,
            )
        record.loa_id = loa.id
        record.status = "APPROVED"
        record.approved_at = datetime.now(UTC)
        record.approved_by_user_id = actor_id
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            "approve_create_loa",
            record.id,
            None,
            {"loa_id": str(loa.id), "boq_lines": len(record.lines)},
        )
        return await self.get(record.id)

    async def cancel(self, import_id: UUID, actor_id: UUID) -> RailwayLoaImport:
        record = await self.get(import_id)
        if record.status == "APPROVED":
            raise AppError(409, "loa_import_locked", "An approved import cannot be cancelled.")
        old = record.status
        record.status = "CANCELLED"
        await self.repository.save(record)
        self.repository.audit(
            actor_id, "cancel", record.id, {"status": old}, {"status": "CANCELLED"}
        )
        return record
