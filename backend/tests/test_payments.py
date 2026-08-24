from datetime import date, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from test_invoicing import action as invoice_action
from test_invoicing import invoice_foundation, invoice_payload
from test_receiving import auth, login, master

from app.models.auth import AuditLog
from app.models.invoicing import TaxInvoice


async def issued_invoice(client, admin, super_admin, quantity="4"):
    data = await invoice_foundation(client, admin, super_admin)
    invoice = (
        await client.post(
            "/api/v1/tax-invoices", json=invoice_payload(data, quantity), headers=auth(admin)
        )
    ).json()
    await invoice_action(client, admin, invoice["id"], "SUBMIT")
    await invoice_action(client, super_admin, invoice["id"], "APPROVE")
    await invoice_action(client, super_admin, invoice["id"], "ISSUE")
    return data, invoice


def payment_payload(data, amount="424.80"):
    return {
        "receipt_date": "2026-08-28",
        "customer_party_id": data["customer_id"],
        "organization_id": str(data["organization"].id),
        "bank_account_id": data["bank"]["id"],
        "payment_mode": "NEFT",
        "transaction_reference": "UTR-001",
        "transaction_date": "2026-08-28",
        "amount_received": amount,
        "currency": "INR",
    }


@pytest.mark.asyncio
async def test_partial_payment_confirmation_receivable_and_reversal(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data, invoice = await issued_invoice(client, admin, super_admin)
    created = await client.post(
        "/api/v1/payments", json=payment_payload(data, "200.00"), headers=auth(admin)
    )
    assert created.status_code == 201, created.text
    payment = created.json()
    assert payment["receipt_number"] == "RCT-000001"
    assert payment["customer_snapshot"]["legal_name"]
    allocated = await client.post(
        f"/api/v1/payments/{payment['id']}/allocations",
        json={
            "tax_invoice_id": invoice["id"],
            "allocated_amount": "200.00",
            "allocation_date": "2026-08-28",
        },
        headers=auth(admin),
    )
    assert allocated.status_code == 200
    before = (await client.get("/api/v1/receivables", headers=auth(admin))).json()[0]
    assert before["received_amount"] == "0.00" and before["payment_status"] == "UNPAID"
    denied = await client.post(
        f"/api/v1/payments/{payment['id']}/actions",
        json={"action": "CONFIRM", "reason": "received"},
        headers=auth(admin),
    )
    assert denied.status_code == 403
    confirmed = await client.post(
        f"/api/v1/payments/{payment['id']}/actions",
        json={"action": "CONFIRM", "reason": "bank verified"},
        headers=auth(super_admin),
    )
    assert confirmed.status_code == 200
    position = (await client.get("/api/v1/receivables", headers=auth(admin))).json()[0]
    assert position["received_amount"] == "200.00"
    assert position["outstanding_amount"] == "224.80"
    assert position["payment_status"] == "PARTIALLY_PAID"
    reversed_payment = await client.post(
        f"/api/v1/payments/{payment['id']}/actions",
        json={"action": "REVERSE", "reason": "bank return"},
        headers=auth(super_admin),
    )
    assert reversed_payment.status_code == 200
    assert len(reversed_payment.json()["allocations"]) == 1
    after = (await client.get("/api/v1/receivables", headers=auth(admin))).json()[0]
    assert after["received_amount"] == "0.00"
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "customer_payment")
            )
        )
    assert {"assign_number", "create", "confirm", "reverse"}.issubset(actions)


@pytest.mark.asyncio
async def test_overallocation_cross_customer_validation_and_unallocated_receipt(
    client: AsyncClient,
):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data, invoice = await issued_invoice(client, admin, super_admin)
    payment = (
        await client.post(
            "/api/v1/payments", json=payment_payload(data, "500.00"), headers=auth(admin)
        )
    ).json()
    assert payment["unallocated_amount"] == "500.00"
    excessive = await client.post(
        f"/api/v1/payments/{payment['id']}/allocations",
        json={
            "tax_invoice_id": invoice["id"],
            "allocated_amount": "500.00",
            "allocation_date": "2026-08-28",
        },
        headers=auth(admin),
    )
    assert excessive.status_code == 409
    cancel = await client.post(
        f"/api/v1/payments/{payment['id']}/actions",
        json={"action": "CANCEL", "reason": "duplicate receipt"},
        headers=auth(super_admin),
    )
    assert cancel.status_code == 200 and cancel.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_multiple_payments_paid_overdue_history_and_cross_customer(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data, invoice = await issued_invoice(client, admin, super_admin)
    async with client._session_factory.begin() as session:  # type: ignore[attr-defined]
        stored = await session.get(TaxInvoice, UUID(invoice["id"]))
        stored.due_date = date.today() - timedelta(days=5)
    other = await master(
        client,
        admin,
        "parties",
        {"code": "PAY-OTHER", "legal_name": "Other Customer", "roles": ["CUSTOMER"]},
    )
    wrong_payload = payment_payload(data, "100.00")
    wrong_payload["customer_party_id"] = other["id"]
    wrong = (await client.post("/api/v1/payments", json=wrong_payload, headers=auth(admin))).json()
    cross = await client.post(
        f"/api/v1/payments/{wrong['id']}/allocations",
        json={
            "tax_invoice_id": invoice["id"],
            "allocated_amount": "1.00",
            "allocation_date": "2026-08-28",
        },
        headers=auth(admin),
    )
    assert cross.status_code == 422
    assert (await client.get("/api/v1/receivables", headers=auth(admin))).json()[0][
        "payment_status"
    ] == "OVERDUE"
    for index, amount in enumerate(("200.00", "224.80"), start=1):
        payload = payment_payload(data, amount)
        payload["transaction_reference"] = f"UTR-MULTI-{index}"
        payment = (await client.post("/api/v1/payments", json=payload, headers=auth(admin))).json()
        assert (
            await client.post(
                f"/api/v1/payments/{payment['id']}/allocations",
                json={
                    "tax_invoice_id": invoice["id"],
                    "allocated_amount": amount,
                    "allocation_date": "2026-08-28",
                },
                headers=auth(admin),
            )
        ).status_code == 200
        assert (
            await client.post(
                f"/api/v1/payments/{payment['id']}/actions",
                json={"action": "CONFIRM", "reason": "verified"},
                headers=auth(super_admin),
            )
        ).status_code == 200
        position = (await client.get("/api/v1/receivables", headers=auth(admin))).json()[0]
        assert position["payment_status"] == ("PARTIALLY_PAID_OVERDUE" if index == 1 else "PAID")
    history = await client.get(
        f"/api/v1/tax-invoices/{invoice['id']}/payments", headers=auth(admin)
    )
    assert history.status_code == 200 and len(history.json()) == 2


@pytest.mark.asyncio
async def test_one_payment_allocates_multiple_invoices(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await invoice_foundation(client, admin, super_admin)
    invoices = [
        (
            await client.post(
                "/api/v1/tax-invoices", json=invoice_payload(data, "2"), headers=auth(admin)
            )
        ).json()
        for _ in range(2)
    ]
    payment = (
        await client.post("/api/v1/payments", json=payment_payload(data), headers=auth(admin))
    ).json()
    invalid = await client.post(
        f"/api/v1/payments/{payment['id']}/allocations",
        json={
            "tax_invoice_id": invoices[0]["id"],
            "allocated_amount": "1.00",
            "allocation_date": "2026-08-28",
        },
        headers=auth(admin),
    )
    assert invalid.status_code == 422
    for invoice in invoices:
        await invoice_action(client, admin, invoice["id"], "SUBMIT")
        await invoice_action(client, super_admin, invoice["id"], "APPROVE")
        await invoice_action(client, super_admin, invoice["id"], "ISSUE")
        result = await client.post(
            f"/api/v1/payments/{payment['id']}/allocations",
            json={
                "tax_invoice_id": invoice["id"],
                "allocated_amount": "212.40",
                "allocation_date": "2026-08-28",
            },
            headers=auth(admin),
        )
        assert result.status_code == 200
    confirmed = await client.post(
        f"/api/v1/payments/{payment['id']}/actions",
        json={"action": "CONFIRM", "reason": "two invoices verified"},
        headers=auth(super_admin),
    )
    assert confirmed.status_code == 200 and len(confirmed.json()["allocations"]) == 2
    assert confirmed.json()["unallocated_amount"] == "0.00"
