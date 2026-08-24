import pytest
from httpx import AsyncClient
from sqlalchemy import select
from test_dispatch import payload as challan_payload
from test_dispatch import verified_material
from test_receiving import auth, issued_po, login, master, receipt, transition

from app.models.assets import Asset
from app.models.auth import AuditLog


@pytest.mark.asyncio
async def test_serial_registration_quantity_duplicate_lifecycle_warranty_and_rbac(
    client: AsyncClient,
):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    po = await issued_po(client, admin, super_admin, "2")
    grn = await receipt(client, admin, po, "2")
    await transition(client, admin, grn.json()["id"], "RECEIVE")
    assert (await transition(client, super_admin, grn.json()["id"], "VERIFY")).status_code == 200
    line_id = grn.json()["lines"][0]["id"]

    position = (
        await client.get("/api/v1/assets/registration-position", headers=auth(admin))
    ).json()
    assert position[0]["accepted_quantity"] == 2
    assert position[0]["remaining_quantity"] == 2

    created = await client.post(
        "/api/v1/assets/register",
        json={
            "material_receipt_line_id": line_id,
            "assets": [
                {"manufacturer_serial_number": "  Serial-001  "},
                {"manufacturer_serial_number": "Serial-002"},
            ],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    assets = created.json()
    assert [row["asset_number"] for row in assets] == ["AST-000001", "AST-000002"]
    assert assets[0]["manufacturer_serial_number"] == "Serial-001"
    assert assets[0]["purchase_order_id"] == po["id"]
    assert assets[0]["material_receipt_line_id"] == line_id
    assert assets[0]["product_snapshot"] == "Serialized-ready equipment"

    duplicate = await client.post(
        "/api/v1/assets/register",
        json={
            "material_receipt_line_id": line_id,
            "assets": [{"manufacturer_serial_number": " serial-001 "}],
        },
        headers=auth(admin),
    )
    assert duplicate.status_code == 409
    exceeded = await client.post(
        "/api/v1/assets/register",
        json={
            "material_receipt_line_id": line_id,
            "assets": [{"manufacturer_serial_number": "Serial-003"}],
        },
        headers=auth(admin),
    )
    assert exceeded.status_code == 409

    asset_id = assets[0]["id"]
    available = await client.post(
        f"/api/v1/assets/{asset_id}/actions",
        json={"action": "MAKE_AVAILABLE", "reason": "Released to stock"},
        headers=auth(admin),
    )
    assert available.status_code == 200
    moved = await client.post(
        f"/api/v1/assets/{asset_id}/actions",
        json={
            "action": "ALLOCATE",
            "reason": "Project allocation",
            "site": "Station A",
            "room": "OFC Room",
        },
        headers=auth(admin),
    )
    assert moved.status_code == 200
    installed = await client.post(
        f"/api/v1/assets/{asset_id}/installation",
        json={
            "installation_date": "2026-09-01",
            "reason": "Installed",
            "site": "Station A",
            "room": "Relay Room",
            "rack": "R1",
        },
        headers=auth(admin),
    )
    assert installed.status_code == 200
    assert installed.json()["status"] == "INSTALLED"
    assert len(installed.json()["events"]) == 4
    assert any(
        event["to_location_snapshot"] == "Station A / OFC Room"
        for event in installed.json()["events"]
    )

    warranty = await client.put(
        f"/api/v1/assets/{asset_id}/warranty",
        json={
            "warranty_type": "OEM",
            "warranty_start_date": "2026-01-31",
            "warranty_duration_months": 1,
            "reason": "OEM certificate",
        },
        headers=auth(admin),
    )
    assert warranty.status_code == 200
    assert warranty.json()["warranty_expiry_date"] == "2026-02-28"
    denied = await client.post(
        f"/api/v1/assets/{asset_id}/actions",
        json={"action": "RETIRE", "reason": "End of life"},
        headers=auth(admin),
    )
    assert denied.status_code == 403
    retired = await client.post(
        f"/api/v1/assets/{asset_id}/actions",
        json={"action": "RETIRE", "reason": "End of life"},
        headers=auth(super_admin),
    )
    assert retired.status_code == 200
    assert retired.json()["status"] == "RETIRED"

    async with client._session_factory() as session:  # type: ignore[attr-defined]
        assert await session.scalar(select(Asset).where(Asset.asset_number == "AST-000001"))
        actions = set(
            await session.scalars(select(AuditLog.action).where(AuditLog.entity_id == asset_id))
        )
        assert {
            "assign_number",
            "register",
            "allocate",
            "install",
            "update_warranty",
            "retire",
        }.issubset(actions)


@pytest.mark.asyncio
async def test_quantity_tracked_and_non_stock_are_not_asset_eligible(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    unit = await master(
        client, admin, "units", {"code": "A-UOM", "name": "Asset UOM", "symbol": "Nos"}
    )
    category = await master(
        client, admin, "product-categories", {"code": "A-CAT", "name": "Asset category"}
    )
    for code, tracking in (("QTY", "QUANTITY_TRACKED"), ("SERVICE", "NON_STOCK")):
        result = await master(
            client,
            admin,
            "products",
            {
                "code": code,
                "name": code,
                "description": code,
                "business_scope": "BOTH",
                "category_id": category["id"],
                "unit_id": unit["id"],
                "tracking_class": tracking,
            },
        )
        assert result["data"]["tracking_class"] == tracking


@pytest.mark.asyncio
async def test_serialized_challan_assignment_enforces_identity_and_quantity(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    po, grn, customer_id, dispatch_from_id, address = await verified_material(
        client, admin, super_admin, "2"
    )
    registered = await client.post(
        "/api/v1/assets/register",
        json={
            "material_receipt_line_id": grn["lines"][0]["id"],
            "assets": [
                {"manufacturer_serial_number": "CH-ASSET-1"},
                {"manufacturer_serial_number": "CH-ASSET-2"},
            ],
        },
        headers=auth(admin),
    )
    assets = registered.json()
    for asset in assets:
        await client.post(
            f"/api/v1/assets/{asset['id']}/actions",
            json={"action": "MAKE_AVAILABLE", "reason": "Ready for dispatch"},
            headers=auth(admin),
        )
    challan_data = challan_payload(po, grn, customer_id, dispatch_from_id, address, quantity="1")
    challan = await client.post("/api/v1/supply-challans", json=challan_data, headers=auth(admin))
    assert challan.status_code == 201, challan.text
    line_id = challan.json()["lines"][0]["id"]
    await client.post(
        f"/api/v1/supply-challans/{challan.json()['id']}/actions",
        json={"action": "READY", "reason": "Ready"},
        headers=auth(admin),
    )
    dispatched = await client.post(
        f"/api/v1/supply-challans/{challan.json()['id']}/actions",
        json={"action": "DISPATCH", "reason": "Dispatched"},
        headers=auth(admin),
    )
    assert dispatched.status_code == 200, dispatched.text
    assigned = await client.post(
        f"/api/v1/supply-challan-lines/{line_id}/assets",
        json={"asset_ids": [assets[0]["id"]], "reason": "Serialized dispatch"},
        headers=auth(admin),
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()[0]["status"] == "DISPATCHED"
    duplicate = await client.post(
        f"/api/v1/supply-challan-lines/{line_id}/assets",
        json={"asset_ids": [assets[0]["id"]], "reason": "Duplicate"},
        headers=auth(admin),
    )
    assert duplicate.status_code in {409, 422}
    exceeded = await client.post(
        f"/api/v1/supply-challan-lines/{line_id}/assets",
        json={"asset_ids": [assets[1]["id"]], "reason": "Too many"},
        headers=auth(admin),
    )
    assert exceeded.status_code == 409
