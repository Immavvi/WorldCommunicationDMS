from uuid import uuid4

import pytest
from httpx import AsyncClient
from test_procurement import foundation as procurement_foundation
from test_procurement import po_payload


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_foundation(client: AsyncClient, token: str) -> tuple[str, str, str]:
    party = await client.post(
        "/api/v1/master-data/parties",
        json={"code": "RLY-CUST", "legal_name": "Railway Customer", "roles": ["CUSTOMER"]},
        headers=auth(token),
    )
    unit = await client.post(
        "/api/v1/master-data/units",
        json={"code": "NOS", "name": "Numbers", "symbol": "Nos"},
        headers=auth(token),
    )
    project = await client.post(
        "/api/v1/projects",
        json={
            "code": "PRJ-001",
            "name": "Contract Work",
            "customer_party_id": party.json()["id"],
            "business_scope": "NON_RAILWAY",
        },
        headers=auth(token),
    )
    loa = await client.post(
        "/api/v1/loas",
        json={
            "project_id": project.json()["id"],
            "loa_number": "LOA/001",
            "loa_date": "2026-08-24",
            "description": "Supply contract",
            "original_contract_value": "1000.00",
        },
        headers=auth(token),
    )
    assert loa.status_code == 201, loa.text
    return project.json()["id"], loa.json()["id"], unit.json()["id"]


@pytest.mark.asyncio
async def test_loa_items_and_variations_derive_exact_approved_position(client: AsyncClient) -> None:
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    _, loa_id, unit_id = await create_foundation(client, admin)
    item_response = await client.post(
        f"/api/v1/loas/{loa_id}/items",
        json={
            "item_number": "1",
            "description": "Original contractual item",
            "unit_id": unit_id,
            "original_approved_quantity": "10.0000",
            "contractual_rate": "33.33",
        },
        headers=auth(admin),
    )
    assert item_response.status_code == 201, item_response.text
    item = item_response.json()
    assert item["original_line_value"] == "333.30"

    async def variation(reference: str, direction: str, quantity: str):
        return await client.post(
            f"/api/v1/loas/{loa_id}/variations",
            json={
                "reference_number": reference,
                "variation_date": "2026-08-25",
                "lines": [
                    {
                        "loa_item_id": item["id"],
                        "description": item["description"],
                        "unit_id": unit_id,
                        "direction": direction,
                        "quantity": quantity,
                        "rate": "33.33",
                    }
                ],
            },
            headers=auth(admin),
        )

    positive = await variation("VAR/+1", "POSITIVE", "2.0000")
    assert positive.status_code == 201
    draft_position = await client.get(
        f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin)
    )
    assert draft_position.json()["lines"][0]["current_approved_quantity"] == "10.0000"

    approved = await client.post(
        f"/api/v1/variations/{positive.json()['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved contract variation"},
        headers=auth(super_admin),
    )
    assert approved.status_code == 200
    negative = await variation("VAR/-1", "NEGATIVE", "1.5000")
    await client.post(
        f"/api/v1/variations/{negative.json()['id']}/actions",
        json={"action": "APPROVE", "reason": "Approved reduction"},
        headers=auth(super_admin),
    )
    current = (
        await client.get(f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin))
    ).json()
    line = current["lines"][0]
    assert line["original_quantity"] == "10.0000"
    assert line["positive_variation_quantity"] == "2.0000"
    assert line["negative_variation_quantity"] == "1.5000"
    assert line["current_approved_quantity"] == "10.5000"
    assert line["current_approved_value"] == "349.96"
    assert item["original_approved_quantity"] == "10.0000"
    assert item["original_line_value"] == "333.30"


@pytest.mark.asyncio
async def test_rejected_cancelled_and_excess_negative_variations_do_not_change_position(
    client: AsyncClient,
) -> None:
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    _, loa_id, unit_id = await create_foundation(client, admin)
    item = (
        await client.post(
            f"/api/v1/loas/{loa_id}/items",
            json={
                "item_number": "1",
                "description": "Item",
                "unit_id": unit_id,
                "original_approved_quantity": "5",
                "contractual_rate": "10",
            },
            headers=auth(admin),
        )
    ).json()

    async def make(reference: str, quantity: str):
        return await client.post(
            f"/api/v1/loas/{loa_id}/variations",
            json={
                "reference_number": reference,
                "variation_date": "2026-08-25",
                "lines": [
                    {
                        "loa_item_id": item["id"],
                        "description": "Item",
                        "unit_id": unit_id,
                        "direction": "NEGATIVE",
                        "quantity": quantity,
                        "rate": "10",
                    }
                ],
            },
            headers=auth(admin),
        )

    rejected = await make("REJECTED", "1")
    assert (
        await client.post(
            f"/api/v1/variations/{rejected.json()['id']}/actions",
            json={"action": "REJECT", "reason": "Not approved"},
            headers=auth(super_admin),
        )
    ).status_code == 200
    cancelled = await make("CANCELLED", "1")
    assert (
        await client.post(
            f"/api/v1/variations/{cancelled.json()['id']}/actions",
            json={"action": "CANCEL", "reason": "Withdrawn"},
            headers=auth(admin),
        )
    ).status_code == 200
    excess = await make("EXCESS", "6")
    denied = await client.post(
        f"/api/v1/variations/{excess.json()['id']}/actions",
        json={"action": "APPROVE", "reason": "Should fail"},
        headers=auth(super_admin),
    )
    assert denied.status_code == 422
    position = (
        await client.get(f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin))
    ).json()
    assert position["current_approved_total"] == "50.00"


@pytest.mark.asyncio
async def test_contract_endpoints_require_authorization(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/projects")).status_code == 401
    assert (await client.get(f"/api/v1/loas/{uuid4()}/approved-position")).status_code == 401


@pytest.mark.asyncio
async def test_new_positive_variation_item_enters_position_only_when_approved(
    client: AsyncClient,
) -> None:
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    _, loa_id, unit_id = await create_foundation(client, admin)

    async def create_new_item(reference: str):
        return await client.post(
            f"/api/v1/loas/{loa_id}/variations",
            json={
                "reference_number": reference,
                "variation_date": "2026-08-26",
                "lines": [{
                    "description": "New contractual item",
                    "unit_id": unit_id,
                    "direction": "POSITIVE",
                    "quantity": "3.0000",
                    "rate": "12.35",
                    "remarks": "Introduced through variation",
                }],
            },
            headers=auth(admin),
        )

    draft = await create_new_item("VAR/NEW-DRAFT")
    assert draft.status_code == 201, draft.text
    draft_line_id = draft.json()["lines"][0]["id"]
    position = (await client.get(
        f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin)
    )).json()
    assert all(line["contractual_item_id"] != draft_line_id for line in position["lines"])

    approved = await client.post(
        f"/api/v1/variations/{draft.json()['id']}/actions",
        json={"action": "APPROVE", "reason": "Contractually approved"},
        headers=auth(super_admin),
    )
    assert approved.status_code == 200, approved.text
    position = (await client.get(
        f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin)
    )).json()
    new_line = next(
        line for line in position["lines"] if line["contractual_item_id"] == draft_line_id
    )
    assert new_line["origin"] == "VARIATION"
    assert new_line["loa_item_id"] is None
    assert new_line["originating_variation_id"] == draft.json()["id"]
    assert new_line["current_approved_quantity"] == "3.0000"
    assert new_line["current_approved_value"] == "37.05"
    assert position["original_total"] == "0.00"
    assert position["variation_total"] == "37.05"

    applied = await client.post(
        f"/api/v1/variations/{draft.json()['id']}/actions",
        json={"action": "APPLY", "reason": "Variation order applied"},
        headers=auth(super_admin),
    )
    assert applied.status_code == 200
    applied_position = (await client.get(
        f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin)
    )).json()
    assert any(line["contractual_item_id"] == draft_line_id for line in applied_position["lines"])
    assert (await client.get(f"/api/v1/loas/{loa_id}/items", headers=auth(admin))).json() == []


@pytest.mark.asyncio
async def test_negative_variation_cannot_reduce_approval_below_po_commitment(
    client: AsyncClient,
) -> None:
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await procurement_foundation(client, admin)
    po = (
        await client.post(
            "/api/v1/purchase-orders",
            json=po_payload(data, quantity="70"),
            headers=auth(admin),
        )
    ).json()
    for action, token in (("SUBMIT", admin), ("APPROVE", super_admin)):
        response = await client.post(
            f"/api/v1/purchase-orders/{po['id']}/actions",
            json={"action": action, "reason": "Integration test"},
            headers=auth(token),
        )
        assert response.status_code == 200, response.text

    variation = (
        await client.post(
            f"/api/v1/loas/{data['loa']['id']}/variations",
            json={
                "reference_number": "VAR/BELOW-COMMITMENT",
                "variation_date": "2026-08-26",
                "lines": [
                    {
                        "loa_item_id": data["item"]["id"],
                        "description": "Contract item reduction",
                        "unit_id": data["unit"]["id"],
                        "direction": "NEGATIVE",
                        "quantity": "40",
                        "rate": "20",
                    }
                ],
            },
            headers=auth(admin),
        )
    ).json()
    denied = await client.post(
        f"/api/v1/variations/{variation['id']}/actions",
        json={"action": "APPROVE", "reason": "Would invalidate the PO"},
        headers=auth(super_admin),
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "variation_below_committed_quantity"

    position = (
        await client.get(
            f"/api/v1/loas/{data['loa']['id']}/approved-position", headers=auth(admin)
        )
    ).json()
    assert position["lines"][0]["current_approved_quantity"] == "100.0000"


@pytest.mark.asyncio
async def test_rejected_cancelled_new_items_are_excluded_and_standalone_negative_is_rejected(
    client: AsyncClient,
) -> None:
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    _, loa_id, unit_id = await create_foundation(client, admin)

    async def create(reference: str, direction: str = "POSITIVE"):
        return await client.post(
            f"/api/v1/loas/{loa_id}/variations",
            json={
                "reference_number": reference,
                "variation_date": "2026-08-26",
                "lines": [{
                    "description": "Standalone item",
                    "unit_id": unit_id,
                    "direction": direction,
                    "quantity": "1",
                    "rate": "25",
                }],
            },
            headers=auth(admin),
        )

    negative = await create("VAR/INVALID-NEGATIVE", "NEGATIVE")
    assert negative.status_code == 422
    assert negative.json()["error"]["code"] == "negative_variation_requires_item"

    rejected = await create("VAR/REJECTED-NEW")
    cancelled = await create("VAR/CANCELLED-NEW")
    assert (await client.post(
        f"/api/v1/variations/{rejected.json()['id']}/actions",
        json={"action": "REJECT", "reason": "Not accepted"},
        headers=auth(super_admin),
    )).status_code == 200
    assert (await client.post(
        f"/api/v1/variations/{cancelled.json()['id']}/actions",
        json={"action": "CANCEL", "reason": "Withdrawn"},
        headers=auth(admin),
    )).status_code == 200
    position = (await client.get(
        f"/api/v1/loas/{loa_id}/approved-position", headers=auth(admin)
    )).json()
    excluded_ids = {rejected.json()["lines"][0]["id"], cancelled.json()["lines"][0]["id"]}
    assert not excluded_ids.intersection(
        line["contractual_item_id"] for line in position["lines"]
    )
    assert (await client.get(f"/api/v1/loas/{loa_id}/items", headers=auth(admin))).json() == []
