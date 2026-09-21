"""Regression tests for manufacture/best-before date defects found in production.

Live Tesseract scan of a basundi-mix label extracted mfg_date_str='2.39' (35%
confidence) from a nutrition-table decimal, which the rule engine turned into
a "Feb 2039 is in the future" NON_COMPLIANT violation. Guards:
- dot-separated numbers are never extracted as numeric dates;
- a date read below the confidence threshold routes to manual review, never
  to a future-date or unreadable-value violation;
- keyword-anchored dates with / and - separators still extract correctly.
"""

import pytest

from app.models.scan import Verdict
from app.services.field_extractors import extract_fields_from_ocr
from app.services.rule_engine import evaluate_product_compliance
from app.rule_checkers.rule_6_declarations import check_mfg_date_declaration


class FakeOCRItem:
    def __init__(self, text: str, confidence: float = 0.95, bbox: list | None = None):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox


def make_items(lines, confidence: float = 0.95):
    items = []
    for index, line in enumerate(lines):
        top = 40.0 * index
        items.append(FakeOCRItem(
            line, confidence,
            [[20.0, top], [600.0, top], [600.0, top + 24.0], [20.0, top + 24.0]],
        ))
    return items


def extract(lines, confidence: float = 0.95):
    return extract_fields_from_ocr(make_items(lines, confidence)).to_dict()


# ------------------------------------------------------------extractor
def test_nutrition_decimal_is_not_extracted_as_mfg_date():
    """'2.39' (a nutrition value) must never become a Feb-2039 manufacture date."""
    fields = extract([
        "BUTTERFLY Basundi Mix",
        "Nutririon Facis Per 100gm",
        "Energy 2.39 kcal Total Fat 1.42g",
        "Protein6.53g",
    ])
    assert "mfg_date_str" not in fields


def test_slash_separated_keyword_date_is_extracted():
    fields = extract(["Basundi Mix", "MFG 05/2026", "Net Wt. 500 g"])
    assert fields.get("mfg_date_str", {}).get("value") == "05/2026"


def test_hyphen_separated_keyword_date_is_extracted():
    fields = extract(["Basundi Mix", "MFD 05-2026"])
    assert fields.get("mfg_date_str", {}).get("value") == "05-2026"


def test_bare_slash_date_fallback_still_works():
    fields = extract(["Basundi Mix", "05/2026"])
    assert fields.get("mfg_date_str", {}).get("value") == "05/2026"


def test_barcode_digits_are_not_dates():
    fields = extract(["Basundi Mix", "81906028800030", "Customer Care No Ph:(02691) 252922"])
    assert "mfg_date_str" not in fields


# ------------------------------------------------------------rule checker
def test_low_confidence_date_read_does_not_produce_future_date_violation():
    """The exact production failure: '2.39' at 35% confidence."""
    result = check_mfg_date_declaration(
        date_str="2.39", category="food", confidence=0.35
    )
    assert result.status == Verdict.NEEDS_REVIEW
    assert "future" not in result.message_en.lower()


def test_low_confidence_date_does_not_block_food_compliance():
    result = check_mfg_date_declaration(
        date_str="2.39", category="food", confidence=0.35
    )
    assert result.status == Verdict.NEEDS_REVIEW


def test_high_confidence_future_date_still_violates():
    """Positive evidence is unaffected: a confident future date is a violation."""
    result = check_mfg_date_declaration(
        date_str="05/2099", category="other", confidence=0.95
    )
    assert result.status == Verdict.NON_COMPLIANT
    assert "future" in result.message_en.lower()


def test_high_confidence_readable_date_on_food_is_compliant():
    result = check_mfg_date_declaration(
        date_str="01/2026", category="food", confidence=0.95
    )
    assert result.status == Verdict.COMPLIANT


# --------------------------------------------------------end-to-end engine
def test_value_first_exp_date_layout_is_extracted():
    """Real panel layout: date printed LEFT of the keyword (':01-01-2027 Exp.Date').
    The old forward-only regex required a value after the keyword, so the expiry
    date was silently dropped from this layout."""
    fields = extract([
        ": J-10 Batch No.",
        ":02-01-2026 Mfg. Date",
        "\uff1a01-01-2027 Exp.Date",
        "\uff1a80.00/ (0.80/g) MRP/USP",
    ])
    assert fields.get("mfg_date_str", {}).get("value") == "02-01-2026"
    assert fields.get("best_before", {}).get("value") == "01-01-2027"


def test_stacked_best_before_layout_is_extracted():
    """Keyword alone on one line, date on the next."""
    fields = extract([
        "Basundi Mix",
        "Best Before:",
        "01/2027",
    ])
    assert fields.get("best_before", {}).get("value") == "01/2027"


def test_stacked_exp_date_layout_is_extracted():
    """Exp keyword alone, value on the next line (fullwidth colon normalized)."""
    fields = extract([
        "Mfg. Date",
        ":02-01-2026",
        "Exp.Date",
        "\uff1a01-01-2027",
    ]
    )
    assert fields.get("mfg_date_str", {}).get("value") == "02-01-2026"
    assert fields.get("best_before", {}).get("value") == "01-01-2027"


def test_exp_keyword_with_prose_after_is_rejected():
    """An 'Exp.' with no date-shaped value must stay missing (NEEDS_REVIEW),
    never store prose as the expiry date."""
    fields = extract([
        "Basundi Mix",
        "Exp.Date maiemoe eicosuse ful oeam mi",
    ])
    assert "best_before" not in fields


def test_garbled_low_confidence_date_yields_needs_review_not_violation():
    """Full pipeline on the live Tesseract output shape."""
    lines = [
        "'ay [a SF. BUTTERFL*) ( 4",
        "Nutririon Facis Per 100gm DIRECTIONS",
        "Energy 2.39 kcal Total Fat 1.42g",
        "grAA fssai Lic.No.10717012000120",
        "e-mail:paikynj@gmail.comD 81906028800030 Customer Care No Ph:(02691) 252922",
    ]
    captured = extract_fields_from_ocr(make_items(lines, confidence=0.55))
    result = evaluate_product_compliance(
        extracted_data=captured.to_dict(), category="food", package_type="retail"
    )
    # No violation may cite a manufactured future date.
    future_violations = [v for v in result.violations if "future" in v.message_en.lower()]
    assert future_violations == []
    assert result.verdict in (Verdict.NEEDS_REVIEW, Verdict.NON_COMPLIANT)
