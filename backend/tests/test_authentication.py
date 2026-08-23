import pytest
from httpx import AsyncClient


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_login_and_current_user_return_only_safe_information(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@example.com", "password": "super-admin-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["roles"] == [{"name": "SUPER-ADMIN"}]
    assert "password_hash" not in body["user"]

    me_response = await client.get("/api/v1/auth/me", headers=authorization(body["access_token"]))
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "superadmin@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("unknown@example.com", "not-the-password"),
        ("admin@example.com", "incorrect-password"),
    ],
)
async def test_login_rejects_invalid_credentials(
    client: AsyncClient, email: str, password: str
) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_inactive_user_cannot_authenticate(client: AsyncClient) -> None:
    super_admin_token = await login(client, "superadmin@example.com", "super-admin-password")
    users = await client.get("/api/v1/users", headers=authorization(super_admin_token))
    admin_id = next(
        user["id"] for user in users.json()["items"] if user["email"] == "admin@example.com"
    )
    await client.patch(
        f"/api/v1/users/{admin_id}/active",
        json={"is_active": False},
        headers=authorization(super_admin_token),
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-user-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_invalid_jwt_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers=authorization("not-a-jwt"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_super_admin_user_management_and_admin_denial(client: AsyncClient) -> None:
    super_admin_token = await login(client, "superadmin@example.com", "super-admin-password")
    admin_token = await login(client, "admin@example.com", "admin-user-password")

    denied_response = await client.get("/api/v1/users", headers=authorization(admin_token))
    assert denied_response.status_code == 403

    create_response = await client.post(
        "/api/v1/users",
        json={
            "email": "new.admin@example.com",
            "password": "new-admin-password",
            "role_name": "ADMIN",
        },
        headers=authorization(super_admin_token),
    )
    assert create_response.status_code == 201
    created_user = create_response.json()
    assert created_user["roles"] == [{"name": "ADMIN"}]
    assert "password_hash" not in created_user

    assigned_response = await client.put(
        f"/api/v1/users/{created_user['id']}/role",
        json={"role_name": "SUPER-ADMIN"},
        headers=authorization(super_admin_token),
    )
    assert assigned_response.status_code == 200
    assert assigned_response.json()["roles"] == [{"name": "SUPER-ADMIN"}]

    deactivated_response = await client.patch(
        f"/api/v1/users/{created_user['id']}/active",
        json={"is_active": False},
        headers=authorization(super_admin_token),
    )
    assert deactivated_response.status_code == 200
    assert deactivated_response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_password_change_and_reset_invalidate_existing_tokens(client: AsyncClient) -> None:
    admin_token = await login(client, "admin@example.com", "admin-user-password")
    change_response = await client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "admin-user-password",
            "new_password": "changed-admin-password",
        },
        headers=authorization(admin_token),
    )
    assert change_response.status_code == 204
    old_token_response = await client.get("/api/v1/auth/me", headers=authorization(admin_token))
    assert old_token_response.status_code == 401

    changed_token = await login(client, "admin@example.com", "changed-admin-password")
    super_admin_token = await login(client, "superadmin@example.com", "super-admin-password")
    users = await client.get("/api/v1/users", headers=authorization(super_admin_token))
    admin_id = next(
        user["id"] for user in users.json()["items"] if user["email"] == "admin@example.com"
    )
    reset_response = await client.put(
        f"/api/v1/users/{admin_id}/password",
        json={"new_password": "reset-admin-password"},
        headers=authorization(super_admin_token),
    )
    assert reset_response.status_code == 204
    reset_token_response = await client.get("/api/v1/auth/me", headers=authorization(changed_token))
    assert reset_token_response.status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "changed-admin-password"},
        )
    ).status_code == 401
    assert await login(client, "admin@example.com", "reset-admin-password")
