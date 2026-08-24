import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth import AuditLog


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_local_frontend_origin_can_reach_login(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


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


@pytest.mark.asyncio
async def test_last_active_super_admin_cannot_be_deactivated_or_demoted(
    client: AsyncClient,
) -> None:
    token = await login(client, "superadmin@example.com", "super-admin-password")
    users = await client.get("/api/v1/users", headers=authorization(token))
    super_id = next(
        user["id"] for user in users.json()["items"] if user["email"] == "superadmin@example.com"
    )

    deactivate = await client.patch(
        f"/api/v1/users/{super_id}/active",
        json={"is_active": False},
        headers=authorization(token),
    )
    assert deactivate.status_code == 409
    assert deactivate.json()["error"]["code"] == "last_super_admin"

    demote = await client.put(
        f"/api/v1/users/{super_id}/role",
        json={"role_name": "ADMIN"},
        headers=authorization(token),
    )
    assert demote.status_code == 409
    assert demote.json()["error"]["code"] == "last_super_admin"


@pytest.mark.asyncio
async def test_temporary_password_requires_change_before_module_access(client: AsyncClient) -> None:
    super_token = await login(client, "superadmin@example.com", "super-admin-password")
    created = await client.post(
        "/api/v1/users",
        json={
            "display_name": "Second Administrator",
            "email": "second.admin@example.com",
            "password": "temporary-password",
            "role_name": "ADMIN",
        },
        headers=authorization(super_token),
    )
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True

    temporary_token = await login(client, "second.admin@example.com", "temporary-password")
    denied = await client.get("/api/v1/projects", headers=authorization(temporary_token))
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "password_change_required"
    me = await client.get("/api/v1/auth/me", headers=authorization(temporary_token))
    assert me.status_code == 200

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "temporary-password", "new_password": "permanent-password"},
        headers=authorization(temporary_token),
    )
    assert changed.status_code == 204
    permanent_token = await login(client, "second.admin@example.com", "permanent-password")
    projects = await client.get("/api/v1/projects", headers=authorization(permanent_token))
    assert projects.status_code == 200


@pytest.mark.asyncio
async def test_administration_endpoints_are_safe_and_super_admin_only(client: AsyncClient) -> None:
    admin_token = await login(client, "admin@example.com", "admin-user-password")
    assert (
        await client.get("/api/v1/admin/system-status", headers=authorization(admin_token))
    ).status_code == 403

    super_token = await login(client, "superadmin@example.com", "super-admin-password")
    status = await client.get("/api/v1/admin/system-status", headers=authorization(super_token))
    assert status.status_code == 200
    assert status.json()["database"] == "connected"
    assert "database_url" not in status.json()

    numbering = await client.get("/api/v1/admin/numbering", headers=authorization(super_token))
    assert numbering.status_code == 200
    assert numbering.json()[0].keys() == {
        "id", "document_type", "prefix", "next_number", "padding", "preview"
    }


@pytest.mark.asyncio
async def test_user_administration_actions_are_audited_without_credentials(
    client: AsyncClient,
) -> None:
    token = await login(client, "superadmin@example.com", "super-admin-password")
    created = await client.post(
        "/api/v1/users",
        json={
            "display_name": "Audited User",
            "email": "audited@example.com",
            "password": "temporary-password",
            "role_name": "ADMIN",
        },
        headers=authorization(token),
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    duplicate = await client.post(
        "/api/v1/users",
        json={
            "email": "AUDITED@example.com",
            "password": "another-password",
            "role_name": "ADMIN",
        },
        headers=authorization(token),
    )
    assert duplicate.status_code == 409

    assert (
        await client.put(
            f"/api/v1/users/{user_id}/role",
            json={"role_name": "SUPER-ADMIN"},
            headers=authorization(token),
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/users/{user_id}/active",
            json={"is_active": False},
            headers=authorization(token),
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/users/{user_id}/active",
            json={"is_active": True},
            headers=authorization(token),
        )
    ).status_code == 200
    assert (
        await client.put(
            f"/api/v1/users/{user_id}/password",
            json={"new_password": "reset-password", "reason": "Access recovery"},
            headers=authorization(token),
        )
    ).status_code == 204

    async with client._session_factory() as session:
        logs = list(
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.entity_type == "user", AuditLog.entity_id == user_id
                )
            )
        )
    assert {log.action for log in logs} >= {
        "create", "assign_role", "deactivate", "activate", "reset_password"
    }
    assert all("password_hash" not in str(log.new_value).lower() for log in logs)
    assert all("reset-password" not in str(log.new_value) for log in logs)
    reset_log = next(log for log in logs if log.action == "reset_password")
    assert reset_log.reason == "Access recovery"
