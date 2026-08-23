import pytest
from httpx import AsyncClient
from sqlalchemy import select
from test_invoicing import invoice_foundation, setup_railway_pi
from test_receiving import auth, login, master

from app.models.auth import AuditLog
from app.models.billing import ProformaInvoice
from app.models.master_data import Organization, Product, ProductCategory, UnitOfMeasure


async def quotation_foundation(client, admin, super_admin, tax_mode="INTRA_STATE"):
    data = await invoice_foundation(client, admin, super_admin, tax_mode)
    async with client._session_factory.begin() as session:  # type: ignore[attr-defined]
        category = ProductCategory(code="QTN-CAT", name="Quotation Products")
        unit = UnitOfMeasure(code="QTN-NOS", name="Quotation Numbers", symbol="Nos")
        session.add_all([category, unit])
        await session.flush()
        product = Product(
            code="QTN-PRODUCT",
            name="Managed appliance",
            description="Managed network appliance",
            category_id=category.id,
            unit_id=unit.id,
        )
        session.add(product)
        await session.flush()
        data["product_id"] = str(product.id)
    return data


def quotation_payload(data, *, tax_mode="INTRA_STATE"):
    return {
        "quotation_date": "2026-08-28",
        "validity_date": "2026-09-27",
        "customer_party_id": data["customer_id"],
        "business_scope": "NON_RAILWAY",
        "bill_to_party_address_id": data["address"]["id"],
        "ship_to_party_address_id": data["address"]["id"],
        "organization_id": str(data["organization"].id),
        "gst_registration_id": data["organization_gst"]["id"],
        "payment_term_id": data["payment"]["id"],
        "terms_version_id": data["terms"]["id"],
        "subject": "Supply of network equipment",
        "enquiry_reference": "ENQ/2026/1",
        "tax_mode": tax_mode,
        "lines": [
            {
                "description": "Commercial network appliance",
                "unit_text": "Nos",
                "hsn_code": "8517",
                "quantity": "2.5000",
                "quoted_rate": "100.00",
                "discount_percent": "10",
                "cgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
                "sgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
                "igst_percent": "18" if tax_mode == "INTER_STATE" else "0",
            },
            {
                "product_id": data["product_id"],
                "quantity": "1",
                "quoted_rate": "200.00",
                "cgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
                "sgst_percent": "9" if tax_mode == "INTRA_STATE" else "0",
                "igst_percent": "18" if tax_mode == "INTER_STATE" else "0",
            },
        ],
    }


async def quotation_action(client, token, quotation_id, action):
    return await client.post(
        f"/api/v1/quotations/{quotation_id}/actions",
        json={"action": action, "reason": f"{action} quotation test"},
        headers=auth(token),
    )


@pytest.mark.asyncio
async def test_non_railway_quotation_calculation_snapshots_workflow_and_revision(
    client: AsyncClient,
):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await quotation_foundation(client, admin, super_admin)
    created = await client.post(
        "/api/v1/quotations", json=quotation_payload(data), headers=auth(admin)
    )
    assert created.status_code == 201, created.text
    quotation = created.json()
    assert quotation["quotation_number"] == "QTN-000001" and quotation["revision_number"] == 0
    assert quotation["project_id"] is None and quotation["loa_id"] is None
    assert len(quotation["lines"]) == 2
    assert quotation["subtotal"] == "450.00"
    assert quotation["discount_amount"] == "25.00"
    assert quotation["taxable_amount"] == "425.00"
    assert quotation["cgst_amount"] == "38.25" and quotation["sgst_amount"] == "38.25"
    assert quotation["grand_total"] == "501.50"
    assert "Five Hundred One" in quotation["amount_in_words"]
    assert quotation["payment_terms_snapshot"]["code"] == data["payment"]["data"]["code"]
    assert quotation["terms_snapshot"]["content"]
    assert "vendor" not in created.text.lower() and "purchase_rate" not in created.text.lower()
    assert (await quotation_action(client, admin, quotation["id"], "SUBMIT")).status_code == 200
    assert (await quotation_action(client, admin, quotation["id"], "APPROVE")).status_code == 403
    assert (
        await quotation_action(client, super_admin, quotation["id"], "APPROVE")
    ).status_code == 200
    assert (
        await quotation_action(client, super_admin, quotation["id"], "ISSUE")
    ).status_code == 200
    immutable = await client.patch(
        f"/api/v1/quotations/{quotation['id']}", json={"subject": "Changed"}, headers=auth(admin)
    )
    assert immutable.status_code == 409
    revision_response = await client.post(
        f"/api/v1/quotations/{quotation['id']}/revisions",
        json={"reason": "Customer requested quantity change"},
        headers=auth(admin),
    )
    assert revision_response.status_code == 201, revision_response.text
    revision = revision_response.json()
    assert revision["quotation_number"] == "QTN-000001" and revision["revision_number"] == 1
    assert revision["previous_revision_id"] == quotation["id"] and revision["status"] == "DRAFT"
    history = (
        await client.get(f"/api/v1/quotations/{revision['id']}/revisions", headers=auth(admin))
    ).json()
    assert [item["revision_number"] for item in history] == [1, 0]
    assert history[0]["is_latest"] is True and history[1]["is_latest"] is False
    assert history[1]["subject"] == "Supply of network equipment"
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        actions = set(
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "quotation")
            )
        )
    assert {"assign_number", "create", "submit", "approve", "issue", "create_revision"}.issubset(
        actions
    )


@pytest.mark.asyncio
async def test_interstate_quotation_tax_validation_and_number_uniqueness(client: AsyncClient):
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    data = await quotation_foundation(client, admin, super_admin, "INTER_STATE")
    payload = quotation_payload(data, tax_mode="INTER_STATE")
    first = await client.post("/api/v1/quotations", json=payload, headers=auth(admin))
    second = await client.post("/api/v1/quotations", json=payload, headers=auth(admin))
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["quotation_number"] == "QTN-000001"
    assert second.json()["quotation_number"] == "QTN-000002"
    assert first.json()["cgst_amount"] == "0.00" and first.json()["igst_amount"] == "76.50"
    conflicting = quotation_payload(data, tax_mode="INTRA_STATE")
    assert (
        await client.post("/api/v1/quotations", json=conflicting, headers=auth(admin))
    ).status_code == 422


@pytest.mark.asyncio
async def test_railway_pre_contract_quotation_without_project_or_loa(client: AsyncClient):
    await setup_railway_pi(client)
    admin = await login(client, "admin@example.com", "admin-user-password")
    super_admin = await login(client, "superadmin@example.com", "super-admin-password")
    async with client._session_factory() as session:  # type: ignore[attr-defined]
        pi = await session.scalar(select(ProformaInvoice))
        organization = await session.scalar(
            select(Organization).where(Organization.code == "WC-RLY-D")
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
        "/api/v1/quotations",
        json={
            "quotation_date": "2026-08-28",
            "customer_party_id": str(pi.customer_party_id),
            "business_scope": "RAILWAY",
            "railway_division_id": str(pi.railway_division_id),
            "railway_authority_id": str(pi.railway_authority_id),
            "bill_to_railway_address_id": str(pi.bill_to_railway_address_id),
            "ship_to_railway_address_id": str(pi.ship_to_railway_address_id),
            "organization_id": str(organization.id),
            "gst_registration_id": gst["id"],
            "place_of_supply_state": "West Bengal",
            "place_of_supply_state_code": "19",
            "subject": "Railway tender offer",
            "lines": [
                {
                    "description": "Railway networking equipment",
                    "unit_text": "Nos",
                    "quantity": "1",
                    "quoted_rate": "1000",
                    "cgst_percent": "9",
                    "sgst_percent": "9",
                }
            ],
        },
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["project_id"] is None and body["loa_id"] is None
    assert body["division_snapshot"] and body["authority_snapshot"]
    assert not any(
        value in created.text.lower()
        for value in ("vendor_snapshot", "purchase_order", "purchase_rate", "margin")
    )
