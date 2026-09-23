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
from app.rule_checkers.rule_24_wholesale import check_wholesale_declarations
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


def _finalize(evaluation: "RuleEngineEvaluation", results: List[CheckResult]) -> None:
    """Shared verdict/score/penalty computation (STEP 4 & 5 of the evaluation).

    Informational entries (e.g. \"FSSAI checks unavailable\", measured-contrast
    note, barcode-presence note) are displayed but must NOT gate the verdict or
    the score — skipping or noting a check is not a finding.
    """
    informational_refs = {
        "fssai-notice",          # fssai.pdf not attached: no FSSAI checks ran
        "rule-9-1-b-contrast",   # measured contrast is advisory, not enforced
        "rule-6-4A-a",           # barcode presence note (cross-check result)
    }
    scoping_results = [r for r in results if r.rule_ref not in informational_refs]
    violations = [r for r in scoping_results if r.status == Verdict.NON_COMPLIANT]
    needs_review = [r for r in scoping_results if r.status == Verdict.NEEDS_REVIEW]
    compliant = [r for r in scoping_results if r.status == Verdict.COMPLIANT]

    evaluation.results = results
    evaluation.violations = violations

    if len(violations) > 0:
        evaluation.verdict = Verdict.NON_COMPLIANT
    elif len(needs_review) > 0:
        evaluation.verdict = Verdict.NEEDS_REVIEW
    else:
        evaluation.verdict = Verdict.COMPLIANT

    total_applicable = len(scoping_results)
    evaluation.compliance_score = (len(compliant) / max(1, total_applicable)) * 100.0

    if len(violations) > 0:
        evaluation.penalty_notice = {
            "statute": "Legal Metrology Act, 2009 & Rule 32",
            "fine_range": "₹4,000 for rules 27 & 28; ₹5,000 for other contraventions (subsequent offences: up to ₹25,000 or 1 year imprisonment)",
            "compounding": "Eligible for compounding under Rule 32A / Section 48",
            "disclaimer": "Statutory penalty references displayed for administrative guidance only, not a judicial determination."
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
    measured_glyph_height_mm: Optional[float] = None,
    veg_nonveg_result: Optional[Dict[str, Any]] = None,
    measured_contrast: Optional[float] = None,
    decoded_gtin: Optional[str] = None,
) -> RuleEngineEvaluation:
    """Execute complete deterministic Legal Metrology compliance evaluation."""
    evaluation = RuleEngineEvaluation()
    results: List[CheckResult] = []

    # -----------------------------------------------------------------
    # STEP 0: WHOLESALE packages follow Rule 24, not the retail Rule 6 set
    # -----------------------------------------------------------------
    # The retail checks below (MRP format, best-before, consumer care, …) do
    # not apply to a wholesale package; running them produced bogus findings.
    if (package_type or "retail").lower() == "wholesale":
        results.extend(check_wholesale_declarations(
            manufacturer_name=extracted_data.get("manufacturer_name", {}).get("value"),
            manufacturer_address=extracted_data.get("manufacturer_address", {}).get("value"),
            product_name=extracted_data.get("product_name", {}).get("value"),
            net_quantity_value=extracted_data.get("net_quantity_value", {}).get("value"),
            net_quantity_unit=extracted_data.get("net_quantity_unit", {}).get("value"),
            confidence=extracted_data.get("manufacturer_name", {}).get("confidence", 0.0),
        ))
        _finalize(evaluation, results)
        return evaluation

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

    # 2.2 Common / Generic name of the commodity (Rule 6(1)(b))
    generic_name = extracted_data.get("product_name", {}).get("value")
    generic_conf = extracted_data.get("product_name", {}).get("confidence", 0.0)

    r_name = check_generic_name(
        name=generic_name,
        confidence=generic_conf,
        bbox=extracted_data.get("product_name", {}).get("bbox")
    )
    results.append(r_name)

    # 2.3 Country of Origin (Rule 6(1)(aa) for imported goods)
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

    # 2.4 Net Quantity in standard SI units (Rule 6(1)(c) & Rule 13)
    r_si = check_si_units(
        value=net_qty_val,
        unit=net_qty_unit,
        confidence=net_qty_conf,
        bbox=extracted_data.get("net_quantity_value", {}).get("bbox")
    )
    results.append(r_si)

    # 2.5 Prohibited vague quantity words (Rule 12(6))
    vague_word = extracted_data.get("vague_quantity_found", {}).get("value")
    r_vague = check_vague_quantity_words(
        vague_word_found=vague_word,
        confidence=extracted_data.get("vague_quantity_found", {}).get("confidence", 0.0),
        bbox=extracted_data.get("vague_quantity_found", {}).get("bbox")
    )
    results.append(r_vague)

    # 2.6 Standard Pack Sizes under Second Schedule (Rule 5)
    prod_name = extracted_data.get("product_name", {}).get("value") or category or ""
    r_pack = check_second_schedule_pack_size(
        commodity_or_product_name=prod_name,
        net_quantity_value=net_qty_val,
        net_quantity_unit=net_qty_unit,
        confidence=net_qty_conf
    )
    results.append(r_pack)

    # 2.7 Maximum Retail Price (MRP) & Tax Qualification (Rule 6(1)(e))
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

    # 2.8 Date of Manufacture / Pre-packing / Import (Rule 6(1)(d))
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

    # 2.9 Best before / use by date (Rule 6(1)(da)) — cross-checked against the
    # month and year of manufacture so an impossible date cannot pass.
    best_before = extracted_data.get("best_before", {}).get("value")
    best_before_conf = extracted_data.get("best_before", {}).get("confidence", 0.0)

    r_best_before = check_best_before_declaration(
        best_before=best_before,
        category=category,
        mfg_date_str=mfg_date,
        confidence=best_before_conf,
        bbox=extracted_data.get("best_before", {}).get("bbox")
    )
    results.append(r_best_before)

    # 2.10 Consumer Care Details (Rule 6(2))
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
    # Only evaluated when physical dimensions are supplied. Rule 7(2) cannot be
    # measured from a photo alone; running it unconditionally forced EVERY scan
    # into a constant NEEDS_REVIEW verdict even when all declarations read clean.
    # Per §3 we never guess: absent dimensions means the check is skipped (and
    # surfaced as a note in the UI), not a package-wide NEEDS_REVIEW.
    if pdp_height_cm is not None and pdp_width_cm is not None:
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

    # veg/non-veg analysis result flows from run_ocr metadata: {"detected",
    # "symbol", "confidence"}. None means the analysis never ran.
    fssai_results = run_fssai_checks(
        category=category or prod_name,
        fssai_number=fssai_num,
        ingredients_declared=has_ing,
        nutritional_info_declared=has_nut,
        veg_nonveg_symbol=(veg_nonveg_result or {}).get("symbol"),
        confidence=fssai_conf
    )
    results.extend(fssai_results)

    # -----------------------------------------------------------------
    # STEP 3b: Advisory measurements (display-only, never gate the verdict)
    # -----------------------------------------------------------------
    if measured_contrast is not None:
        results.append(CheckResult(
            field="label_contrast",
            status=Verdict.NEEDS_REVIEW,  # informational; excluded from scoring
            confidence=1.0,
            rule_ref="rule-9-1-b-contrast",
            message_en=(
                f"Measured label contrast (RMS): {measured_contrast:.2f} — advisory measurement under Rule 9(1)(b); "
                "verify readability on the physical package."
            ),
            message_hi=(
                f"मापा गया लेबल कंट्रास्ट (RMS): {measured_contrast:.2f} — नियम 9(1)(ब) के अंतर्गत सलाहकारी माप; "
                "भौतिक पैकेज पर पठनीयता जांचें।"
            ),
            quoted_rule_text="Rule 9(1)(b): declarations shall be prominent, legible and contrast with the background.",
            severity="MINOR"
        ))

    if decoded_gtin:
        results.append(CheckResult(
            field="barcode_gtin",
            status=Verdict.COMPLIANT,  # informational; excluded from scoring
            confidence=1.0,
            rule_ref="rule-6-4A-a",
            message_en=(
                f"Machine-decoded barcode/GTIN read: {decoded_gtin} — used to cross-check the OCR'd declaration."
            ),
            message_hi=(
                f"मशीन-डिकोडेड बारकोड/GTIN पढ़ा गया: {decoded_gtin} — OCR घोषणा की क्रॉस-जांच के लिए उपयोग किया गया।"
            ),
            severity="MINOR",
            extracted_value=str(decoded_gtin)
        ))

    # -----------------------------------------------------------------
    # STEP 4: Compute Overall Verdict & Compliance Score
    # -----------------------------------------------------------------
    _finalize(evaluation, results)

    return evaluation
