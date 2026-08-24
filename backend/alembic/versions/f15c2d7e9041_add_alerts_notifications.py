"""add alerts rules and notifications

Revision ID: f15c2d7e9041
Revises: e14a7b92c301
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "f15c2d7e9041"
down_revision = "e14a7b92c301"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rule_type", sa.String(50), nullable=False, unique=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("warning_days", sa.Integer()),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')", name="ck_alert_rules_severity"
        ),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_entity_type", sa.String(50), nullable=False),
        sa.Column("source_entity_id", sa.String(100), nullable=False),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("loa_id", sa.Uuid(), sa.ForeignKey("loas.id")),
        sa.Column("party_id", sa.Uuid(), sa.ForeignKey("parties.id")),
        sa.Column("assigned_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("assigned_role", sa.String(64)),
        sa.Column(
            "triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("due_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("acknowledged_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_reason", sa.String(1000)),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')", name="ck_alerts_severity"
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','ACKNOWLEDGED','RESOLVED','DISMISSED')", name="ck_alerts_status"
        ),
    )
    for name, cols in (
        ("ix_alerts_status", ["status"]),
        ("ix_alerts_severity", ["severity"]),
        ("ix_alerts_type", ["alert_type"]),
        ("ix_alerts_assigned_user", ["assigned_user_id"]),
        ("ix_alerts_source", ["source_entity_type", "source_entity_id"]),
        ("ix_alerts_project_loa", ["project_id", "loa_id"]),
        ("ix_alerts_dates", ["triggered_at", "due_date"]),
    ):
        op.create_index(name, "alerts", cols)
    op.create_index(
        "uq_alert_active_condition",
        "alerts",
        ["dedup_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN','ACKNOWLEDGED')"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_entity_type", sa.String(50), nullable=False),
        sa.Column("source_entity_id", sa.String(100), nullable=False),
        sa.Column("alert_id", sa.Uuid(), sa.ForeignKey("alerts.id")),
        sa.Column("action_url", sa.String(500)),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "alert_id", "recipient_user_id", name="uq_notification_alert_recipient"
        ),
    )
    op.create_index(
        "ix_notifications_recipient_read", "notifications", ["recipient_user_id", "is_read"]
    )
    defaults = [
        ("WORKFLOW_PENDING", None, "HIGH"),
        ("PO_DELIVERY", 7, "MEDIUM"),
        ("GRN_DISCREPANCY", None, "HIGH"),
        ("PROJECT_DEADLINE", 30, "MEDIUM"),
        ("LOA_DEADLINE", 30, "MEDIUM"),
        ("WARRANTY_EXPIRY", 30, "MEDIUM"),
        ("RECEIVABLE_DUE", 7, "MEDIUM"),
        ("ASSET_EXCEPTION", None, "HIGH"),
    ]
    table = sa.table(
        "alert_rules",
        sa.column("id"),
        sa.column("rule_type"),
        sa.column("is_enabled"),
        sa.column("warning_days"),
        sa.column("severity"),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": uuid.uuid4(),
                "rule_type": t,
                "is_enabled": True,
                "warning_days": w,
                "severity": s,
            }
            for t, w, s in defaults
        ],
    )


def downgrade():
    op.drop_table("notifications")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
