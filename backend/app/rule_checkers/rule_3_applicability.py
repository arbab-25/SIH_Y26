"""Rule 3 Checker — Applicability of Chapter II.
Exempts >25kg/25L, cement/fertilizer >50kg, and industrial/institutional consumers.
"""

from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def check_rule_3_applicability(
    net_quantity_value: float | None,
    net_quantity_unit: str | None,
    category: str | None,
    is_industrial_or_institutional: bool = False
) -> CheckResult:
    """Evaluates whether the package is exempt under Rule 3."""
    quoted_text = (
        "Rule 3: The provisions of this chapter shall not apply to,-\n"
        "(a) packages of commodities containing quantity of more than 25 kg or 25 litre;\n"
        "(b) cement, fertilizer and agricultural farm produce sold in bags above 50 kg; and\n"
        "(c) packaged commodities meant for industrial consumers or institutional consumers."
    )

    if is_industrial_or_institutional:
        return CheckResult(
            field="applicability",
            status=Verdict.COMPLIANT,
            confidence=1.0,
            rule_ref="rule-3",
            message_en="Package is exempt from Chapter II as it is meant for industrial or institutional consumers.",
            message_hi="पैकेज अध्याय II से मुक्त है क्योंकि यह औद्योगिक या संस्थागत उपभोक्ताओं के लिए है।",
            quoted_rule_text=quoted_text,
            severity="MINOR"
        )

    cat_lower = (category or "").lower()

    if net_quantity_value is not None and net_quantity_unit:
        unit = net_quantity_unit.lower()

        # Cement/Fertilizer > 50kg exemption
        if any(c in cat_lower for c in ["cement", "fertilizer", "farm"]):
            if unit in ["kg", "kilogram"] and net_quantity_value > 50:
                return CheckResult(
                    field="applicability",
                    status=Verdict.COMPLIANT,
                    confidence=1.0,
                    rule_ref="rule-3",
                    message_en=f"Exempt: Cement/fertilizer/farm produce bag above 50kg ({net_quantity_value}kg).",
                    message_hi=f"छूट प्राप्त: 50 किग्रा से अधिक का सीमेंट/उर्वरक बैग ({net_quantity_value} किग्रा)।",
                    quoted_rule_text=quoted_text,
                    severity="MINOR"
                )

        # General > 25kg or > 25L exemption
        if (unit in ["kg", "kilogram"] and net_quantity_value > 25) or \
           (unit in ["l", "litre", "liter"] and net_quantity_value > 25):
            return CheckResult(
                field="applicability",
                status=Verdict.COMPLIANT,
                confidence=1.0,
                rule_ref="rule-3",
                message_en=f"Exempt from Chapter II: Package quantity exceeds 25kg/25L ({net_quantity_value} {unit}).",
                message_hi=f"अध्याय II से छूट: पैकेज की मात्रा 25 किग्रा/25 लीटर से अधिक है ({net_quantity_value} {unit})।",
                quoted_rule_text=quoted_text,
                severity="MINOR"
            )

    return CheckResult(
        field="applicability",
        status=Verdict.COMPLIANT,
        confidence=1.0,
        rule_ref="rule-3",
        message_en="Retail package falls within the scope of Legal Metrology Chapter II rules.",
        message_hi="खुदरा पैकेज विधिक माप विज्ञान अध्याय II नियमों के दायरे में आता है।",
        quoted_rule_text=quoted_text,
        severity="MINOR"
    )
