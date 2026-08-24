from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from test_procurement import auth, foundation, login


@pytest.mark.asyncio
async def test_role_aware_dashboard_and_financial_report_restriction(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    operational = await client.get("/api/v1/dashboard", headers=auth(admin))
    assert operational.status_code == 200
    assert "operational" in operational.json() and "financial" not in operational.json()
    financial = await client.get("/api/v1/dashboard", headers=auth(super_admin))
    assert financial.status_code == 200 and "financial" in financial.json()
    assert (await client.get("/api/v1/reports/receivables", headers=auth(admin))).status_code == 403
    assert (
        await client.get("/api/v1/reports/receivables", headers=auth(super_admin))
    ).status_code == 200


@pytest.mark.asyncio
async def test_loa_reconciliation_uses_approved_contract_position(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    data = await foundation(client, admin)
    rows = (
        await client.get(
            f"/api/v1/reports/loas/{data['loa']['id']}/reconciliation",
            headers=auth(admin),
        )
    ).json()
    assert rows[0]["origin"] == "ORIGINAL_LOA"
    assert rows[0]["original_quantity"] == 100
    assert rows[0]["current_approved_quantity"] == 100
    assert rows[0]["remaining_procurement"] == 100
    assert "contract_rate" not in rows[0]


@pytest.mark.asyncio
async def test_excel_export_valid_headings_numeric_cells_and_no_admin_commercial_value(
    client: AsyncClient,
):
    admin = await login(client, "admin@example.com", "admin-user-password")
    await foundation(client, admin)
    response = await client.get("/api/v1/reports/projects/export.xlsx", headers=auth(admin))
    assert response.status_code == 200
    sheet = load_workbook(BytesIO(response.content)).active
    headings = [cell.value for cell in sheet[1]]
    assert {"code", "name", "business_scope", "status"}.issubset(headings)
    assert "grand_total" not in headings and "unit_rate" not in headings
