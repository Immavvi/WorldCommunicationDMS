from datetime import date, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from test_payments import issued_invoice, payment_payload
from test_receiving import auth, login

from app.models.invoicing import TaxInvoice


@pytest.mark.asyncio
async def test_overdue_alert_dedup_acknowledge_notification_and_auto_resolution(
    client: AsyncClient,
):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data, invoice = await issued_invoice(client, admin, super_admin)
    async with client._session_factory.begin() as session:  # type: ignore[attr-defined]
        stored = await session.get(TaxInvoice, UUID(invoice["id"]))
        stored.due_date = date.today() - timedelta(days=3)
    first = await client.post("/api/v1/alerts/evaluate", headers=auth(super_admin))
    assert first.status_code == 200 and first.json()["created"] >= 1
    second = await client.post("/api/v1/alerts/evaluate", headers=auth(super_admin))
    assert second.status_code == 200 and second.json()["created"] == 0
    alerts = (await client.get("/api/v1/alerts", headers=auth(super_admin))).json()
    receivable = next(a for a in alerts if a["alert_type"] == "RECEIVABLE_DUE")
    assert receivable["severity"] == "HIGH" and "Outstanding" in receivable["message"]
    acknowledged = await client.post(
        f"/api/v1/alerts/{receivable['id']}/actions",
        json={"action": "ACKNOWLEDGE"},
        headers=auth(super_admin),
    )
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"
    assert (
        await client.get("/api/v1/notifications/unread-count", headers=auth(super_admin))
    ).json()["count"] >= 1
    note = (await client.get("/api/v1/notifications", headers=auth(super_admin))).json()[0]
    assert (
        await client.post(f"/api/v1/notifications/{note['id']}/read", headers=auth(super_admin))
    ).status_code == 200
    payment = (
        await client.post("/api/v1/payments", json=payment_payload(data), headers=auth(admin))
    ).json()
    await client.post(
        f"/api/v1/payments/{payment['id']}/allocations",
        json={
            "tax_invoice_id": invoice["id"],
            "allocated_amount": invoice["grand_total"],
            "allocation_date": str(date.today()),
        },
        headers=auth(admin),
    )
    await client.post(
        f"/api/v1/payments/{payment['id']}/actions",
        json={"action": "CONFIRM", "reason": "bank verified"},
        headers=auth(super_admin),
    )
    result = await client.post("/api/v1/alerts/evaluate", headers=auth(super_admin))
    assert result.json()["resolved"] >= 1
    historical = (await client.get("/api/v1/alerts", headers=auth(super_admin))).json()
    assert next(a for a in historical if a["id"] == receivable["id"])["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_rule_permissions_and_private_notifications(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    rules = (await client.get("/api/v1/alert-rules", headers=auth(admin))).json()
    rule = next(r for r in rules if r["rule_type"] == "WARRANTY_EXPIRY")
    denied = await client.patch(
        f"/api/v1/alert-rules/{rule['id']}", json={"warning_days": 14}, headers=auth(admin)
    )
    assert denied.status_code == 403
    changed = await client.patch(
        f"/api/v1/alert-rules/{rule['id']}", json={"warning_days": 14}, headers=auth(super_admin)
    )
    assert changed.status_code == 200 and changed.json()["warning_days"] == 14
    assert (await client.post("/api/v1/alerts/evaluate", headers=auth(admin))).status_code == 403
