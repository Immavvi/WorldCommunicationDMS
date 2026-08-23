from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from test_procurement import foundation as procurement_foundation
from test_procurement import po_payload
from test_receiving import auth, issued_po, login, master, receipt, transition

from app.models.auth import AuditLog
from app.models.master_data import OrganizationAddress, Project


async def verified_material(client, admin, super_admin, quantity="10"):
    po = await issued_po(client, admin, super_admin, quantity)
    grn = await receipt(client, admin, po, quantity)
    await transition(client, admin, grn.json()["id"], "RECEIVE")
    await transition(client, super_admin, grn.json()["id"], "VERIFY")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        project = await session.get(Project, UUID(po["project_id"]))
        dispatch_from = await session.scalar(select(OrganizationAddress))
    address = await master(
        client,
        admin,
        "party-addresses",
        {
            "party_id": str(project.customer_party_id),
            "address_type": "SHIP_TO",
            "label": "Customer Store",
            "address_line_1": "Destination",
            "city": "Kolkata",
            "state": "West Bengal",
            "postal_code": "700003",
        },
    )
    return po, grn.json(), str(project.customer_party_id), str(dispatch_from.id), address


def payload(po, grn, customer_id, dispatch_from_id, address, quantity="10"):
    return {
        "challan_date": "2026-08-26",
        "project_id": po["project_id"],
        "business_scope": "NON_RAILWAY",
        "customer_party_id": customer_id,
        "ship_to_party_address_id": address["id"],
        "dispatch_from_address_id": dispatch_from_id,
        "vehicle_number": "WB01AB1234",
        "lines": [
            {
                "dispatched_quantity": quantity,
                "allocations": [
                    {
                        "material_receipt_line_id": grn["lines"][0]["id"],
                        "allocated_quantity": quantity,
                    }
                ],
            }
        ],
    }


async def action(client, token, challan_id, name):
    return await client.post(
        f"/api/v1/supply-challans/{challan_id}/actions",
        json={"action": name, "reason": f"{name} test"},
        headers=auth(token),
    )


@pytest.mark.asyncio
async def test_variation_origin_contract_item_dispatch(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await procurement_foundation(client, admin)
    variation = (
        await client.post(
            f"/api/v1/loas/{data['loa']['id']}/variations",
            json={
                "reference_number": "VAR/DISPATCH",
                "variation_date": "2026-08-25",
                "lines": [
                    {
                        "description": "Variation-origin equipment",
                        "unit_id": data["unit"]["id"],
                        "direction": "POSITIVE",
                        "quantity": "3",
                        "rate": "50",
                    }
                ],
            },
            headers=auth(admin),
        )
    ).json()
    await client.post(
        f"/api/v1/variations/{variation['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved new contractual item"},
        headers=auth(super_admin),
    )
    variation_line = variation["lines"][0]
    purchase = po_payload(data, "3")
    purchase["lines"][0].pop("loa_item_id")
    purchase["lines"][0]["variation_line_id"] = variation_line["id"]
    po = (await client.post("/api/v1/purchase-orders", json=purchase, headers=auth(admin))).json()
    for transition_name, token in (
        ("SUBMIT", admin),
        ("APPROVE", super_admin),
        ("ISSUE", super_admin),
    ):
        await client.post(
            f"/api/v1/purchase-orders/{po['id']}/actions",
            json={"action": transition_name, "reason": transition_name},
            headers=auth(token),
        )
    grn = await receipt(client, admin, po, "3")
    await transition(client, admin, grn.json()["id"], "RECEIVE")
    await transition(client, super_admin, grn.json()["id"], "VERIFY")
    party_address = await master(
        client,
        admin,
        "party-addresses",
        {
            "party_id": data["customer"]["id"],
            "address_type": "SHIP_TO",
            "label": "Variation Destination",
            "address_line_1": "Customer Store",
            "city": "Kolkata",
            "state": "West Bengal",
            "postal_code": "700010",
        },
    )
    created = await client.post(
        "/api/v1/supply-challans",
        json={
            "challan_date": "2026-08-26",
            "project_id": data["project"]["id"],
            "loa_id": data["loa"]["id"],
            "business_scope": "NON_RAILWAY",
            "customer_party_id": data["customer"]["id"],
            "ship_to_party_address_id": party_address["id"],
            "dispatch_from_address_id": data["shipping"]["id"],
            "lines": [
                {
                    "dispatched_quantity": "3",
                    "allocations": [
                        {
                            "material_receipt_line_id": grn.json()["lines"][0]["id"],
                            "allocated_quantity": "3",
                        }
                    ],
                }
            ],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["lines"][0]["variation_line_id"] == variation_line["id"]
    await action(client, admin, created.json()["id"], "READY")
    dispatched = await action(client, admin, created.json()["id"], "DISPATCH")
    assert dispatched.status_code == 200, dispatched.text
    available = (
        await client.get(
            "/api/v1/dispatch-availability",
            params={"project_id": data["project"]["id"]},
            headers=auth(admin),
        )
    ).json()[0]
    assert available["contract_origin"] == "VARIATION"
    assert Decimal(available["remaining_contract_quantity"]) == Decimal("0")


@pytest.mark.asyncio
async def test_railway_original_contract_dispatch_uses_safe_snapshots(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    customer = await master(
        client,
        admin,
        "parties",
        {"code": "RLY-D-C", "legal_name": "Railway Customer", "roles": ["CUSTOMER"]},
    )
    vendor = await master(
        client,
        admin,
        "parties",
        {"code": "RLY-D-V", "legal_name": "Secret Vendor", "roles": ["VENDOR"]},
    )
    zone = await master(client, admin, "railway-zones", {"code": "ER-D", "name": "Eastern Railway"})
    division = await master(
        client,
        admin,
        "railway-divisions",
        {"code": "SDAH-D", "name": "Sealdah", "zone_id": zone["id"]},
    )
    authority = await master(
        client,
        admin,
        "railway-authorities",
        {
            "division_id": division["id"],
            "code": "RLY-CONS-D",
            "name": "Railway Consignee",
            "roles": ["CONSIGNEE", "BILL_TO"],
        },
    )
    railway_address = await master(
        client,
        admin,
        "railway-authority-addresses",
        {
            "authority_id": authority["id"],
            "label": "Railway Store",
            "address_line_1": "Platform Store",
            "city": "Kolkata",
            "state": "West Bengal",
            "postal_code": "700014",
        },
    )
    unit = await master(
        client,
        admin,
        "units",
        {"code": "RLY-NOS-D", "name": "Railway Numbers", "symbol": "Nos"},
    )
    organization = await master(
        client,
        admin,
        "organizations",
        {"code": "WC-RLY-D", "legal_name": "World Communication"},
    )
    addresses = []
    for kind, label_text in (("BILL_TO", "Office"), ("SHIP_TO", "Dispatch Store")):
        addresses.append(
            await master(
                client,
                admin,
                "organization-addresses",
                {
                    "organization_id": organization["id"],
                    "address_type": kind,
                    "label": label_text,
                    "address_line_1": label_text,
                    "city": "Kolkata",
                    "state": "West Bengal",
                    "postal_code": "700001",
                },
            )
        )
    project = (
        await client.post(
            "/api/v1/projects",
            json={
                "code": "RLY-D-P",
                "name": "Railway Dispatch",
                "customer_party_id": customer["id"],
                "business_scope": "RAILWAY",
                "railway_division_id": division["id"],
            },
            headers=auth(admin),
        )
    ).json()
    loa = (
        await client.post(
            "/api/v1/loas",
            json={
                "project_id": project["id"],
                "loa_number": "LOA/RLY/D",
                "loa_date": "2026-08-24",
            },
            headers=auth(admin),
        )
    ).json()
    loa_item = (
        await client.post(
            f"/api/v1/loas/{loa['id']}/items",
            json={
                "item_number": "1",
                "description": "Railway contract equipment",
                "unit_id": unit["id"],
                "original_approved_quantity": "5",
                "contractual_rate": "999.99",
            },
            headers=auth(admin),
        )
    ).json()
    po = (
        await client.post(
            "/api/v1/purchase-orders",
            json={
                "po_date": "2026-08-24",
                "vendor_party_id": vendor["id"],
                "project_id": project["id"],
                "loa_id": loa["id"],
                "organization_id": organization["id"],
                "billing_organization_address_id": addresses[0]["id"],
                "ship_to_organization_address_id": addresses[1]["id"],
                "tax_mode": "INTRA_STATE",
                "lines": [
                    {
                        "description": "Confidential purchase description",
                        "unit_id": unit["id"],
                        "ordered_quantity": "5",
                        "unit_rate": "123.45",
                        "cgst_percent": "9",
                        "sgst_percent": "9",
                        "loa_item_id": loa_item["id"],
                    }
                ],
            },
            headers=auth(admin),
        )
    ).json()
    for transition_name, token in (
        ("SUBMIT", admin),
        ("APPROVE", super_admin),
        ("ISSUE", super_admin),
    ):
        result = await client.post(
            f"/api/v1/purchase-orders/{po['id']}/actions",
            json={"action": transition_name, "reason": transition_name},
            headers=auth(token),
        )
        assert result.status_code == 200, result.text
    grn = await receipt(client, admin, po, "5")
    await transition(client, admin, grn.json()["id"], "RECEIVE")
    await transition(client, super_admin, grn.json()["id"], "VERIFY")
    created = await client.post(
        "/api/v1/supply-challans",
        json={
            "challan_date": "2026-08-26",
            "project_id": project["id"],
            "loa_id": loa["id"],
            "business_scope": "RAILWAY",
            "customer_party_id": customer["id"],
            "railway_division_id": division["id"],
            "consignee_authority_id": authority["id"],
            "bill_to_authority_id": authority["id"],
            "ship_to_railway_address_id": railway_address["id"],
            "dispatch_from_address_id": addresses[1]["id"],
            "lines": [
                {
                    "dispatched_quantity": "5",
                    "allocations": [
                        {
                            "material_receipt_line_id": grn.json()["lines"][0]["id"],
                            "allocated_quantity": "5",
                        }
                    ],
                }
            ],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["lines"][0]["loa_item_id"] == loa_item["id"]
    assert record["consignee_snapshot"]["name"] == "Railway Consignee"
    assert record["delivery_address_snapshot"]["address_line_1"] == "Platform Store"
    forbidden = ("unit_rate", "subtotal", "grand_total", "vendor_snapshot", "margin")
    assert not any(field in created.text.lower() for field in forbidden)
    await action(client, admin, record["id"], "READY")
    dispatched = await action(client, admin, record["id"], "DISPATCH")
    assert dispatched.status_code == 200, dispatched.text
    available = (
        await client.get(
            "/api/v1/dispatch-availability",
            params={"project_id": project["id"]},
            headers=auth(admin),
        )
    ).json()[0]
    assert available["contract_origin"] == "ORIGINAL_LOA"
    assert Decimal(available["remaining_contract_quantity"]) == Decimal("0")


@pytest.mark.asyncio
async def test_partial_dispatch_workflow_availability_cancellation_and_confidentiality(
    client: AsyncClient,
):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    po, grn, customer_id, dispatch_from_id, address = await verified_material(
        client, admin, super_admin
    )
    first = await client.post(
        "/api/v1/supply-challans",
        json=payload(po, grn, customer_id, dispatch_from_id, address, "4"),
        headers=auth(admin),
    )
    assert first.status_code == 201, first.text
    record = first.json()
    assert record["challan_number"] == "CH-000001"
    assert record["status"] == "DRAFT"
    line_id = record["lines"][0]["id"]
    edited = await client.put(
        f"/api/v1/supply-challans/{record['id']}/lines/{line_id}",
        json={
            "dispatched_quantity": "4.2500",
            "allocations": [
                {
                    "material_receipt_line_id": grn["lines"][0]["id"],
                    "allocated_quantity": "4.2500",
                }
            ],
        },
        headers=auth(admin),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["lines"][0]["id"] == line_id
    forbidden_names = {"rate", "price", "cost", "tax", "margin", "vendor"}
    assert not any(name in first.text.lower() for name in forbidden_names)
    availability = (
        await client.get(
            "/api/v1/dispatch-availability",
            params={"project_id": po["project_id"]},
            headers=auth(admin),
        )
    ).json()[0]
    assert Decimal(availability["available_quantity"]) == Decimal("10")
    assert (await action(client, admin, record["id"], "READY")).status_code == 200
    dispatched = await action(client, admin, record["id"], "DISPATCH")
    assert dispatched.status_code == 200, dispatched.text
    availability = (
        await client.get(
            "/api/v1/dispatch-availability",
            params={"project_id": po["project_id"]},
            headers=auth(admin),
        )
    ).json()[0]
    assert Decimal(availability["available_quantity"]) == Decimal("5.75")

    over = await client.post(
        "/api/v1/supply-challans",
        json=payload(po, grn, customer_id, dispatch_from_id, address, "6"),
        headers=auth(admin),
    )
    await action(client, admin, over.json()["id"], "READY")
    denied = await action(client, admin, over.json()["id"], "DISPATCH")
    assert denied.status_code == 422
    assert (await action(client, admin, record["id"], "CANCEL")).status_code == 403
    cancelled = await action(client, super_admin, record["id"], "CANCEL")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "supply_challan")
            )
        )
    assert {"assign_number", "create", "ready", "dispatch", "cancel"}.issubset(actions)


@pytest.mark.asyncio
async def test_delivery_acknowledgement_and_authorization(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    po, grn, customer_id, dispatch_from_id, address = await verified_material(
        client, admin, super_admin, "2"
    )
    created = await client.post(
        "/api/v1/supply-challans",
        json=payload(po, grn, customer_id, dispatch_from_id, address, "2"),
        headers=auth(admin),
    )
    challan_id = created.json()["id"]
    await action(client, admin, challan_id, "READY")
    await action(client, admin, challan_id, "DISPATCH")
    delivered = await action(client, admin, challan_id, "DELIVER")
    assert delivered.json()["status"] == "DELIVERED"
    acknowledged = await client.post(
        f"/api/v1/supply-challans/{challan_id}/acknowledgement",
        json={
            "acknowledged_date": "2026-08-27",
            "receiving_authority_text": "Customer Store Officer",
            "acknowledgement_reference": "ACK-1",
        },
        headers=auth(admin),
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"
    assert (await client.get("/api/v1/supply-challans", headers={})).status_code == 401
