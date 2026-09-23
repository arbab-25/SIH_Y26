"""Field-extractor tests using OCR text captured from a real packaged-food label.

`BUTTERFLY_LABEL_LINES` is the visual line reconstruction produced by RapidOCR for
`assets/test 1.jpeg` (a Basundi-mix back panel). It is kept verbatim, including its
OCR damage, because every bug guarded below was found by running the real pipeline
rather than by inventing input:

1. the consumer-care phone regex matched "Lic.No.10717012000120" and stored an FSSAI
   licence number as the telephone number, which then passed the Rule 6(2) check;
2. the e-mail captured the character OCR glued to the end ("...gmail.comD");
3. the manufacturer address swallowed the consumer-care line printed below it;
4. "Per 100gm" from the nutrition table became the declared net quantity.
"""


from app.models.scan import Verdict
from app.services.field_extractors import extract_fields_from_ocr
from app.services.rule_engine import evaluate_product_compliance


class FakeOCRItem:
    """Minimal stand-in for OCRItem with the attributes the extractor reads."""

    def __init__(self, text: str, confidence: float = 0.95, bbox: list | None = None):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox


def make_items(lines, confidence: float = 0.95):
    """One OCR item per visual line, with polygon boxes like the real engine."""
    items = []
    for index, line in enumerate(lines):
        top = 40.0 * index
        items.append(FakeOCRItem(
            line,
            confidence,
            [[20.0, top], [600.0, top], [600.0, top + 24.0], [20.0, top + 24.0]],
        ))
    return items


def extract(lines, confidence: float = 0.95):
    return extract_fields_from_ocr(make_items(lines, confidence)).to_dict()


# Verbatim RapidOCR line reconstruction of assets/test 1.jpeg (back panel).
BUTTERFLY_LABEL_LINES = [
    "BUTTERFLY",
    "sta",
    "M",
    "Nutririon Facis Per 100gm DIRECTIONS",
    "39i.7 Add BUTTERFLYBasundiMixPowder slowly to 1/2 lit.of boiling",
    "Total Fat 1.42g ready to serve.",
    "Protein6.53g",
    "grAA fssai",
    "Lic.No.10717012000120",
    "MAKE ININDU Manufactured by PAPER ART INDUSTRIES",
    "296-297Mohmedpura.Kapadwanj-387620",
    "e-mail:paikynj@gmail.comD 81906028800030 Customer Care No Ph:(02691) 252922",
]


# ----------------------------------------------------------------------
# Real-label regressions
# ----------------------------------------------------------------------
def test_fssai_licence_number_is_not_stored_as_consumer_care_phone():
    fields = extract(BUTTERFLY_LABEL_LINES)
    phone = fields.get("consumer_care_phone", {}).get("value")
    assert phone != "10717012000120"
    assert "10717012000120" not in str(phone or "")


def test_real_label_consumer_care_phone_is_the_printed_number():
    fields = extract(BUTTERFLY_LABEL_LINES)
    phone = fields.get("consumer_care_phone", {}).get("value")
    assert phone is not None
    assert "252922" in phone


def test_real_label_email_is_not_trimmed_into_and_out_of_the_address():
    fields = extract(BUTTERFLY_LABEL_LINES)
    assert fields.get("consumer_care_email", {}).get("value") == "paikynj@gmail.com"


def test_real_label_address_is_the_street_line_not_the_care_line():
    fields = extract(BUTTERFLY_LABEL_LINES)
    address = fields.get("manufacturer_address", {}).get("value")
    assert address == "296-297Mohmedpura.Kapadwanj-387620"
    assert "e-mail" not in address.lower()
    assert "Customer Care" not in address


def test_real_label_manufacturer_name_and_pin_code():
    fields = extract(BUTTERFLY_LABEL_LINES)
    assert fields.get("manufacturer_name", {}).get("value") == "PAPER ART INDUSTRIES"
    assert fields.get("pin_code", {}).get("value") == "387620"
    assert fields.get("fssai_number", {}).get("value") == "10717012000120"


def test_nutrition_reference_is_not_taken_as_the_net_quantity():
    fields = extract(BUTTERFLY_LABEL_LINES)
    assert "net_quantity_value" not in fields
    assert "net_quantity_unit" not in fields


def test_unreadable_origin_fragment_is_not_recorded():
    # "MAKE ININDU" is OCR damage for "MADE IN INDIA"; storing "ININDU Manufactured
    # by PAPER ART INDUSTRIES" as a country would put a fragment on the report.
    fields = extract(BUTTERFLY_LABEL_LINES)
    assert "country_of_origin" not in fields


def test_real_back_panel_verdict_is_manual_review_not_a_guessed_verdict():
    """MRP, month of manufacture and best before are absent from this panel."""
    captured = extract_fields_from_ocr(make_items(BUTTERFLY_LABEL_LINES))
    result = evaluate_product_compliance(
        extracted_data=captured.to_dict(), category="food", package_type="retail"
    )
    assert result.verdict == Verdict.NEEDS_REVIEW
    assert result.violations == []
    needs_review = {r.field for r in result.results if r.status == Verdict.NEEDS_REVIEW}
    assert {"mrp", "mfg_date", "best_before"}.issubset(needs_review)


# ----------------------------------------------------------------------
# Net quantity declarations
# ----------------------------------------------------------------------
def test_net_weight_declaration_is_extracted():
    fields = extract(["BUTTERFLY Basundi Mix", "Net Wt. 500 g"])
    assert fields.get("net_quantity_value", {}).get("value") == 500.0
    assert fields.get("net_quantity_unit", {}).get("value") == "g"


def test_net_quantity_declaration_is_extracted():
    fields = extract(["Basundi Mix", "Net Quantity: 200 gm"])
    assert fields.get("net_quantity_value", {}).get("value") == 200.0


def test_net_quantity_after_the_number_is_extracted():
    fields = extract(["Basundi Mix", "500 g NET"])
    assert fields.get("net_quantity_value", {}).get("value") == 500.0


def test_per_serving_reference_is_not_extracted_as_net_quantity():
    fields = extract(["Basundi Mix", "Nutritional Information per 100gm", "Energy 391 kcal"])
    assert "net_quantity_value" not in fields


def test_nutrition_table_weights_are_not_extracted_as_net_quantity():
    fields = extract(["Total Fat 1.42g", "Total Carbohydrate 88.38g", "Protein 6.53g"])
    assert "net_quantity_value" not in fields


# ----------------------------------------------------------------------
# Consumer-care contact details
# ----------------------------------------------------------------------
def test_lying_consumer_care_label_case_is_case_insensitive():
    fields = extract(["ACME Ltd", "CUSTOMER CARE NO: 1800-425-4449"])
    phone = fields.get("consumer_care_phone", {}).get("value")
    assert phone is not None
    assert "1800" in phone


def test_short_number_after_tel_is_rejected():
    # "tel you how much" is OCR for "tell you ..." and is followed by "2000".
    fields = extract(["The %Daily Value tells you how much a nutrient in 2000 calories contributes"])
    assert "consumer_care_phone" not in fields


def test_fourteen_digit_licence_run_is_never_a_phone_number():
    fields = extract(["Ph: 10717012000120"])
    assert "consumer_care_phone" not in fields


def test_std_code_phone_with_spaces_is_extracted():
    fields = extract(["ACME Ltd", "Ph: (02691) 252922"])
    phone = fields.get("consumer_care_phone", {}).get("value")
    assert phone is not None
    assert "02691" in phone


def test_registered_email_is_kept_intact():
    fields = extract(["ACME Ltd", "care@acme.co.in"])
    assert fields.get("consumer_care_email", {}).get("value") == "care@acme.co.in"


# ----------------------------------------------------------------------
# Maximum retail price
# ----------------------------------------------------------------------
def test_mrp_with_tax_qualification_is_extracted():
    fields = extract(["Basundi Mix", "MRP Rs. 250.00 incl. of all taxes"])
    assert fields.get("mrp", {}).get("value") == 250.0
    assert fields.get("mrp_inclusive_taxes", {}).get("value") is True


def test_lowercase_currency_prefix_is_extracted():
    fields = extract(["Basundi Mix", "rs. 99.50 (incl. of all taxes)"])
    assert fields.get("mrp", {}).get("value") == 99.5


def test_nutrition_sugar_weight_is_not_read_as_mrp():
    # "Total Sugars 71.9g": the previous fallback pattern could read "rs 71.9" as MRP.
    fields = extract(["Total Sugars 71.9g 143%", "Total Carbonydrate 88.38g"])
    assert "mrp" not in fields


def test_mrp_absent_from_the_panel_is_not_invented():
    fields = extract(BUTTERFLY_LABEL_LINES)
    assert "mrp" not in fields


# ----------------------------------------------------------------------
# Rule 12(6) vague quantity words
# ----------------------------------------------------------------------
def test_vague_word_before_a_quantity_is_flagged():
    fields = extract(["Basundi Mix", "Net Wt. about 500 g"])
    assert fields.get("vague_quantity_found", {}).get("value", "").lower() == "about"


def test_vague_word_in_unrelated_prose_is_not_flagged():
    fields = extract([
        "About this pack: read the instructions before use.",
        "Average values per serving are indicative only.",
    ])
    assert "vague_quantity_found" not in fields


def test_minimum_without_a_quantity_is_not_flagged():
    fields = extract(["Store below minimum 25 C", "Best before 24 months"])
    assert "vague_quantity_found" not in fields


# ----------------------------------------------------------------------
# Manufacturer name and address block
# ----------------------------------------------------------------------
def test_address_stops_at_the_consumer_care_line():
    fields = extract([
        "Marketed by ACME Foods Pvt Ltd",
        "12 MG Road, Pune 411001",
        "Customer Care No 1800 123 4567",
    ])
    address = fields.get("manufacturer_address", {}).get("value")
    assert address == "12 MG Road, Pune 411001"
    assert fields.get("manufacturer_name", {}).get("value") == "ACME Foods Pvt Ltd"


def test_name_on_following_line_keeps_address_on_the_line_after_it():
    fields = extract([
        "Manufactured by",
        "ACME Foods Pvt Ltd",
        "12 MG Road, Pune 411001",
        "Net Wt. 500 g",
    ])
    assert fields.get("manufacturer_name", {}).get("value") == "ACME Foods Pvt Ltd"
    assert fields.get("manufacturer_address", {}).get("value") == "12 MG Road, Pune 411001"


# ----------------------------------------------------------------------
# Country of origin
# ----------------------------------------------------------------------
def test_made_in_country_is_extracted():
    fields = extract(["Delicious Pasta", "Made in Italy"])
    assert fields.get("country_of_origin", {}).get("value") == "Italy"


def test_product_of_country_is_extracted():
    fields = extract(["Delicious Pasta", "Product of India"])
    assert fields.get("country_of_origin", {}).get("value") == "India"


def test_origin_running_into_the_next_declaration_is_trimmed():
    fields = extract(["Made in Italy Net Wt. 500 g"])
    assert fields.get("country_of_origin", {}).get("value") == "Italy"


# ----------------------------------------------------------------------
# Extractor -> rule engine, on a readable and compliant label
# ----------------------------------------------------------------------
COMPLIANT_LABEL_LINES = [
    "BUTTERFLY Basundi Mix",
    "INGREDIENTS: Sugar, Milk Powder, Cardamom",
    "Nutritional Information per 100gm: Energy 391 kcal, Protein 6.53g",
    "Net Wt. 500 g",
    "MRP Rs. 250.00 incl. of all taxes",
    "Mfd: 01/2026",
    "Best Before: 24 months from packaging",
    "Lic.No.10717012000120",
    "Marketed by ACME Foods Pvt Ltd",
    "12 MG Road, Pune 411001",
    "Customer Care: 1800-425-4449",
]


def test_compliant_label_passes_every_checker():
    captured = extract_fields_from_ocr(make_items(COMPLIANT_LABEL_LINES))
    result = evaluate_product_compliance(
        extracted_data=captured.to_dict(),
        category="food",
        package_type="retail",
        pdp_height_cm=10.0,
        pdp_width_cm=5.0,
        measured_glyph_height_mm=2.0,
    )

    needs_review = [r.field for r in result.results if r.status == Verdict.NEEDS_REVIEW]
    assert needs_review == []
    assert result.violations == []
    assert result.verdict == Verdict.COMPLIANT
    assert result.compliance_score == 100.0
