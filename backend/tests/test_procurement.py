from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth import AuditLog
from app.models.master_data import Loa


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def master(client, token, resource, data):
    response = await client.post(f"/api/v1/master-data/{resource}", json=data, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()


async def foundation(client: AsyncClient, token: str):
    customer = await master(
        client,
        token,
        "parties",
        {"code": "BUY-CUST", "legal_name": "Customer", "roles": ["CUSTOMER"]},
    )
    vendor = await master(
        client,
        token,
        "parties",
        {"code": "VENDOR-1", "legal_name": "Original Vendor", "roles": ["VENDOR"]},
    )
    oem = await master(
        client,
        token,
        "parties",
        {"code": "OEM-P5", "legal_name": "Original OEM", "roles": ["OEM"]},
    )
    oem_profile = await master(
        client,
        token,
        "oem-profiles",
        {"party_id": oem["id"], "manufacturer_code": "OEM-P5"},
    )
    product_model = await master(
        client,
        token,
        "product-models",
        {
            "oem_profile_id": oem_profile["id"],
            "model_number": "MODEL-OLD",
            "name": "Original Model",
        },
    )
    unit = await master(
        client, token, "units", {"code": "NOS-P5", "name": "Numbers P5", "symbol": "Nos"}
    )
    organization = await master(
        client, token, "organizations", {"code": "WC-P5", "legal_name": "World Communication"}
    )
    billing = await master(
        client,
        token,
        "organization-addresses",
        {
            "organization_id": organization["id"],
            "address_type": "BILL_TO",
            "label": "Billing",
            "address_line_1": "Old billing",
            "city": "Kolkata",
            "state": "West Bengal",
            "state_code": "19",
            "postal_code": "700001",
        },
    )
    shipping = await master(
        client,
        token,
        "organization-addresses",
        {
            "organization_id": organization["id"],
            "address_type": "SHIP_TO",
            "label": "Warehouse",
            "address_line_1": "Old warehouse",
            "city": "Kolkata",
            "state": "West Bengal",
            "state_code": "19",
            "postal_code": "700002",
        },
    )
    project = (
        await client.post(
            "/api/v1/projects",
            json={
                "code": "P5-PROJ",
                "name": "Procurement Project",
                "customer_party_id": customer["id"],
                "business_scope": "NON_RAILWAY",
            },
            headers=auth(token),
        )
    ).json()
    loa = (
        await client.post(
            "/api/v1/loas",
            json={"project_id": project["id"], "loa_number": "LOA/P5", "loa_date": "2026-08-24"},
            headers=auth(token),
        )
    ).json()
    item = (
        await client.post(
            f"/api/v1/loas/{loa['id']}/items",
            json={
                "item_number": "1",
                "description": "Contract item",
                "unit_id": unit["id"],
                "original_approved_quantity": "100",
                "contractual_rate": "20",
            },
            headers=auth(token),
        )
    ).json()
    return {
        "customer": customer,
        "vendor": vendor,
        "oem": oem,
        "product_model": product_model,
        "unit": unit,
        "organization": organization,
        "billing": billing,
        "shipping": shipping,
        "project": project,
        "loa": loa,
        "item": item,
    }


def po_payload(data, quantity="40", tax_mode="INTRA_STATE"):
    return {
        "po_date": "2026-08-24",
        "vendor_party_id": data["vendor"]["id"],
        "project_id": data["project"]["id"],
        "loa_id": data["loa"]["id"],
        "organization_id": data["organization"]["id"],
        "billing_organization_address_id": data["billing"]["id"],
        "ship_to_organization_address_id": data["shipping"]["id"],
        "tax_mode": tax_mode,
        "lines": [
            {
                "description": "Purchased snapshot",
                "product_model_id": data["product_model"]["id"],
                "unit_id": data["unit"]["id"],
                "ordered_quantity": quantity,
                "unit_rate": "33.33",
                "discount_percent": "10",
                "cgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
                "sgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
                "igst_percent": "18" if tax_mode == "INTER_STATE" else "0",
                "loa_item_id": data["item"]["id"],
            }
        ],
    }


@pytest.mark.asyncio
async def test_requirement_po_totals_numbering_snapshots_and_workflow(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await foundation(client, admin)
    requirement = await client.post(
        "/api/v1/procurement-requirements",
        json={
            "project_id": data["project"]["id"],
            "loa_id": data["loa"]["id"],
            "requirement_date": "2026-08-24",
            "lines": [
                {
                    "description": "Required item",
                    "unit_id": data["unit"]["id"],
                    "required_quantity": "100",
                    "loa_item_id": data["item"]["id"],
                }
            ],
        },
        headers=auth(admin),
    )
    assert requirement.status_code == 201, requirement.text
    assert requirement.json()["requirement_number"] == "PR-000001"

    first = await client.post("/api/v1/purchase-orders", json=po_payload(data), headers=auth(admin))
    assert first.status_code == 201, first.text
    po = first.json()
    assert po["po_number"] == "PO-000001"
    assert po["subtotal"] == "1333.20"
    assert po["discount_amount"] == "133.32"
    assert po["taxable_amount"] == "1199.88"
    assert po["cgst_amount"] == "107.99" and po["sgst_amount"] == "107.99"
    assert po["grand_total"] == "1415.86"
    assert po["shipping_address_snapshot"]["address_line_1"] == "Old warehouse"
    assert po["vendor_snapshot"]["legal_name"] == "Original Vendor"
    assert po["project_name_snapshot"] == "Procurement Project"
    assert po["loa_number_snapshot"] == "LOA/P5"
    assert po["loa_date_snapshot"] == "2026-08-24"
    assert po["project_id"] == data["project"]["id"]
    assert po["loa_id"] == data["loa"]["id"]
    assert po["lines"][0]["oem_snapshot"] == "Original OEM"
    assert po["lines"][0]["model_snapshot"] == "MODEL-OLD - Original Model"

    edited_line = po_payload(data)["lines"][0]
    edited_line["unit_rate"] = "33.34"
    edited = await client.put(
        f"/api/v1/purchase-orders/{po['id']}/lines/{po['lines'][0]['id']}",
        json=edited_line,
        headers=auth(admin),
    )
    assert edited.status_code == 200, edited.text
    po = edited.json()
    assert po["lines"][0]["unit_rate"] == "33.34"

    submitted = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "SUBMIT", "reason": "Ready"},
        headers=auth(admin),
    )
    assert submitted.status_code == 200
    denied = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "APPROVE", "reason": "Self"},
        headers=auth(admin),
    )
    assert denied.status_code == 403
    approved = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved"},
        headers=auth(super_admin),
    )
    assert approved.status_code == 200
    issued = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "ISSUE", "reason": "Issued to vendor"},
        headers=auth(super_admin),
    )
    assert issued.status_code == 200
    commitments = (
        await client.get(
            f"/api/v1/loas/{data['loa']['id']}/procurement-commitments", headers=auth(admin)
        )
    ).json()
    assert commitments[0]["committed_quantity"] == "40.0000"
    assert commitments[0]["remaining_quantity"] == "60.0000"

    changed = await client.patch(
        f"/api/v1/master-data/organization-addresses/{data['shipping']['id']}",
        json={"address_line_1": "New warehouse"},
        headers=auth(admin),
    )
    assert changed.status_code == 200
    assert (
        await client.patch(
            f"/api/v1/master-data/parties/{data['vendor']['id']}",
            json={"legal_name": "Renamed Vendor"},
            headers=auth(admin),
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/master-data/parties/{data['oem']['id']}",
            json={"legal_name": "Renamed OEM"},
            headers=auth(admin),
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/master-data/product-models/{data['product_model']['id']}",
            json={"model_number": "MODEL-NEW", "name": "Renamed Model"},
            headers=auth(admin),
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/projects/{data['project']['id']}",
            json={"name": "Renamed Project"},
            headers=auth(admin),
        )
    ).status_code == 200
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        current_loa = await session.get(Loa, UUID(data["loa"]["id"]))
        current_loa.loa_number = "LOA/CHANGED"
        await session.commit()
    unchanged = (
        await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=auth(admin))
    ).json()
    assert unchanged["shipping_address_snapshot"]["address_line_1"] == "Old warehouse"
    assert unchanged["vendor_snapshot"]["legal_name"] == "Original Vendor"
    assert unchanged["project_name_snapshot"] == "Procurement Project"
    assert unchanged["loa_number_snapshot"] == "LOA/P5"
    assert unchanged["lines"][0]["oem_snapshot"] == "Original OEM"
    assert unchanged["lines"][0]["model_snapshot"] == "MODEL-OLD - Original Model"

    current = await client.post(
        "/api/v1/purchase-orders",
        json=po_payload(data, "1"),
        headers=auth(admin),
    )
    assert current.status_code == 201, current.text
    assert current.json()["vendor_snapshot"]["legal_name"] == "Renamed Vendor"
    assert current.json()["project_name_snapshot"] == "Renamed Project"
    assert current.json()["loa_number_snapshot"] == "LOA/CHANGED"
    assert current.json()["lines"][0]["oem_snapshot"] == "Renamed OEM"
    assert current.json()["lines"][0]["model_snapshot"] == "MODEL-NEW - Renamed Model"

    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = list(
            await session.scalars(select(AuditLog.action).where(AuditLog.entity_id == po["id"]))
        )
        assert {"assign_number", "create", "submit", "approve", "issue"}.issubset(actions)
        line_actions = list(
            await session.scalars(
                select(AuditLog.action).where(
                    AuditLog.entity_id == po["lines"][0]["id"],
                    AuditLog.entity_type == "purchase_order_line",
                )
            )
        )
        assert "update_line" in line_actions


@pytest.mark.asyncio
async def test_partial_commitment_overcommit_cancel_and_igst(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await foundation(client, admin)

    async def create_submit_approve(quantity, tax_mode="INTER_STATE"):
        po = (
            await client.post(
                "/api/v1/purchase-orders",
                json=po_payload(data, quantity, tax_mode),
                headers=auth(admin),
            )
        ).json()
        await client.post(
            f"/api/v1/purchase-orders/{po['id']}/actions",
            json={"action": "SUBMIT", "reason": "Ready"},
            headers=auth(admin),
        )
        response = await client.post(
            f"/api/v1/purchase-orders/{po['id']}/actions",
            json={"action": "APPROVE", "reason": "Approved"},
            headers=auth(super_admin),
        )
        return po, response

    first, approved = await create_submit_approve("40")
    assert approved.status_code == 200
    assert approved.json()["igst_amount"] == "215.98"
    second, approved = await create_submit_approve("30")
    assert approved.status_code == 200
    third, approved = await create_submit_approve("31")
    assert approved.status_code == 422
    cancelled = await client.post(
        f"/api/v1/purchase-orders/{second['id']}/actions",
        json={"action": "CANCEL", "reason": "No longer required"},
        headers=auth(super_admin),
    )
    assert cancelled.status_code == 200
    replacement, approved = await create_submit_approve("60")
    assert approved.status_code == 200
    assert (
        len({first["po_number"], second["po_number"], third["po_number"], replacement["po_number"]})
        == 4
    )


@pytest.mark.asyncio
async def test_vendor_validation_and_variation_origin_commitment(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await foundation(client, admin)
    data["vendor"] = data["customer"]
    denied = await client.post(
        "/api/v1/purchase-orders", json=po_payload(data, "1"), headers=auth(admin)
    )
    assert denied.status_code == 422
    data["vendor"] = await master(
        client,
        admin,
        "parties",
        {"code": "VENDOR-2", "legal_name": "Vendor 2", "roles": ["VENDOR"]},
    )
    variation = (
        await client.post(
            f"/api/v1/loas/{data['loa']['id']}/variations",
            json={
                "reference_number": "VAR/NEW-P5",
                "variation_date": "2026-08-24",
                "lines": [
                    {
                        "description": "Variation item",
                        "unit_id": data["unit"]["id"],
                        "direction": "POSITIVE",
                        "quantity": "10",
                        "rate": "10",
                    }
                ],
            },
            headers=auth(admin),
        )
    ).json()
    await client.post(
        f"/api/v1/variations/{variation['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved"},
        headers=auth(super_admin),
    )
    payload = po_payload(data, "10")
    payload["lines"][0].pop("loa_item_id")
    payload["lines"][0]["variation_line_id"] = variation["lines"][0]["id"]
    po = (await client.post("/api/v1/purchase-orders", json=payload, headers=auth(admin))).json()
    await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "SUBMIT", "reason": "Ready"},
        headers=auth(admin),
    )
    approved = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved"},
        headers=auth(super_admin),
    )
    assert approved.status_code == 200, approved.text
    commitments = (
        await client.get(
            f"/api/v1/loas/{data['loa']['id']}/procurement-commitments", headers=auth(admin)
        )
    ).json()
    variation_commitment = next(item for item in commitments if item["origin"] == "VARIATION")
    assert variation_commitment["remaining_quantity"] == "0.0000"


@pytest.mark.asyncio
async def test_multiple_lines_and_purchase_terms_version_snapshot(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    data = await foundation(client, admin)
    terms_set = await master(
        client,
        admin,
        "terms-condition-sets",
        {"code": "PO-TC", "name": "Purchase Terms", "context": "PURCHASE"},
    )
    version = await client.post(
        f"/api/v1/master-data/terms-condition-sets/{terms_set['id']}/versions",
        json={"content": "Payment and delivery terms v1", "effective_from": "2026-08-24"},
        headers=auth(admin),
    )
    assert version.status_code == 201
    payload = po_payload(data, "2", "INTER_STATE")
    payload["terms_version_id"] = version.json()["id"]
    second = dict(payload["lines"][0])
    second.update({"description": "Second PO line", "ordered_quantity": "3", "unit_rate": "10"})
    second.pop("loa_item_id")
    payload["lines"].append(second)
    response = await client.post("/api/v1/purchase-orders", json=payload, headers=auth(admin))
    assert response.status_code == 201, response.text
    po = response.json()
    assert len(po["lines"]) == 2
    assert po["terms_snapshot"]["version"] == 1
    assert po["terms_snapshot"]["content"] == "Payment and delivery terms v1"
