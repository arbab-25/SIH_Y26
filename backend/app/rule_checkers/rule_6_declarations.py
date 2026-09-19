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
from typing import Optional, Dict, Any
from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult
from app.config import settings


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
        "Rule 6(1)(e): Maximum Retail Price (MRP) shall be accompanied by the words 'inclusive of all taxes' "
        "or in permitted forms:\n"
        "(i) 'Maximum or Max. retail price Rs......../ ₹.......inclusive of all taxes' or 'MRP Rs......./ ₹.......incl. of all taxes';\n"
        "(ii) 'MRP Rs......./ ₹........inclusive of all taxes' or 'MRP Rs......./ ₹........incl. of all taxes';\n"
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
    bbox: Optional[list] = None
) -> CheckResult:
    quoted_text = (
        "Rule 6(1)(d): The month and year in which the commodity is manufactured or pre-packed or imported "
        "shall be mentioned on the package:\n"
        "Provided that for packages containing food articles, the provisions of this clause shall not apply, "
        "but the provisions of the Food Safety and Standards Act, 2006 shall apply."
    )

    cat_lower = (category or "").lower()
    is_food = "food" in cat_lower or "beverage" in cat_lower or "snack" in cat_lower

    if is_food:
        # Food articles defer date checks to FSS Act per Rule 6(1)(d) Explanation III
        if date_str:
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
