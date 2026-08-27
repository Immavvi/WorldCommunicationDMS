from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

from app.core.config import get_settings
from app.services.loa_extraction import ExtractedLine, PdfLoaExtractor, normalize_extraction
from app.services.loa_import_service import RailwayLoaImportService, normalized

STRUCTURAL_FIXTURES = Path(__file__).parent / "fixtures" / "railway_loa_structures"


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def railway_loa_workbook(
    *,
    loa_number: str = "LOA/RAIL/20",
    division: str = "Adra Division",
    unit: str = "Nos",
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "LOA and BOQ"
    sheet.append([f"LOA Number: {loa_number}"])
    sheet.append(["LOA Date: 24/08/2026"])
    sheet.append(["Tender Reference: TENDER/42"])
    sheet.append(["Name of Work: Supply of railway communication equipment"])
    sheet.append(["Contract Value: INR 2469.00"])
    sheet.append(["Completion Period: 180 days"])
    sheet.append(["Completion Date: 20/02/2027"])
    sheet.append(["Consignee: Sr DSTE Adra"])
    sheet.append([division])
    sheet.append(["South Eastern Railway Zone"])
    sheet.append(["Item No", "Description", "HSN", "UOM", "Qty", "Rate", "Amount"])
    sheet.append(["1", "IP communication terminal", "8517", unit, 3, 823, 2469])
    sheet.append(["", "including installation accessories", "", "", "", "", ""])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_native_pdf_text_and_scanned_pdf_ocr_use_the_same_normalizer(tmp_path, monkeypatch) -> None:
    class Result:
        stdout = (
            "LOA Number: LOA/PDF/1\nLOA Date: 24/08/2026\n"
            "Name of Work: Railway terminal supply\nContract Value: 200.00\n"
            "1  Terminal  Nos  2  100  200"
        )

    monkeypatch.setattr(
        "app.services.loa_extraction.subprocess.run", lambda *args, **kwargs: Result()
    )
    source = tmp_path / "loa.pdf"
    source.write_bytes(b"%PDF-test")
    native = PdfLoaExtractor().extract(source)
    assert native.method == "NATIVE_PDF"
    assert native.loa_number == "LOA/PDF/1"
    assert native.contract_value == 200

    class FakeOcr:
        def extract(self, _path):
            return Result.stdout

    class EmptyResult:
        stdout = ""

    monkeypatch.setattr(
        "app.services.loa_extraction.subprocess.run", lambda *args, **kwargs: EmptyResult()
    )
    scanned = PdfLoaExtractor(ocr=FakeOcr()).extract(source)
    assert scanned.method == "OCR"
    assert scanned.loa_number == native.loa_number
    assert scanned.contract_value == native.contract_value


def test_ireps_loa_header_boundaries_and_boq_columns_are_semantic() -> None:
    text = """
                         SOUTH EASTERN RLY
                             ADRA DIVISION-S AND T
    Letter No: ADRA DIVISION-S AND T /                                      Dated:
    SnT_e_Tender_SYNTH_25_26_18 /                                           18/03/2026
    00999990000111

    M/s SYNTHETIC VENDOR
    Sub: Letter Of Acceptance
    Ref: 1. Tender No. SnT_e_Tender_SYNTH_25_26_18 closing
           date 09-02-2026 11:00 for Supply, Installation, Testing and Commissioning
           of a synthetic CCTV system at controlled test locations in Adra division.
         2. Your bid ID 12345 dated 09/02/2026 09:41

    The Competent Authority has accepted your offered rates. The total cost of the work
    at the accepted rates works out to Rs. 27492281.33.
    The entire work shall be completed within 10 month from the date of issue of
    Letter of Acceptance.
    Direction: You are hereby directed to Sr.DSTE/Adra for briefing the work.

    Awarded Quantities And Rates
    Total Value 23738364.62                  27492281.33
    Rebate on Total Value 0.00
    Net Bid Value 27492281.33

    Item Breakup
    Schedule B-SOR SUPPLY
    Item - 1       SOR : 46 LC GATE
    S No.          Item No        Description of Item        Unit       Qty       Rate       Amount

                                 Supply of HDPE pipe as per synthetic specification
    1  02023000 with suitable couplers  Kilometre  13.8  56520.00  779976.00
                                 and inspection by RITES.

    SOUTH EASTERN RAILWAY
    TENDER DOCUMENT e-Tender No: SnT_e_Tender_SYNTH_25_26_18
    Name of Work: Supporting attachment that must not override LOA metadata.
    Tender opening date: 30/04/2027
    Estimated Value: 99999999.99
    """
    extractor = PdfLoaExtractor()
    result = normalize_extraction("NATIVE_PDF", text, extractor._parse_table(text))
    assert result.loa_number == (
        "ADRA DIVISION-S AND T / SnT_e_Tender_SYNTH_25_26_18 / 00999990000111"
    )
    assert result.tender_reference == "SnT_e_Tender_SYNTH_25_26_18"
    assert result.loa_date.strftime("%d/%m/%Y") == "18/03/2026"
    assert result.loa_date_provenance == "SOURCE_EXTRACTED"
    assert result.loa_date_source == "LOA header / Dated"
    assert result.completion_date.strftime("%d/%m/%Y") == "18/01/2027"
    assert result.completion_date_provenance == "DERIVED"
    assert result.work_description == (
        "Supply, Installation, Testing and Commissioning of a synthetic CCTV system at "
        "controlled test locations in Adra division."
    )
    assert result.completion_period == "10 months"
    assert result.contract_value == Decimal("27492281.33")
    assert result.zone_text == "SOUTH EASTERN"
    assert result.division_text == "ADRA"
    assert result.authority_text == "Sr.DSTE/Adra"
    assert normalized("SOUTH EASTERN RLY") == normalized("South Eastern Railway")
    assert len(result.lines) == 1
    line = result.lines[0]
    assert not hasattr(line, "item_number")
    assert "02023000" not in line.description
    assert "02023000" in line.source_raw_text
    assert line.description == (
        "Supply of HDPE pipe as per synthetic specification with suitable couplers "
        "and inspection by RITES."
    )
    assert line.unit_text == "Kilometre"
    assert line.quantity == Decimal("13.8")
    assert line.rate == Decimal("56520.00")
    assert line.amount == Decimal("779976.00")
    assert "Schedule B-SOR SUPPLY" in line.remarks
    assert "Item - 1 SOR : 46 LC GATE" in line.remarks


def test_awarded_quantities_are_authoritative_over_subordinate_item_breakup() -> None:
    text = """
    LOA Number: TEST/AWARDED/1
    LOA Date: 18/03/2026
    Name of Work: Contract schedule test
    Contract Value: 336.00

    Awarded Quantities And Rates
    Schedule A-NON SOR ITEMS
    1     Network equipment     01001       2 Numbers       100.00 At Par       200.00
    2     Terminal accessory    01002       4 Numbers        25.00 At Par       100.00
    Schedule B-SOR ITEMS
    1     Installation work     02001       3 Metre          10.00 At Par        36.00
    Schedule Totals 36.00
    Total Value 330.00 336.00

    Item Breakup
    Schedule B-SOR ITEMS
    Item - 01 subordinate breakup
    S No. Item No Description of Item Unit Qty Rate Amount
    1  SUB-1  Subordinate component  Metre  1  10.00  10.00

    SOUTH EASTERN RAILWAY
    TENDER DOCUMENT e-Tender No: TEST/AWARDED/1
    99 unrelated tender condition 01099 999 Numbers 999.00 At Par 999.00
    """
    extractor = PdfLoaExtractor()
    lines = extractor._parse_table(text)
    assert len(lines) == 3
    assert not any(hasattr(line, "item_number") for line in lines)
    assert all("Awarded Quantities And Rates" in (line.remarks or "") for line in lines)
    assert lines[-1].rate == Decimal("10.00")
    assert lines[-1].extraction_outcome == "NEEDS_REVIEW"
    assert "quantity × source rate" in lines[-1].extraction_issue
    reconciliation = extractor.last_reconciliation
    assert reconciliation["authoritative_boq_section"] == "Awarded Quantities And Rates"
    assert reconciliation["attached_tender_excluded"] is True
    assert reconciliation["source_rows_detected"] == 3
    assert reconciliation["complete"] is False


def test_awarded_row_accepts_compact_quantity_uom_rate_layout() -> None:
    parsed = PdfLoaExtractor._parse_awarded_row(
        "07     Sanitized equipment description        EQ-07"
        "                  2 Numbers 125.50 At Par          251.00"
    )

    assert parsed == (
        "07",
        "Sanitized equipment description",
        "Numbers",
        Decimal("2"),
        Decimal("125.50"),
        Decimal("251.00"),
    )
    sparse_description = PdfLoaExtractor._parse_awarded_row(
        "3   Sanitized cable   CB-03 2440 Metre 40.00 At Par 97600.00"
    )
    assert sparse_description == (
        "3",
        "Sanitized cable",
        "Metre",
        Decimal("2440"),
        Decimal("40.00"),
        Decimal("97600.00"),
    )


def test_explicit_source_percentage_adjustment_preserves_contractual_rate() -> None:
    text = """
    Awarded Quantities And Rates
    Schedule A-SANITIZED ITEMS
    1  Sanitized service  SV-01  2 Numbers  100.00 18.00 % Above  236.00
    """

    line = PdfLoaExtractor()._parse_table(text)[0]

    assert line.rate == Decimal("100.00")
    assert line.amount == Decimal("236.00")
    assert line.tax_text == "18.00% source adjustment"
    assert line.extraction_outcome == "EXTRACTED"


@pytest.mark.parametrize(
    ("fixture_name", "source_tokens", "expected_schedules"),
    [
        ("detailed_awarded.txt", ["EQ-01", "SV-02"], 1),
        ("summary_breakup.txt", ["BK-01", None], 1),
        ("mixed_schedules.txt", ["DR-01", "BX-01"], 2),
    ],
)
def test_sanitized_structural_corpus_preserves_hierarchy_and_candidates(
    fixture_name, source_tokens, expected_schedules
) -> None:
    text = (STRUCTURAL_FIXTURES / fixture_name).read_text()
    extractor = PdfLoaExtractor()
    lines = extractor._parse_table(text)
    assert not any(hasattr(line, "item_code") for line in lines)
    for token in filter(None, source_tokens):
        assert token not in " ".join(line.description or "" for line in lines)
        assert token in " ".join(line.source_raw_text or "" for line in lines)
    assert len({line.candidate_key for line in lines}) == len(lines)
    assert all(line.description_raw for line in lines)
    assert all(line.source_page_start and line.source_page_end for line in lines)
    assert extractor.last_reconciliation["schedules_detected"] == expected_schedules
    assert extractor.last_reconciliation["source_rows_detected"] == len(lines)
    assert extractor.last_reconciliation["attached_tender_excluded"] is (
        fixture_name == "detailed_awarded.txt"
    )


def test_page_furniture_does_not_break_logical_description_or_become_source_text() -> None:
    text = (STRUCTURAL_FIXTURES / "summary_breakup.txt").read_text()
    extractor = PdfLoaExtractor()
    lines = extractor._parse_table(text)
    first = lines[0]
    assert first.source_page_start == 1
    assert first.source_page_end == 2
    assert "continuation on the next PDF page" in first.description_raw
    assert "ireps.gov.in" not in first.description_raw
    assert "Page 1 of 2" not in first.description_raw


def test_ocr_schedule_table_without_awarded_or_breakup_retains_uncertain_uom() -> None:
    text = """
    Name of the work: Sanitized OCR schedule
    Schedule-A.
    SN Description Unit Qty Rate Amount
    1. |Supply and installation of terminal | Nos. 2 100.00 200.00
    description continuation across the OCR line.
    Page 1 of 2
    \fSN Description Unit Qty Rate Amount
    2. |Supply of connector 10 5.00 50.00
    3. |Corrupted numeric tail No. [xx 3 20.00
    Total 250.00
    """
    extractor = PdfLoaExtractor()
    lines = extractor._parse_table(text)
    assert len(lines) == 3
    assert lines[0].uom_raw == "Nos."
    assert "description continuation" in lines[0].description_raw
    assert lines[1].uom_raw is None
    assert lines[1].extraction_outcome == "NEEDS_REVIEW"
    assert lines[2].extraction_outcome == "NEEDS_REVIEW"
    assert extractor.last_reconciliation["complete"] is False


def test_ocr_at_par_rows_are_separate_candidates_without_item_code_semantics() -> None:
    text = """
    Awarded Quantities And Rates
    Schedule A-SUPPLY
    1 Supply of terminal 02023000 1 60]Numbers 6030.17} At Par 361810.25
    2 Supply of accessory 02024000 2 Numbers 50.00 At Par 100.00
    Total Value 361910.25
    """
    lines = PdfLoaExtractor()._parse_table(text)

    assert [line.source_serial for line in lines] == ["1", "2"]
    assert [line.amount for line in lines] == [Decimal("361810.25"), Decimal("100.00")]
    assert "02023000" not in (lines[0].description or "")
    assert "02023000" in (lines[0].source_raw_text or "")
    assert not any(hasattr(line, "item_code") for line in lines)


def test_missing_ocr_serial_preserves_contractual_candidate_for_review() -> None:
    text = """
    Schedule A-SUPPLY
    SN Description Unit Qty Rate Amount
    |Supply of terminal | Numbers 2 100.00 200.00
    2 |Supply of accessory | Numbers 1 50.00 50.00
    Total 250.00
    """
    lines = PdfLoaExtractor()._parse_table(text)

    assert len(lines) == 2
    assert lines[0].source_serial is None
    assert lines[0].quantity == Decimal("2")
    assert lines[0].amount == Decimal("200.00")
    assert lines[0].extraction_outcome == "NEEDS_REVIEW"
    assert "Sn. No." in (lines[0].extraction_issue or "")


def test_schedule_and_serial_form_identity_while_candidate_keys_remain_unique() -> None:
    text = """
    Schedule A-SUPPLY
    SN Description Unit Qty Rate Amount
    1 |First schedule item | Numbers 1 10.00 10.00
    Schedule B-SUPPLY
    SN Description Unit Qty Rate Amount
    1 |Second schedule item | Numbers 1 20.00 20.00
    Total 30.00
    """
    lines = PdfLoaExtractor()._parse_table(text)

    assert [line.source_serial for line in lines] == ["1", "1"]
    assert "Schedule A" in (lines[0].remarks or "")
    assert "Schedule B" in (lines[1].remarks or "")
    assert lines[0].candidate_key != lines[1].candidate_key


def test_raw_description_is_immutable_evidence_separate_from_interpreted_description() -> None:
    text = (STRUCTURAL_FIXTURES / "detailed_awarded.txt").read_text()
    line = PdfLoaExtractor()._parse_table(text)[0]
    assert "complete technical specification" in line.description_raw
    assert line.description_normalized == _clean_for_assertion(line.description_raw)
    line.description = "Owner-reviewed concise interpretation"
    assert "complete technical specification" in line.description_raw


def _clean_for_assertion(value: str) -> str:
    return " ".join(value.split())


@pytest.mark.parametrize(
    ("duration", "expected"),
    [("6 months", "2026-09-18"), ("10 month", "2027-01-18"), ("180 days", "2026-09-14")],
)
def test_completion_date_uses_contractual_calendar_arithmetic(duration, expected) -> None:
    text = (
        "LOA Number: TEST/1\nLOA Date: 18/03/2026\nName of Work: Test work\n"
        "Contract Value: 100.00\nThe entire work shall be completed within "
        f"{duration} from the date of issue of Letter of Acceptance."
    )
    result = normalize_extraction("NATIVE_PDF", text, [])
    assert result.completion_date.strftime("%Y-%m-%d") == expected
    assert result.completion_date_provenance == "DERIVED"


def test_explicit_completion_wins_and_unrelated_or_ambiguous_periods_do_not_derive() -> None:
    explicit = normalize_extraction(
        "NATIVE_PDF",
        "LOA Number: T/1\nLOA Date: 31/01/2026\nCompletion Date: 15/09/2026\n"
        "Name of Work: Work\nContract Value: 1.00\nThe entire work shall be completed within "
        "6 months from the date of issue of LOA. Warranty period shall be 24 months.",
        [],
    )
    assert explicit.completion_date.strftime("%Y-%m-%d") == "2026-09-15"
    assert explicit.completion_date_provenance == "SOURCE_EXTRACTED"
    ambiguous = normalize_extraction(
        "NATIVE_PDF",
        "LOA Number: T/2\nLOA Date: 31/01/2026\nName of Work: Work\nContract Value: 1.00\n"
        "Work shall be completed within 6 months. Warranty period shall be 24 months.",
        [],
    )
    assert ambiguous.completion_period == "6 months"
    assert ambiguous.completion_date is None
    assert ambiguous.completion_date_provenance is None


def test_authority_roles_and_unparsed_boq_candidates_remain_visible() -> None:
    text = """
    LOA Number: TEST/ROLE/1
    LOA Date: 18/03/2026
    Name of Work: Role test
    Contract Value: 100.00
    Direction: You are hereby directed to Sr.DSTE/Test for briefing the work.
    DSTE/TEST

    Item Breakup
    Schedule A-SUPPLY
    Item - 1 TEST GROUP

    1  02001  Incomplete row  Nos  2  invalid  100.00
    """
    extractor = PdfLoaExtractor()
    result = normalize_extraction("NATIVE_PDF", text, extractor._parse_table(text))
    assert {candidate["role"] for candidate in result.authority_candidates} == {
        "EXECUTION_AUTHORITY",
        "ISSUING_AUTHORITY",
    }
    assert result.authority_text == "Sr.DSTE/Test"
    assert len(result.lines) == 1
    assert result.lines[0].extraction_outcome == "NEEDS_REVIEW"
    assert result.lines[0].source_serial == "1"
    assert result.lines[0].source_raw_text
    assert extractor.last_reconciliation["source_rows_detected"] == 1
    assert extractor.last_reconciliation["needs_review"] == 1


def test_authority_boundary_and_ckp_header_reference_are_not_conflated() -> None:
    text = """
    Letter No: CKP-DIVN-S AND T / ST-CKP-OT-
    25-26-120 / 001122                                      28/04/2026
    Name of Work: Test work
    Contract Value: 100.00
    The entire work shall be completed within 6 month from the date of issue of
    Letter of Acceptance.
    DSTE/CKPwithin 21 days from the date of issue of Letter of Acceptance.
    OFFICER NAME
    DSTE/CKP
    Digitally Signed
    """
    result = normalize_extraction("NATIVE_PDF", text, [])
    assert result.loa_number.endswith("25-26-120 / 001122")
    assert result.loa_date.strftime("%d/%m/%Y") == "28/04/2026"
    assert result.completion_date.strftime("%d/%m/%Y") == "28/10/2026"
    assert result.authority_candidates == [
        {"text": "DSTE/CKP", "role": "ISSUING_AUTHORITY", "source": "Signature block"}
    ]


def test_decimal_row_reconciliation_does_not_rewrite_source_amount() -> None:
    line = ExtractedLine(quantity=Decimal("3"), rate=Decimal("33.33"), amount=Decimal("100.00"))
    assert line.quantity * line.rate == Decimal("99.99")
    assert line.amount == Decimal("100.00")


def test_multi_page_schedule_coverage_and_shifted_numeric_columns_are_recovered() -> None:
    text = """
    LOA Number: TEST/MULTI/1
    LOA Date: 18/03/2026
    Name of Work: Multi schedule work
    Contract Value: 300.00

    Item Breakup
    Schedule A-NON SOR SUPPLY
    Item - 1 SUPPLY
    S No.  Item No  Description of Item  Unit  Qty  Rate  Amount

    Long wrapped description before the numeric row
    1              01003003                  Numbers                 2 100.00  200.00

    Total 200.00
    \fRepeated page header
    Schedule B-SOR EXECUTION
    Item - 1 EXECUTION
    S No.  Item No  Description of Item  Unit  Qty  Rate  Amount

    1  02001 Installation work  Metre  2  50.00  100.00
    continuation after numeric row

    Total 100.00
    """
    extractor = PdfLoaExtractor()
    lines = extractor._parse_table(text)
    assert len(lines) == 2
    assert not hasattr(lines[0], "item_number")
    assert "01003003" not in lines[0].description
    assert lines[0].unit_text == "Numbers"
    assert lines[0].quantity == Decimal("2")
    assert "Long wrapped description" in lines[0].description
    assert "continuation after numeric row" in lines[1].description
    assert lines[1].source_page > lines[0].source_page
    reconciliation = extractor.last_reconciliation
    assert reconciliation["schedule_sections_detected"] == 2
    assert reconciliation["schedule_sections_accounted_for"] == 2
    assert reconciliation["document_coverage_status"] == "COMPLETE"
    assert reconciliation["source_rows_detected"] == 2
    assert reconciliation["extracted_successfully"] == 2
    assert reconciliation["needs_review"] == 0
    assert reconciliation["total_discrepancies"] == 0
    assert reconciliation["complete"] is True


def test_many_native_rows_are_all_accounted_and_partial_rows_block_completeness() -> None:
    rows = "\n".join(
        f"{number}  CODE-{number:02d}  Equipment item {number}  Numbers  2  10.00  20.00"
        for number in range(1, 13)
    )
    text = f"""
    LOA Number: MANY/1
    LOA Date: 18/03/2026
    Name of Work: Multi-row generic fixture
    Contract Value: 240.00
    Item Breakup
    Schedule A-SUPPLY
    Item - 1 EQUIPMENT
    S No. Item No Description of Item Unit Qty Rate Amount

    {rows}

    Total 240.00
    """
    extractor = PdfLoaExtractor()
    extracted = extractor._parse_table(text)
    assert len(extracted) == 12
    assert [line.source_serial for line in extracted] == [str(value) for value in range(1, 13)]
    assert extractor.last_reconciliation["source_rows_detected"] == 12
    assert extractor.last_reconciliation["extracted_successfully"] == 12
    assert extractor.last_reconciliation["complete"] is True

    partial = text.replace(
        "6  CODE-06  Equipment item 6  Numbers  2  10.00  20.00",
        "6  CODE-06  Equipment item 6  Numbers  2  invalid  20.00",
    )
    partial_lines = extractor._parse_table(partial)
    assert len(partial_lines) == 12
    unresolved = [line for line in partial_lines if line.extraction_outcome == "NEEDS_REVIEW"]
    assert [line.source_serial for line in unresolved] == ["6"]
    assert unresolved[0].source_raw_text
    assert extractor.last_reconciliation["source_rows_detected"] == 12
    assert extractor.last_reconciliation["extracted_successfully"] == 11
    assert extractor.last_reconciliation["needs_review"] == 1
    assert extractor.last_reconciliation["complete"] is False


def test_pdf_page_router_uses_ocr_only_for_missing_pages_and_accounts_pages(
    tmp_path, monkeypatch
) -> None:
    native_page = (
        "LOA Number: MIXED/1\nLOA Date: 18/03/2026\n"
        "Name of Work: Mixed source fixture\nContract Value: 20.00\n"
    )

    class NativeResult:
        stdout = f"{native_page}\f\f"

    monkeypatch.setattr(
        "app.services.loa_extraction.subprocess.run", lambda *args, **kwargs: NativeResult()
    )

    class PageOcr:
        requested = None

        def extract_pages(self, _path, pages):
            self.requested = pages
            return {
                2: (
                    "Item Breakup\nSchedule A-SUPPLY\nItem - 1 EQUIPMENT\n"
                    "S No. Item No Description of Item Unit Qty Rate Amount\n\n"
                    "1  CODE-1  Mixed-page equipment  Numbers  2  10.00  20.00\n\n"
                    "Total 20.00"
                )
            }

    source = tmp_path / "mixed.pdf"
    source.write_bytes(b"%PDF-test")
    ocr = PageOcr()
    result = PdfLoaExtractor(ocr=ocr).extract(source)
    assert ocr.requested == [2]
    assert result.method == "MIXED_PDF"
    assert len(result.lines) == 1
    assert result.lines[0].source_page == 2
    assert result.boq_reconciliation["pages_total"] == 2
    assert result.boq_reconciliation["pages_processed"] == 2
    assert result.boq_reconciliation["native_text_pages"] == 1
    assert result.boq_reconciliation["ocr_pages"] == 1


def test_scanned_pdf_uses_shared_pipeline_and_missing_ocr_is_actionable(
    tmp_path, monkeypatch
) -> None:
    class EmptyPages:
        stdout = "\f\f"

    monkeypatch.setattr(
        "app.services.loa_extraction.subprocess.run", lambda *args, **kwargs: EmptyPages()
    )
    source = tmp_path / "scanned.pdf"
    source.write_bytes(b"%PDF-test")

    class ScannedOcr:
        def extract_pages(self, _path, pages):
            assert pages == [1, 2]
            return {
                1: (
                    "LOA Number: OCR/1\nLOA Date: 18/03/2026\n"
                    "Name of Work: OCR fixture\nContract Value: 30.00"
                ),
                2: (
                    "Item Breakup\nSchedule A-SUPPLY\nItem - 1 EQUIPMENT\n"
                    "S No. Item No Description of Item Unit Qty Rate Amount\n\n"
                    "1  OCR-CODE  OCR equipment  Numbers  3  10.00  30.00\n\nTotal 30.00"
                ),
            }

    result = PdfLoaExtractor(ocr=ScannedOcr()).extract(source)
    assert result.method == "OCR"
    assert result.loa_number == "OCR/1"
    assert result.lines[0].source_page == 2
    assert result.lines[0].source_raw_text
    assert result.boq_reconciliation["native_text_pages"] == 0
    assert result.boq_reconciliation["ocr_pages"] == 2

    class MissingOcr:
        def extract_pages(self, _path, _pages):
            raise RuntimeError(
                "Local OCR is unavailable. Install Tesseract and retry extraction; "
                "the original upload has been preserved."
            )

    with pytest.raises(RuntimeError, match="original upload has been preserved"):
        PdfLoaExtractor(ocr=MissingOcr()).extract(source)


async def create_foundation(client: AsyncClient, token: str) -> dict[str, str]:
    party = await client.post(
        "/api/v1/master-data/parties",
        json={
            "code": "SER-CUST",
            "legal_name": "South Eastern Railway",
            "business_scope": "RAILWAY",
            "roles": ["CUSTOMER"],
        },
        headers=auth(token),
    )
    zone = await client.post(
        "/api/v1/master-data/railway-zones",
        json={"code": "SER", "name": "South Eastern Railway"},
        headers=auth(token),
    )
    division = await client.post(
        "/api/v1/master-data/railway-divisions",
        json={
            "code": "ADRA",
            "name": "Adra",
            "zone_id": zone.json()["id"],
            "customer_party_id": party.json()["id"],
        },
        headers=auth(token),
    )
    authority = await client.post(
        "/api/v1/master-data/railway-authorities",
        json={
            "code": "SR-DSTE-ADRA",
            "name": "Sr DSTE Adra",
            "division_id": division.json()["id"],
            "roles": ["CONSIGNEE"],
        },
        headers=auth(token),
    )
    unit = await client.post(
        "/api/v1/master-data/units",
        json={"code": "NOS", "name": "Numbers", "symbol": "Nos"},
        headers=auth(token),
    )
    project = await client.post(
        "/api/v1/projects",
        json={
            "code": "RAIL-P20",
            "name": "Railway Communication Supply",
            "customer_party_id": party.json()["id"],
            "business_scope": "RAILWAY",
            "railway_zone_id": zone.json()["id"],
            "railway_division_id": division.json()["id"],
        },
        headers=auth(token),
    )
    for response in (party, zone, division, authority, unit, project):
        assert response.status_code == 201, response.text
    return {
        "party": party.json()["id"],
        "zone": zone.json()["id"],
        "division": division.json()["id"],
        "authority": authority.json()["id"],
        "unit": unit.json()["id"],
        "project": project.json()["id"],
    }


@pytest.mark.asyncio
async def test_xlsx_import_requires_review_then_creates_authoritative_loa(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    masters = await create_foundation(client, token)
    monkeypatch.setattr(get_settings(), "document_storage_root", tmp_path / "documents")
    source_workbook = railway_loa_workbook()

    uploaded = await client.post(
        "/api/v1/railway-loa-imports",
        files={
            "file": (
                "Railway LOA.xlsx",
                    source_workbook,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth(token),
    )
    assert uploaded.status_code == 201, uploaded.text
    imported = uploaded.json()
    assert imported["status"] == "NEEDS_REVIEW", imported["extraction_error"]
    assert imported["extraction_method"] == "XLSX"
    assert imported["loa_number"] == "LOA/RAIL/20"
    assert imported["railway_division_id"] == masters["division"]
    assert imported["railway_zone_id"] == masters["zone"]
    assert imported["authority_id"] == masters["authority"]
    assert imported["authority_candidates"][0]["master_id"] == masters["authority"]
    assert imported["authority_candidates"][0]["master_status"] == "MATCHED"
    assert imported["issuing_party_id"] == masters["party"]
    assert imported["completion_period"] == "180 days"
    assert imported["completion_date"] == "2027-02-20"
    assert Decimal(imported["lines"][0]["quantity"]) == Decimal("3.0000")
    assert Decimal(imported["lines"][0]["rate"]) == Decimal("823.00")
    assert "installation accessories" in imported["lines"][0]["description"]
    original = tmp_path / "documents" / "loa" / imported["id"] / "original.xlsx"
    assert original.read_bytes() == source_workbook

    second = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("Railway LOA.xlsx", railway_loa_workbook())},
        headers=auth(token),
    )
    assert second.status_code == 201
    second_original = tmp_path / "documents" / "loa" / second.json()["id"] / "original.xlsx"
    assert second.json()["id"] != imported["id"]
    assert second_original.exists()

    premature = await client.post(
        f"/api/v1/railway-loa-imports/{imported['id']}/approve",
        json={},
        headers=auth(token),
    )
    assert premature.status_code == 422

    reviewed = await client.patch(
        f"/api/v1/railway-loa-imports/{imported['id']}",
        json={
            "project_id": masters["project"],
            "railway_zone_id": masters["zone"],
            "railway_division_id": masters["division"],
            "issuing_party_id": masters["party"],
            "lines": [
                {
                    **imported["lines"][0],
                    "unit_id": masters["unit"],
                    "id": None,
                }
            ],
        },
        headers=auth(token),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "READY_FOR_APPROVAL"

    approved = await client.post(
        f"/api/v1/railway-loa-imports/{imported['id']}/approve",
        json={},
        headers=auth(token),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    loa_id = approved.json()["loa_id"]
    loa = await client.get(f"/api/v1/loas/{loa_id}", headers=auth(token))
    assert loa.status_code == 200
    assert loa.json()["loa_number"] == "LOA/RAIL/20"
    items = await client.get(f"/api/v1/loas/{loa_id}/items", headers=auth(token))
    assert items.status_code == 200
    assert items.json()[0]["original_line_value"] == "2469.00"

    async with client._session_factory() as session:
        from sqlalchemy import func, select

        from app.models.auth import AuditLog

        audit_count = await session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.entity_type == "railway_loa_import")
        )
        assert audit_count >= 4


@pytest.mark.asyncio
async def test_registration_preserves_unmapped_contractual_uom_and_source_provenance(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    masters = await create_foundation(client, token)
    monkeypatch.setattr(get_settings(), "document_storage_root", tmp_path / "documents")
    uploaded = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("unmapped-uom.xlsx", railway_loa_workbook(unit="Pair"))},
        headers=auth(token),
    )
    assert uploaded.status_code == 201, uploaded.text
    imported = uploaded.json()
    assert imported["lines"][0]["unit_text"] == "Pair"
    assert imported["lines"][0]["unit_id"] is None
    assert imported["lines"][0]["product_id"] is None
    assert imported["boq_readiness_issues"] == []
    source_before = imported["lines"][0]["source_raw_text"]

    reviewed = await client.patch(
        f"/api/v1/railway-loa-imports/{imported['id']}",
        json={"project_id": masters["project"]},
        headers=auth(token),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "READY_FOR_APPROVAL"
    assert reviewed.json()["boq_readiness_issues"] == []

    approved = await client.post(
        f"/api/v1/railway-loa-imports/{imported['id']}/approve",
        json={},
        headers=auth(token),
    )
    assert approved.status_code == 200, approved.text
    items = await client.get(
        f"/api/v1/loas/{approved.json()['loa_id']}/items", headers=auth(token)
    )
    item = items.json()[0]
    assert item["product_id"] is None
    assert item["unit_id"] is None
    assert item["unit_text"] == "Pair"
    assert item["source_raw_text"] == source_before
    assert item["source_serial"] == imported["lines"][0]["source_serial"]


@pytest.mark.asyncio
async def test_import_validation_access_and_failure_preserve_safe_source(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "document_storage_root", tmp_path / "documents")
    token = await login(client, "admin@example.com", "admin-user-password")
    assert (await client.get("/api/v1/railway-loa-imports")).status_code == 401

    unsafe = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("../loa.xlsx", railway_loa_workbook())},
        headers=auth(token),
    )
    assert unsafe.status_code == 422
    invalid = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("loa.pdf", b"not a pdf", "application/pdf")},
        headers=auth(token),
    )
    assert invalid.status_code == 415

    failed = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("scan.pdf", b"%PDF-1.4\ninvalid body", "application/pdf")},
        headers=auth(token),
    )
    assert failed.status_code == 201
    assert failed.json()["status"] == "EXTRACTION_FAILED"
    saved_source = tmp_path / "documents" / "loa" / failed.json()["id"] / "original.pdf"
    assert saved_source.exists()
    retried = await client.post(
        f"/api/v1/railway-loa-imports/{failed.json()['id']}/retry", headers=auth(token)
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "EXTRACTION_FAILED"
    assert saved_source.exists()

    monkeypatch.setattr(settings, "loa_upload_max_bytes", 10)
    oversized = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("loa.xlsx", railway_loa_workbook())},
        headers=auth(token),
    )
    assert oversized.status_code == 413


@pytest.mark.asyncio
async def test_duplicate_import_requires_explicit_confirmation(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    masters = await create_foundation(client, token)
    monkeypatch.setattr(get_settings(), "document_storage_root", tmp_path / "documents")
    existing = await client.post(
        "/api/v1/loas",
        json={
            "project_id": masters["project"],
            "loa_number": "LOA/DUPLICATE",
            "loa_date": "2026-08-24",
            "railway_division_id": masters["division"],
            "description": "Existing contract",
            "original_contract_value": "2469.00",
        },
        headers=auth(token),
    )
    assert existing.status_code == 201
    uploaded = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("duplicate.xlsx", railway_loa_workbook(loa_number="LOA/DUPLICATE"))},
        headers=auth(token),
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["duplicate_candidates"]


@pytest.mark.asyncio
async def test_unknown_division_is_retained_for_review_without_creating_master(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    await create_foundation(client, token)
    monkeypatch.setattr(get_settings(), "document_storage_root", tmp_path / "documents")
    before = await client.get("/api/v1/master-data/railway-divisions", headers=auth(token))
    uploaded = await client.post(
        "/api/v1/railway-loa-imports",
        files={
            "file": (
                "unknown-division.xlsx",
                railway_loa_workbook(division="Imaginary Division"),
            )
        },
        headers=auth(token),
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["extracted_division_text"] == "Imaginary"
    assert uploaded.json()["railway_division_id"] is None
    assert uploaded.json()["status"] == "NEEDS_REVIEW"
    after = await client.get("/api/v1/master-data/railway-divisions", headers=auth(token))
    assert after.json()["total"] == before.json()["total"]


@pytest.mark.asyncio
async def test_railway_customer_mapping_validates_persists_and_is_reused(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    masters = await create_foundation(client, token)
    monkeypatch.setattr(get_settings(), "document_storage_root", tmp_path / "documents")
    cleared = await client.patch(
        f"/api/v1/master-data/railway-divisions/{masters['division']}",
        json={"customer_party_id": None},
        headers=auth(token),
    )
    assert cleared.status_code == 200
    vendor = await client.post(
        "/api/v1/master-data/parties",
        json={"code": "ONLY-VENDOR", "legal_name": "Vendor Only", "roles": ["VENDOR"]},
        headers=auth(token),
    )
    assert vendor.status_code == 201
    first = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("first.xlsx", railway_loa_workbook())},
        headers=auth(token),
    )
    assert first.status_code == 201
    assert first.json()["issuing_party_id"] is None
    invalid = await client.post(
        f"/api/v1/railway-loa-imports/{first.json()['id']}/customer-mapping",
        json={"customer_party_id": vendor.json()["id"]},
        headers=auth(token),
    )
    assert invalid.status_code == 422
    mapped = await client.post(
        f"/api/v1/railway-loa-imports/{first.json()['id']}/customer-mapping",
        json={"customer_party_id": masters["party"]},
        headers=auth(token),
    )
    assert mapped.status_code == 200
    assert mapped.json()["issuing_party_id"] == masters["party"]
    refreshed = await client.get(
        f"/api/v1/railway-loa-imports/{first.json()['id']}", headers=auth(token)
    )
    assert refreshed.json()["issuing_party_id"] == masters["party"]
    second = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("second.xlsx", railway_loa_workbook(loa_number="LOA/RAIL/21"))},
        headers=auth(token),
    )
    assert second.status_code == 201
    assert second.json()["issuing_party_id"] == masters["party"]


@pytest.mark.asyncio
async def test_railway_project_and_import_readiness_do_not_require_customer_party(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    token = await login(client, "admin@example.com", "admin-user-password")
    masters = await create_foundation(client, token)
    cleared = await client.patch(
        f"/api/v1/master-data/railway-divisions/{masters['division']}",
        json={"customer_party_id": None},
        headers=auth(token),
    )
    assert cleared.status_code == 200, cleared.text
    inactive_authority = await client.patch(
        f"/api/v1/master-data/railway-authorities/{masters['authority']}/active?active=false",
        headers=auth(token),
    )
    assert inactive_authority.status_code == 200
    project = await client.post(
        "/api/v1/projects",
        json={
            "code": "RAIL-NO-CUSTOMER",
            "name": "Railway domain-only project",
            "customer_party_id": None,
            "business_scope": "RAILWAY",
            "railway_zone_id": masters["zone"],
            "railway_division_id": masters["division"],
        },
        headers=auth(token),
    )
    assert project.status_code == 201, project.text
    assert project.json()["customer_party_id"] is None
    non_railway = await client.post(
        "/api/v1/projects",
        json={
            "code": "NON-RAIL-NO-CUSTOMER",
            "name": "Commercial project without customer",
            "customer_party_id": None,
            "business_scope": "NON_RAILWAY",
        },
        headers=auth(token),
    )
    assert non_railway.status_code == 422
    assert non_railway.json()["error"]["code"] == "customer_required"
    monkeypatch.setattr(get_settings(), "document_storage_root", tmp_path / "documents")
    uploaded = await client.post(
        "/api/v1/railway-loa-imports",
        files={"file": ("Railway LOA.xlsx", railway_loa_workbook())},
        headers=auth(token),
    )
    assert uploaded.status_code == 201, uploaded.text
    imported = uploaded.json()
    assert imported["issuing_party_id"] is None
    assert imported["authority_id"] is None
    assert imported["authority_candidates"][0]["master_status"] == "NOT_CONFIGURED"
    configured_authority = await client.post(
        "/api/v1/master-data/railway-authorities",
        json={
            "code": "NEW-CONSIGNEE",
            "name": "New Consignee",
            "designation": "Sr.DSTE/Adra",
            "division_id": masters["division"],
            "roles": ["CONSIGNEE"],
        },
        headers=auth(token),
    )
    assert configured_authority.status_code == 201, configured_authority.text
    resolved = await client.post(
        f"/api/v1/railway-loa-imports/{imported['id']}/resolve-masters",
        headers=auth(token),
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["authority_id"] == configured_authority.json()["id"]
    assert resolved.json()["authority_candidates"][0]["master_status"] == "MATCHED"
    assert resolved.json()["authority_candidates"][0]["text"] == "Sr DSTE Adra"
    assert resolved.json()["boq_reconciliation"] == imported["boq_reconciliation"]
    persisted = await client.get(
        f"/api/v1/railway-loa-imports/{imported['id']}", headers=auth(token)
    )
    assert persisted.json()["authority_candidates"][0]["master_status"] == "MATCHED"
    repeated = await client.post(
        f"/api/v1/railway-loa-imports/{imported['id']}/resolve-masters",
        headers=auth(token),
    )
    assert repeated.status_code == 200
    assert repeated.json()["authority_candidates"] == persisted.json()["authority_candidates"]
    assert repeated.json()["lines"] == persisted.json()["lines"]
    other_zone = await client.post(
        "/api/v1/master-data/railway-zones",
        json={"code": "OTHER", "name": "Other Railway"},
        headers=auth(token),
    )
    other_division = await client.post(
        "/api/v1/master-data/railway-divisions",
        json={"code": "OTHER", "name": "Other", "zone_id": other_zone.json()["id"]},
        headers=auth(token),
    )
    incompatible = await client.patch(
        f"/api/v1/railway-loa-imports/{imported['id']}",
        json={"railway_division_id": other_division.json()["id"]},
        headers=auth(token),
    )
    assert incompatible.status_code == 422
    assert incompatible.json()["error"]["code"] == "railway_hierarchy_mismatch"
    reviewed = await client.patch(
        f"/api/v1/railway-loa-imports/{imported['id']}",
        json={
            "project_id": project.json()["id"],
            "lines": [{**imported["lines"][0], "unit_id": masters["unit"], "id": None}],
        },
        headers=auth(token),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "READY_FOR_APPROVAL"


def test_master_match_requires_one_unambiguous_normalized_result() -> None:
    from types import SimpleNamespace

    records = [
        SimpleNamespace(code="ARZ", name="Arbitrary Railway", aliases=["AR Railway"]),
        SimpleNamespace(code="BRZ", name="Branch Railway", aliases=["BR Railway"]),
    ]
    assert RailwayLoaImportService._match("AR Railway", records, "code", "name") is records[0]
    assert RailwayLoaImportService._match("Railway", records, "code", "name") is None
    assert RailwayLoaImportService._match("Unknown Railway", records, "code", "name") is None


def test_authority_resolution_is_role_division_active_alias_and_ambiguity_safe() -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    division_id = uuid4()
    other_division_id = uuid4()

    def authority(*, code, roles, division=division_id, active=True, aliases=None):
        return SimpleNamespace(
            id=uuid4(), code=code, name=code, designation=code,
            aliases=aliases or [], division_id=division, is_active=active,
            roles=[SimpleNamespace(role=role) for role in roles],
        )

    def resolve(candidate, authorities):
        zone_id = uuid4()
        record = SimpleNamespace(
            extracted_zone_text="Eastern", extracted_division_text="Alpha",
            railway_zone_id=None, railway_division_id=None, authority_id=None,
            authority_candidates=[candidate],
        )
        division = SimpleNamespace(
            id=division_id, zone_id=zone_id, code="ALPHA", name="Alpha Division", aliases=[]
        )
        zone = SimpleNamespace(id=zone_id, code="ER", name="Eastern Railway", aliases=[])
        service = object.__new__(RailwayLoaImportService)
        service._resolve_railway_masters(record, [division], [zone], authorities)
        return record.authority_candidates[0]

    base = {"text": "Senior Signal Store", "role": "CONSIGNEE", "source": "clause"}
    alias_match = authority(code="STORE-1", roles=["CONSIGNEE"], aliases=["Senior Signal Store"])
    assert resolve(base, [alias_match])["master_status"] == "MATCHED"
    wrong_role = authority(code="Senior Signal Store", roles=["ISSUING_AUTHORITY"])
    assert "do not support" in resolve(base, [wrong_role])["master_detail"]
    wrong_division = authority(
        code="Senior Signal Store", roles=["CONSIGNEE"], division=other_division_id
    )
    assert "another Railway Division" in resolve(base, [wrong_division])["master_detail"]
    inactive = authority(code="Senior Signal Store", roles=["CONSIGNEE"], active=False)
    assert "inactive" in resolve(base, [inactive])["master_detail"]
    duplicate = authority(code="STORE-2", roles=["CONSIGNEE"], aliases=["Senior Signal Store"])
    assert resolve(base, [alias_match, duplicate])["master_status"] == "AMBIGUOUS"


def test_boq_readiness_uses_contractual_fields_not_optional_master_mapping() -> None:
    from types import SimpleNamespace

    reconciliation = {
        "document_coverage_status": "COMPLETE",
        "complete": True,
        "total_discrepancies": 0,
    }

    def record(**line_changes):
        line = SimpleNamespace(
            line_number=1,
            source_serial="1",
            extraction_outcome="EXTRACTED",
            description="Contractual equipment",
            unit_text="Pair",
            unit_id=None,
            product_id=None,
            quantity=Decimal("2"),
            rate=Decimal("50"),
            amount=Decimal("100"),
        )
        for key, value in line_changes.items():
            setattr(line, key, value)
        return SimpleNamespace(lines=[line], boq_reconciliation=dict(reconciliation))

    assert RailwayLoaImportService.boq_readiness_issues(record()) == []
    unresolved_serial = RailwayLoaImportService.boq_readiness_issues(
        record(source_serial=None)
    )
    assert unresolved_serial[0]["field"] == "Sn. No."
    assert "unresolved Sn. No." in unresolved_serial[0]["message"]
    missing = RailwayLoaImportService.boq_readiness_issues(record(description=None))
    assert missing == [
        {
            "scope": "LINE",
            "line_number": 1,
            "field": "description",
            "message": "Unresolved schedule - Sn. 1: description is required.",
        }
    ]
    unresolved = RailwayLoaImportService.boq_readiness_issues(
        record(extraction_outcome="NEEDS_REVIEW")
    )
    assert unresolved[0]["field"] == "outcome"
    rejected = RailwayLoaImportService.boq_readiness_issues(
        record(extraction_outcome="REJECTED_WITH_REASON")
    )
    assert rejected[0]["field"] == "outcome"
    discrepant = record()
    discrepant.boq_reconciliation["total_discrepancies"] = 1
    assert any(
        issue["field"] == "totals"
        for issue in RailwayLoaImportService.boq_readiness_issues(discrepant)
    )
