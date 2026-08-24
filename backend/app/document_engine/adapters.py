from dataclasses import dataclass, field


@dataclass
class RenderLine:
    number: int
    description: str
    hsn: str | None
    unit: str
    quantity: object
    rate: object | None = None
    discount: object | None = None
    taxable: object | None = None
    gst: str | None = None
    amount: object | None = None
    remarks: str | None = None
    model: str | None = None
    oem: str | None = None


@dataclass
class RenderDocument:
    kind: str
    title: str
    identifier: str
    status: str
    organization: dict
    identity: list[tuple[str, str]]
    parties: list[tuple[str, str]]
    lines: list[RenderLine]
    financial: bool
    totals: list[tuple[str, object]] = field(default_factory=list)
    amount_in_words: str | None = None
    bank: dict | None = None
    payment_terms: dict | None = None
    terms: str | None = None
    notes: str | None = None
    special_instructions: str | None = None
    continuation_reference: str | None = None


def _gst(line):
    values = []
    for name in ("cgst", "sgst", "igst"):
        percent = getattr(line, f"{name}_percent", 0)
        if percent:
            values.append(f"{name.upper()} {percent}%")
    return " / ".join(values)


def _commercial_lines(record, quantity_name, rate_name, description_name="description_snapshot"):
    return [
        RenderLine(
            number=line.line_number,
            description=getattr(line, description_name),
            hsn=getattr(line, "hsn_snapshot", None) or getattr(line, "hsn_code", None),
            unit=line.unit_snapshot,
            quantity=getattr(line, quantity_name),
            rate=getattr(line, rate_name),
            discount=line.discount_percent,
            taxable=line.taxable_amount,
            gst=_gst(line),
            amount=line.line_total,
            remarks=line.remarks,
            model=getattr(line, "model_snapshot", None),
            oem=getattr(line, "oem_snapshot", None),
        )
        for line in record.lines
    ]


def _totals(record):
    names = (
        ("Subtotal", "subtotal"),
        ("Discount", "discount_amount"),
        ("Taxable Amount", "taxable_amount"),
        ("CGST", "cgst_amount"),
        ("SGST", "sgst_amount"),
        ("IGST", "igst_amount"),
        ("Round Off", "round_off"),
        ("Grand Total", "grand_total"),
    )
    return [
        (label, getattr(record, attr))
        for label, attr in names
        if attr == "grand_total" or getattr(record, attr, 0)
    ]


def quotation(record):
    project_loa = _project_loa(record)
    return RenderDocument(
        "quotation",
        "QUOTATION",
        f"{record.quotation_number}-R{record.revision_number}",
        record.status,
        record.organization_snapshot
        | {"gstin": (getattr(record, "organization_gst_snapshot", None) or {}).get("gstin")},
        _clean_identity(
            [
                ("WORLD COMMUNICATION DOCUMENT NUMBER", record.quotation_number),
                ("REVISION", str(record.revision_number)),
                ("DATE", str(record.quotation_date)),
                ("VALIDITY", str(record.validity_date) if record.validity_date else None),
                ("PROJECT NAME / LOA NUMBER", project_loa),
                ("RAILWAY DIVISION", _reference(record.division_snapshot)),
                ("ENQUIRY / TENDER / CUSTOMER REFERENCE", record.enquiry_reference),
                ("REFERENCE DATE", str(record.enquiry_date) if record.enquiry_date else None),
                ("SUBJECT", record.subject),
            ]
        ),
        [
            (
                "CUSTOMER DETAILS",
                _party(record.customer_snapshot, getattr(record, "customer_gst_snapshot", None)),
            ),
            ("BILL TO", _address(record.bill_to_snapshot)),
            ("SHIP TO", _address(record.ship_to_snapshot)),
            ("RAILWAY AUTHORITY", _party(record.authority_snapshot)),
        ]
        if record.business_scope == "RAILWAY"
        else [
            (
                "CUSTOMER DETAILS",
                _party(record.customer_snapshot, getattr(record, "customer_gst_snapshot", None)),
            ),
            ("BILL TO", _address(record.bill_to_snapshot)),
            ("SHIP TO", _address(record.ship_to_snapshot)),
        ],
        _commercial_lines(record, "quantity", "quoted_rate"),
        True,
        _totals(record),
        record.amount_in_words,
        payment_terms=record.payment_terms_snapshot,
        terms=(record.terms_snapshot or {}).get("content"),
        notes=record.notes,
        special_instructions=record.special_instructions,
        continuation_reference=_loa_reference(record) or f"REVISION {record.revision_number}",
    )


def purchase_order(record):
    lines = _commercial_lines(record, "ordered_quantity", "unit_rate", "description")
    return RenderDocument(
        "purchase_order",
        "PURCHASE ORDER",
        record.po_number,
        record.status,
        record.organization_snapshot
        | {"gstin": (getattr(record, "organization_gst_snapshot", None) or {}).get("gstin")},
        _clean_identity(
            [
                ("WORLD COMMUNICATION DOCUMENT NUMBER", record.po_number),
                ("DATE", str(record.po_date)),
                ("PROCUREMENT TYPE / INTENDED USE", getattr(record, "procurement_type", None)),
                ("PROJECT NAME / LOA NUMBER", _project_loa(record)),
                ("LOA DATE", getattr(record, "loa_date_snapshot", None)),
                ("RAILWAY ZONE", getattr(record, "railway_zone_snapshot", None)),
                ("RAILWAY DIVISION", getattr(record, "railway_division_snapshot", None)),
                ("CONTRACT / TENDER REFERENCE", getattr(record, "contract_reference", None)),
                (
                    "PROCUREMENT REQUIREMENT REFERENCE",
                    getattr(record, "procurement_requirement_number_snapshot", None),
                ),
                ("DELIVERY DATE", str(record.delivery_date) if record.delivery_date else None),
            ]
        ),
        [
            (
                "VENDOR / SUPPLIER",
                _vendor(
                    record.vendor_snapshot,
                    getattr(record, "vendor_address_snapshot", None),
                    getattr(record, "vendor_gstin_snapshot", None),
                ),
            ),
            (
                "BUYER / BILL TO",
                _buyer(
                    record.organization_snapshot
                    | {
                        "gstin": (getattr(record, "organization_gst_snapshot", None) or {}).get(
                            "gstin"
                        )
                    },
                    record.billing_address_snapshot,
                ),
            ),
            ("SHIP TO", _address(record.shipping_address_snapshot)),
        ],
        lines,
        True,
        _totals(record),
        payment_terms=record.payment_terms_snapshot,
        terms=record.terms_override_text or (record.terms_snapshot or {}).get("content"),
        special_instructions=record.special_instructions,
        continuation_reference=_loa_reference(record) or getattr(record, "procurement_type", None),
    )


def proforma_invoice(record):
    return RenderDocument(
        "proforma_invoice",
        "PROFORMA INVOICE",
        record.pi_number,
        record.status,
        record.organization_snapshot
        | {"gstin": (getattr(record, "organization_gst_snapshot", None) or {}).get("gstin")},
        _clean_identity(
            [
                ("WORLD COMMUNICATION DOCUMENT NUMBER", record.pi_number),
                ("DATE", str(record.pi_date)),
                ("PROJECT NAME / LOA NUMBER", _project_loa(record)),
                ("LOA DATE", getattr(record, "loa_date_snapshot", None)),
                ("RAILWAY DIVISION", _reference(record.division_snapshot)),
                (
                    "CHALLAN / DISPATCH REFERENCES",
                    _line_references(record.lines, "challan_number_snapshot"),
                ),
            ]
        ),
        [
            (
                "CUSTOMER DETAILS",
                _party(record.customer_snapshot, getattr(record, "customer_gst_snapshot", None)),
            ),
            ("BILL TO", _address(record.bill_to_snapshot)),
            ("SHIP TO", _address(record.ship_to_snapshot)),
            ("CONSIGNEE / RAILWAY AUTHORITY", _party(record.authority_snapshot)),
        ]
        if record.business_scope == "RAILWAY"
        else [
            (
                "CUSTOMER DETAILS",
                _party(record.customer_snapshot, getattr(record, "customer_gst_snapshot", None)),
            ),
            ("BILL TO", _address(record.bill_to_snapshot)),
            ("SHIP TO", _address(record.ship_to_snapshot)),
        ],
        _commercial_lines(record, "billable_quantity", "sales_rate"),
        True,
        _totals(record),
        record.amount_in_words,
        record.bank_snapshot,
        record.payment_terms_snapshot,
        (record.terms_snapshot or {}).get("content"),
        record.notes,
        record.special_instructions,
        _loa_reference(record),
    )


def tax_invoice(record):
    return RenderDocument(
        "tax_invoice",
        "TAX INVOICE",
        record.invoice_number,
        record.status,
        record.organization_snapshot | {"gstin": record.organization_gst_snapshot.get("gstin")},
        _clean_identity(
            [
                ("WORLD COMMUNICATION DOCUMENT NUMBER", record.invoice_number),
                ("DATE", str(record.invoice_date)),
                ("DUE DATE", str(record.due_date) if record.due_date else None),
                ("PROJECT NAME / LOA NUMBER", _project_loa(record)),
                ("LOA DATE", getattr(record, "loa_date_snapshot", None)),
                (
                    "Place of Supply",
                    f"{record.place_of_supply_state} ({record.place_of_supply_state_code})",
                ),
                ("RAILWAY DIVISION / AUTHORITY", _reference(record.division_snapshot)),
                ("PI REFERENCE", _line_references(record.lines, "pi_number_snapshot")),
                ("CHALLAN REFERENCE", _line_references(record.lines, "challan_number_snapshot")),
            ]
        ),
        [
            ("CUSTOMER DETAILS", _party(record.customer_snapshot, record.customer_gst_snapshot)),
            ("BILL TO", _address(record.bill_to_snapshot)),
            ("SHIP TO", _address(record.ship_to_snapshot)),
        ],
        _commercial_lines(record, "invoiced_quantity", "sales_rate"),
        True,
        _totals(record),
        record.amount_in_words,
        record.bank_snapshot,
        record.payment_terms_snapshot,
        (record.terms_snapshot or {}).get("content"),
        record.notes,
        record.special_instructions,
        _loa_reference(record),
    )


def challan(record):
    lines = [
        RenderLine(
            line.line_number,
            line.description_snapshot,
            line.hsn_snapshot,
            line.unit_snapshot,
            line.dispatched_quantity,
            remarks=line.remarks,
        )
        for line in record.lines
    ]
    identities = _clean_identity(
        [
            ("WORLD COMMUNICATION DOCUMENT NUMBER", record.challan_number),
            ("DATE", str(record.challan_date)),
            ("PROJECT NAME / LOA NUMBER", _project_loa(record)),
            ("LOA DATE", getattr(record, "loa_date_snapshot", None)),
            ("RAILWAY DIVISION", _reference(record.division_snapshot)),
            (
                "TRANSPORTER / VEHICLE",
                " / ".join(v for v in (record.transporter, record.vehicle_number) if v),
            ),
            ("LR / RR", record.transport_reference),
            ("E-WAY BILL", record.eway_bill_reference),
            ("DELIVERY REFERENCE", record.acknowledgement_reference),
        ]
    )
    parties = [
        ("CUSTOMER DETAILS", _party(record.customer_snapshot)),
        ("CONSIGNEE", _party(record.consignee_snapshot)),
        ("DELIVERY ADDRESS", _address(record.delivery_address_snapshot)),
        ("DISPATCH DETAILS / DISPATCH FROM", _address(record.dispatch_from_snapshot)),
    ]
    return RenderDocument(
        "challan",
        "SUPPLY CHALLAN",
        record.challan_number,
        record.status,
        record.organization_snapshot,
        identities,
        parties,
        lines,
        False,
        notes=record.delivery_notes or record.remarks,
        special_instructions=record.special_instructions,
        continuation_reference=_loa_reference(record),
    )


def _address(value):
    from app.document_engine.formatting import address_text

    return address_text(value)


def _party(value, gst=None):
    from app.document_engine.formatting import party_text

    merged = dict(value or {})
    if gst:
        merged["gstin"] = gst.get("gstin")
    return party_text(merged)


def _vendor(value, address=None, gstin=None):
    merged = dict(value or {})
    lines = [_party(merged)]
    if merged.get("trade_name") and merged.get("trade_name") != merged.get("legal_name"):
        lines.append(f"Trade Name: {merged['trade_name']}")
    address_text = _address(address) if address else merged.get("address")
    if address_text:
        lines.append(f"Address: {address_text}")
    if gstin or merged.get("gstin"):
        lines.append(f"GSTIN: {gstin or merged.get('gstin')}")
    if merged.get("pan"):
        lines.append(f"PAN: {merged['pan']}")
    if merged.get("contact_name"):
        lines.append(f"Contact: {merged['contact_name']}")
    return "\n".join(lines)


def _buyer(organization, address):
    value = dict(organization or {})
    return "\n".join(
        (
            _party(value),
            _address(address),
            f"GSTIN: {value.get('gstin') or 'Not recorded in PO snapshot'}",
        )
    )


def _reference(value):
    if not value:
        return "-"
    if not isinstance(value, dict):
        return str(value)
    return str(value.get("name") or value.get("code") or value.get("division_code") or "-")


def _line_references(lines, attribute):
    values = []
    for line in lines:
        value = getattr(line, attribute, None)
        if value and str(value) not in values:
            values.append(str(value))
    return ", ".join(values) or "-"


def _clean_identity(values):
    return [(label, str(value)) for label, value in values if value not in (None, "", "-")]


def _snapshot_value(record, snapshot_name, key):
    value = getattr(record, snapshot_name, None) or {}
    return value.get(key)


def _project_loa(record):
    project = getattr(record, "project_snapshot", None) or {}
    loa = getattr(record, "loa_snapshot", None) or {}
    project_name = (
        getattr(record, "project_name_snapshot", None)
        or project.get("name")
        or project.get("project_name")
    )
    loa_number = (
        getattr(record, "loa_number_snapshot", None) or loa.get("loa_number") or loa.get("number")
    )
    if not project_name and not loa_number:
        return None
    return " / ".join(value for value in (project_name, loa_number) if value)


def _loa_reference(record):
    loa = getattr(record, "loa_snapshot", None) or {}
    number = (
        getattr(record, "loa_number_snapshot", None) or loa.get("loa_number") or loa.get("number")
    )
    return f"LOA: {number}" if number else None
