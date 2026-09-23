"""Rule 24 Checker — Declarations on every WHOLESALE package.

Rule 24 requires every wholesale package to bear:
(a) the name and address of the manufacturer or packer;
(b) the identity of the commodity contained in the package; and
(c) the total number of retail packages or net quantity contained in it.

The retail Rule 6 checks do not apply to wholesale packages; without this
checker a wholesale scan silently ran retail checks and never cited Rule 24.
"""

from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult

QUOTED_TEXT = (
    "Rule 24: Declarations applicable to be made on every wholesale package — "
    "Every wholesale package shall bear thereon: "
    "(a) the name and address of the manufacturer or packer; "
    "(b) the identity of the commodity contained in the package; and "
    "(c) the total number of retail packages or the net quantity contained "
    "in the wholesale package."
)


def check_wholesale_declarations(
    manufacturer_name: str | None,
    manufacturer_address: str | None,
    product_name: str | None,
    net_quantity_value: float | None,
    net_quantity_unit: str | None,
    confidence: float,
) -> list[CheckResult]:
    """Evaluate the three Rule 24 declarations on a wholesale package."""
    results: list[CheckResult] = []

    has_name = bool(str(manufacturer_name or "").strip())
    has_address = bool(str(manufacturer_address or "").strip())
    results.append(CheckResult(
        field="wholesale_manufacturer",
        status=Verdict.COMPLIANT if (has_name and has_address) else Verdict.NON_COMPLIANT,
        confidence=confidence if (has_name and has_address) else max(0.0, min(1.0, confidence)),
        rule_ref="rule-24",
        message_en=(
            "Manufacturer/packer name and address declared on the wholesale package."
            if (has_name and has_address)
            else "Rule 24(a): the wholesale package must bear the name and address of the manufacturer or packer — not detected."
        ),
        message_hi=(
            "थोक पैकेज पर निर्माता/पैकर का नाम और पता घोषित है।"
            if (has_name and has_address)
            else "नियम 24(क): थोक पैकेज पर निर्माता या पैकर का नाम और पता होना चाहिए — पता नहीं चला।"
        ),
        suggested_fix=None if (has_name and has_address) else "Declare manufacturer/packer name and full address on the wholesale package.",
        quoted_rule_text=QUOTED_TEXT,
        severity="MAJOR",
        extracted_value=str(manufacturer_name or "") or None,
    ))

    has_identity = bool(str(product_name or "").strip())
    results.append(CheckResult(
        field="wholesale_identity",
        status=Verdict.COMPLIANT if has_identity else Verdict.NON_COMPLIANT,
        confidence=confidence if has_identity else max(0.0, min(1.0, confidence)),
        rule_ref="rule-24",
        message_en=(
            f"Commodity identity declared: '{product_name}'."
            if has_identity
            else "Rule 24(b): the wholesale package must declare the identity of the commodity contained — not detected."
        ),
        message_hi=(
            f"पैकेज में शामिल वस्तु की पहचान घोषित: '{product_name}'।"
            if has_identity
            else "नियम 24(ख): थोक पैकेज पर वस्तु की पहचान घोषित होनी चाहिए — पता नहीं चला।"
        ),
        suggested_fix=None if has_identity else "Declare the common/generic name of the commodity on the wholesale package.",
        quoted_rule_text=QUOTED_TEXT,
        severity="MAJOR",
        extracted_value=str(product_name or "") or None,
    ))

    has_quantity = (
        net_quantity_value is not None
        and float(net_quantity_value) > 0
        and bool(str(net_quantity_unit or "").strip())
    )
    results.append(CheckResult(
        field="wholesale_quantity",
        status=Verdict.COMPLIANT if has_quantity else Verdict.NON_COMPLIANT,
        confidence=confidence if has_quantity else max(0.0, min(1.0, confidence)),
        rule_ref="rule-24",
        message_en=(
            f"Total quantity/number declared on the wholesale package: {net_quantity_value} {net_quantity_unit}."
            if has_quantity
            else "Rule 24(c): the wholesale package must declare the total number of retail packages or the net quantity contained — not detected."
        ),
        message_hi=(
            f"थोक पैकेज पर कुल मात्रा/संख्या घोषित: {net_quantity_value} {net_quantity_unit}।"
            if has_quantity
            else "नियम 24(ग): थोक पैकेज पर कुल रिटेल पैकेजों की संख्या या अंतर्निहित शुद्ध मात्रा घोषित होनी चाहिए — पता नहीं चला।"
        ),
        suggested_fix=None if has_quantity else "Declare the total number of retail packages or the net quantity on the wholesale package.",
        quoted_rule_text=QUOTED_TEXT,
        severity="MAJOR",
        extracted_value=f"{net_quantity_value} {net_quantity_unit}" if has_quantity else None,
    ))

    return results
