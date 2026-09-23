"""Regression tests for the DEMO-RUN session fixes (Sep 24, 2026).

Covers the reported breakages:
1. Rule engine gaps — wholesale packages ran retail checks (Rule 24 never
   cited); the veg/non-veg symbol parameter was accepted and ignored.
2. Rule book incomplete — seed file carried only 28 curated entries; it now
   ships all 34 main rules (1-34 incl. 32A; 31 omitted by amendment) plus
   granular sub-rules, 55 entries total.
3. Image scan quality / speed — preprocessing now downscales oversized phone
   photos to a bounded long edge instead of OCR-ing megapixel inputs.
4. Barcode cross-check — a pyzbar-decoded GTIN may confirm or demote an OCR
   read, never silently invent one.
"""

import json
import os
import re

import numpy as np

from app.models.scan import Verdict
from app.rule_checkers import fssai_checks as fssai_module
from app.rule_checkers.rule_24_wholesale import check_wholesale_declarations
from app.services.barcode_service import (
    BARCODE_MISMATCH_MAX_CONF,
    BARCODE_MISSING_READ_CONF,
    apply_barcode_crosscheck,
)
from app.services.field_extractors import ExtractedData
from app.services.image_service import OCR_MAX_DIM, preprocess_image_for_ocr
from app.services.rule_engine import evaluate_product_compliance

SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed", "rules.json")


# ---------------------------------------------------------------------------
# 1. Rule 24 wholesale path
# ---------------------------------------------------------------------------

def _empty_extraction() -> dict:
    return {}


def test_wholesale_scan_cites_rule_24_not_retail_rules():
    evaluation = evaluate_product_compliance(
        extracted_data=_empty_extraction(),
        category="other",
        package_type="wholesale",
    )
    cited = {r.rule_ref for r in evaluation.results}
    assert "rule-24" in cited, "wholesale packages must be evaluated against Rule 24"
    # Retail-only citations must not appear for a wholesale package.
    assert not any(ref.startswith("rule-6-1-") for ref in cited)
    assert evaluation.verdict in (Verdict.NON_COMPLIANT, Verdict.NEEDS_REVIEW)


def test_wholesale_complete_declarations_pass():
    evaluation = evaluate_product_compliance(
        extracted_data={
            "manufacturer_name": {"value": "Acme Foods Pvt Ltd", "confidence": 0.9, "bbox": None},
            "manufacturer_address": {"value": "12 MG Road, Mumbai 400001", "confidence": 0.9, "bbox": None},
            "product_name": {"value": "Detergent Powder", "confidence": 0.9, "bbox": None},
            "net_quantity_value": {"value": 10.0, "confidence": 0.9, "bbox": None},
            "net_quantity_unit": {"value": "kg", "confidence": 0.9, "bbox": None},
        },
        category="other",
        package_type="wholesale",
    )
    assert evaluation.verdict == Verdict.COMPLIANT
    assert evaluation.compliance_score == 100.0


def test_retail_still_runs_retail_checks():
    evaluation = evaluate_product_compliance(
        extracted_data=_empty_extraction(),
        category="other",
        package_type="retail",
    )
    cited = {r.rule_ref for r in evaluation.results}
    assert any(ref.startswith("rule-6-1-") for ref in cited), "retail path must keep Rule 6 checks"
    assert "rule-24" not in cited


def test_rule_24_checker_individual_fields():
    results = check_wholesale_declarations(
        manufacturer_name="Acme",
        manufacturer_address="12 MG Road, Mumbai",
        product_name=None,
        net_quantity_value=5.0,
        net_quantity_unit="kg",
        confidence=0.9,
    )
    by_field = {r.field: r for r in results}
    assert by_field["wholesale_manufacturer"].status == Verdict.COMPLIANT
    assert by_field["wholesale_identity"].status == Verdict.NON_COMPLIANT
    assert all(r.rule_ref == "rule-24" for r in results)


# ---------------------------------------------------------------------------
# 2. Veg / non-veg symbol is actually evaluated
# ---------------------------------------------------------------------------

def test_fssai_uses_detected_veg_symbol(monkeypatch):
    monkeypatch.setattr(fssai_module, "is_fssai_pdf_available", lambda: True)
    results = fssai_module.run_fssai_checks(
        category="food",
        fssai_number="10015043001129",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol="VEGETARIAN",
        confidence=0.9,
    )
    veg = [r for r in results if r.field == "veg_nonveg_symbol"]
    assert len(veg) == 1
    assert veg[0].status == Verdict.COMPLIANT
    assert veg[0].rule_ref == "fssai-reg-2-2-2"


def test_fssai_missing_symbol_is_review_not_silent(monkeypatch):
    monkeypatch.setattr(fssai_module, "is_fssai_pdf_available", lambda: True)
    results = fssai_module.run_fssai_checks(
        category="food",
        fssai_number="10015043001129",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol=None,
        confidence=0.9,
        veg_analysis_ran=True,  # dot analysis ran but found no symbol on this panel
    )
    veg = [r for r in results if r.field == "veg_nonveg_symbol"]
    assert len(veg) == 1
    assert veg[0].status == Verdict.NEEDS_REVIEW


def test_fssai_skips_symbol_when_analysis_never_ran(monkeypatch):
    """A mocked/single-panel scan without dot analysis must not gain a
    phantom veg-symbol review result — matching the pipeline contract."""
    monkeypatch.setattr(fssai_module, "is_fssai_pdf_available", lambda: True)
    results = fssai_module.run_fssai_checks(
        category="food",
        fssai_number="10015043001129",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol=None,
        confidence=0.9,
        veg_analysis_ran=False,
    )
    assert [r for r in results if r.field == "veg_nonveg_symbol"] == []


def test_engine_flows_symbol_into_fssai_block():
    extracted = {
        "fssai_number": {"value": "10015043001129", "confidence": 0.9, "bbox": None},
        "ingredients_declared": {"value": True, "confidence": 0.9, "bbox": None},
        "nutritional_info_declared": {"value": True, "confidence": 0.9, "bbox": None},
        "veg_nonveg_symbol": {"value": "NON_VEGETARIAN", "confidence": 0.8, "bbox": None},
    }
    evaluation = evaluate_product_compliance(
        extracted_data=extracted,
        category="food",
        package_type="retail",
    )
    veg = [r for r in evaluation.results if r.field == "veg_nonveg_symbol"]
    assert veg and veg[0].extracted_value == "NON_VEGETARIAN"


def test_engine_skips_veg_check_when_analysis_never_ran():
    """No veg_nonveg_symbol key in extracted data -> the check must not run,
    so legacy/mocked fixtures keep their historical verdicts."""
    extracted = {
        "fssai_number": {"value": "10015043001129", "confidence": 0.9, "bbox": None},
        "ingredients_declared": {"value": True, "confidence": 0.9, "bbox": None},
        "nutritional_info_declared": {"value": True, "confidence": 0.9, "bbox": None},
    }
    evaluation = evaluate_product_compliance(
        extracted_data=extracted,
        category="food",
        package_type="retail",
    )
    assert [r for r in evaluation.results if r.field == "veg_nonveg_symbol"] == []


# ---------------------------------------------------------------------------
# 3. Seed file completeness
# ---------------------------------------------------------------------------

def test_seed_rules_carry_all_main_rules():
    with open(SEED_PATH, encoding="utf-8") as f:
        rules = json.load(f)
    numbers = {r["rule_number"] for r in rules}
    main = {n for n in numbers if re.fullmatch(r"rule-\d+[A-Z]?", n)}
    # Main rules 1-34 (31 removed by amendment) must all be present.
    for i in range(1, 35):
        if i == 31:
            continue
        assert f"rule-{i}" in main, f"main rule-{i} missing from seed"
    assert "rule-32A" in main
    assert len(rules) >= 55


# ---------------------------------------------------------------------------
# 4. Barcode cross-check semantics
# ---------------------------------------------------------------------------

def test_barcode_crosscheck_confirm():
    data = ExtractedData()
    data.set_field("barcode_gtin", "8901234567890", 0.92)
    outcome = apply_barcode_crosscheck(data, "8901234567890")
    assert outcome["outcome"] == "confirmed"
    assert data.fields["barcode_gtin"]["confidence"] == 0.92


def test_barcode_crosscheck_mismatch_demotes_never_corrects():
    data = ExtractedData()
    data.set_field("barcode_gtin", "8901234567891", 0.90)
    outcome = apply_barcode_crosscheck(data, "8901234567890")
    assert outcome["outcome"] == "mismatch"
    entry = data.fields["barcode_gtin"]
    assert entry["value"] == "8901234567891"  # value NOT overwritten
    assert entry["confidence"] <= BARCODE_MISMATCH_MAX_CONF
    assert entry["mismatch_with_barcode"] == "8901234567890"


def test_barcode_crosscheck_fill_keeps_field_in_review():
    data = ExtractedData()
    outcome = apply_barcode_crosscheck(data, "8901234567890")
    assert outcome["outcome"] == "filled_from_barcode"
    entry = data.fields["barcode_gtin"]
    assert entry["value"] == "8901234567890"
    assert entry["confidence"] == BARCODE_MISSING_READ_CONF < 0.75


# ---------------------------------------------------------------------------
# 5. Preprocessing downscale
# ---------------------------------------------------------------------------

def test_preprocessing_downscales_oversized_photos():
    big = np.zeros((3200, 2400, 3), dtype=np.uint8)
    out = preprocess_image_for_ocr(big)
    long_edge = max(out.shape[:2])
    assert long_edge <= OCR_MAX_DIM, "oversized photos must be downscaled before OCR"


def test_preprocessing_keeps_small_photos_untouched():
    small = np.full((400, 300, 3), 200, dtype=np.uint8)
    out = preprocess_image_for_ocr(small)
    assert max(out.shape[:2]) == 400  # no upscaling of already-small inputs
