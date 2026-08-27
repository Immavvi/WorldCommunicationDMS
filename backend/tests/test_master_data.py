import pytest
from httpx import AsyncClient


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_can_manage_operational_master_with_audit(client: AsyncClient) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    response = await client.post(
        "/api/v1/master-data/parties",
        json={"code": "cust-1", "legal_name": "Railway Customer", "roles": ["CUSTOMER"]},
        headers=authorization(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["data"]["code"] == "CUST-1"
    assert body["data"]["roles"] == ["CUSTOMER"]

    listed = await client.get("/api/v1/master-data/parties", headers=authorization(token))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    deactivated = await client.patch(
        f"/api/v1/master-data/parties/{body['id']}/active?active=false",
        headers=authorization(token),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_cannot_modify_financial_masters(client: AsyncClient) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    response = await client.post(
        "/api/v1/master-data/tax-rate-sets",
        json={
            "code": "GST18",
            "name": "GST 18%",
            "effective_from": "2026-04-01",
            "components": {"CGST": 9, "SGST": 9},
        },
        headers=authorization(token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_product_master_rejects_vendor_purchase_rate(client: AsyncClient) -> None:
    token = await login(client, "superadmin@example.com", "super-admin-password")
    response = await client.post(
        "/api/v1/master-data/products",
        json={"code": "ITEM-1", "name": "Item", "vendor_purchase_rate": "100.00"},
        headers=authorization(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_only_super_admin_can_persist_single_primary_organization(
    client: AsyncClient,
) -> None:
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    admin = await login(client, "admin@example.com", "admin-user-password")
    first = await client.post(
        "/api/v1/master-data/organizations",
        json={"code": "WC", "legal_name": "World Communication"},
        headers=authorization(super_admin),
    )
    second = await client.post(
        "/api/v1/master-data/organizations",
        json={"code": "WC2", "legal_name": "World Communication Branch"},
        headers=authorization(super_admin),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    denied = await client.post(
        f"/api/v1/master-data/organizations/{first.json()['id']}/set-primary",
        headers=authorization(admin),
    )
    assert denied.status_code == 403

    selected = await client.post(
        f"/api/v1/master-data/organizations/{first.json()['id']}/set-primary",
        headers=authorization(super_admin),
    )
    assert selected.status_code == 200
    assert selected.json()["data"]["is_primary"] is True

    replaced = await client.post(
        f"/api/v1/master-data/organizations/{second.json()['id']}/set-primary",
        headers=authorization(super_admin),
    )
    assert replaced.status_code == 200
    listed = await client.get(
        "/api/v1/master-data/organizations", headers=authorization(super_admin)
    )
    primaries = [item for item in listed.json()["items"] if item["data"]["is_primary"]]
    assert [item["id"] for item in primaries] == [second.json()["id"]]
    assert listed.json()["total"] == 2


@pytest.mark.asyncio
async def test_railway_master_hierarchy_crud_roles_and_validation(client: AsyncClient) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    headers = authorization(token)
    zone = await client.post(
        "/api/v1/master-data/railway-zones",
        json={"code": "ARZ", "name": "Arbitrary Railway", "aliases": ["AR Railway"]},
        headers=headers,
    )
    assert zone.status_code == 201, zone.text
    division = await client.post(
        "/api/v1/master-data/railway-divisions",
        json={
            "code": "ARD",
            "name": "Arbitrary Division",
            "aliases": ["ARD Division"],
            "zone_id": zone.json()["id"],
        },
        headers=headers,
    )
    assert division.status_code == 201, division.text
    location = await client.post(
        "/api/v1/master-data/railway-locations",
        json={
            "code": "STORE-1",
            "name": "Signal Store",
            "division_id": division.json()["id"],
            "location_type": "store",
        },
        headers=headers,
    )
    assert location.status_code == 201, location.text
    assert location.json()["data"]["location_type"] == "STORE"
    authority = await client.post(
        "/api/v1/master-data/railway-authorities",
        json={
            "code": "AUTH-1",
            "name": "Signal Authority",
            "designation": "DSTE/ARD",
            "division_id": division.json()["id"],
            "location_id": location.json()["id"],
            "roles": ["ISSUING_AUTHORITY", "CONSIGNEE"],
            "aliases": ["DSTE ARD"],
        },
        headers=headers,
    )
    assert authority.status_code == 201, authority.text
    assert authority.json()["data"]["roles"] == ["CONSIGNEE", "ISSUING_AUTHORITY"]
    updated = await client.patch(
        f"/api/v1/master-data/railway-authorities/{authority.json()['id']}",
        json={"roles": ["EXECUTION_AUTHORITY"]},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["roles"] == ["EXECUTION_AUTHORITY"]
    deactivated = await client.patch(
        f"/api/v1/master-data/railway-locations/{location.json()['id']}/active?active=false",
        headers=headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    missing_parent = await client.post(
        "/api/v1/master-data/railway-divisions",
        json={"code": "NO-ZONE", "name": "No Zone"},
        headers=headers,
    )
    assert missing_parent.status_code == 422
    duplicate_alias = await client.post(
        "/api/v1/master-data/railway-zones",
        json={"code": "ARZ2", "name": "Second", "aliases": ["AR Railway"]},
        headers=headers,
    )
    assert duplicate_alias.status_code == 409


@pytest.mark.asyncio
async def test_railway_hierarchy_rejects_cross_division_authority_location(
    client: AsyncClient,
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    headers = authorization(token)
    first_zone = await client.post(
        "/api/v1/master-data/railway-zones",
        json={"code": "Z-A", "name": "Zone Alpha"},
        headers=headers,
    )
    second_zone = await client.post(
        "/api/v1/master-data/railway-zones",
        json={"code": "Z-B", "name": "Zone Beta"},
        headers=headers,
    )
    divisions = []
    for code, zone in (("D-A", first_zone), ("D-B", second_zone)):
        divisions.append(
            await client.post(
                "/api/v1/master-data/railway-divisions",
                json={"code": code, "name": code, "zone_id": zone.json()["id"]},
                headers=headers,
            )
        )
    location = await client.post(
        "/api/v1/master-data/railway-locations",
        json={
            "code": "LOC-A",
            "name": "Location Alpha",
            "division_id": divisions[0].json()["id"],
            "location_type": "OFFICE",
        },
        headers=headers,
    )
    conflict = await client.post(
        "/api/v1/master-data/railway-authorities",
        json={
            "code": "AUTH-B",
            "name": "Authority Beta",
            "division_id": divisions[1].json()["id"],
            "location_id": location.json()["id"],
            "roles": ["ISSUING_AUTHORITY"],
        },
        headers=headers,
    )
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "railway_hierarchy_mismatch"


@pytest.mark.asyncio
async def test_railway_master_delete_is_restricted_and_reference_safe(
    client: AsyncClient,
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    headers = authorization(token)

    async def create(resource: str, payload: dict):
        response = await client.post(
            f"/api/v1/master-data/{resource}", json=payload, headers=headers
        )
        assert response.status_code == 201, response.text
        return response.json()

    unused_zone = await create(
        "railway-zones", {"code": "DEL-Z", "name": "Deletable Railway"}
    )
    deleted = await client.delete(
        f"/api/v1/master-data/railway-zones/{unused_zone['id']}", headers=headers
    )
    assert deleted.status_code == 204

    zone = await create("railway-zones", {"code": "USE-Z", "name": "Used Railway"})
    division = await create(
        "railway-divisions",
        {"code": "USE-D", "name": "Used Division", "zone_id": zone["id"]},
    )
    blocked_zone = await client.delete(
        f"/api/v1/master-data/railway-zones/{zone['id']}", headers=headers
    )
    assert blocked_zone.status_code == 409
    assert blocked_zone.json()["error"]["code"] == "master_record_in_use"

    unused_division = await create(
        "railway-divisions",
        {"code": "DEL-D", "name": "Deletable Division", "zone_id": zone["id"]},
    )
    assert (
        await client.delete(
            f"/api/v1/master-data/railway-divisions/{unused_division['id']}",
            headers=headers,
        )
    ).status_code == 204

    location = await create(
        "railway-locations",
        {
            "code": "USE-L",
            "name": "Used Location",
            "division_id": division["id"],
            "location_type": "STORE",
        },
    )
    blocked_division = await client.delete(
        f"/api/v1/master-data/railway-divisions/{division['id']}", headers=headers
    )
    assert blocked_division.status_code == 409

    unused_location = await create(
        "railway-locations",
        {
            "code": "DEL-L",
            "name": "Deletable Location",
            "division_id": division["id"],
            "location_type": "OFFICE",
        },
    )
    assert (
        await client.delete(
            f"/api/v1/master-data/railway-locations/{unused_location['id']}",
            headers=headers,
        )
    ).status_code == 204

    authority = await create(
        "railway-authorities",
        {
            "code": "DEL-A",
            "name": "Deletable Authority",
            "division_id": division["id"],
            "roles": ["ISSUING_AUTHORITY", "CONSIGNEE"],
        },
    )
    # AuthorityRole children are ON DELETE CASCADE and must not block their parent.
    assert (
        await client.delete(
            f"/api/v1/master-data/railway-authorities/{authority['id']}", headers=headers
        )
    ).status_code == 204

    used_authority = await create(
        "railway-authorities",
        {
            "code": "USE-A",
            "name": "Used Authority",
            "division_id": division["id"],
            "location_id": location["id"],
            "roles": ["CONSIGNEE"],
        },
    )
    await create(
        "railway-authority-addresses",
        {
            "authority_id": used_authority["id"],
            "label": "Receiving store",
            "address_line_1": "Railway store yard",
            "city": "Adra",
            "state": "West Bengal",
            "postal_code": "723121",
            "country": "India",
        },
    )
    blocked_authority = await client.delete(
        f"/api/v1/master-data/railway-authorities/{used_authority['id']}",
        headers=headers,
    )
    assert blocked_authority.status_code == 409
    assert blocked_authority.json()["error"]["code"] == "master_record_in_use"
    blocked_location = await client.delete(
        f"/api/v1/master-data/railway-locations/{location['id']}", headers=headers
    )
    assert blocked_location.status_code == 409
    assert used_authority["id"]

    party = await create(
        "parties", {"code": "NO-DELETE", "legal_name": "Protected Party", "roles": ["OEM"]}
    )
    denied = await client.delete(
        f"/api/v1/master-data/parties/{party['id']}", headers=headers
    )
    assert denied.status_code == 405
    assert denied.json()["error"]["code"] == "master_delete_not_allowed"
