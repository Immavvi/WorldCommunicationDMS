from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.reporting_repository import MODELS, ReportingRepository
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.reporting_service import FINANCE, ReportingService

router = APIRouter(tags=["reporting"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def service(session: AsyncSession = Depends(get_db_session)):
    return ReportingService(ReportingRepository(session))


def is_super(user):
    return any(r.name == SUPER_ADMIN_ROLE for r in user.roles)


def guard(name, user):
    if name in FINANCE and not is_super(user):
        raise AppError(
            403,
            "financial_report_denied",
            "SUPER-ADMIN access is required for this financial report.",
        )


@router.get("/dashboard")
async def dashboard(user: User = Manager, reports: ReportingService = Depends(service)):
    return await reports.dashboard(user.id, is_super(user))


@router.get("/reports/{name}")
async def report(
    name: str,
    date_from: date | None = None,
    date_to: date | None = None,
    financial_year: str | None = None,
    project_id: UUID | None = None,
    loa_id: UUID | None = None,
    status: str | None = None,
    customer_party_id: UUID | None = None,
    vendor_party_id: UUID | None = None,
    railway_division_id: UUID | None = None,
    product_id: UUID | None = None,
    oem_party_id: UUID | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user: User = Manager,
    reports: ReportingService = Depends(service),
):
    if name not in MODELS and name != "receivables":
        raise AppError(404, "report_not_found", "Report does not exist.")
    guard(name, user)
    if financial_year:
        try:
            start = int(financial_year.split("-")[0])
            date_from = date(start, 4, 1)
            date_to = date(start + 1, 3, 31)
        except ValueError:
            raise AppError(
                422, "invalid_financial_year", "Use a starting year such as 2026-27."
            ) from None
    filters = {
        k: v
        for k, v in locals().items()
        if k
        in {
            "date_from",
            "date_to",
            "project_id",
            "loa_id",
            "status",
            "customer_party_id",
            "vendor_party_id",
            "railway_division_id",
            "product_id",
            "oem_party_id",
        }
        and v is not None
    }
    return await reports.report(name, filters, is_super(user), offset, limit)


@router.get("/reports/projects/{project_id}/summary")
async def project_summary(
    project_id: UUID, user: User = Manager, reports: ReportingService = Depends(service)
):
    project = await reports.report("projects", {"project_id": project_id}, is_super(user), 0, 1)
    if not project:
        raise AppError(404, "project_not_found", "Project does not exist.")
    result = {
        "project": project[0],
        "purchase_orders": await reports.report(
            "purchase-orders", {"project_id": project_id}, is_super(user), 0, 1000
        ),
        "receipts": await reports.report(
            "receipts", {"project_id": project_id}, is_super(user), 0, 1000
        ),
        "challans": await reports.report(
            "challans", {"project_id": project_id}, is_super(user), 0, 1000
        ),
        "assets": await reports.report(
            "assets", {"project_id": project_id}, is_super(user), 0, 1000
        ),
        "alerts": await reports.report(
            "alerts", {"project_id": project_id}, is_super(user), 0, 1000
        ),
    }
    if is_super(user):
        result.update(
            proforma_invoices=await reports.report(
                "proforma-invoices", {"project_id": project_id}, True, 0, 1000
            ),
            tax_invoices=await reports.report(
                "tax-invoices", {"project_id": project_id}, True, 0, 1000
            ),
            receivables=await reports.report(
                "receivables", {"project_id": project_id}, True, 0, 1000
            ),
        )
    return result


@router.get("/reports/loas/{loa_id}/reconciliation")
async def reconciliation(
    loa_id: UUID, user: User = Manager, reports: ReportingService = Depends(service)
):
    return await reports.loa_reconciliation(loa_id, is_super(user))


@router.get("/reports/{name}/export.xlsx")
async def export(
    name: str,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: UUID | None = None,
    loa_id: UUID | None = None,
    status: str | None = None,
    user: User = Manager,
    reports: ReportingService = Depends(service),
):
    if name not in MODELS and name != "receivables":
        raise AppError(404, "report_not_found", "Report does not exist.")
    guard(name, user)
    filters = {
        k: v
        for k, v in {
            "date_from": date_from,
            "date_to": date_to,
            "project_id": project_id,
            "loa_id": loa_id,
            "status": status,
        }.items()
        if v is not None
    }
    rows = await reports.report(name, filters, is_super(user), 0, 10000)
    stream = reports.excel(name, rows)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="wcdms-{name}-{date.today()}.xlsx"'},
    )
