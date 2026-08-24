from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.attention_repository import AttentionRepository
from app.schemas.attention import (
    AlertAction,
    AlertResponse,
    EvaluationResult,
    NotificationResponse,
    RuleResponse,
    RuleUpdate,
)
from app.services.attention_service import AttentionService
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE

router = APIRouter(tags=["attention"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))
Super = Depends(require_roles(SUPER_ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return AttentionService(AttentionRepository(session))


@router.get("/alerts", response_model=list[AlertResponse])
async def alerts(
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    project_id: UUID | None = None,
    loa_id: UUID | None = None,
    assigned_user_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user: User = Manager,
    service: AttentionService = Depends(get_service),
):
    rows = await service.repository.alerts(
        status=status,
        severity=severity,
        alert_type=alert_type,
        project_id=project_id,
        loa_id=loa_id,
        assigned_user_id=assigned_user_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
    if any(role.name == SUPER_ADMIN_ROLE for role in user.roles):
        return rows
    return [
        alert
        for alert in rows
        if alert.assigned_role == ADMIN_ROLE or alert.assigned_user_id == user.id
    ]


@router.get("/alerts/my-attention", response_model=list[AlertResponse])
async def my_attention(user: User = Manager, service: AttentionService = Depends(get_service)):
    rows = await service.repository.alerts(limit=500)
    roles = {r.name for r in user.roles}
    return [
        a
        for a in rows
        if a.status in ("OPEN", "ACKNOWLEDGED")
        and (a.assigned_user_id == user.id or a.assigned_role in roles)
    ]


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def alert_detail(
    alert_id: UUID, user: User = Manager, service: AttentionService = Depends(get_service)
):
    row = await service.repository.get_alert(alert_id)
    if not row:
        raise AppError(404, "alert_not_found", "Alert does not exist.")
    if not any(role.name == SUPER_ADMIN_ROLE for role in user.roles):
        if row.assigned_role != ADMIN_ROLE and row.assigned_user_id != user.id:
            raise AppError(403, "authorization_denied", "Alert access is denied.")
    return row


@router.post("/alerts/{alert_id}/actions", response_model=AlertResponse)
async def alert_action(
    alert_id: UUID,
    payload: AlertAction,
    user: User = Manager,
    service: AttentionService = Depends(get_service),
):
    return await service.action(
        alert_id, payload, user, any(r.name == SUPER_ADMIN_ROLE for r in user.roles)
    )


@router.get("/alert-rules", response_model=list[RuleResponse])
async def rules(_: User = Manager, service: AttentionService = Depends(get_service)):
    return await service.repository.rules()


@router.patch("/alert-rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    payload: RuleUpdate,
    user: User = Super,
    service: AttentionService = Depends(get_service),
):
    rule = next((r for r in await service.repository.rules() if r.id == rule_id), None)
    if not rule:
        raise AppError(404, "alert_rule_not_found", "Alert rule does not exist.")
    old = {k: getattr(rule, k) for k in payload.model_dump(exclude_unset=True)}
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    service.repository.audit(
        user.id, "update", "alert_rule", rule.id, old, payload.model_dump(exclude_unset=True)
    )
    await service.session.flush()
    await service.session.refresh(rule)
    return rule


@router.post("/alerts/evaluate", response_model=EvaluationResult)
async def evaluate(user: User = Super, service: AttentionService = Depends(get_service)):
    return await service.evaluate(user.id)


@router.get("/notifications", response_model=list[NotificationResponse])
async def notifications(user: User = Manager, service: AttentionService = Depends(get_service)):
    return await service.repository.notifications(user.id)


@router.get("/notifications/unread-count")
async def unread_count(user: User = Manager, service: AttentionService = Depends(get_service)):
    return {"count": await service.repository.unread_count(user.id)}


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def read_notification(
    notification_id: UUID, user: User = Manager, service: AttentionService = Depends(get_service)
):
    note = await service.repository.get_notification(notification_id, user.id)
    if not note:
        raise AppError(404, "notification_not_found", "Notification does not exist.")
    note.is_read = True
    note.read_at = datetime.now().astimezone()
    await service.session.flush()
    return note


@router.post("/notifications/read-all")
async def read_all(user: User = Manager, service: AttentionService = Depends(get_service)):
    now = datetime.now().astimezone()
    rows = await service.repository.unread(user.id)
    for note in rows:
        note.is_read = True
        note.read_at = now
    await service.session.flush()
    return {"updated": len(rows)}
