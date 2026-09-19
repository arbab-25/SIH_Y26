"""CODE MAZE Master Rule Engine per §3 & §8.
Registry of independent, deterministic checker functions.
Strict Fail-Closed Architecture:
- No LLM decides legal verdicts
- 3 verdict states: COMPLIANT | NON_COMPLIANT | NEEDS_REVIEW
- Missing or low-confidence reads (<0.75) -> NEEDS_REVIEW
- All non-compliances cite exact quoted rule text loaded from RULE_BOOK.pdf
- Penalty reference displayed per Rule 32 & 32A ('for reference only, not a legal determination')
"""

from typing import Dict, Any, List, Optional
from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult
from app.rule_checkers.rule_3_applicability import check_rule_3_applicability
from app.rule_checkers.rule_26_exemptions import check_rule_26_exemptions
from app.rule_checkers.rule_6_declarations import (
    check_manufacturer_details,
    check_country_of_origin,
    check_mrp_declaration,
    check_mfg_date_declaration,
    check_consumer_care_details
)
from app.rule_checkers.rule_12_quantity import check_vague_quantity_words
from app.rule_checkers.rule_13_si_units import check_si_units
from app.rule_checkers.rule_5_pack_sizes import check_second_schedule_pack_size
from app.rule_checkers.rule_7_letter_height import check_letter_height_and_pdp_area
from app.rule_checkers.fssai_checks import run_fssai_checks
from app.config import settings


class RuleEngineEvaluation:
    def __init__(self):
        self.verdict: Verdict = Verdict.NEEDS_REVIEW
        self.compliance_score: float = 0.0
        self.results: List[CheckResult] = []
        self.violations: List[CheckResult] = []
        self.penalty_notice: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "compliance_score": round(self.compliance_score, 2),
            "results": [r.to_dict() for r in self.results],
            "violations": [v.to_dict() for v in self.violations],
            "penalty_notice": self.penalty_notice,
            "disclaimer": "Verify against the physical package before issuing any notice."
        }


def evaluate_product_compliance(
    extracted_data: Dict[str, Any],
    category: Optional[str] = None,
    package_type: Optional[str] = "retail",
    is_imported: bool = False,
    is_industrial_or_institutional: bool = False,
    is_fast_food: bool = False,
    pdp_height_cm: Optional[float] = None,
    pdp_width_cm: Optional[float] = None,
    measured_glyph_height_mm: Optional[float] = None
) -> RuleEngineEvaluation:
    """Execute complete deterministic Legal Metrology compliance evaluation."""
    evaluation = RuleEngineEvaluation()
    results: List[CheckResult] = []

    net_qty_val = extracted_data.get("net_quantity_value", {}).get("value")
    net_qty_unit = extracted_data.get("net_quantity_unit", {}).get("value")
    net_qty_conf = extracted_data.get("net_quantity_value", {}).get("confidence", 0.0)

    # -----------------------------------------------------------------
    # STEP 1: Applicability & Exemptions (Rules 3, 24, 26) run FIRST
    # -----------------------------------------------------------------
    r3 = check_rule_3_applicability(
        net_quantity_value=net_qty_val,
        net_quantity_unit=net_qty_unit,
        category=category,
        is_industrial_or_institutional=is_industrial_or_institutional
    )
    if "Exempt" in r3.message_en:
        evaluation.verdict = Verdict.COMPLIANT
        evaluation.compliance_score = 100.0
        evaluation.results = [r3]
        return evaluation

    r26 = check_rule_26_exemptions(
        net_quantity_value=net_qty_val,
        net_quantity_unit=net_qty_unit,
        category=category,
        is_fast_food=is_fast_food
    )
    if "Exempt" in r26.message_en:
        evaluation.verdict = Verdict.COMPLIANT
        evaluation.compliance_score = 100.0
        evaluation.results = [r26]
        return evaluation

    # -----------------------------------------------------------------
    # STEP 2: Mandatory Retail Declarations (Rule 6, 10, 12, 13)
    # -----------------------------------------------------------------
    # 2.1 Manufacturer & Complete Address with 6-digit PIN
    mfg_name = extracted_data.get("manufacturer_name", {}).get("value")
    mfg_addr = extracted_data.get("manufacturer_address", {}).get("value")
    pin_code = extracted_data.get("pin_code", {}).get("value")
    mfg_conf = extracted_data.get("manufacturer_name", {}).get("confidence", 0.0)
    mfg_bbox = extracted_data.get("manufacturer_name", {}).get("bbox")

    r_mfg = check_manufacturer_details(
        name=mfg_name,
        address=mfg_addr,
        pin_code=pin_code,
        confidence=mfg_conf,
        bbox=mfg_bbox
    )
    results.append(r_mfg)

    # 2.2 Country of Origin (Rule 6(1)(aa) for imported goods)
    origin = extracted_data.get("country_of_origin", {}).get("value")
    origin_conf = extracted_data.get("country_of_origin", {}).get("confidence", 0.0)
    origin_bbox = extracted_data.get("country_of_origin", {}).get("bbox")

    r_origin = check_country_of_origin(
        country=origin,
        is_imported=is_imported,
        confidence=origin_conf,
        bbox=origin_bbox
    )
    results.append(r_origin)

    # 2.3 Net Quantity in standard SI units (Rule 6(1)(c) & Rule 13)
    r_si = check_si_units(
        value=net_qty_val,
        unit=net_qty_unit,
        confidence=net_qty_conf,
        bbox=extracted_data.get("net_quantity_value", {}).get("bbox")
    )
    results.append(r_si)

    # 2.4 Prohibited vague quantity words (Rule 12(6))
    vague_word = extracted_data.get("vague_quantity_found", {}).get("value")
    r_vague = check_vague_quantity_words(
        vague_word_found=vague_word,
        confidence=extracted_data.get("vague_quantity_found", {}).get("confidence", 0.0),
        bbox=extracted_data.get("vague_quantity_found", {}).get("bbox")
    )
    results.append(r_vague)

    # 2.5 Standard Pack Sizes under Second Schedule (Rule 5)
    prod_name = extracted_data.get("product_name", {}).get("value") or category or ""
    r_pack = check_second_schedule_pack_size(
        commodity_or_product_name=prod_name,
        net_quantity_value=net_qty_val,
        net_quantity_unit=net_qty_unit,
        confidence=net_qty_conf
    )
    results.append(r_pack)

    # 2.6 Maximum Retail Price (MRP) & Tax Qualification (Rule 6(1)(e))
    mrp_val = extracted_data.get("mrp", {}).get("value")
    has_taxes = extracted_data.get("mrp_inclusive_taxes", {}).get("value", False)
    mrp_conf = extracted_data.get("mrp", {}).get("confidence", 0.0)
    mrp_bbox = extracted_data.get("mrp", {}).get("bbox")

    r_mrp = check_mrp_declaration(
        mrp=mrp_val,
        has_tax_qualification=has_taxes,
        confidence=mrp_conf,
        bbox=mrp_bbox
    )
    results.append(r_mrp)

    # 2.7 Date of Manufacture / Pre-packing / Import (Rule 6(1)(d))
    mfg_date = extracted_data.get("mfg_date_str", {}).get("value")
    mfg_date_conf = extracted_data.get("mfg_date_str", {}).get("confidence", 0.0)
    mfg_date_bbox = extracted_data.get("mfg_date_str", {}).get("bbox")

    r_date = check_mfg_date_declaration(
        date_str=mfg_date,
        category=category,
        confidence=mfg_date_conf,
        bbox=mfg_date_bbox
    )
    results.append(r_date)

    # 2.8 Consumer Care Details (Rule 6(2))
    cc_phone = extracted_data.get("consumer_care_phone", {}).get("value")
    cc_email = extracted_data.get("consumer_care_email", {}).get("value")
    cc_conf = max(
        extracted_data.get("consumer_care_phone", {}).get("confidence", 0.0),
        extracted_data.get("consumer_care_email", {}).get("confidence", 0.0)
    )

    r_cc = check_consumer_care_details(
        phone=cc_phone,
        email=cc_email,
        confidence=cc_conf,
        bbox=extracted_data.get("consumer_care_phone", {}).get("bbox")
    )
    results.append(r_cc)

    # 2.9 Minimum Letter & Numeral Height by PDP Area (Rule 7(2) Table-I)
    r_font = check_letter_height_and_pdp_area(
        pdp_height_cm=pdp_height_cm,
        pdp_width_cm=pdp_width_cm,
        measured_glyph_height_mm=measured_glyph_height_mm
    )
    results.append(r_font)

    # -----------------------------------------------------------------
    # STEP 3: FSSAI & Food Regulations (if category=food)
    # -----------------------------------------------------------------
    fssai_num = extracted_data.get("fssai_number", {}).get("value")
    fssai_conf = extracted_data.get("fssai_number", {}).get("confidence", 0.0)
    has_ing = extracted_data.get("ingredients_declared", {}).get("value", False)
    has_nut = extracted_data.get("nutritional_info_declared", {}).get("value", False)

    fssai_results = run_fssai_checks(
        category=category or prod_name,
        fssai_number=fssai_num,
        ingredients_declared=has_ing,
        nutritional_info_declared=has_nut,
        veg_nonveg_symbol=None,
        confidence=fssai_conf
    )
    results.extend(fssai_results)

    # -----------------------------------------------------------------
    # STEP 4: Compute Overall Verdict & Compliance Score
    # -----------------------------------------------------------------
    evaluation.results = results
    violations = [r for r in results if r.status == Verdict.NON_COMPLIANT]
    needs_review = [r for r in results if r.status == Verdict.NEEDS_REVIEW]
    compliant = [r for r in results if r.status == Verdict.COMPLIANT]

    evaluation.violations = violations

    # Overall Verdict
    if len(violations) > 0:
        evaluation.verdict = Verdict.NON_COMPLIANT
    elif len(needs_review) > 0:
        evaluation.verdict = Verdict.NEEDS_REVIEW
    else:
        evaluation.verdict = Verdict.COMPLIANT

    # Compliance score = compliant / applicable fields %
    total_applicable = len(results)
    evaluation.compliance_score = (len(compliant) / max(1, total_applicable)) * 100.0

    # -----------------------------------------------------------------
    # STEP 5: Penalty Context (Display-only per Rule 32 & 32A)
    # -----------------------------------------------------------------
    if len(violations) > 0:
        evaluation.penalty_notice = {
            "statute": "Legal Metrology Act, 2009 & Rule 32",
            "fine_range": "₹4,000 for rules 27 & 28; ₹5,000 for other contraventions (subsequent offences: up to ₹25,000 or 1 year imprisonment)",
            "compounding": "Eligible for compounding under Rule 32A / Section 48",
            "disclaimer": "Statutory penalty references displayed for administrative guidance only, not a judicial determination."
        }

    return evaluation
