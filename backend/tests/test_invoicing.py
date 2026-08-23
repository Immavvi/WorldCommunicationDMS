import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from test_billing import action as pi_action
from test_billing import pi_foundation, pi_payload
from test_billing import (
    test_railway_pi_uses_original_contract_rate_without_procurement_exposure as setup_railway_pi,
)
from test_billing import test_variation_origin_pi_uses_variation_contract_rate as setup_variation_pi
from test_receiving import auth, login, master

from app.models.auth import AuditLog
from app.models.billing import ProformaInvoice
from app.models.master_data import BankAccount, Organization


async def invoice_foundation(client, admin, super_admin, tax_mode="INTRA_STATE"):
    data = await pi_foundation(client, admin, super_admin)
    await client.patch(
        f"/api/v1/master-data/party-addresses/{data['address']['id']}",
        json={"state_code": "19" if tax_mode == "INTRA_STATE" else "20"},
        headers=auth(admin),
    )
    organization_gst = await master(
        client,
        super_admin,
        "gst-registrations",
        {
            "organization_id": str(data["organization"].id),
            "gstin": "19ABCDE1234F1Z5",
            "registered_name": "World Communication",
            "state": "West Bengal",
            "state_code": "19",
            "effective_from": "2026-04-01",
            "is_default": True,
        },
    )
    customer_gst = await master(
        client,
        super_admin,
        "gst-registrations",
        {
            "party_id": data["customer_id"],
            "gstin": "19ABCDE1234F2Z4",
            "registered_name": "Customer",
            "state": "West Bengal",
            "state_code": "19",
            "effective_from": "2026-04-01",
            "is_default": True,
        },
    )
    pi = (
        await client.post(
            "/api/v1/proforma-invoices",
            json=pi_payload(data, "10", tax_mode),
            headers=auth(admin),
        )
    ).json()
    await pi_action(client, admin, pi["id"], "SUBMIT")
    await pi_action(client, super_admin, pi["id"], "APPROVE")
    data.update({"pi": pi, "organization_gst": organization_gst, "customer_gst": customer_gst})
    return data


def invoice_payload(data, quantity="4", tax_mode=None):
    payload = {
        "invoice_date": "2026-08-27",
        "project_id": str(data["project"].id),
        "customer_party_id": data["customer_id"],
        "business_scope": "NON_RAILWAY",
        "bill_to_party_address_id": data["address"]["id"],
        "ship_to_party_address_id": data["address"]["id"],
        "organization_id": str(data["organization"].id),
        "gst_registration_id": data["organization_gst"]["id"],
        "bank_account_id": data["bank"]["id"],
        "payment_term_id": data["payment"]["id"],
        "terms_version_id": data["terms"]["id"],
        "lines": [
            {
                "proforma_invoice_line_id": data["pi"]["lines"][0]["id"],
                "invoiced_quantity": quantity,
            }
        ],
    }
    if tax_mode:
        payload["tax_mode"] = tax_mode
    return payload


async def action(client, token, invoice_id, name):
    return await client.post(
        f"/api/v1/tax-invoices/{invoice_id}/actions",
        json={"action": name, "reason": f"{name} invoice test"},
        headers=auth(token),
    )


@pytest.mark.asyncio
async def test_invoice_snapshots_auto_tax_due_date_workflow_and_traceability(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await invoice_foundation(client, admin, super_admin)
    created = await client.post(
        "/api/v1/tax-invoices", json=invoice_payload(data), headers=auth(admin)
    )
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["invoice_number"] == "INV-000001"
    assert invoice["tax_mode"] == "INTRA_STATE"
    assert invoice["place_of_supply_state_code"] == "19"
    assert invoice["due_date"] == "2026-09-26"
    assert invoice["taxable_amount"] == "360.00"
    assert invoice["cgst_amount"] == "32.40" and invoice["sgst_amount"] == "32.40"
    assert invoice["grand_total"] == "424.80"
    assert (
        invoice["amount_in_words"] == "Indian Rupees Four Hundred Twenty Four and Eighty Paise Only"
    )
    line = invoice["lines"][0]
    assert line["proforma_invoice_line_id"] == data["pi"]["lines"][0]["id"]
    assert line["supply_challan_line_id"] == data["challan"]["lines"][0]["id"]
    assert invoice["organization_gst_snapshot"]["gstin"] == "19ABCDE1234F1Z5"
    assert invoice["customer_gst_snapshot"]["gstin"] == "19ABCDE1234F2Z4"
    assert "vendor_snapshot" not in created.text.lower()
    await client.patch(
        f"/api/v1/master-data/gst-registrations/{data['organization_gst']['id']}",
        json={"registered_name": "World Communication Updated"},
        headers=auth(super_admin),
    )
    historical = await client.get(f"/api/v1/tax-invoices/{invoice['id']}", headers=auth(admin))
    assert (
        historical.json()["organization_gst_snapshot"]["registered_name"] == "World Communication"
    )
    edited = await client.put(
        f"/api/v1/tax-invoices/{invoice['id']}/lines/{line['id']}",
        json={
            "proforma_invoice_line_id": line["proforma_invoice_line_id"],
            "invoiced_quantity": "4",
        },
        headers=auth(admin),
    )
    assert edited.status_code == 200
    position = (
        await client.get(
            "/api/v1/invoiceable-position",
            params={"project_id": str(data["project"].id)},
            headers=auth(admin),
        )
    ).json()[0]
    assert position["remaining_invoiceable_quantity"] == "10.0000"
    await action(client, admin, invoice["id"], "SUBMIT")
    assert (await action(client, admin, invoice["id"], "APPROVE")).status_code == 403
    assert (await action(client, super_admin, invoice["id"], "APPROVE")).status_code == 200
    assert (await action(client, super_admin, invoice["id"], "ISSUE")).status_code == 200
    position = (
        await client.get(
            "/api/v1/invoiceable-position",
            params={"project_id": str(data["project"].id)},
            headers=auth(admin),
        )
    ).json()[0]
    assert position["previously_invoiced_quantity"] == "4.0000"
    assert position["remaining_invoiceable_quantity"] == "6.0000"
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "tax_invoice")
            )
        )
    assert {"assign_number", "create", "submit", "approve", "issue"}.issubset(actions)


@pytest.mark.asyncio
async def test_interstate_explicit_validation_overinvoice_and_cancel_release(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await invoice_foundation(client, admin, super_admin, "INTER_STATE")
    conflicting = await client.post(
        "/api/v1/tax-invoices", json=invoice_payload(data, "6", "INTRA_STATE"), headers=auth(admin)
    )
    assert conflicting.status_code == 422
    first = (
        await client.post(
            "/api/v1/tax-invoices",
            json=invoice_payload(data, "6", "INTER_STATE"),
            headers=auth(admin),
        )
    ).json()
    assert first["tax_mode"] == "INTER_STATE" and first["igst_amount"] == "97.20"
    await action(client, admin, first["id"], "SUBMIT")
    await action(client, super_admin, first["id"], "APPROVE")
    second = (
        await client.post(
            "/api/v1/tax-invoices",
            json=invoice_payload(data, "5", "INTER_STATE"),
            headers=auth(admin),
        )
    ).json()
    await action(client, admin, second["id"], "SUBMIT")
    assert (await action(client, super_admin, second["id"], "APPROVE")).status_code == 422
    assert (await action(client, super_admin, first["id"], "CANCEL")).status_code == 200
    assert (await action(client, super_admin, second["id"], "APPROVE")).status_code == 200


@pytest.mark.asyncio
async def test_railway_invoice_preserves_contract_and_confidentiality(client: AsyncClient):
    await setup_railway_pi(client)
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        pi = await session.scalar(
            select(ProformaInvoice).options(selectinload(ProformaInvoice.lines))
        )
        organization = await session.scalar(
            select(Organization).where(Organization.code == "WC-RLY-D")
        )
        bank = await session.scalar(
            select(BankAccount).where(BankAccount.organization_id == organization.id)
        )
    await pi_action(client, admin, pi.id, "SUBMIT")
    await pi_action(client, super_admin, pi.id, "APPROVE")
    gst = await master(
        client,
        super_admin,
        "gst-registrations",
        {
            "organization_id": str(organization.id),
            "gstin": "19ABCDE1234F1Z5",
            "registered_name": "World Communication",
            "state": "West Bengal",
            "state_code": "19",
            "effective_from": "2026-04-01",
        },
    )
    created = await client.post(
        "/api/v1/tax-invoices",
        json={
            "invoice_date": "2026-08-28",
            "project_id": str(pi.project_id),
            "loa_id": str(pi.loa_id),
            "customer_party_id": str(pi.customer_party_id),
            "business_scope": "RAILWAY",
            "railway_division_id": str(pi.railway_division_id),
            "railway_authority_id": str(pi.railway_authority_id),
            "bill_to_railway_address_id": str(pi.bill_to_railway_address_id),
            "ship_to_railway_address_id": str(pi.ship_to_railway_address_id),
            "organization_id": str(organization.id),
            "gst_registration_id": gst["id"],
            "bank_account_id": str(bank.id),
            "place_of_supply_state": "West Bengal",
            "place_of_supply_state_code": "19",
            "lines": [{"proforma_invoice_line_id": str(pi.lines[0].id), "invoiced_quantity": "1"}],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    line = created.json()["lines"][0]
    assert line["loa_item_id"] is not None and line["sales_rate"] == "999.99"
    assert not any(
        value in created.text.lower()
        for value in ("vendor_snapshot", "unit_rate", "purchase_order", "margin")
    )
    assert (await client.get("/api/v1/tax-invoices", headers={})).status_code == 401


@pytest.mark.asyncio
async def test_variation_origin_invoice_traceability(client: AsyncClient):
    await setup_variation_pi(client)
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        pi = await session.scalar(
            select(ProformaInvoice).options(selectinload(ProformaInvoice.lines))
        )
        organization = await session.scalar(
            select(Organization).where(Organization.code == "WC-P5")
        )
        bank = await session.scalar(
            select(BankAccount).where(BankAccount.organization_id == organization.id)
        )
    await pi_action(client, admin, pi.id, "SUBMIT")
    await pi_action(client, super_admin, pi.id, "APPROVE")
    await client.patch(
        f"/api/v1/master-data/party-addresses/{pi.ship_to_party_address_id}",
        json={"state_code": "20"},
        headers=auth(admin),
    )
    gst = await master(
        client,
        super_admin,
        "gst-registrations",
        {
            "organization_id": str(organization.id),
            "gstin": "19ABCDE1234F1Z5",
            "registered_name": "World Communication",
            "state": "West Bengal",
            "state_code": "19",
            "effective_from": "2026-04-01",
        },
    )
    created = await client.post(
        "/api/v1/tax-invoices",
        json={
            "invoice_date": "2026-08-28",
            "project_id": str(pi.project_id),
            "loa_id": str(pi.loa_id),
            "customer_party_id": str(pi.customer_party_id),
            "business_scope": "NON_RAILWAY",
            "bill_to_party_address_id": str(pi.bill_to_party_address_id),
            "ship_to_party_address_id": str(pi.ship_to_party_address_id),
            "organization_id": str(organization.id),
            "gst_registration_id": gst["id"],
            "bank_account_id": str(bank.id),
            "lines": [{"proforma_invoice_line_id": str(pi.lines[0].id), "invoiced_quantity": "1"}],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    line = created.json()["lines"][0]
    assert line["variation_line_id"] is not None
    assert line["sales_rate"] == "50.00"
