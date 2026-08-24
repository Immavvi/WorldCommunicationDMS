import re
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as canvas_module
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.document_engine.formatting import currency, indian_number

BROWN = colors.HexColor("#5A2D0C")
IVORY = colors.HexColor("#FAF7F0")
TAN = colors.HexColor("#C8B08D")
INK = colors.HexColor("#211A15")
LOGO_PATH = Path(__file__).parent / "assets" / "world_communication_logo.png"
TERM_LIMITS = {
    "tax_invoice": 5,
    "proforma_invoice": 7,
    "quotation": 8,
    "purchase_order": 12,
    "challan": 5,
}


class NumberedCanvas(canvas_module.Canvas):
    """Canvas that can render stable Page X of Y footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.setFont(_font(), 8)
            self.setFillColor(INK)
            self.drawRightString(
                landscape(A4)[0] - 12 * mm,
                8 * mm,
                f"Page {self._pageNumber} of {page_count}",
            )
            super().showPage()
        super().save()


def _font():
    candidates = (
        Path("backend/assets/fonts/NotoSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.exists():
            if "WCDMS" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("WCDMS", str(path)))
            return "WCDMS"
    return "Helvetica"


def render_pdf(document, logo_path=None):
    output = BytesIO()
    width, height = landscape(A4)
    font = _font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontName=font, fontSize=8, leading=10, textColor=INK
    )
    small = ParagraphStyle("Small", parent=body, fontSize=7, leading=9)
    heading = ParagraphStyle("Heading", parent=body, fontSize=9, leading=11, textColor=colors.white)
    title = ParagraphStyle(
        "Title", parent=body, fontSize=12, leading=15, alignment=1, textColor=colors.white
    )
    doc = BaseDocTemplate(
        output,
        pagesize=(width, height),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=document.identifier,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="content")

    def decorate(canvas, _):
        canvas.saveState()
        canvas.setFillColor(IVORY)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFont(font, 8)
        canvas.setFillColor(INK)
        canvas.drawString(
            doc.leftMargin, 8 * mm, "This is a Computer Generated Document  |  E. & O.E."
        )
        canvas.setStrokeColor(TAN)
        canvas.line(doc.leftMargin, 12 * mm, width - doc.rightMargin, 12 * mm)
        if canvas.getPageNumber() > 1:
            left_text, center_text, right_text = _continuation_parts(document)
            band_y = height - 14 * mm
            band_height = 8 * mm
            third = doc.width / 3
            canvas.setFillColor(BROWN)
            canvas.setStrokeColor(TAN)
            canvas.rect(
                doc.leftMargin,
                band_y,
                doc.width,
                band_height,
                fill=1,
                stroke=1,
            )
            canvas.setStrokeColor(TAN)
            canvas.line(
                doc.leftMargin + third,
                band_y,
                doc.leftMargin + third,
                band_y + band_height,
            )
            canvas.line(
                doc.leftMargin + 2 * third,
                band_y,
                doc.leftMargin + 2 * third,
                band_y + band_height,
            )
            canvas.setFillColor(colors.white)
            baseline = band_y + 2.8 * mm
            canvas.setFont(font, _fit_font_size(left_text, font, third - 8 * mm))
            canvas.drawString(doc.leftMargin + 4 * mm, baseline, left_text)
            canvas.setFont(font, _fit_font_size(center_text, font, third - 8 * mm))
            canvas.drawCentredString(
                doc.leftMargin + 1.5 * third,
                baseline,
                center_text,
            )
            if right_text:
                canvas.setFont(font, _fit_font_size(right_text, font, third - 8 * mm))
                canvas.drawRightString(
                    width - doc.rightMargin - 4 * mm,
                    baseline,
                    right_text,
                )
        if document.status == "DRAFT":
            canvas.setFillColor(colors.Color(0.75, 0.75, 0.75, alpha=0.25))
            canvas.setFont(font, 62)
            canvas.translate(width / 2, height / 2)
            canvas.rotate(28)
            canvas.drawCentredString(0, 0, "DRAFT")
        canvas.restoreState()

    doc.addPageTemplates(PageTemplate(id="wcdms", frames=[frame], onPage=decorate))
    company = document.organization.get("legal_name") or "World Communication"
    company_details = [
        document.organization.get("address"),
        document.organization.get("trade_name"),
        document.organization.get("email"),
        document.organization.get("phone"),
        f"GSTIN: {document.organization.get('gstin')}"
        if document.organization.get("gstin")
        else None,
        document.organization.get("website"),
    ]
    detail_text = "<br/>".join(escape(str(value)) for value in company_details if value)
    header_left = f"<b>{escape(str(company))}</b><br/>{detail_text}"
    resolved_logo = Path(logo_path) if logo_path else LOGO_PATH
    logo = (
        Image(str(resolved_logo), width=50 * mm, height=21 * mm, kind="proportional")
        if resolved_logo.exists()
        else ""
    )
    story = [
        Table(
            [
                [
                    logo,
                    Paragraph(
                        header_left,
                        ParagraphStyle(
                            "Company", parent=body, alignment=TA_RIGHT, fontSize=9, leading=12
                        ),
                    ),
                ]
            ],
            colWidths=[55 * mm, doc.width - 55 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 0), (-1, -1), IVORY),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Table(
            [[Paragraph(document.title, title)]],
            colWidths=[doc.width],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BROWN),
                    ("BOX", (0, 0), (-1, -1), 0.6, TAN),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            ),
        ),
        Spacer(1, 3 * mm),
    ]
    story.append(_identity_card(document, body, small, doc.width))
    story.append(Spacer(1, 3 * mm))
    if document.parties:
        story.append(_party_card(document.parties, heading, body, doc.width))
    story.extend([Spacer(1, 4 * mm), _line_table(document, body, small), Spacer(1, 4 * mm)])
    if document.kind == "challan":
        total_quantity = sum(Decimal(str(line.quantity)) for line in document.lines)
        acknowledgement = (
            "Received the above material in good condition.<br/>"
            "Name: __________________ &nbsp;&nbsp; Designation: __________________<br/>"
            "Signature / Stamp: __________________ &nbsp;&nbsp; Date: __________"
        )
        story.append(
            Table(
                [
                    [
                        Paragraph("<b>SPECIAL INSTRUCTIONS / NOTES</b>", heading),
                        Paragraph(
                            f"<b>TOTAL QUANTITY</b>: {indian_number(total_quantity, 4)}", body
                        ),
                    ],
                    [
                        Paragraph(
                            escape(document.special_instructions or document.notes or "-").replace(
                                "\n", "<br/>"
                            ),
                            body,
                        ),
                        Paragraph(
                            "<b>MATERIAL STATUS</b>: Non-Financial Delivery Challan<br/>"
                            f"<b>REFERENCE</b>: {escape(document.identifier)}<br/><br/>"
                            f"<b>RECEIVER'S ACKNOWLEDGEMENT</b><br/>{acknowledgement}",
                            body,
                        ),
                    ],
                ],
                colWidths=[doc.width / 2] * 2,
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), BROWN),
                        ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.5, TAN),
                        ("INNERGRID", (0, 0), (-1, -1), 0.35, TAN),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 1), (-1, -1), IVORY),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]
                ),
            )
        )
    if document.financial:
        total_rows = []
        for label, value in document.totals:
            text_color = colors.white if label == "Grand Total" else INK
            label_style = ParagraphStyle(f"TotalLabel-{label}", parent=body, textColor=text_color)
            value_style = ParagraphStyle(
                f"TotalValue-{label}",
                parent=body,
                alignment=TA_RIGHT,
                textColor=text_color,
            )
            total_rows.append(
                [Paragraph(label, label_style), Paragraph(currency(value), value_style)]
            )
        total_table = Table(
            total_rows,
            colWidths=[42 * mm, 45 * mm],
            style=TableStyle(
                [
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEABOVE", (0, -1), (-1, -1), 1.2, BROWN),
                    ("BACKGROUND", (0, -1), (-1, -1), BROWN),
                    ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                    ("FONTNAME", (0, -1), (-1, -1), font),
                ]
            ),
        )
        words = Paragraph(
            f"<b>Amount in Words</b><br/>{escape(document.amount_in_words or '-')}", body
        )
        story.append(
            Table(
                [[words, total_table]],
                colWidths=[doc.width - 90 * mm, 87 * mm],
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
            )
        )
    if document.bank:
        story.extend(
            [
                Spacer(1, 3 * mm),
                _section(
                    "Bank Details",
                    " | ".join(
                        f"{k.replace('_', ' ').title()}: {v}" for k, v in document.bank.items() if v
                    ),
                    heading,
                    body,
                    doc.width,
                ),
            ]
        )
    if document.payment_terms:
        story.extend(
            [
                Spacer(1, 3 * mm),
                _section(
                    "Payment Terms",
                    str(
                        document.payment_terms.get("description")
                        or document.payment_terms.get("name")
                    ),
                    heading,
                    body,
                    doc.width,
                ),
            ]
        )
    if document.notes:
        story.extend(
            [Spacer(1, 3 * mm), _section("Notes", document.notes, heading, body, doc.width)]
        )
    if document.special_instructions:
        story.extend(
            [
                Spacer(1, 3 * mm),
                _section(
                    "Special Instructions", document.special_instructions, heading, body, doc.width
                ),
            ]
        )
    main_terms, annexure_terms = _presented_terms(document)
    main_height = sum(_term_height(term) for term in main_terms) + 28
    if main_terms and main_height <= 330:
        closure = [Spacer(1, 4 * mm), _terms_heading("Terms & Conditions", heading, doc.width)]
        closure.extend(Paragraph(_term_markup(term), body) for term in main_terms)
        closure.extend([Spacer(1, 5 * mm), _signature_table(body, doc.width)])
        story.append(KeepTogether(closure))
    elif main_terms:
        story.extend(_terms_flowables(main_terms, heading, body, doc.width))
        story.extend([Spacer(1, 5 * mm), _signature_table(body, doc.width)])
    else:
        story.extend([Spacer(1, 5 * mm), _signature_table(body, doc.width)])
    if annexure_terms:
        story.extend(
            _annexure_flowables(document, annexure_terms, heading, body, small, doc.width)
        )
    doc.build(story, canvasmaker=NumberedCanvas)
    return output.getvalue()


def _identity_card(document, body, small, width):
    values = [(label, value) for label, value in document.identity if _displayable(value)]
    pairs = []
    for index in range(0, len(values), 2):
        row = []
        for label, value in values[index : index + 2]:
            emphasis = label in {
                "WORLD COMMUNICATION DOCUMENT NUMBER",
                "DATE",
                "PROJECT NAME / LOA NUMBER",
                "RAILWAY DIVISION",
            }
            row.extend(
                [
                    Paragraph(f"<b>{escape(str(label).upper())}</b>", small),
                    Paragraph(
                        f"<b>{escape(str(value))}</b>" if emphasis else escape(str(value)), body
                    ),
                ]
            )
        while len(row) < 4:
            row.extend(["", ""])
        pairs.append(row)
    label_width = 42 * mm
    value_width = width / 2 - label_width
    table = Table(
        pairs or [["", "", "", ""]],
        colWidths=[label_width, value_width, label_width, value_width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), IVORY),
                ("BOX", (0, 0), (-1, -1), 1.0, BROWN),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, TAN),
                ("LINEBEFORE", (2, 0), (2, -1), 0.5, TAN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _party_card(parties, heading, body, width):
    headings = [Paragraph(f"<b>{escape(label.upper())}</b>", heading) for label, _ in parties]
    bodies = [
        Paragraph(escape(value).replace(chr(10), "<br/>"), body) for _, value in parties
    ]
    table = Table([headings, bodies], colWidths=[width / len(parties)] * len(parties))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BROWN),
                ("BACKGROUND", (0, 1), (-1, 1), IVORY),
                ("BOX", (0, 0), (-1, -1), 1.0, BROWN),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, TAN),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _displayable(value):
    return value not in (None, "", "-")


def _continuation_parts(document):
    return (
        "WORLD COMMUNICATION",
        f"{document.title} - {document.identifier}",
        document.continuation_reference or "",
    )


def _fit_font_size(text, font, available_width, maximum=8, minimum=6):
    size = maximum
    while size > minimum and pdfmetrics.stringWidth(text, font, size) > available_width:
        size -= 0.25
    return size


def _signature_table(body, width):
    signature_style = ParagraphStyle("Signature", parent=body, alignment=1)
    value = (
        "<b>FOR WORLD COMMUNICATION</b><br/><br/><br/>"
        "____________________________<br/>Authorised Signatory"
    )
    table = Table(
        [[Paragraph(value, signature_style), Paragraph(value, signature_style)]],
        colWidths=[width / 2] * 2,
        rowHeights=[25 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.0, BROWN),
                ("LINEBEFORE", (1, 0), (1, 0), 0.35, TAN),
                ("BACKGROUND", (0, 0), (-1, -1), IVORY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _line_table(document, body, small):
    if document.kind == "purchase_order":
        headers = [
            "Sl.",
            "Description",
            "OEM / Make",
            "Model / Part No.",
            "HSN/SAC",
            "Qty / UOM",
            "Purchase Rate / Tax",
            "Amount",
        ]
        widths = [9, 75, 30, 32, 22, 27, 32, 33]
        rows = [
            [
                line.number,
                Paragraph(escape(line.description), small),
                line.oem or "-",
                line.model or "-",
                line.hsn or "-",
                f"{indian_number(line.quantity, 4)} {line.unit}",
                Paragraph(
                    f"{escape(currency(line.rate))}<br/>{escape(line.gst or 'Tax: -')}", small
                ),
                currency(line.amount),
            ]
            for line in document.lines
        ]
    elif document.financial:
        headers = [
            "Sl.",
            "Description",
            "Model / Part No.",
            "HSN",
            "Qty",
            "Rate",
            "Amount",
        ]
        widths = [10, 100, 35, 25, 25, 30, 35]
        rows = [
            [
                line.number,
                Paragraph(escape(line.description), small),
                line.model or "-",
                line.hsn or "-",
                f"{indian_number(line.quantity, 4)} {line.unit}",
                currency(line.rate),
                currency(line.amount),
            ]
            for line in document.lines
        ]
    else:
        headers = ["Sl.", "Description", "Model / Part No.", "HSN/SAC", "Qty", "Unit", "Remarks"]
        widths = [10, 100, 30, 25, 25, 20, 50]
        rows = [
            [
                line.number,
                Paragraph(escape(line.description), small),
                line.model or "-",
                line.hsn or "-",
                indian_number(line.quantity, 4),
                line.unit,
                Paragraph(escape(line.remarks or ""), small),
            ]
            for line in document.lines
        ]
    table = Table([headers, *rows], colWidths=[value * mm for value in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BROWN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), body.fontName),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, TAN),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [IVORY, colors.HexColor("#F5EFE4")]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _section(title, text, heading, body, width):
    content = escape(str(text)).replace("\n", "<br/>")
    return KeepTogether(
        [
            Table(
                [[Paragraph(title, heading)]],
                colWidths=[width],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), BROWN),
                        ("PADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            Paragraph(content, body),
        ]
    )


def _terms_flowables(text, heading, body, width):
    terms = text if isinstance(text, list) else _term_items(text)
    estimated = sum(_term_height(term) for term in terms) + 28
    if estimated <= 380:
        content = [_terms_heading("Terms & Conditions", heading, width)]
        content.extend(KeepTogether([Paragraph(_term_markup(term), body)]) for term in terms)
        return [Spacer(1, 4 * mm), CondPageBreak(estimated + 85), KeepTogether(content)]

    # Keep enough room for real paragraph wrapping and the authorisation block.
    chunks = _term_chunks(terms, 280)

    result = [PageBreak()]
    for index, chunk in enumerate(chunks):
        if index:
            result.append(PageBreak())
        title = "Terms & Conditions" if index == 0 else "TERMS & CONDITIONS - CONTINUED"
        page = [_terms_heading(title, heading, width), Spacer(1, 2 * mm)]
        page.extend(KeepTogether([Paragraph(_term_markup(term), body)]) for term in chunk)
        result.append(KeepTogether(page))
    return result


def _presented_terms(document):
    terms = _term_items(document.terms) if document.terms else []
    limit = TERM_LIMITS.get(document.kind, 5)
    if len(terms) <= limit:
        return terms, []
    main = [*terms[:limit], "Detailed Terms & Conditions: Refer Annexure-A."]
    return main, terms


def _annexure_flowables(document, terms, heading, body, small, width):
    result = [PageBreak()]
    chunks = _term_chunks(terms, 300)
    for index, chunk in enumerate(chunks):
        if index:
            result.append(PageBreak())
        title = "ANNEXURE-A" if index == 0 else "ANNEXURE-A - CONTINUED"
        content = [_terms_heading(title, heading, width)]
        if index == 0:
            content.extend(
                [
                    Paragraph("<b>DETAILED TERMS &amp; CONDITIONS</b>", body),
                    Paragraph(
                        f"<b>Document Type:</b> {escape(document.title)} &nbsp;&nbsp; "
                        f"<b>Document Number:</b> {escape(document.identifier)} &nbsp;&nbsp; "
                        f"<b>Document Date:</b> {escape(_document_date(document))}",
                        small,
                    ),
                    Spacer(1, 2 * mm),
                ]
            )
        content.extend(KeepTogether([Paragraph(_term_markup(term), body)]) for term in chunk)
        result.append(KeepTogether(content))
    return result


def _term_chunks(terms, budget):
    chunks = []
    current = []
    used = 0
    for term in terms:
        height = _term_height(term)
        if current and used + height > budget:
            chunks.append(current)
            current = []
            used = 0
        current.append(term)
        used += height
    if current:
        chunks.append(current)
    return chunks


def _document_date(document):
    for label, value in document.identity:
        if label == "DATE":
            return str(value)
    return "-"


def _terms_heading(title, heading, width):
    return Table(
        [[Paragraph(title, heading)]],
        colWidths=[width],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BROWN),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        ),
    )


def _term_items(text):
    normalized = str(text).replace("\r\n", "\n").strip()
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    split = re.split(r"(?=\b\d+[.)]\s+)", normalized)
    return [item.strip() for item in split if item.strip()] or ["-"]


def _term_markup(term):
    return escape(term).replace("\n", "<br/>")


def _term_height(term):
    logical_lines = max(1, (len(term) + 139) // 140) + term.count("\n")
    return 8 + logical_lines * 10
