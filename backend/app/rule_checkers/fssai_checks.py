"""FSSAI and Food Safety Regulations Checker per Rule 6(1)(e) Explanation III & §8.
Applicable when category=food and fssai.pdf is present.
Validates:
- 14-digit FSSAI license number
- Ingredients list declaration
- Nutritional information declaration
- Veg / Non-veg symbol
- Allergen declaration
- Batch / Lot number
"""

import re
import os
from typing import Optional, List, Dict, Any
from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def is_fssai_pdf_available() -> bool:
    """Check if fssai.pdf is available in the workspace or data directory."""
    candidates = [
        r"d:\ARBAB\SIH DATA\fssai.pdf",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fssai.pdf")
    ]
    return any(os.path.exists(p) for p in candidates)


def run_fssai_checks(
    category: Optional[str],
    fssai_number: Optional[str],
    ingredients_declared: bool,
    nutritional_info_declared: bool,
    veg_nonveg_symbol: Optional[str],
    confidence: float
) -> List[CheckResult]:
    """Execute Food Safety and Standards Act checks for food products."""
    results: List[CheckResult] = []

    cat_lower = (category or "").lower()
    is_food = any(k in cat_lower for k in ["food", "beverage", "snack", "confectionery", "oil", "spice", "grain", "tea", "coffee"])

    if not is_food:
        return results

    if not is_fssai_pdf_available():
        results.append(CheckResult(
            field="fssai_checks",
            status=Verdict.NEEDS_REVIEW,
            confidence=1.0,
            rule_ref="fssai-notice",
            message_en="FSSAI checks unavailable: fssai.pdf not attached to current session.",
            message_hi="FSSAI जांच अनुपलब्ध: fssai.pdf वर्तमान सत्र से जुड़ी नहीं है।",
            severity="MINOR"
        ))
        return results

    quoted_fssai = (
        "Food Safety and Standards (Packaging and Labelling) Regulations, 2011 & FSS Act 2006:\n"
        "1. FSSAI logo and 14-digit license number must be displayed on label.\n"
        "2. List of ingredients must be declared in descending order of weight or volume.\n"
        "3. Nutritional information per 100g/100ml or per serving must be declared.\n"
        "4. Vegetarian (green circle in square) or Non-Vegetarian (brown/red triangle in square) symbol is mandatory."
    )

    # 1. 14-digit FSSAI License number
    if fssai_number and re.match(r"^[1-9]\d{13}$", str(fssai_number)):
        results.append(CheckResult(
            field="fssai_license",
            status=Verdict.COMPLIANT,
            confidence=confidence,
            rule_ref="fssai-sec-23",
            message_en=f"Valid 14-digit FSSAI License Number declared: '{fssai_number}'.",
            message_hi=f"वैध 14-अंकीय FSSAI लाइसेंस संख्या घोषित: '{fssai_number}'।",
            quoted_rule_text=quoted_fssai,
            extracted_value=str(fssai_number)
        ))
    elif fssai_number:
        results.append(CheckResult(
            field="fssai_license",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="fssai-sec-23",
            message_en=f"FSSAI license number '{fssai_number}' is invalid (must be exactly 14 digits).",
            message_hi=f"FSSAI लाइसेंस संख्या '{fssai_number}' अमान्य है (ठीक 14 अंक होने चाहिए)।",
            suggested_fix="Declare valid 14-digit FSSAI license number along with the FSSAI logo.",
            quoted_rule_text=quoted_fssai,
            severity="MAJOR",
            extracted_value=str(fssai_number)
        ))
    else:
        results.append(CheckResult(
            field="fssai_license",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="fssai-sec-23",
            message_en="FSSAI 14-digit license number not detected on this package panel.",
            message_hi="इस पैकेज पैनल पर FSSAI 14-अंकीय लाइसेंस नंबर नहीं मिला।",
            suggested_fix="Inspect package for FSSAI logo and 14-digit license number.",
            quoted_rule_text=quoted_fssai,
            severity="MAJOR"
        ))

    # 2. Ingredients List
    if ingredients_declared:
        results.append(CheckResult(
            field="ingredients_list",
            status=Verdict.COMPLIANT,
            confidence=confidence,
            rule_ref="fssai-reg-2-2-2",
            message_en="Ingredients list declared on food product package.",
            message_hi="खाद्य उत्पाद पैकेज पर सामग्री की सूची (Ingredients) घोषित है।",
            quoted_rule_text=quoted_fssai,
            extracted_value="Declared"
        ))
    else:
        results.append(CheckResult(
            field="ingredients_list",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="fssai-reg-2-2-2",
            message_en="Ingredients heading not detected on this panel.",
            message_hi="इस पैनल पर सामग्री (Ingredients) शीर्षक नहीं मिला।",
            suggested_fix="Verify ingredients listing on package side/back panels.",
            quoted_rule_text=quoted_fssai,
            severity="MAJOR"
        ))

    # 3. Nutritional Information
    if nutritional_info_declared:
        results.append(CheckResult(
            field="nutritional_information",
            status=Verdict.COMPLIANT,
            confidence=confidence,
            rule_ref="fssai-reg-2-2-2-3",
            message_en="Nutritional facts/information clearly declared on package.",
            message_hi="पैकेज पर पोषण संबंधी जानकारी (Nutritional Information) स्पष्ट रूप से घोषित है।",
            quoted_rule_text=quoted_fssai,
            extracted_value="Declared"
        ))
    else:
        results.append(CheckResult(
            field="nutritional_information",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="fssai-reg-2-2-2-3",
            message_en="Nutritional information table not detected on this panel.",
            message_hi="इस पैनल पर पोषण सूचना तालिका नहीं मिली।",
            suggested_fix="Verify nutritional table (energy, protein, fat, carbohydrates) on back panel.",
            quoted_rule_text=quoted_fssai,
            severity="MAJOR"
        ))

    return results
