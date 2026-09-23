"""Rule 13 Checker — Metric SI Units of Weight, Measure or Number.
Rules:
- g if below 1 kg, kg if 1 kg or more
- ml if below 1 litre, L if 1 litre or more (symbol 'L' preferred over 'l')
- Rejects dozen, score, gross per Rule 13(4)
- Units of number: 'N' or 'U' per Rule 13(5)
"""

from typing import Optional

from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def check_si_units(
    value: Optional[float],
    unit: Optional[str],
    confidence: float,
    bbox: Optional[list] = None
) -> CheckResult:
    quoted_text = (
        "Rule 13: Statement of units of weight, measure or number.-\n"
        "(1) Units of weight: gram (g) if less than 1 kilogram, and kilogram (kg) if 1 kilogram or more.\n"
        "(2) Units of volume: millilitre (ml) if less than 1 litre, and litre (L) if 1 litre or more.\n"
        "(4) The unit of dozen, score, or gross is prohibited.\n"
        "(5) The unit of number shall be expressed by the symbol 'N' or 'U'."
    )

    if value is None or not unit:
        return CheckResult(
            field="net_quantity",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-13",
            message_en="Net quantity value or SI unit not detected with high confidence. Manual review required.",
            message_hi="शुद्ध मात्रा मान या SI इकाई पर्याप्त विश्वास के साथ नहीं मिली। मैन्युअल समीक्षा आवश्यक है।",
            suggested_fix="Locate net quantity declaration on the principal display panel.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    clean_unit = unit.lower().strip()

    # Reject prohibited units (Rule 13(4))
    prohibited_units = ["dozen", "score", "gross"]
    if clean_unit in prohibited_units:
        return CheckResult(
            field="net_quantity_unit",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-13",
            message_en=f"Prohibited non-metric unit '{unit}' declared. Dozen, score, and gross are banned under Rule 13(4).",
            message_hi=f"प्रतिबंधित गैर-मीट्रिक इकाई '{unit}' घोषित की गई है। नियम 13(4) के तहत दर्जन, स्कोर और ग्रॉस प्रतिबंधित हैं।",
            suggested_fix="Express quantity in metric SI units or number (N/U).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"{value} {unit}",
            severity="MAJOR"
        )

    # Check SI unit thresholds:
    # 1. kg vs g
    if clean_unit in ["kg", "kilogram"] and value < 1.0:
        return CheckResult(
            field="net_quantity_unit",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-13",
            message_en=f"Non-compliant unit: {value}kg is less than 1kg; must be expressed in grams (e.g. '{int(value*1000)} g').",
            message_hi=f"गैर-अनुपालन इकाई: {value} किग्रा 1 किग्रा से कम है; इसे ग्राम में व्यक्त किया जाना चाहिए (उदा. '{int(value*1000)} g')।",
            suggested_fix="Express quantities under 1 kg in grams (g) per Rule 13(1).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"{value} {unit}",
            severity="MAJOR"
        )

    if clean_unit in ["g", "gm", "gram", "grams"] and value >= 1000.0:
        return CheckResult(
            field="net_quantity_unit",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-13",
            message_en=f"Non-compliant unit: {value}g is 1000g or more; must be expressed in kilograms (e.g. '{value/1000} kg').",
            message_hi=f"गैर-अनुपालन इकाई: {value} ग्राम 1000 ग्राम या अधिक है; इसे किलोग्राम में व्यक्त किया जाना चाहिए (उदा. '{value/1000} kg')।",
            suggested_fix="Express quantities 1 kg or more in kilograms (kg) per Rule 13(1).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"{value} {unit}",
            severity="MAJOR"
        )

    # 2. L vs ml
    if clean_unit in ["l", "litre", "liter"] and value < 1.0:
        return CheckResult(
            field="net_quantity_unit",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-13",
            message_en=f"Non-compliant unit: {value}L is less than 1L; must be expressed in millilitres (e.g. '{int(value*1000)} ml').",
            message_hi=f"गैर-अनुपालन इकाई: {value} लीटर 1 लीटर से कम है; इसे मिलीलीटर में व्यक्त किया जाना चाहिए (उदा. '{int(value*1000)} ml')।",
            suggested_fix="Express volumes under 1 litre in millilitres (ml) per Rule 13(2).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"{value} {unit}",
            severity="MAJOR"
        )

    if clean_unit in ["ml", "millilitre"] and value >= 1000.0:
        return CheckResult(
            field="net_quantity_unit",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-13",
            message_en=f"Non-compliant unit: {value}ml is 1000ml or more; must be expressed in litres (e.g. '{value/1000} L').",
            message_hi=f"गैर-अनुपालन इकाई: {value} मिली 1000 मिली या अधिक है; इसे लीटर में व्यक्त किया जाना चाहिए (उदा. '{value/1000} L')।",
            suggested_fix="Express volumes 1 litre or more in litres (L) per Rule 13(2).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"{value} {unit}",
            severity="MAJOR"
        )

    return CheckResult(
        field="net_quantity",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-13",
        message_en=f"Net quantity '{value} {unit}' declared in correct metric SI units.",
        message_hi=f"शुद्ध मात्रा '{value} {unit}' सही मीट्रिक SI इकाइयों में घोषित है।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=f"{value} {unit}"
    )
