from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    alert_type: str
    severity: str
    title: str
    message: str
    source_entity_type: str
    source_entity_id: str
    project_id: UUID | None
    loa_id: UUID | None
    party_id: UUID | None
    assigned_user_id: UUID | None
    assigned_role: str | None
    triggered_at: datetime
    due_date: date | None
    status: str
    acknowledged_by_user_id: UUID | None
    acknowledged_at: datetime | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    resolution_reason: str | None
    last_evaluated_at: datetime
    context: dict | None
    created_at: datetime
    updated_at: datetime


class AlertAction(BaseModel):
    action: str = Field(pattern="^(ACKNOWLEDGE|RESOLVE|DISMISS)$")
    reason: str | None = Field(default=None, max_length=1000)


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rule_type: str
    is_enabled: bool
    warning_days: int | None
    severity: str
    created_at: datetime
    updated_at: datetime


class RuleUpdate(BaseModel):
    is_enabled: bool | None = None
    warning_days: int | None = Field(default=None, ge=0, le=3650)
    severity: str | None = Field(default=None, pattern="^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    recipient_user_id: UUID
    category: str
    title: str
    message: str
    source_entity_type: str
    source_entity_id: str
    alert_id: UUID | None
    action_url: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class EvaluationResult(BaseModel):
    created: int
    updated: int
    resolved: int
