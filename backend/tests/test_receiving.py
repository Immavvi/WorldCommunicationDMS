from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth import AuditLog


async def login(client, email, password):
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def master(client, token, resource, data):
    response = await client.post(f"/api/v1/master-data/{resource}", json=data, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()


async def issued_po(client: AsyncClient, admin: str, super_admin: str, quantity="100"):
    customer = await master(
        client,
        admin,
        "parties",
        {"code": "GRN-CUST", "legal_name": "Customer", "roles": ["CUSTOMER"]},
    )
    vendor = await master(
        client,
        admin,
        "parties",
        {"code": "GRN-VEND", "legal_name": "Receipt Vendor", "roles": ["VENDOR"]},
    )
    unit = await master(
        client,
        admin,
        "units",
        {"code": "GRN-NOS", "name": "GRN Numbers", "symbol": "Nos", "decimal_places": 4},
    )
    organization = await master(
        client, admin, "organizations", {"code": "GRN-WC", "legal_name": "World Communication"}
    )
    billing = await master(
        client,
        admin,
        "organization-addresses",
        {
            "organization_id": organization["id"],
            "address_type": "BILL_TO",
            "label": "Bill",
            "address_line_1": "Billing",
            "city": "Kolkata",
            "state": "West Bengal",
            "postal_code": "700001",
        },
    )
    shipping = await master(
        client,
        admin,
        "organization-addresses",
        {
            "organization_id": organization["id"],
            "address_type": "SHIP_TO",
            "label": "Store",
            "address_line_1": "Store",
            "city": "Kolkata",
            "state": "West Bengal",
            "postal_code": "700002",
        },
    )
    project = (
        await client.post(
            "/api/v1/projects",
            json={
                "code": "GRN-PROJ",
                "name": "Receiving Project",
                "customer_party_id": customer["id"],
                "business_scope": "NON_RAILWAY",
            },
            headers=auth(admin),
        )
    ).json()
    po_response = await client.post(
        "/api/v1/purchase-orders",
        json={
            "po_date": "2026-08-24",
            "vendor_party_id": vendor["id"],
            "project_id": project["id"],
            "organization_id": organization["id"],
            "billing_organization_address_id": billing["id"],
            "ship_to_organization_address_id": shipping["id"],
            "tax_mode": "INTRA_STATE",
            "lines": [
                {
                    "description": "Serialized-ready equipment",
                    "unit_id": unit["id"],
                    "ordered_quantity": quantity,
                    "unit_rate": "10",
                    "cgst_percent": "9",
                    "sgst_percent": "9",
                }
            ],
        },
        headers=auth(admin),
    )
    assert po_response.status_code == 201, po_response.text
    po = po_response.json()
    await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "SUBMIT", "reason": "Ready"},
        headers=auth(admin),
    )
    await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved"},
        headers=auth(super_admin),
    )
    issued = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "ISSUE", "reason": "Issued"},
        headers=auth(super_admin),
    )
    return issued.json()


async def receipt(client, token, po, accepted, damaged="0", rejected="0", short="0"):
    received = Decimal(accepted) + Decimal(damaged) + Decimal(rejected)
    return await client.post(
        "/api/v1/material-receipts",
        json={
            "purchase_order_id": po["id"],
            "receipt_date": "2026-08-25",
            "receiving_location": "Main Store",
            "delivery_reference": "DELIVERY-1",
            "lines": [
                {
                    "purchase_order_line_id": po["lines"][0]["id"],
                    "quantity_received": str(received),
                    "quantity_accepted": accepted,
                    "quantity_short": short,
                    "quantity_damaged": damaged,
                    "quantity_rejected": rejected,
                }
            ],
        },
        headers=auth(token),
    )


async def transition(client, token, receipt_id, action):
    return await client.post(
        f"/api/v1/material-receipts/{receipt_id}/actions",
        json={"action": action, "reason": f"{action} receipt"},
        headers=auth(token),
    )


@pytest.mark.asyncio
async def test_partial_multiple_receipts_discrepancies_and_fulfillment(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    po = await issued_po(client, admin, super_admin)

    first = await receipt(client, admin, po, "40", damaged="2", rejected="1", short="5")
    assert first.status_code == 201, first.text
    assert first.json()["receipt_number"] == "GRN-000001"
    edited = await client.put(
        f"/api/v1/material-receipts/{first.json()['id']}/lines/{first.json()['lines'][0]['id']}",
        json={
            "purchase_order_line_id": po["lines"][0]["id"],
            "quantity_received": "43",
            "quantity_accepted": "40",
            "quantity_short": "5",
            "quantity_damaged": "2",
            "quantity_rejected": "1",
            "remarks": "Counts confirmed",
        },
        headers=auth(admin),
    )
    assert edited.status_code == 200, edited.text
    draft_position = (
        await client.get(
            f"/api/v1/purchase-orders/{po['id']}/receipt-position", headers=auth(admin)
        )
    ).json()[0]
    assert draft_position["accepted_to_date"] == "0.0000"
    await transition(client, admin, first.json()["id"], "RECEIVE")
    denied = await transition(client, admin, first.json()["id"], "VERIFY")
    assert denied.status_code == 403
    assert (await transition(client, super_admin, first.json()["id"], "VERIFY")).status_code == 200
    current_po = (
        await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth(admin))
    ).json()
    assert current_po["status"] == "PARTIALLY_FULFILLED"

    second = await receipt(client, admin, po, "35")
    await transition(client, admin, second.json()["id"], "RECEIVE")
    await transition(client, super_admin, second.json()["id"], "VERIFY")
    third = await receipt(client, admin, po, "25")
    await transition(client, admin, third.json()["id"], "RECEIVE")
    await transition(client, super_admin, third.json()["id"], "VERIFY")
    position = (
        await client.get(
            f"/api/v1/purchase-orders/{po['id']}/receipt-position", headers=auth(admin)
        )
    ).json()[0]
    assert position["ordered_quantity"] == "100.0000"
    assert position["accepted_to_date"] == "100.0000"
    assert position["pending_quantity"] == "0.0000"
    fulfilled = (
        await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth(admin))
    ).json()
    assert fulfilled["status"] == "FULFILLED"
    assert fulfilled["lines"][0]["ordered_quantity"] == "100.0000"
    assert first.json()["lines"][0]["description_snapshot"] == "Serialized-ready equipment"
    assert Decimal(first.json()["lines"][0]["quantity_damaged"]) == Decimal("2.0000")
    assert Decimal(first.json()["lines"][0]["quantity_rejected"]) == Decimal("1.0000")
    assert Decimal(first.json()["lines"][0]["quantity_short"]) == Decimal("5.0000")

    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = set(await session.scalars(select(AuditLog.action)))
        assert {
            "assign_number",
            "create",
            "update",
            "receive",
            "verify",
            "auto_fulfillment",
        }.issubset(actions)


@pytest.mark.asyncio
async def test_overreceipt_excess_and_verified_cancellation(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    po = await issued_po(client, admin, super_admin, "10")
    excess = await receipt(client, admin, po, "10", rejected="2")
    assert excess.status_code == 201
    assert excess.json()["lines"][0]["quantity_excess"] == "2.0000"
    await transition(client, admin, excess.json()["id"], "RECEIVE")
    await transition(client, super_admin, excess.json()["id"], "VERIFY")
    over = await receipt(client, admin, po, "0.0001")
    assert over.status_code == 422
    cancelled = await transition(client, super_admin, excess.json()["id"], "CANCEL")
    assert cancelled.status_code == 200
    position = (
        await client.get(
            f"/api/v1/purchase-orders/{po['id']}/receipt-position", headers=auth(admin)
        )
    ).json()[0]
    assert position["accepted_to_date"] == "0.0000"
    restored = (await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth(admin))).json()
    assert restored["status"] == "ISSUED"
