"""Rule 6 Checkers — Mandatory Retail Declarations under Legal Metrology Rules, 2011.
Rules:
- Rule 6(1)(a) & 10(1): Manufacturer name & complete postal address with 6-digit PIN
- Rule 6(1)(aa): Country of origin for imported goods
- Rule 6(1)(b): Generic or common name
- Rule 6(1)(c): Net quantity declaration in standard SI units
- Rule 6(1)(d): Month and year of manufacture/packing/import
- Rule 6(1)(da): Best before / use by date where perishable
- Rule 6(1)(e): Maximum Retail Price (MRP) format & inclusive of all taxes
- Rule 6(2): Consumer care details (name/address, phone, email)
- Rule 6(8): Veg / Non-veg symbol for cosmetics and toiletries
"""

import re
from datetime import date
from typing import Optional

from app.config import settings
from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult
from app.utils.regulatory_parsing import (
    add_period,
    current_month_index,
    format_month_year,
    is_known_country,
    month_index,
    months_until,
    parse_month_year,
    parse_relative_period,
)

# Every quoted_rule_text in this module is transcribed verbatim from
# backend/seed/rules.json, which is parsed from RULE_BOOK.pdf. Rule text is never
# written from memory (no-hallucination rule: a wrong "Compliant" is worse than
# no verdict).


def check_manufacturer_details(
    name: Optional[str],
    address: Optional[str],
    pin_code: Optional[str],
    confidence: float,
    bbox: Optional[list] = None
) -> CheckResult:
    quoted_text = (
        "Rule 6(1)(a): Every package shall bear thereon the name and address of the manufacturer, "
        "or where the manufacturer is not the packer, the name and address of the manufacturer and packer.\n"
        "Rule 10(1): Complete address shall include the postal index number (PIN code) of six digits."
    )

    if not name and not address:
        return CheckResult(
            field="manufacturer",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-a",
            message_en="Manufacturer/packer name and address not detected with sufficient confidence. Manual review required.",
            message_hi="निर्माता/पैकर का नाम और पता पर्याप्त विश्वास के साथ नहीं मिला। मैन्युअल समीक्षा आवश्यक है।",
            suggested_fix="Verify manufacturer or packer declaration on package panel.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    # Validate 6-digit Indian PIN code (Rule 10(1))
    has_valid_pin = bool(pin_code and re.match(r"^[1-9]\d{5}$", str(pin_code)))

    if not has_valid_pin:
        if not pin_code:
            # Fail-closed per §3: the PIN was not READ, which is not proof the PIN is
            # absent from the package — OCR may have missed the address block. A
            # false NON_COMPLIANT is worse than a manual review.
            return CheckResult(
                field="manufacturer_address",
                status=Verdict.NEEDS_REVIEW,
                confidence=confidence,
                rule_ref="rule-10-1",
                message_en="Manufacturer/packer declared, but a 6-digit postal PIN code was not detected on the scanned panel. Manual review required (Rule 10(1)).",
                message_hi="निर्माता/पैकर घोषित है, लेकिन स्कैन किए गए पैनल पर 6-अंकीय पोस्टल पिन कोड नहीं मिला। मैन्युअल समीक्षा आवश्यक है (नियम 10(1))।",
                suggested_fix="Verify the complete postal address includes the 6-digit PIN code as required by Rule 10(1).",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=f"{name or ''}, {address or ''}",
                severity="MAJOR"
            )
        # PIN was positively read but has an invalid format — that is positive
        # evidence of a non-compliant declaration, so NON_COMPLIANT is warranted.
        return CheckResult(
            field="manufacturer_address",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-10-1",
            message_en=f"Manufacturer address declares PIN '{pin_code}', which is not a valid 6-digit Indian postal PIN code (Rule 10(1)).",
            message_hi=f"निर्माता के पते में पिन '{pin_code}' घोषित है, जो वैध 6-अंकीय भारतीय पोस्टल पिन कोड नहीं है (नियम 10(1))।",
            suggested_fix="Correct the declared PIN code to a valid 6-digit Indian postal PIN per Rule 10(1).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"{name or ''}, {address or ''} (PIN: {pin_code})",
            severity="MAJOR"
        )

    return CheckResult(
        field="manufacturer",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-6-1-a",
        message_en=f"Manufacturer and complete postal address with PIN {pin_code} clearly declared.",
        message_hi=f"निर्माता और पिन {pin_code} सहित पूरा डाक पता स्पष्ट रूप से घोषित है।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=f"{name or ''} (PIN: {pin_code})"
    )


def check_country_of_origin(
    country: Optional[str],
    is_imported: bool,
    confidence: float,
    bbox: Optional[list] = None
) -> CheckResult:
    quoted_text = (
        "Rule 6(1)(aa): The name of the country of origin or manufacture or assembly in case of "
        "imported products shall be mentioned on the package."
    )

    if is_imported:
        if not country or confidence < settings.OCR_CONFIDENCE_THRESHOLD:
            # Fail-closed per §3: not detected ≠ not declared — the origin may be
            # printed on a panel the photo did not capture.
            return CheckResult(
                field="country_of_origin",
                status=Verdict.NEEDS_REVIEW,
                confidence=confidence,
                rule_ref="rule-6-1-aa",
                message_en="Country of origin was not detected on the scanned panel of this imported package. Manual review required (Rule 6(1)(aa)).",
                message_hi="इस आयातित पैकेज के स्कैन किए गए पैनल पर मूल देश (Country of Origin) नहीं मिला। मैन्युअल समीक्षा आवश्यक है (नियम 6(1)(कक))।",
                suggested_fix="Verify 'Country of Origin: [Country Name]' is declared on the package as required by Rule 6(1)(aa).",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                severity="MAJOR"
            )
        if not is_known_country(country):
            # A garbled read is not proof that the declaration is missing, so an
            # unrecognised origin is routed to manual review rather than a verdict.
            return CheckResult(
                field="country_of_origin",
                status=Verdict.NEEDS_REVIEW,
                confidence=confidence,
                rule_ref="rule-6-1-aa",
                message_en=(
                    f"Country of origin read as '{country}', which is not a recognised country name "
                    "or ISO country code. Manual review required."
                ),
                message_hi=(
                    f"मूल देश '{country}' के रूप में पढ़ा गया, जो मान्य देश का नाम या ISO देश कोड नहीं है। "
                    "मैन्युअल समीक्षा आवश्यक है।"
                ),
                suggested_fix=(
                    "Verify the country of origin or manufacture against the physical package and "
                    "declare it by its standard country name."
                ),
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=str(country),
                severity="MAJOR"
            )
        return CheckResult(
            field="country_of_origin",
            status=Verdict.COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-aa",
            message_en=f"Country of origin declared: '{country}'.",
            message_hi=f"मूल देश घोषित: '{country}'।",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=country
        )

    # For domestic products, country of origin is optional
    return CheckResult(
        field="country_of_origin",
        status=Verdict.COMPLIANT,
        confidence=1.0,
        rule_ref="rule-6-1-aa",
        message_en="Country of origin not required for domestic Indian products.",
        message_hi="घरेलू भारतीय उत्पादों के लिए मूल देश की घोषणा अनिवार्य नहीं है।",
        quoted_rule_text=quoted_text,
        severity="MINOR"
    )


def check_mrp_declaration(
    mrp: Optional[float],
    has_tax_qualification: bool,
    confidence: float,
    bbox: Optional[list] = None,
    raw_text: Optional[str] = None
) -> CheckResult:
    quoted_text = (
        "Rule 6(1)(e): The retail sale price of the package shall clearly indicate that it is the "
        "maximum retail price and the price shall be accompanied by the words 'inclusive of all taxes' or in the form:\n"
        "(i) 'Maximum or Max. retail price Rs......../ ₹.......inclusive of all taxes' or 'MRP Rs......./ ₹.......incl. of all taxes'; or\n"
        "(ii) 'MRP Rs......./ ₹........inclusive of all taxes' or 'MRP Rs......./ ₹........incl. of all taxes'; or\n"
        "(iii) 'MRP Rs......./ ₹........(inclusive of all taxes)' or 'MRP Rs......./ ₹........(incl. of all taxes)'.\n"
        "Explanation I: 'Retail sale price' means the maximum price at which the commodity in packaged form may be sold to the consumer inclusive of all taxes.\n"
        "Explanation II: Price is to be rounded off to the nearest rupee or 50 paise."
    )

    if mrp is None:
        return CheckResult(
            field="mrp",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-e",
            message_en="Maximum Retail Price (MRP) not detected with high confidence. Needs manual review.",
            message_hi="अधिकतम खुदरा मूल्य (MRP) पर्याप्त विश्वास के साथ नहीं मिला। मैन्युअल समीक्षा आवश्यक है।",
            suggested_fix="Locate and verify MRP declaration on the label.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    # A price of zero (or a negative read) is not a valid retail sale price. This
    # guard exists because ₹0 previously passed the rounding and tax checks and
    # was reported as COMPLIANT — a wrong "Compliant" verdict on a price defect.
    if float(mrp) <= 0:
        return CheckResult(
            field="mrp",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-e",
            message_en=(
                f"Price read as '{mrp:g}', which is not a valid retail sale price. Explanation I requires "
                "the price at which the commodity is sold to the consumer to be declared."
            ),
            message_hi=(
                f"मूल्य '{mrp:g}' पढ़ा गया, जो वैध खुदरा विक्रय मूल्य नहीं है। स्पष्टीकरण I के अनुसार "
                "उपभोक्ता को बिक्री मूल्य घोषित होना आवश्यक है।"
            ),
            suggested_fix="Re-check the printed price and declare the actual maximum retail price greater than ₹0.00.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"₹{mrp:.2f}",
            severity="MAJOR"
        )

    # Check rounding to nearest rupee or 50 paise
    paise = round((mrp - int(mrp)) * 100)
    if paise not in [0, 50]:
        return CheckResult(
            field="mrp_rounding",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-e",
            message_en=f"MRP ₹{mrp:.2f} violates rounding rules (must be rounded to the nearest rupee or 50 paise).",
            message_hi=f"MRP ₹{mrp:.2f} गोलाई नियमों का उल्लंघन करता है (निकटतम रुपये या 50 पैसे तक होना चाहिए)।",
            suggested_fix="Round MRP to nearest ₹1 or 50 paise per Rule 6(1)(e) Explanation II.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"₹{mrp:.2f}",
            severity="MINOR"
        )

    # Check "inclusive of all taxes"
    if not has_tax_qualification:
        return CheckResult(
            field="mrp",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-e",
            message_en=f"MRP ₹{mrp:.2f} declared without mandatory 'inclusive of all taxes' (or 'incl. of all taxes') qualification.",
            message_hi=f"MRP ₹{mrp:.2f} अनिवार्य 'सभी करों सहित' ('incl. of all taxes') के बिना घोषित किया गया है।",
            suggested_fix="Ensure MRP is accompanied by 'inclusive of all taxes' or 'incl. of all taxes'.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=f"₹{mrp:.2f}",
            severity="MAJOR"
        )

    return CheckResult(
        field="mrp",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-6-1-e",
        message_en=f"MRP ₹{mrp:.2f} declared with mandatory tax qualification ('inclusive of all taxes').",
        message_hi=f"MRP ₹{mrp:.2f} अनिवार्य कर घोषणा ('सभी करों सहित') के साथ घोषित है।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=f"₹{mrp:.2f} (incl. of all taxes)"
    )


def check_mfg_date_declaration(
    date_str: Optional[str],
    category: Optional[str],
    confidence: float,
    bbox: Optional[list] = None,
    today: Optional[date] = None
) -> CheckResult:
    quoted_text = (
        "Rule 6(1)(d): The month and year in which the commodity is manufactured or pre-packed or imported "
        "shall be mentioned in the package:\n"
        "Provided that for packages containing food articles, the provisions of this clause shall not apply, "
        "but the provisions of, and the requirements specified in the Food Safety and Standards Act, 2006 "
        "(34 of 2006) and the rules made there under shall apply."
    )

    cat_lower = (category or "").lower()
    is_food = "food" in cat_lower or "beverage" in cat_lower or "snack" in cat_lower

    # A declaration that was read but cannot be interpreted, or that names a month
    # that has not happened yet, must never pass as compliant (fail closed).
    # A LOW-CONFIDENCE read is not positive evidence either: Tesseract routinely
    # turns a nutrition-table decimal into a date-shaped string, and acting on
    # that garbage produced future-date NON_COMPLIANT violations. Below the
    # threshold the read routes to manual review instead.
    if date_str and confidence >= settings.OCR_CONFIDENCE_THRESHOLD:
        parsed_date = parse_month_year(date_str)
        if parsed_date is None:
            return CheckResult(
                field="mfg_date",
                status=Verdict.NEEDS_REVIEW,
                confidence=confidence,
                rule_ref="rule-6-1-d",
                message_en=(
                    f"Month and year of manufacture read as '{date_str}', which is not a readable "
                    "month-and-year date. Manual review required."
                ),
                message_hi=(
                    f"निर्माण का महीना और वर्ष '{date_str}' पढ़ा गया, जो पढ़ने योग्य महीना-वर्ष प्रारूप नहीं है। "
                    "मैन्युअल समीक्षा आवश्यक है।"
                ),
                suggested_fix="Verify the printed month and year of manufacture/packing and correct the value if it was misread.",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=date_str,
                severity="MAJOR"
            )
        if month_index(*parsed_date) > current_month_index(today):
            return CheckResult(
                field="mfg_date",
                status=Verdict.NON_COMPLIANT,
                confidence=confidence,
                rule_ref="rule-6-1-d",
                message_en=(
                    f"Declared month and year of manufacture ({format_month_year(parsed_date)}) is in the "
                    "future, so the declaration cannot be correct."
                ),
                message_hi=(
                    f"घोषित निर्माण का महीना और वर्ष ({format_month_year(parsed_date)}) भविष्य में है, "
                    "इसलिए यह घोषणा सही नहीं हो सकती।"
                ),
                suggested_fix="Re-verify the month and year of manufacture/packing printed on the package.",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=date_str,
                severity="MAJOR"
            )

    if is_food:
        # Food articles defer date checks to FSS Act per Rule 6(1)(d) Explanation III
        if date_str and confidence >= settings.OCR_CONFIDENCE_THRESHOLD:
            return CheckResult(
                field="mfg_date",
                status=Verdict.COMPLIANT,
                confidence=confidence,
                rule_ref="rule-6-1-d",
                message_en=f"Manufacture/packing date '{date_str}' declared (under FSS Act provisions).",
                message_hi=f"निर्माण/पैकिंग तिथि '{date_str}' घोषित (FSS अधिनियम के प्रावधानों के तहत)।",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=date_str
            )
        return CheckResult(
            field="mfg_date",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-d",
            message_en="Manufacture date not detected on label. Food articles require date under FSSAI regulations.",
            message_hi="लेबल पर निर्माण तिथि नहीं मिली। खाद्य पदार्थों के लिए FSSAI नियमों के तहत तिथि आवश्यक है।",
            suggested_fix="Check package for manufacture or expiry/use-by date.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    # Non-food articles
    # Fail-closed per §3: a missing OCR read is NOT proof the declaration is
    # absent — the photo may cover a different panel. Only genuinely unreadable
    # fields go to NEEDS_REVIEW; NON_COMPLIANT is reserved for positive evidence.
    if not date_str or confidence < settings.OCR_CONFIDENCE_THRESHOLD:
        return CheckResult(
            field="mfg_date",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-d",
            message_en="Month and year of manufacture, packing or import was not detected on the scanned panel. Manual review required (Rule 6(1)(d)).",
            message_hi="स्कैन किए गए पैनल पर निर्माण, पैकिंग या आयात का महीना और वर्ष नहीं मिला। मैन्युअल समीक्षा आवश्यक है (नियम 6(1)(घ))।",
            suggested_fix="Verify the package declares month and year of manufacture/packing in format 'MM/YYYY' or 'Month YYYY'.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    return CheckResult(
        field="mfg_date",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-6-1-d",
        message_en=f"Month and year of manufacture/packing declared: '{date_str}'.",
        message_hi=f"निर्माण/पैकिंग का महीना और वर्ष घोषित: '{date_str}'।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=date_str
    )


def check_consumer_care_details(
    phone: Optional[str],
    email: Optional[str],
    confidence: float,
    bbox: Optional[list] = None
) -> CheckResult:
    quoted_text = (
        "Rule 6(2): Every package shall bear the name, address, telephone number, e-mail address of the person "
        "who can be contacted, or the office which can be contacted, in case of consumer complaints."
    )

    if not phone and not email:
        # Fail-closed per §3: not detected ≠ not declared. Most labels print
        # consumer-care contacts on a side/back panel the photo may not cover.
        return CheckResult(
            field="consumer_care",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-2",
            message_en="Consumer care contact details (telephone number and e-mail) were not detected on the scanned panel. Manual review required (Rule 6(2)).",
            message_hi="स्कैन किए गए पैनल पर उपभोक्ता सेवा संपर्क विवरण (टेलीफोन नंबर और ईमेल) नहीं मिले। मैन्युअल समीक्षा आवश्यक है (नियम 6(2))।",
            suggested_fix="Verify consumer care telephone number and e-mail address on the package as required by Rule 6(2).",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    # If at least phone or email is found
    details = []
    if phone:
        details.append(f"Phone: {phone}")
    if email:
        details.append(f"Email: {email}")

    return CheckResult(
        field="consumer_care",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-6-2",
        message_en=f"Consumer care details declared ({', '.join(details)}).",
        message_hi=f"उपभोक्ता सेवा संपर्क विवरण घोषित ({', '.join(details)})।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=", ".join(details)
    )


def check_generic_name(
    name: Optional[str],
    confidence: float,
    bbox: Optional[list] = None
) -> CheckResult:
    """Rule 6(1)(b): the common or generic name of the commodity is mandatory.

    The check reports itself as ``product_name`` because that is the extractor key
    the declaration is read into; keeping the two names identical lets the analysis
    screen attach the violation to the declaration row it belongs to.
    """
    quoted_text = (
        "Rule 6(1)(b): The common or generic names of the commodity contained in the package and in "
        "case of packages with more than one product, the name and number or quantity of each product "
        "shall be mentioned on the package."
    )

    cleaned = str(name).strip() if name not in (None, "") else ""

    if not cleaned:
        return CheckResult(
            field="product_name",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-b",
            message_en="Common or generic name of the commodity was not detected on the scanned panel. Manual review required.",
            message_hi="स्कैन किए गए पैनल पर वस्तु का सामान्य नाम नहीं मिला। मैन्युअल समीक्षा आवश्यक है।",
            suggested_fix="Read the generic commodity name (for example 'Biscuits' or 'Wheat Flour') from the principal display panel.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    if confidence < settings.OCR_CONFIDENCE_THRESHOLD:
        return CheckResult(
            field="product_name",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-b",
            message_en=(
                f"Common or generic name read as '{cleaned}' with {confidence * 100:.0f}% OCR confidence, "
                "which is below the review threshold. Manual review required."
            ),
            message_hi=(
                f"सामान्य नाम '{cleaned}' केवल {confidence * 100:.0f}% OCR विश्वास के साथ पढ़ा गया, जो समीक्षा "
                "सीमा से कम है। मैन्युअल समीक्षा आवश्यक है।"
            ),
            suggested_fix="Confirm the generic commodity name against the physical package before relying on this reading.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=cleaned,
            severity="MAJOR"
        )

    letters = re.sub(r"[^A-Za-z]", "", cleaned)
    if len(letters) < 3:
        return CheckResult(
            field="product_name",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-b",
            message_en=(
                f"'{cleaned}' is not a readable common or generic commodity name; the commodity's "
                "common name must be mentioned on the package."
            ),
            message_hi=(
                f"'{cleaned}' पढ़ने योग्य सामान्य नाम नहीं है; पैकेज पर वस्तु का सामान्य नाम अंकित होना चाहिए।"
            ),
            suggested_fix="Print the common or generic name of the commodity on the principal display panel.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=cleaned,
            severity="MAJOR"
        )

    return CheckResult(
        field="product_name",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-6-1-b",
        message_en=f"Common or generic name declared: '{cleaned}'.",
        message_hi=f"वस्तु का सामान्य नाम घोषित: '{cleaned}'।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=cleaned
    )


# Commodity categories whose contents may become unfit for human consumption, and
# which therefore fall under Rule 6(1)(da).
PERISHABLE_CATEGORY_TOKENS = (
    "food", "beverage", "snack", "dairy", "milk", "bakery", "confectionery",
    "cosmetic", "medicine", "pharma", "drug", "juice", "meat", "perishable",
)

# A declared date inside the current month counts as expiring soon.
EXPIRING_SOON_MONTHS = 1


def _is_perishable_category(category: Optional[str]) -> bool:
    cat = (category or "").lower()
    return any(token in cat for token in PERISHABLE_CATEGORY_TOKENS)


def check_best_before_declaration(
    best_before: Optional[str],
    category: Optional[str] = None,
    mfg_date_str: Optional[str] = None,
    confidence: float = 0.0,
    bbox: Optional[list] = None,
    today: Optional[date] = None,
    is_perishable: Optional[bool] = None
) -> CheckResult:
    """Rule 6(1)(da): best before / use by date for perishable commodities.

    The declared date is also ordered against the month and year of manufacture,
    because a best-before date at or before the packing date cannot be correct. A
    declaration printed as a shelf life ('6 months from packaging') is only
    resolved when the month and year of manufacture were read as well; otherwise
    the field is routed to manual review instead of being guessed.
    """
    quoted_text = (
        "Rule 6(1)(da): The 'best before' or 'use by' date, month and year shall be mentioned on the "
        "package in case of a commodity which may become unfit for human consumption after a period of time."
    )

    perishable = _is_perishable_category(category) if is_perishable is None else is_perishable
    declared = str(best_before).strip() if best_before not in (None, "") else ""

    if not declared:
        if not perishable:
            return CheckResult(
                field="best_before",
                status=Verdict.COMPLIANT,
                confidence=1.0,
                rule_ref="rule-6-1-da",
                message_en="Best before / use by date is not required for this commodity category.",
                message_hi="इस वस्तु श्रेणी के लिए 'बेस्ट बिफोर' तिथि अनिवार्य नहीं है।",
                quoted_rule_text=quoted_text,
                severity="MINOR"
            )
        return CheckResult(
            field="best_before",
            status=Verdict.NEEDS_REVIEW,
            confidence=confidence,
            rule_ref="rule-6-1-da",
            message_en=(
                "Best before / use by date, month and year was not detected on this perishable "
                "commodity. Manual review required."
            ),
            message_hi=(
                "इस शीघ्र खराब होने वाली वस्तु पर 'बेस्ट बिफोर' तिथि, महीना और वर्ष नहीं मिला। "
                "मैन्युअल समीक्षा आवश्यक है।"
            ),
            suggested_fix="Locate the printed best before / use by month and year on the package, or record it as absent.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            severity="MAJOR"
        )

    manufacture = parse_month_year(mfg_date_str)
    expiry = parse_month_year(declared)
    derived_note = ""

    if expiry is None:
        period = parse_relative_period(declared)
        if period and manufacture:
            expiry = add_period(manufacture[0], manufacture[1], period[0], period[1])
            derived_note = f" (derived from the declared shelf life '{declared}')"
        elif period:
            return CheckResult(
                field="best_before",
                status=Verdict.NEEDS_REVIEW,
                confidence=confidence,
                rule_ref="rule-6-1-da",
                message_en=(
                    f"Best before is declared as a shelf life ('{declared}'), but no readable month and "
                    "year of manufacture was detected to anchor it. Manual review required."
                ),
                message_hi=(
                    f"'बेस्ट बिफोर' अवधि ('{declared}') के रूप में घोषित है, लेकिन इसे आधार बनाने के लिए "
                    "निर्माण का महीना और वर्ष नहीं मिला। मैन्युअल समीक्षा आवश्यक है।"
                ),
                suggested_fix="Read the month and year of manufacture, then confirm the resulting best before date.",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=declared,
                severity="MAJOR"
            )
        else:
            return CheckResult(
                field="best_before",
                status=Verdict.NEEDS_REVIEW,
                confidence=confidence,
                rule_ref="rule-6-1-da",
                message_en=(
                    f"Best before declaration '{declared}' could not be read as a date, month and year. "
                    "Manual review required."
                ),
                message_hi=(
                    f"'बेस्ट बिफोर' घोषणा '{declared}' को दिनांक, महीना और वर्ष के रूप में नहीं पढ़ा जा सका। "
                    "मैन्युअल समीक्षा आवश्यक है।"
                ),
                suggested_fix="Verify the printed best before / use by date against the physical package.",
                quoted_rule_text=quoted_text,
                bbox=bbox,
                extracted_value=declared,
                severity="MAJOR"
            )

    if manufacture and month_index(*expiry) <= month_index(*manufacture):
        return CheckResult(
            field="best_before",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-da",
            message_en=(
                f"Best before / use by date {format_month_year(expiry)} is not after the declared month "
                f"and year of manufacture {format_month_year(manufacture)}."
            ),
            message_hi=(
                f"'बेस्ट बिफोर' तिथि {format_month_year(expiry)} घोषित निर्माण माह {format_month_year(manufacture)} "
                "के बाद की नहीं है।"
            ),
            suggested_fix="Re-verify the printed best before / use by date against the date of manufacture or pre-packing.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=declared,
            severity="MAJOR"
        )

    months_remaining = months_until(month_index(*expiry), today)

    if months_remaining < 0:
        return CheckResult(
            field="best_before",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-6-1-da",
            message_en=(
                f"Declared best before / use by date {format_month_year(expiry)}{derived_note} has already "
                "passed for the commodity declared as fit for consumption."
            ),
            message_hi=(
                f"घोषित 'बेस्ट बिफोर' तिथि {format_month_year(expiry)}{derived_note} बीत चुकी है।"
            ),
            suggested_fix="Verify whether the stock is still fit for sale or must be withdrawn from the shelf.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=declared,
            severity="MINOR"
        )

    expiring_note = ""
    if months_remaining < EXPIRING_SOON_MONTHS:
        expiring_note = " Best before falls within the current month — verify stock rotation."

    return CheckResult(
        field="best_before",
        status=Verdict.COMPLIANT,
        confidence=confidence,
        rule_ref="rule-6-1-da",
        message_en=f"Best before / use by date declared: {format_month_year(expiry)}{derived_note}.{expiring_note}",
        message_hi=f"'बेस्ट बिफोर' तिथि घोषित: {format_month_year(expiry)}{derived_note}।",
        quoted_rule_text=quoted_text,
        bbox=bbox,
        extracted_value=declared
    )
