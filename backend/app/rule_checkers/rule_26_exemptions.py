"""Rule 26 Checker — General Exemptions.
Exempts <=10g/10ml (except tobacco), fast food, DPCO-2013 formulations, and handloom thread.
"""

from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def check_rule_26_exemptions(
    net_quantity_value: float | None,
    net_quantity_unit: str | None,
    category: str | None,
    is_fast_food: bool = False,
    is_dpco_formulation: bool = False
) -> CheckResult:
    """Evaluates whether package is exempt under Rule 26."""
    quoted_text = (
        "Rule 26: Nothing in these rules shall apply to,-\n"
        "(a) packages of commodities containing quantity of not more than 10 g or 10 ml (except tobacco and tobacco products);\n"
        "(b) package containing fast food items packed by restaurant or hotel;\n"
        "(c) scheduled formulations and non-scheduled formulations covered under the Drugs (Price Control) Order, 2013;\n"
        "(d) agricultural farm produce sold in packages above 50 kg;\n"
        "(e) thread which is sold in coil to handloom weavers."
    )

    cat_lower = (category or "").lower()

    if is_fast_food:
        return CheckResult(
            field="exemption",
            status=Verdict.COMPLIANT,
            confidence=1.0,
            rule_ref="rule-26",
            message_en="Exempt: Fast food items packed by restaurant or hotel under Rule 26(b).",
            message_hi="छूट प्राप्त: नियम 26(ख) के तहत रेस्तरां या होटल द्वारा पैक किए गए फास्ट फूड आइटम।",
            quoted_rule_text=quoted_text,
            severity="MINOR"
        )

    if is_dpco_formulation or "dpco" in cat_lower:
        return CheckResult(
            field="exemption",
            status=Verdict.COMPLIANT,
            confidence=1.0,
            rule_ref="rule-26",
            message_en="Exempt: Drugs (Price Control) Order, 2013 scheduled/non-scheduled formulation under Rule 26(c).",
            message_hi="छूट प्राप्त: नियम 26(ग) के तहत औषधि (मूल्य नियंत्रण) आदेश, 2013 फॉर्मूलेशन।",
            quoted_rule_text=quoted_text,
            severity="MINOR"
        )

    # Check <= 10g or <= 10ml exemption (except tobacco)
    if net_quantity_value is not None and net_quantity_unit:
        unit = net_quantity_unit.lower()
        is_tobacco = any(t in cat_lower for t in ["tobacco", "cigarette", "bidi", "gutkha", "pan masala"])

        if not is_tobacco:
            if (unit in ["g", "gm", "gram", "grams"] and net_quantity_value <= 10.0) or \
               (unit in ["ml", "millilitre"] and net_quantity_value <= 10.0):
                return CheckResult(
                    field="exemption",
                    status=Verdict.COMPLIANT,
                    confidence=1.0,
                    rule_ref="rule-26",
                    message_en=f"Exempt: Small package ≤10g or ≤10ml ({net_quantity_value}{unit}) under Rule 26(a).",
                    message_hi=f"छूट प्राप्त: नियम 26(क) के तहत ≤10 ग्राम या ≤10 मिली का छोटा पैकेज ({net_quantity_value}{unit})।",
                    quoted_rule_text=quoted_text,
                    severity="MINOR"
                )

    return CheckResult(
        field="exemption",
        status=Verdict.COMPLIANT,
        confidence=1.0,
        rule_ref="rule-26",
        message_en="Package is subject to Legal Metrology compliance (not exempt under Rule 26).",
        message_hi="पैकेज विधिक माप विज्ञान अनुपालन के अधीन है (नियम 26 के तहत छूट नहीं)।",
        quoted_rule_text=quoted_text,
        severity="MINOR"
    )
