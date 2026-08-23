from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from test_dispatch import action as challan_action
from test_dispatch import payload as challan_payload
from test_dispatch import (
    test_railway_original_contract_dispatch_uses_safe_snapshots as setup_railway_dispatch,
)
from test_dispatch import (
    test_variation_origin_contract_item_dispatch as setup_variation_dispatch,
)
from test_dispatch import (
    verified_material,
)
from test_receiving import auth, login, master

from app.models.auth import AuditLog
from app.models.dispatch import SupplyChallan
from app.models.master_data import Organization, Project


async def pi_foundation(client, admin, super_admin):
    po, grn, customer_id, dispatch_from_id, address = await verified_material(
        client, admin, super_admin, "10"
    )
    challan = (
        await client.post(
            "/api/v1/supply-challans",
            json=challan_payload(po, grn, customer_id, dispatch_from_id, address, "10"),
            headers=auth(admin),
        )
    ).json()
    await challan_action(client, admin, challan["id"], "READY")
    await challan_action(client, admin, challan["id"], "DISPATCH")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        project = await session.get(Project, UUID(po["project_id"]))
        organization = await session.scalar(select(Organization))
    bank = await master(
        client,
        super_admin,
        "bank-accounts",
        {
            "organization_id": str(organization.id),
            "account_name": "World Communication",
            "bank_name": "WCDMS Bank",
            "branch_name": "Kolkata",
            "account_number": "1234567890",
            "ifsc": "WCDM0000001",
            "is_default": True,
        },
    )
    payment = await master(
        client,
        admin,
        "payment-terms",
        {
            "code": "PI-30D",
            "name": "Thirty Days",
            "description": "Pay within thirty days",
            "due_days": 30,
        },
    )
    terms_set = await master(
        client,
        admin,
        "terms-condition-sets",
        {"code": "PI-GEN", "name": "PI General", "context": "INVOICE"},
    )
    terms = (
        await client.post(
            f"/api/v1/master-data/terms-condition-sets/{terms_set['id']}/versions",
            json={"content": "Payment and delivery terms.", "effective_from": "2026-08-24"},
            headers=auth(admin),
        )
    ).json()
    return {
        "project": project,
        "organization": organization,
        "customer_id": customer_id,
        "address": address,
        "bank": bank,
        "payment": payment,
        "terms": terms,
        "challan": challan,
    }


def pi_payload(data, quantity="4", tax_mode="INTRA_STATE"):
    line = {
        "supply_challan_line_id": data["challan"]["lines"][0]["id"],
        "billable_quantity": quantity,
        "sales_rate": "100",
        "discount_percent": "10",
        "cgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
        "sgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
        "igst_percent": "18" if tax_mode == "INTER_STATE" else "0",
    }
    return {
        "pi_date": "2026-08-27",
        "project_id": str(data["project"].id),
        "customer_party_id": data["customer_id"],
        "business_scope": "NON_RAILWAY",
        "bill_to_party_address_id": data["address"]["id"],
        "ship_to_party_address_id": data["address"]["id"],
        "organization_id": str(data["organization"].id),
        "bank_account_id": data["bank"]["id"],
        "payment_term_id": data["payment"]["id"],
        "terms_version_id": data["terms"]["id"],
        "tax_mode": tax_mode,
        "lines": [line],
    }


async def action(client, token, pi_id, name):
    return await client.post(
        f"/api/v1/proforma-invoices/{pi_id}/actions",
        json={"action": name, "reason": f"{name} PI test"},
        headers=auth(token),
    )


async def bank_for(client, super_admin, organization):
    return await master(
        client,
        super_admin,
        "bank-accounts",
        {
            "organization_id": str(organization.id),
            "account_name": "World Communication",
            "bank_name": "Contract Bank",
            "account_number": "9876543210",
            "ifsc": "WCDM0000002",
        },
    )


@pytest.mark.asyncio
async def test_railway_pi_uses_original_contract_rate_without_procurement_exposure(
    client: AsyncClient,
):
    await setup_railway_dispatch(client)
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        challan = await session.scalar(
            select(SupplyChallan)
            .options(selectinload(SupplyChallan.lines))
            .where(SupplyChallan.business_scope == "RAILWAY")
        )
        organization = await session.scalar(
            select(Organization).where(Organization.code == "WC-RLY-D")
        )
    bank = await bank_for(client, super_admin, organization)
    created = await client.post(
        "/api/v1/proforma-invoices",
        json={
            "pi_date": "2026-08-28",
            "project_id": str(challan.project_id),
            "loa_id": str(challan.loa_id),
            "customer_party_id": str(challan.customer_party_id),
            "business_scope": "RAILWAY",
            "railway_division_id": str(challan.railway_division_id),
            "railway_authority_id": str(challan.consignee_authority_id),
            "bill_to_railway_address_id": str(challan.ship_to_railway_address_id),
            "ship_to_railway_address_id": str(challan.ship_to_railway_address_id),
            "organization_id": str(organization.id),
            "bank_account_id": bank["id"],
            "tax_mode": "INTRA_STATE",
            "lines": [
                {
                    "supply_challan_line_id": str(challan.lines[0].id),
                    "billable_quantity": "1",
                    "sales_rate": "1",
                    "cgst_percent": "9",
                    "sgst_percent": "9",
                }
            ],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["lines"][0]["sales_rate"] == "999.99"
    forbidden = ("vendor_snapshot", "purchase_order", "unit_rate", "margin")
    assert not any(value in created.text.lower() for value in forbidden)


@pytest.mark.asyncio
async def test_variation_origin_pi_uses_variation_contract_rate(client: AsyncClient):
    await setup_variation_dispatch(client)
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        challan = await session.scalar(
            select(SupplyChallan)
            .options(selectinload(SupplyChallan.lines))
            .where(SupplyChallan.business_scope == "NON_RAILWAY")
        )
        organization = await session.scalar(
            select(Organization).where(Organization.code == "WC-P5")
        )
    bank = await bank_for(client, super_admin, organization)
    created = await client.post(
        "/api/v1/proforma-invoices",
        json={
            "pi_date": "2026-08-28",
            "project_id": str(challan.project_id),
            "loa_id": str(challan.loa_id),
            "customer_party_id": str(challan.customer_party_id),
            "business_scope": "NON_RAILWAY",
            "bill_to_party_address_id": str(challan.ship_to_party_address_id),
            "ship_to_party_address_id": str(challan.ship_to_party_address_id),
            "organization_id": str(organization.id),
            "bank_account_id": bank["id"],
            "tax_mode": "INTER_STATE",
            "lines": [
                {
                    "supply_challan_line_id": str(challan.lines[0].id),
                    "billable_quantity": "1",
                    "sales_rate": "1",
                    "igst_percent": "18",
                }
            ],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["lines"][0]["variation_line_id"] is not None
    assert created.json()["lines"][0]["sales_rate"] == "50.00"


@pytest.mark.asyncio
async def test_pi_totals_snapshots_workflow_and_billable_quantity(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await pi_foundation(client, admin, super_admin)
    created = await client.post(
        "/api/v1/proforma-invoices",
        json=pi_payload(data),
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    pi = created.json()
    assert pi["pi_number"] == "PI-000001"
    assert pi["subtotal"] == "400.00"
    assert pi["discount_amount"] == "40.00"
    assert pi["taxable_amount"] == "360.00"
    assert pi["cgst_amount"] == "32.40" and pi["sgst_amount"] == "32.40"
    assert pi["grand_total"] == "424.80"
    assert pi["amount_in_words"] == "Indian Rupees Four Hundred Twenty Four and Eighty Paise Only"
    assert pi["bank_snapshot"]["account_number"] == "1234567890"
    assert pi["terms_snapshot"]["content"] == "Payment and delivery terms."
    assert "vendor_snapshot" not in created.text.lower()
    changed_bank = await client.patch(
        f"/api/v1/master-data/bank-accounts/{data['bank']['id']}",
        json={"account_number": "1234567899"},
        headers=auth(super_admin),
    )
    assert changed_bank.status_code == 200
    historical = await client.get(f"/api/v1/proforma-invoices/{pi['id']}", headers=auth(admin))
    assert historical.json()["bank_snapshot"]["account_number"] == "1234567890"
    edited = await client.put(
        f"/api/v1/proforma-invoices/{pi['id']}/lines/{pi['lines'][0]['id']}",
        json={
            "supply_challan_line_id": data["challan"]["lines"][0]["id"],
            "billable_quantity": "4",
            "sales_rate": "100",
            "discount_percent": "10",
            "cgst_percent": "9",
            "sgst_percent": "9",
        },
        headers=auth(admin),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["lines"][0]["id"] == pi["lines"][0]["id"]
    draft_position = (
        await client.get(
            "/api/v1/billable-position",
            params={"project_id": str(data["project"].id)},
            headers=auth(admin),
        )
    ).json()[0]
    assert draft_position["remaining_billable_quantity"] == "10.0000"
    assert (await action(client, admin, pi["id"], "SUBMIT")).status_code == 200
    denied = await action(client, admin, pi["id"], "APPROVE")
    assert denied.status_code == 403
    approved = await action(client, super_admin, pi["id"], "APPROVE")
    assert approved.status_code == 200, approved.text
    position = (
        await client.get(
            "/api/v1/billable-position",
            params={"project_id": str(data["project"].id)},
            headers=auth(admin),
        )
    ).json()[0]
    assert position["previously_committed_pi_quantity"] == "4.0000"
    assert position["remaining_billable_quantity"] == "6.0000"
    assert (await action(client, super_admin, pi["id"], "ISSUE")).status_code == 200
    assert (await client.get("/api/v1/proforma-invoices", headers={})).status_code == 401
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "proforma_invoice")
            )
        )
    assert {"assign_number", "create", "submit", "approve", "issue"}.issubset(actions)


@pytest.mark.asyncio
async def test_interstate_tax_overbilling_and_cancel_release(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await pi_foundation(client, admin, super_admin)
    first = (
        await client.post(
            "/api/v1/proforma-invoices",
            json=pi_payload(data, "6", "INTER_STATE"),
            headers=auth(admin),
        )
    ).json()
    assert first["igst_amount"] == "97.20"
    assert first["cgst_amount"] == "0.00"
    await action(client, admin, first["id"], "SUBMIT")
    await action(client, super_admin, first["id"], "APPROVE")
    second = (
        await client.post(
            "/api/v1/proforma-invoices",
            json=pi_payload(data, "5"),
            headers=auth(admin),
        )
    ).json()
    await action(client, admin, second["id"], "SUBMIT")
    over = await action(client, super_admin, second["id"], "APPROVE")
    assert over.status_code == 422
    cancelled = await action(client, super_admin, first["id"], "CANCEL")
    assert cancelled.status_code == 200
    approved_after_release = await action(client, super_admin, second["id"], "APPROVE")
    assert approved_after_release.status_code == 200
    assert Decimal(approved_after_release.json()["grand_total"]) == Decimal("531.00")
