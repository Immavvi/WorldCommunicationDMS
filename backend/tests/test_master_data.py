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
