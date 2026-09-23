"""Rule 5 & Second Schedule Checker — Standard Pack Sizes for 19 Commodity Groups.
Validates net quantity against legally permitted pack sizes parsed from RULE_BOOK.pdf.
"""

import json
import os
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz, process

from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def load_second_schedule() -> List[Dict[str, Any]]:
    # backend root is 3 levels up from this file (app/rule_checkers/rule_5_pack_sizes.py)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schedules_path = os.path.join(backend_dir, "seed", "schedules.json")
    if not os.path.exists(schedules_path):
        # Fallback to app/seed/schedules.json
        schedules_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed", "schedules.json")
    if os.path.exists(schedules_path):
        with open(schedules_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("second_schedule_commodities", [])
    return []


_COMMODITIES_CACHE = None


def get_second_schedule_commodities():
    global _COMMODITIES_CACHE
    if _COMMODITIES_CACHE is None:
        _COMMODITIES_CACHE = load_second_schedule()
    return _COMMODITIES_CACHE


def check_second_schedule_pack_size(
    commodity_or_product_name: str,
    net_quantity_value: Optional[float],
    net_quantity_unit: Optional[str],
    confidence: float
) -> CheckResult:
    quoted_text = (
        "Rule 5: The commodities specified in the Second Schedule shall be packed for sale, "
        "distribution or delivery in such standard quantities as are specified in that Schedule: "
        "Provided that if a commodity is packed in a size other than that specified, a declaration that "
        "'Not a standard pack size' shall not be made."
    )

    if net_quantity_value is None or not net_quantity_unit:
        return CheckResult(
            field="standard_pack_size",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-5",
            message_en="Net quantity not available to check standard pack size under Second Schedule.",
            message_hi="द्वितीय अनुसूची के तहत मानक पैक आकार की जांच करने के लिए शुद्ध मात्रा उपलब्ध नहीं है।",
            quoted_rule_text=quoted_text,
            severity="MAJOR"
        )

    commodities = get_second_schedule_commodities()
    if not commodities:
        return CheckResult(
            field="standard_pack_size",
            status=Verdict.NEEDS_REVIEW,
            confidence=1.0,
            rule_ref="rule-5",
            message_en="Second schedule reference tables not loaded.",
            message_hi="द्वितीय अनुसूची संदर्भ तालिकाएँ लोड नहीं की गईं।",
            quoted_rule_text=quoted_text,
            severity="MINOR"
        )

    # Match commodity using fuzzy search (token_set_ratio prevents false substring positives)
    comm_names = [c["commodity"] for c in commodities]
    match = process.extractOne(
        commodity_or_product_name,
        comm_names,
        scorer=fuzz.token_set_ratio,
        score_cutoff=70
    )

    if not match:
        # Not one of the 19 regulated commodity groups in the Second Schedule
        return CheckResult(
            field="standard_pack_size",
            status=Verdict.COMPLIANT,
            confidence=1.0,
            rule_ref="rule-5",
            message_en=f"Commodity '{commodity_or_product_name}' is not in the 19 regulated groups of the Second Schedule (exempt from fixed pack sizes).",
            message_hi=f"कमोडिटी '{commodity_or_product_name}' द्वितीय अनुसूची के 19 विनियमित समूहों में नहीं है (निश्चित पैक आकार से मुक्त)।",
            quoted_rule_text=quoted_text,
            severity="MINOR"
        )

    matched_commodity = next(c for c in commodities if c["commodity"] == match[0])
    allowed = matched_commodity["allowed_values"]
    unit = net_quantity_unit.lower()

    # Normalize quantity to gram or ml
    val = net_quantity_value
    if unit in ["kg", "kilogram"]:
        val = net_quantity_value * 1000
    elif unit in ["l", "litre", "liter"]:
        val = net_quantity_value * 1000

    # Check if value is in allowed list
    is_standard = False
    if val in allowed or int(val) in allowed:
        is_standard = True
    elif val > 1000 and val % 500 == 0:  # Multiples of 500g / 500ml up to 5kg
        is_standard = True

    if not is_standard:
        allowed_str = ", ".join(f"{v}g" for v in allowed[:10])
        return CheckResult(
            field="standard_pack_size",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-5",
            message_en=(
                f"Non-standard pack size for {matched_commodity['commodity']}: {net_quantity_value}{net_quantity_unit} "
                f"is not permitted under the Second Schedule. Allowed standard sizes include: {allowed_str}..."
            ),
            message_hi=(
                f"{matched_commodity['commodity']} के लिए गैर-मानक पैक आकार: {net_quantity_value}{net_quantity_unit} "
                f"द्वितीय अनुसूची के तहत अनुमत नहीं है। अनुमत मानक आकार: {allowed_str}..."
            ),
            suggested_fix=f"Pack commodity only in standard sizes specified in Second Schedule ({allowed_str}).",
            quoted_rule_text=quoted_text,
            severity="MAJOR",
            extracted_value=f"{net_quantity_value}{net_quantity_unit}"
        )

    return CheckResult(
        field="standard_pack_size",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-5",
        message_en=f"Pack size {net_quantity_value}{net_quantity_unit} matches standard sizes for {matched_commodity['commodity']} under Second Schedule.",
        message_hi=f"पैक आकार {net_quantity_value}{net_quantity_unit} द्वितीय अनुसूची के तहत {matched_commodity['commodity']} के मानक आकारों से मेल खाता है।",
        quoted_rule_text=quoted_text,
        extracted_value=f"{net_quantity_value}{net_quantity_unit}"
    )
