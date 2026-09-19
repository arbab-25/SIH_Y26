"""Comprehensive test suite for Legal Metrology Rule Checkers per §8 & §14.
Includes ≥40 independent test cases:
- Fully compliant label
- Missing MRP -> NEEDS_REVIEW
- MRP without 'incl. of all taxes' -> NON_COMPLIANT
- MRP non-standard rounding (e.g. ₹99.73) -> NON_COMPLIANT
- Missing month/year of manufacture -> NEEDS_REVIEW (fail-closed: not detected ≠ not declared)
- Non-standard pack size for biscuits (e.g. 63g) -> NON_COMPLIANT
- Standard pack size for biscuits (e.g. 100g) -> COMPLIANT
- Imported product without country of origin -> NEEDS_REVIEW (fail-closed)
- Imported product with country of origin -> COMPLIANT
- Domestic product without country of origin -> COMPLIANT (optional)
- Exempt <=10g package (e.g. 5g sachet) -> COMPLIANT (Exempt)
- Exempt <=10ml package (e.g. 8ml perfume) -> COMPLIANT (Exempt)
- Tobacco product 5g (NOT exempt from rules) -> evaluated
- Exempt >25kg bulk package -> COMPLIANT (Exempt)
- Exempt >25L bulk container -> COMPLIANT (Exempt)
- Exempt cement bag >50kg -> COMPLIANT (Exempt)
- Industrial/institutional package -> COMPLIANT (Exempt)
- Prohibited vague quantity words: 'about 500g' -> NON_COMPLIANT
- Prohibited vague quantity words: 'approx. 100ml' -> NON_COMPLIANT
- Prohibited vague quantity words: 'minimum 200g' -> NON_COMPLIANT
- Prohibited vague quantity words: 'not less than 1kg' -> NON_COMPLIANT
- Prohibited non-metric units: '1 dozen' -> NON_COMPLIANT
- Prohibited non-metric units: 'gross' -> NON_COMPLIANT
- Incorrect SI unit: 0.5 kg (should be 500 g) -> NON_COMPLIANT
- Incorrect SI unit: 1500 g (should be 1.5 kg) -> NON_COMPLIANT
- Incorrect SI unit: 0.25 L (should be 250 ml) -> NON_COMPLIANT
- Incorrect SI unit: 2000 ml (should be 2 L) -> NON_COMPLIANT
- Manufacturer without detected 6-digit PIN code -> NEEDS_REVIEW (fail-closed); malformed PIN -> NON_COMPLIANT
- Manufacturer with valid 6-digit PIN code -> COMPLIANT
- Manufacturer completely missing -> NEEDS_REVIEW
- Missing consumer care details -> NEEDS_REVIEW (fail-closed: not detected ≠ not declared)
- Consumer care with phone only -> COMPLIANT
- Consumer care with email only -> COMPLIANT
- Package dimensions missing -> NEEDS_REVIEW (never guess per §3!)
- Letter height below Table-I minimum -> NON_COMPLIANT
- Letter height above Table-I minimum -> COMPLIANT
- Food product with valid 14-digit FSSAI license -> COMPLIANT
- Food product with invalid 12-digit FSSAI license -> NON_COMPLIANT
- Food product with ingredients & nutrition declared -> COMPLIANT
- Fast food from restaurant -> COMPLIANT (Exempt)
- DPCO-2013 drug formulation -> COMPLIANT (Exempt)
- MRP read as ₹0 -> NON_COMPLIANT (a zero price used to pass as compliant)
- Missing common/generic name -> NEEDS_REVIEW; unreadable name -> NON_COMPLIANT
- Month of manufacture in the future -> NON_COMPLIANT; unreadable date -> NEEDS_REVIEW
- Imported country text that is not a country -> NEEDS_REVIEW
- Best before after manufacture -> COMPLIANT; at/before manufacture -> NON_COMPLIANT
- Best before already passed -> NON_COMPLIANT; declared as a shelf life -> derived to a date
"""

from datetime import date

import pytest
from app.models.scan import Verdict
from app.rule_checkers.rule_3_applicability import check_rule_3_applicability
from app.rule_checkers.rule_26_exemptions import check_rule_26_exemptions
from app.rule_checkers.rule_6_declarations import (
    check_manufacturer_details,
    check_generic_name,
    check_country_of_origin,
    check_mrp_declaration,
    check_mfg_date_declaration,
    check_best_before_declaration,
    check_consumer_care_details
)
from app.rule_checkers.rule_12_quantity import check_vague_quantity_words
from app.rule_checkers.rule_13_si_units import check_si_units
from app.rule_checkers.rule_5_pack_sizes import check_second_schedule_pack_size
from app.rule_checkers.rule_7_letter_height import check_letter_height_and_pdp_area
from app.rule_checkers.fssai_checks import run_fssai_checks
from app.services.rule_engine import evaluate_product_compliance


# ----------------------------------------------------------------------
# Rule 3: Applicability Tests (Bulk Packages & Institutional)
# ----------------------------------------------------------------------
def test_rule_3_package_above_25kg_is_exempt():
    res = check_rule_3_applicability(net_quantity_value=30.0, net_quantity_unit="kg", category="grain")
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en
    assert res.rule_ref == "rule-3"

def test_rule_3_package_above_25L_is_exempt():
    res = check_rule_3_applicability(net_quantity_value=35.0, net_quantity_unit="L", category="chemical")
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en

def test_rule_3_cement_bag_above_50kg_is_exempt():
    res = check_rule_3_applicability(net_quantity_value=55.0, net_quantity_unit="kg", category="cement")
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en

def test_rule_3_cement_bag_50kg_or_less_is_not_exempt():
    res = check_rule_3_applicability(net_quantity_value=50.0, net_quantity_unit="kg", category="cement")
    assert "Exempt" not in res.message_en

def test_rule_3_industrial_institutional_consumer_is_exempt():
    res = check_rule_3_applicability(net_quantity_value=5.0, net_quantity_unit="kg", category="cleaner", is_industrial_or_institutional=True)
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en


# ----------------------------------------------------------------------
# Rule 26: General Exemptions Tests
# ----------------------------------------------------------------------
def test_rule_26_small_package_10g_is_exempt():
    res = check_rule_26_exemptions(net_quantity_value=8.0, net_quantity_unit="g", category="candy")
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en

def test_rule_26_small_package_10ml_is_exempt():
    res = check_rule_26_exemptions(net_quantity_value=10.0, net_quantity_unit="ml", category="perfume")
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en

def test_rule_26_tobacco_small_package_is_not_exempt():
    res = check_rule_26_exemptions(net_quantity_value=5.0, net_quantity_unit="g", category="tobacco")
    assert "Exempt" not in res.message_en

def test_rule_26_fast_food_restaurant_is_exempt():
    res = check_rule_26_exemptions(net_quantity_value=300.0, net_quantity_unit="g", category="food", is_fast_food=True)
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en

def test_rule_26_dpco_formulation_is_exempt():
    res = check_rule_26_exemptions(net_quantity_value=100.0, net_quantity_unit="ml", category="medicine", is_dpco_formulation=True)
    assert res.status == Verdict.COMPLIANT
    assert "Exempt" in res.message_en


# ----------------------------------------------------------------------
# Rule 6(1)(e): Maximum Retail Price (MRP) Tests
# ----------------------------------------------------------------------
def test_mrp_missing_returns_needs_review():
    res = check_mrp_declaration(mrp=None, has_tax_qualification=False, confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW
    assert res.field == "mrp"

def test_mrp_without_inclusive_of_taxes_is_non_compliant():
    res = check_mrp_declaration(mrp=150.0, has_tax_qualification=False, confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "inclusive of all taxes" in res.message_en

def test_mrp_with_inclusive_of_taxes_is_compliant():
    res = check_mrp_declaration(mrp=150.0, has_tax_qualification=True, confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_mrp_invalid_rounding_is_non_compliant():
    # Price ending in 73 paise (not rounded to 0 or 50 paise)
    res = check_mrp_declaration(mrp=99.73, has_tax_qualification=True, confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "rounding" in res.message_en.lower()

def test_mrp_valid_50_paise_rounding_is_compliant():
    res = check_mrp_declaration(mrp=99.50, has_tax_qualification=True, confidence=0.95)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 6(1)(a) & Rule 10(1): Manufacturer & Postal Address Tests
# ----------------------------------------------------------------------
def test_manufacturer_missing_returns_needs_review():
    res = check_manufacturer_details(name=None, address=None, pin_code=None, confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW

def test_manufacturer_missing_pin_code_fails_closed_to_needs_review():
    # Fail-closed per §3: a PIN that was never READ is not proof it is absent —
    # a false NON_COMPLIANT is worse than a manual review.
    res = check_manufacturer_details(
        name="Parle Products Pvt Ltd",
        address="Vile Parle East, Mumbai",
        pin_code=None,
        confidence=0.92
    )
    assert res.status == Verdict.NEEDS_REVIEW
    assert res.rule_ref == "rule-10-1"
    assert "PIN" in res.message_en

def test_manufacturer_invalid_pin_code_is_non_compliant():
    # A positively-read but malformed PIN is positive evidence -> NON_COMPLIANT
    res = check_manufacturer_details(
        name="ABC Foods",
        address="Kolkata",
        pin_code="012345",  # Cannot start with 0
        confidence=0.90
    )
    assert res.status == Verdict.NON_COMPLIANT

def test_manufacturer_with_valid_pin_code_is_compliant():
    res = check_manufacturer_details(
        name="Britannia Industries Ltd",
        address="5/1A Hungerford Street, Kolkata",
        pin_code="700017",
        confidence=0.95
    )
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 6(1)(aa): Country of Origin Tests
# ----------------------------------------------------------------------
def test_imported_package_missing_country_of_origin_fails_closed_to_needs_review():
    # Fail-closed per §3: not detected ≠ not declared on the captured panel
    res = check_country_of_origin(country=None, is_imported=True, confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW
    assert res.rule_ref == "rule-6-1-aa"

def test_imported_package_with_country_of_origin_is_compliant():
    res = check_country_of_origin(country="Italy", is_imported=True, confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_domestic_package_without_country_of_origin_is_compliant():
    res = check_country_of_origin(country=None, is_imported=False, confidence=0.0)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 6(1)(d): Month and Year of Manufacture Tests
# ----------------------------------------------------------------------
def test_mfg_date_missing_non_food_fails_closed_to_needs_review():
    # Fail-closed per §3: not detected ≠ not declared (the panel may not be in frame)
    res = check_mfg_date_declaration(date_str=None, category="cosmetics", confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW

def test_mfg_date_present_is_compliant():
    res = check_mfg_date_declaration(date_str="05/2026", category="detergent", confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_mfg_date_food_article_with_date_is_compliant():
    res = check_mfg_date_declaration(date_str="12/2025", category="food", confidence=0.92)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 6(2): Consumer Care Details Tests
# ----------------------------------------------------------------------
def test_consumer_care_missing_fails_closed_to_needs_review():
    # Fail-closed per §3: not detected ≠ not declared
    res = check_consumer_care_details(phone=None, email=None, confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW
    assert res.rule_ref == "rule-6-2"

def test_consumer_care_with_phone_only_is_compliant():
    res = check_consumer_care_details(phone="1800-222-444", email=None, confidence=0.90)
    assert res.status == Verdict.COMPLIANT

def test_consumer_care_with_email_only_is_compliant():
    res = check_consumer_care_details(phone=None, email="feedback@brand.com", confidence=0.92)
    assert res.status == Verdict.COMPLIANT

def test_consumer_care_with_both_phone_and_email_is_compliant():
    res = check_consumer_care_details(phone="022-28394400", email="care@parle.biz", confidence=0.95)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 12(6): Vague Quantity Words Tests
# ----------------------------------------------------------------------
def test_vague_word_minimum_is_non_compliant():
    res = check_vague_quantity_words(vague_word_found="minimum", confidence=0.90)
    assert res.status == Verdict.NON_COMPLIANT
    assert res.rule_ref == "rule-12-6"

def test_vague_word_not_less_than_is_non_compliant():
    res = check_vague_quantity_words(vague_word_found="not less than", confidence=0.92)
    assert res.status == Verdict.NON_COMPLIANT

def test_vague_word_approx_is_non_compliant():
    res = check_vague_quantity_words(vague_word_found="approximately", confidence=0.88)
    assert res.status == Verdict.NON_COMPLIANT

def test_vague_word_about_is_non_compliant():
    res = check_vague_quantity_words(vague_word_found="about", confidence=0.85)
    assert res.status == Verdict.NON_COMPLIANT

def test_no_vague_word_is_compliant():
    res = check_vague_quantity_words(vague_word_found=None, confidence=1.0)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 13: Metric SI Units Tests
# ----------------------------------------------------------------------
def test_prohibited_unit_dozen_is_non_compliant():
    res = check_si_units(value=1.0, unit="dozen", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "dozen" in res.message_en.lower()

def test_prohibited_unit_gross_is_non_compliant():
    res = check_si_units(value=2.0, unit="gross", confidence=0.90)
    assert res.status == Verdict.NON_COMPLIANT

def test_under_1kg_expressed_in_kg_is_non_compliant():
    res = check_si_units(value=0.5, unit="kg", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "grams" in res.message_en

def test_1000g_or_more_expressed_in_g_is_non_compliant():
    res = check_si_units(value=1500.0, unit="g", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "kilograms" in res.message_en

def test_under_1L_expressed_in_L_is_non_compliant():
    res = check_si_units(value=0.5, unit="L", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "millilitres" in res.message_en

def test_1000ml_or_more_expressed_in_ml_is_non_compliant():
    res = check_si_units(value=2000.0, unit="ml", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "litres" in res.message_en

def test_correct_si_units_500g_is_compliant():
    res = check_si_units(value=500.0, unit="g", confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_correct_si_units_2kg_is_compliant():
    res = check_si_units(value=2.0, unit="kg", confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_correct_si_units_750ml_is_compliant():
    res = check_si_units(value=750.0, unit="ml", confidence=0.95)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# Rule 5 & Second Schedule: Standard Pack Size Tests
# ----------------------------------------------------------------------
def test_second_schedule_biscuits_standard_size_100g_is_compliant():
    res = check_second_schedule_pack_size("Biscuits", net_quantity_value=100.0, net_quantity_unit="g", confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_second_schedule_biscuits_non_standard_size_63g_is_non_compliant():
    res = check_second_schedule_pack_size("Biscuits", net_quantity_value=63.0, net_quantity_unit="g", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "Second Schedule" in res.message_en

def test_second_schedule_tea_standard_size_250g_is_compliant():
    res = check_second_schedule_pack_size("Tea", net_quantity_value=250.0, net_quantity_unit="g", confidence=0.95)
    assert res.status == Verdict.COMPLIANT

def test_second_schedule_unregulated_commodity_is_exempt():
    res = check_second_schedule_pack_size("Electronics Headphones", net_quantity_value=1.0, net_quantity_unit="N", confidence=0.95)
    assert res.status == Verdict.COMPLIANT
    assert "not in the 19 regulated groups" in res.message_en


# ----------------------------------------------------------------------
# Rule 7(2) Table-I: Letter Height & Dimensions Tests
# ----------------------------------------------------------------------
def test_missing_dimensions_returns_needs_review():
    # Non-negotiable rule: "If package dimensions not supplied → NEEDS_REVIEW, never guess."
    res = check_letter_height_and_pdp_area(pdp_height_cm=None, pdp_width_cm=None, measured_glyph_height_mm=2.0)
    assert res.status == Verdict.NEEDS_REVIEW
    assert "Package dimensions not provided" in res.message_en

def test_letter_height_below_table_1_is_non_compliant():
    # Area = 20cm * 10cm = 200 cm² (requires min 2.5mm)
    # Measured = 1.2mm (< 2.5mm) -> NON_COMPLIANT
    res = check_letter_height_and_pdp_area(pdp_height_cm=20.0, pdp_width_cm=10.0, measured_glyph_height_mm=1.2)
    assert res.status == Verdict.NON_COMPLIANT
    assert "below the minimum" in res.message_en

def test_letter_height_above_table_1_is_compliant():
    # Area = 10cm * 4cm = 40 cm² (requires min 1.0mm)
    # Measured = 2.0mm (> 1.0mm) -> COMPLIANT
    res = check_letter_height_and_pdp_area(pdp_height_cm=10.0, pdp_width_cm=4.0, measured_glyph_height_mm=2.0)
    assert res.status == Verdict.COMPLIANT


# ----------------------------------------------------------------------
# FSSAI Food Regulations Tests
# ----------------------------------------------------------------------
def test_fssai_valid_14_digit_number_is_compliant():
    results = run_fssai_checks(
        category="food",
        fssai_number="10717012000120",
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol="VEGETARIAN",
        confidence=0.95
    )
    lic_res = next((r for r in results if r.field == "fssai_license"), None)
    assert lic_res is not None
    assert lic_res.status == Verdict.COMPLIANT

def test_fssai_invalid_12_digit_number_is_non_compliant():
    results = run_fssai_checks(
        category="food",
        fssai_number="107170120001",  # 12 digits
        ingredients_declared=True,
        nutritional_info_declared=True,
        veg_nonveg_symbol=None,
        confidence=0.95
    )
    lic_res = next((r for r in results if r.field == "fssai_license"), None)
    assert lic_res is not None
    assert lic_res.status == Verdict.NON_COMPLIANT


# ----------------------------------------------------------------------
# End-to-End Master Rule Engine Evaluation Tests
# ----------------------------------------------------------------------
def test_master_evaluation_fully_compliant_product():
    mock_extracted = {
        "manufacturer_name": {"value": "Britannia Industries Ltd", "confidence": 0.95},
        "manufacturer_address": {"value": "Kolkata, West Bengal", "confidence": 0.95},
        "pin_code": {"value": "700017", "confidence": 0.95},
        "product_name": {"value": "Biscuits", "confidence": 0.95},
        "net_quantity_value": {"value": 100.0, "confidence": 0.95},
        "net_quantity_unit": {"value": "g", "confidence": 0.95},
        "mrp": {"value": 25.0, "confidence": 0.95},
        "mrp_inclusive_taxes": {"value": True, "confidence": 0.95},
        "mfg_date_str": {"value": "01/2026", "confidence": 0.95},
        # Rule 6(1)(da) — perishable commodity packed 01/2026 with a 01/2029 best before date.
        "best_before": {"value": "01/2029", "confidence": 0.95},
        "consumer_care_phone": {"value": "1800-425-4449", "confidence": 0.95},
        "consumer_care_email": {"value": "feedback@britannia.co.in", "confidence": 0.95},
        "fssai_number": {"value": "10015043001129", "confidence": 0.95},
        "ingredients_declared": {"value": True, "confidence": 0.95},
        "nutritional_info_declared": {"value": True, "confidence": 0.95}
    }

    eval_result = evaluate_product_compliance(
        extracted_data=mock_extracted,
        category="food",
        pdp_height_cm=10.0,
        pdp_width_cm=5.0,
        measured_glyph_height_mm=2.0
    )

    assert eval_result.verdict == Verdict.COMPLIANT
    assert eval_result.compliance_score == 100.0
    assert len(eval_result.violations) == 0


def test_master_evaluation_violating_product():
    mock_extracted = {
        "manufacturer_name": {"value": "Shady Sweets", "confidence": 0.95},
        "pin_code": {"value": None, "confidence": 0.0},  # Missing PIN
        "product_name": {"value": "Biscuits", "confidence": 0.95},
        "net_quantity_value": {"value": 63.0, "confidence": 0.95},  # Non-standard size
        "net_quantity_unit": {"value": "g", "confidence": 0.95},
        "mrp": {"value": 30.0, "confidence": 0.95},
        "mrp_inclusive_taxes": {"value": False, "confidence": 0.95},  # No tax qualification
        "consumer_care_phone": {"value": None, "confidence": 0.0}
    }

    eval_result = evaluate_product_compliance(
        extracted_data=mock_extracted,
        category="food"
    )

    assert eval_result.verdict == Verdict.NON_COMPLIANT
    assert len(eval_result.violations) >= 2
    assert eval_result.penalty_notice is not None


def test_master_evaluation_missing_best_before_routes_to_needs_review():
    """Rule 6(1)(da): a perishable pack with no readable best before is not a pass."""
    mock_extracted = {
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
    }

    eval_result = evaluate_product_compliance(extracted_data=mock_extracted, category="food")

    best_before_result = next(r for r in eval_result.results if r.field == "best_before")
    assert best_before_result.status == Verdict.NEEDS_REVIEW
    assert eval_result.verdict == Verdict.NEEDS_REVIEW


# ----------------------------------------------------------------------
# Rule 6(1)(e): MRP Amount Validity
# ----------------------------------------------------------------------
def test_mrp_zero_is_non_compliant():
    # Regression: ₹0 passed the rounding and tax checks and was reported COMPLIANT.
    res = check_mrp_declaration(mrp=0.0, has_tax_qualification=True, confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert res.rule_ref == "rule-6-1-e"


def test_mrp_negative_value_is_non_compliant():
    res = check_mrp_declaration(mrp=-12.0, has_tax_qualification=True, confidence=0.90)
    assert res.status == Verdict.NON_COMPLIANT


# ----------------------------------------------------------------------
# Rule 6(1)(b): Common / Generic Name
# ----------------------------------------------------------------------
def test_generic_name_declared_is_compliant():
    res = check_generic_name(name="Biscuits", confidence=0.95)
    assert res.status == Verdict.COMPLIANT
    assert res.rule_ref == "rule-6-1-b"


def test_generic_name_missing_is_needs_review():
    res = check_generic_name(name=None, confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW


def test_generic_name_unreadable_is_non_compliant():
    res = check_generic_name(name="12374", confidence=0.93)
    assert res.status == Verdict.NON_COMPLIANT


def test_generic_name_low_confidence_is_needs_review():
    res = check_generic_name(name="Bisc", confidence=0.42)
    assert res.status == Verdict.NEEDS_REVIEW


# ----------------------------------------------------------------------
# Rule 6(1)(d): Manufacture Date Sanity
# ----------------------------------------------------------------------
def test_mfg_date_in_the_future_is_non_compliant():
    res = check_mfg_date_declaration(date_str="12/2099", category="detergent", confidence=0.95)
    assert res.status == Verdict.NON_COMPLIANT
    assert "future" in res.message_en.lower()


def test_mfg_date_unreadable_value_is_needs_review():
    res = check_mfg_date_declaration(date_str="batch 12 A", category="detergent", confidence=0.95)
    assert res.status == Verdict.NEEDS_REVIEW


def test_mfg_date_before_reference_month_is_compliant():
    res = check_mfg_date_declaration(
        date_str="05/2026", category="detergent", confidence=0.95, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.COMPLIANT


def test_mfg_date_after_reference_month_is_non_compliant():
    res = check_mfg_date_declaration(
        date_str="05/2026", category="detergent", confidence=0.95, today=date(2026, 4, 1)
    )
    assert res.status == Verdict.NON_COMPLIANT


# ----------------------------------------------------------------------
# Rule 6(1)(aa): Country of Origin Content
# ----------------------------------------------------------------------
def test_imported_package_with_iso_country_code_is_compliant():
    res = check_country_of_origin(country="IN", is_imported=True, confidence=0.95)
    assert res.status == Verdict.COMPLIANT


def test_imported_package_with_unrecognised_origin_is_needs_review():
    res = check_country_of_origin(country="Xqrt", is_imported=True, confidence=0.95)
    assert res.status == Verdict.NEEDS_REVIEW
    assert "recognised" in res.message_en


# ----------------------------------------------------------------------
# Rule 6(1)(da): Best Before / Use By Date
# ----------------------------------------------------------------------
def test_best_before_after_manufacture_is_compliant():
    res = check_best_before_declaration(
        best_before="12/2026", category="food", mfg_date_str="06/2026",
        confidence=0.95, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.COMPLIANT
    assert res.rule_ref == "rule-6-1-da"


def test_best_before_not_after_manufacture_is_non_compliant():
    res = check_best_before_declaration(
        best_before="01/2026", category="food", mfg_date_str="06/2026",
        confidence=0.95, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.NON_COMPLIANT
    assert "not after" in res.message_en


def test_best_before_already_passed_is_non_compliant():
    res = check_best_before_declaration(
        best_before="01/2026", category="food", mfg_date_str="06/2025",
        confidence=0.95, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.NON_COMPLIANT
    assert res.severity == "MINOR"


def test_best_before_expiring_in_current_month_is_compliant_with_note():
    res = check_best_before_declaration(
        best_before="09/2026", category="food", mfg_date_str="01/2026",
        confidence=0.95, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.COMPLIANT
    assert "current month" in res.message_en


def test_best_before_shelf_life_is_derived_from_manufacture_month():
    res = check_best_before_declaration(
        best_before="Best Before: 12 months from packaging", category="food",
        mfg_date_str="01/2026", confidence=0.90, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.COMPLIANT
    assert "Jan 2027" in res.message_en


def test_best_before_shelf_life_without_manufacture_is_needs_review():
    res = check_best_before_declaration(
        best_before="6 months from packaging", category="food", mfg_date_str=None,
        confidence=0.90, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.NEEDS_REVIEW


def test_best_before_missing_for_perishable_is_needs_review():
    res = check_best_before_declaration(best_before=None, category="food", confidence=0.0)
    assert res.status == Verdict.NEEDS_REVIEW


def test_best_before_missing_for_non_perishable_is_compliant():
    res = check_best_before_declaration(best_before=None, category="cement", confidence=0.0)
    assert res.status == Verdict.COMPLIANT


def test_best_before_unreadable_value_is_needs_review():
    res = check_best_before_declaration(
        best_before="see bottom of pack", category="food", mfg_date_str="01/2026",
        confidence=0.90, today=date(2026, 9, 19)
    )
    assert res.status == Verdict.NEEDS_REVIEW
