"""Rule 7 Checker — Principal Display Panel Area & Minimum Letter Height (Table-I).
Rules:
- Rule 7(2) Table-I: Min letter/numeral height based on PDP area
- If package dimensions not supplied -> NEEDS_REVIEW, never guess per §3 & §8!
- Rule 7(3): Width >= 1/3 height except 1, i, I, l
- Rule 7(4): Area formulas: rectangular h*w; cylindrical 40% h*circ
"""

from typing import Optional
from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def check_letter_height_and_pdp_area(
    pdp_height_cm: Optional[float],
    pdp_width_cm: Optional[float],
    measured_glyph_height_mm: Optional[float],
    package_shape: str = "rectangular"
) -> CheckResult:
    quoted_text = (
        "Rule 7(2) Table-I: Minimum height of numerals and letters:-\n"
        "- A ≤ 50 cm²: Normal case = 1.0 mm (Blown/embossed = 1.5 mm)\n"
        "- 50 < A ≤ 100 cm²: Normal case = 1.5 mm (Blown/embossed = 3.0 mm)\n"
        "- 100 < A ≤ 500 cm²: Normal case = 2.5 mm (Blown/embossed = 4.0 mm)\n"
        "- 500 < A ≤ 2500 cm²: Normal case = 4.0 mm (Blown/embossed = 6.0 mm)\n"
        "- A > 2500 cm²: Normal case = 6.0 mm (Blown/embossed = 6.0 mm)\n"
        "Rule 7(4): Area: rectangular h×w; cylindrical 40% h×circumference."
    )

    # Per non-negotiable rule: "If package dimensions not supplied → NEEDS_REVIEW, never guess."
    if pdp_height_cm is None or pdp_width_cm is None:
        return CheckResult(
            field="letter_height",
            status=Verdict.NEEDS_REVIEW,
            confidence=0.5,
            rule_ref="rule-7-2",
            message_en="Package dimensions not provided. Principal Display Panel (PDP) area and minimum letter height cannot be calculated without physical package measurements.",
            message_hi="पैकेज के आयाम प्रदान नहीं किए गए हैं। भौतिक पैकेज माप के बिना मुख्य प्रदर्शन पैनल (PDP) क्षेत्र और न्यूनतम अक्षर ऊंचाई की गणना नहीं की जा सकती है।",
            suggested_fix="Measure physical package height and width in centimetres to verify Table-I compliance.",
            quoted_rule_text=quoted_text,
            severity="MINOR"
        )

    # Calculate PDP Area in cm² per Rule 7(4)
    if package_shape.lower() == "cylindrical":
        area = 0.40 * pdp_height_cm * pdp_width_cm
    else:
        area = pdp_height_cm * pdp_width_cm

    # Determine required minimum height from Table-I
    if area <= 50.0:
        min_required_mm = 1.0
    elif area <= 100.0:
        min_required_mm = 1.5
    elif area <= 500.0:
        min_required_mm = 2.5
    elif area <= 2500.0:
        min_required_mm = 4.0
    else:
        min_required_mm = 6.0

    if measured_glyph_height_mm is not None:
        if measured_glyph_height_mm < min_required_mm:
            return CheckResult(
                field="letter_height",
                status=Verdict.NON_COMPLIANT,
                confidence=0.90,
                rule_ref="rule-7-2",
                message_en=(
                    f"Letter/numeral height {measured_glyph_height_mm:.1f}mm is below the minimum required "
                    f"{min_required_mm}mm for PDP area {area:.1f}cm² under Rule 7(2) Table-I."
                ),
                message_hi=(
                    f"अक्षर/संख्या की ऊंचाई {measured_glyph_height_mm:.1f} मिमी नियम 7(2) तालिका-I के तहत "
                    f"PDP क्षेत्र {area:.1f} सेमी² के लिए आवश्यक न्यूनतम {min_required_mm} मिमी से कम है।"
                ),
                suggested_fix=f"Increase numeral and letter size to at least {min_required_mm}mm.",
                quoted_rule_text=quoted_text,
                severity="MAJOR",
                extracted_value=f"Area: {area:.1f}cm², Height: {measured_glyph_height_mm:.1f}mm (min {min_required_mm}mm)"
            )
        else:
            return CheckResult(
                field="letter_height",
                status=Verdict.COMPLIANT,
                confidence=0.90,
                rule_ref="rule-7-2",
                message_en=f"Letter height {measured_glyph_height_mm:.1f}mm meets Table-I requirement (min {min_required_mm}mm for area {area:.1f}cm²).",
                message_hi=f"अक्षर की ऊंचाई {measured_glyph_height_mm:.1f} मिमी तालिका-I की आवश्यकता को पूरा करती है (क्षेत्र {area:.1f} सेमी² के लिए न्यूनतम {min_required_mm} मिमी)।",
                quoted_rule_text=quoted_text,
                extracted_value=f"Area: {area:.1f}cm², Height: {measured_glyph_height_mm:.1f}mm"
            )

    return CheckResult(
        field="letter_height",
        status=Verdict.NEEDS_REVIEW,
        confidence=0.7,
        rule_ref="rule-7-2",
        message_en=f"PDP area calculated as {area:.1f}cm² (requires min {min_required_mm}mm letter height). Manual verification of font height required.",
        message_hi=f"PDP क्षेत्र की गणना {area:.1f} सेमी² के रूप में की गई (न्यूनतम {min_required_mm} मिमी अक्षर ऊंचाई की आवश्यकता है)। फ़ॉन्ट ऊंचाई का मैन्युअल सत्यापन आवश्यक है।",
        suggested_fix=f"Verify that letters/numerals on physical pack measure at least {min_required_mm}mm.",
        quoted_rule_text=quoted_text,
        severity="MINOR"
    )
