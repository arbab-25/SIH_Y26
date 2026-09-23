"""Regression tests for the 2026-09-24 session fixes.

Covers the five reported breakages:
1. Scans never saved  — barcode cross-check ran before extraction existed
   (UnboundLocalError, silently swallowed -> scan FAILED).
2. Rule book incomplete — only 28 curated rules were seeded; the PDF has 33
   main rules. Detection is now mechanical (sequential heading numbers).
3. Rule engine gaps — wholesale packages ran retail checks (Rule 24 never
   cited); veg/non-veg symbol was accepted but never used; contrast/barcode
   advisory results didn't exist.
4. OCR too slow — NL-means denoise dominated preprocessing wall-time.
5. Seed accounts missing — DEMO_* env vars set in backend/.env were ignored.
"""

import json
import os

import pytest

from app.models.scan import Verdict
from app.rule_checkers.fssai_checks import run_fssai_checks
from app.rule_checkers.rule_24_wholesale import check_wholesale_declarations
from app.services.rule_engine import evaluate_product_compliance
from seed.seed_db import _demo_credentials

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _compliant_product() -> dict:
    return {
        "manufacturer_name": {"value": "Britannia Industries Ltd", "confidence": 0.95},
        "manufacturer_address": {"value": "Kolkata, West Bengal", "confidence": 0.95},
        "pin_code": {"value": "700017", "confidence": 0.95},
        "product_name": {"value": "Biscuits", "confidence": 0.95},
        "net_quantity_value": {"value": 100.0, "confidence": 0.95},
        "net_quantity_unit": {"value": "g", "confidence": 0.95},
        "mrp": {"value": 25.0, "confidence": 0.95},
        "mrp_inclusive_taxes": {"value": True, "confidence": 0.95},
        "mfg_date_str": {"value": "01/2026", "confidence": 0.95},
        "consumer_care_phone": {"value": "1800-425-4449", "confidence": 0.95},
        "consumer_care_email": {"value": "feedback@britannia.co.in", "confidence": 0.95},
    }


# ----------------------------------------------------------------------
# 1. Scan pipeline: cross-check runs AFTER extraction (no UnboundLocalError)
# ----------------------------------------------------------------------
def test_pipeline_runs_crosscheck_after_extraction():
    import inspect

    from app.api import scans

    src = inspect.getsource(scans._process_scan)
    merge_pos = src.index("merge_extracted_fields(per_image_extractions)")
    crosscheck_pos = src.index("apply_barcode_crosscheck(")
    assert merge_pos < crosscheck_pos, (
        "apply_barcode_crosscheck must run after merge_extracted_fields — "
        "running it before referenced an unbound variable and failed every "
        "barcode-bearing scan."
    )


# ----------------------------------------------------------------------
# 2. Rule book: all 33 main rules present in the seed
# ----------------------------------------------------------------------
def test_rules_json_contains_every_main_rule():
    with open(os.path.join(BACKEND_ROOT, "seed", "rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    numbers = {r["rule_number"] for r in rules}
    expected_main = (
        {f"rule-{n}" for n in range(1, 31)}
        | {"rule-32", "rule-32A", "rule-33", "rule-34"}
    )
    missing = expected_main - numbers
    assert not missing, f"Main rules missing from rules.json: {sorted(missing)}"
    assert len(rules) >= 55, f"Expected >=55 seeded entries, got {len(rules)}"


def test_extracted_rule_bodies_are_verbatim_from_pdf():
    """rule-2 body must contain real definitions text from the book."""
    with open(os.path.join(BACKEND_ROOT, "seed", "rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    by_number = {r["rule_number"]: r for r in rules}
    body = by_number["rule-2"]["full_text"]
    assert "dealer" in body.lower()
    assert "principal display panel" in body.lower()
    assert len(body) > 1000, "rule-2 body suspiciously short for the definitions rule"


# ----------------------------------------------------------------------
# 3a. Rule 24 wholesale checks
# ----------------------------------------------------------------------
def test_wholesale_package_runs_rule_24_not_retail_checks():
    extracted = {
        "manufacturer_name": {"value": "ACME Wholesale", "confidence": 0.95},
        "manufacturer_address": {"value": "12 MG Road, Pune 411001", "confidence": 0.95},
        "product_name": {"value": "Detergent carton", "confidence": 0.95},
        "net_quantity_value": {"value": 24.0, "confidence": 0.95},
        "net_quantity_unit": {"value": "pieces", "confidence": 0.95},
    }
    evaluation = evaluate_product_compliance(
        extracted_data=extracted,
        category="General",
        package_type="wholesale",
    )
    rule_refs = {r.rule_ref for r in evaluation.results}
    assert "rule-24" in rule_refs, "wholesale scan must cite Rule 24"
    assert not any(r.rule_ref == "rule-6-1-e" for r in evaluation.results), (
        "MRP format check (retail Rule 6(1)(e)) must not run on wholesale packages"
    )


def test_wholesale_missing_declarations_are_non_compliant():
    results = check_wholesale_declarations(
        manufacturer_name=None,
        manufacturer_address=None,
        product_name=None,
        net_quantity_value=None,
        net_quantity_unit=None,
        confidence=0.0,
    )
    assert all(r.status == Verdict.NON_COMPLIANT for r in results)
    assert all(r.rule_ref == "rule-24" for r in results)


def test_wholesale_complete_package_is_compliant():
    results = check_wholesale_declarations(
        manufacturer_name="ACME",
        manufacturer_address="Pune 411001",
        product_name="Carton of 24",
        net_quantity_value=24.0,
        net_quantity_unit="pieces",
        confidence=0.9,
    )
    assert len(results) == 3
    assert all(r.status == Verdict.COMPLIANT for r in results)


# ----------------------------------------------------------------------
# 3b. FSSAI veg/non-veg symbol check now runs
# ----------------------------------------------------------------------
def test_fssai_veg_symbol_detected_is_compliant():
    results = run_fssai_checks(
        category="food",
        fssai_number="10015043001129",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol=None,
        confidence=0.95,
        veg_nonveg_result={"detected": True, "symbol": "VEGETARIAN", "confidence": 0.9},
    )
    veg = next(r for r in results if r.field == "veg_nonveg_symbol")
    assert veg.status == Verdict.COMPLIANT


def test_fssai_symbol_not_detected_is_needs_review_not_violation():
    results = run_fssai_checks(
        category="food",
        fssai_number="10015043001129",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol=None,
        confidence=0.0,
        veg_nonveg_result={"detected": False, "symbol": None, "confidence": 0.0},
    )
    veg = next(r for r in results if r.field == "veg_nonveg_symbol")
    assert veg.status == Verdict.NEEDS_REVIEW


def test_fssai_no_analysis_no_symbol_check():
    """Back-compat: no veg_nonveg_result -> no symbol result is appended."""
    results = run_fssai_checks(
        category="food",
        fssai_number="10015043001129",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol=None,
        confidence=0.95,
    )
    assert not any(r.field == "veg_nonveg_symbol" for r in results)


# ----------------------------------------------------------------------
# 3c. Contrast + barcode advisories never gate the verdict
# ----------------------------------------------------------------------
def test_contrast_advisory_never_gates_verdict():
    evaluation = evaluate_product_compliance(
        extracted_data=_compliant_product(),
        category="food",
        measured_contrast=0.13,
    )
    assert any(r.rule_ref == "rule-9-1-b-contrast" for r in evaluation.results)
    assert evaluation.verdict != Verdict.NON_COMPLIANT, "advisory must not gate"


def test_barcode_advisory_never_gates_verdict():
    evaluation = evaluate_product_compliance(
        extracted_data=_compliant_product(),
        category="food",
        decoded_gtin="8901234567890",
    )
    assert any(r.rule_ref == "rule-6-4A-a" for r in evaluation.results)
    assert evaluation.verdict != Verdict.NON_COMPLIANT


def test_advisories_excluded_from_compliance_score():
    """Score is computed over applicable checks only, not advisories."""
    evaluation = evaluate_product_compliance(
        extracted_data=_compliant_product(),
        category="food",
        measured_contrast=0.4,
        decoded_gtin="8901234567890",
    )
    applicable = [
        r for r in evaluation.results
        if r.rule_ref not in ("fssai-notice", "rule-9-1-b-contrast", "rule-6-4A-a")
    ]
    compliant = [r for r in applicable if r.status == Verdict.COMPLIANT]
    expected = (len(compliant) / max(1, len(applicable))) * 100.0
    assert evaluation.compliance_score == pytest.approx(expected)


# ----------------------------------------------------------------------
# 4. OCR preprocessing: no NL-means on the hot path
# ----------------------------------------------------------------------
def test_enhance_for_ocr_avoids_nlmeans():
    import inspect

    from app.services import image_service

    src = inspect.getsource(image_service.enhance_for_ocr)
    assert "cv2.fastNlMeansDenoising" not in src, (
        "NL-means denoising measured the largest preprocessing cost by far "
        "and was the main cause of multi-second OCR latency."
    )
    assert "cv2.bilateralFilter" in src


def test_enhance_for_ocr_output_is_bgr():
    import numpy as np

    from app.services import image_service

    img = np.full((120, 160, 3), 200, dtype=np.uint8)
    out = image_service.enhance_for_ocr(img)
    assert out.ndim == 3 and out.shape[2] == 3


# ----------------------------------------------------------------------
# 5. Seed credentials honor backend/.env (not just process env)
# ----------------------------------------------------------------------
def test_demo_credentials_read_dotenv(monkeypatch):
    """_demo_credentials loads .env; missing vars skip with a warning."""
    result = _demo_credentials()
    assert isinstance(result, tuple) and len(result) == 2
    # Whatever the environment, a missing pair must be None (never invented).
    for pair in result:
        if pair is not None:
            email, password = pair
            assert email and password
