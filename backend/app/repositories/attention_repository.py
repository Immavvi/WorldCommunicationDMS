from sqlalchemy import func, select

from app.models.attention import Alert, AlertRule, Notification
from app.models.auth import AuditLog, Role, User


class AttentionRepository:
    def __init__(self, session):
        self.session = session

    async def rules(self):
        return list(await self.session.scalars(select(AlertRule).order_by(AlertRule.rule_type)))

    async def alerts(self, **filters):
        q = select(Alert)
        for key in ("status", "severity", "alert_type", "project_id", "loa_id", "assigned_user_id"):
            if filters.get(key):
                q = q.where(getattr(Alert, key) == filters[key])
        if filters.get("date_from"):
            q = q.where(Alert.triggered_at >= filters["date_from"])
        if filters.get("date_to"):
            q = q.where(Alert.triggered_at < filters["date_to"])
        return list(
            await self.session.scalars(
                q.order_by(Alert.triggered_at.desc())
                .offset(filters.get("offset", 0))
                .limit(filters.get("limit", 100))
            )
        )

    async def get_alert(self, alert_id):
        return await self.session.get(Alert, alert_id)

    async def active(self):
        return list(
            await self.session.scalars(
                select(Alert).where(Alert.status.in_(("OPEN", "ACKNOWLEDGED")))
            )
        )

    async def users_for(self, alert):
        q = select(User).where(User.is_active.is_(True))
        if alert.assigned_user_id:
            q = q.where(User.id == alert.assigned_user_id)
        elif alert.assigned_role:
            q = q.join(User.roles).where(Role.name == alert.assigned_role)
        return list((await self.session.scalars(q)).unique())

    async def notifications(self, user_id, limit=50):
        return list(
            await self.session.scalars(
                select(Notification)
                .where(Notification.recipient_user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
        )

    async def unread_count(self, user_id):
        return await self.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_user_id == user_id, Notification.is_read.is_(False))
        )

    async def get_notification(self, nid, user_id):
        return await self.session.scalar(
            select(Notification).where(
                Notification.id == nid, Notification.recipient_user_id == user_id
            )
        )

    async def unread(self, user_id):
        return list(
            await self.session.scalars(
                select(Notification).where(
                    Notification.recipient_user_id == user_id, Notification.is_read.is_(False)
                )
            )
        )

    def audit(self, actor, action, entity, id, old=None, new=None, reason=None):
        self.session.add(
            AuditLog(
                actor_user_id=actor,
                action=action,
                entity_type=entity,
                entity_id=str(id),
                old_value=old,
                new_value=new,
                reason=reason,
            )
        )
