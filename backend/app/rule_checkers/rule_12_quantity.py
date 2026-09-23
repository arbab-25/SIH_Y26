"""Rule 12(6) Checker — Prohibition of Vague Quantity Declarations.
Vague words prohibited: 'minimum', 'not less than', 'average', 'about', 'approximately'.
"""

from typing import Optional

from app.models.scan import Verdict
from app.rule_checkers.base import CheckResult


def check_vague_quantity_words(
    vague_word_found: Optional[str],
    confidence: float,
    bbox: Optional[list] = None
) -> CheckResult:
    quoted_text = (
        "Rule 12(6): The declaration of quantity shall not contain any words such as "
        "'minimum', 'not less than', 'average', 'about', 'approximately', or similar qualifying words."
    )

    if vague_word_found:
        return CheckResult(
            field="net_quantity",
            status=Verdict.NON_COMPLIANT,
            confidence=confidence,
            rule_ref="rule-12-6",
            message_en=f"Prohibited vague quantity word '{vague_word_found}' found in quantity declaration.",
            message_hi=f"मात्रा घोषणा में प्रतिबंधित अस्पष्ट शब्द '{vague_word_found}' पाया गया।",
            suggested_fix="Declare exact net quantity without qualifying words like 'approx.', 'about', 'minimum'.",
            quoted_rule_text=quoted_text,
            bbox=bbox,
            extracted_value=vague_word_found,
            severity="MAJOR"
        )

    return CheckResult(
        field="net_quantity_qualifiers",
        status=Verdict.COMPLIANT,
        confidence=1.0,
        rule_ref="rule-12-6",
        message_en="No prohibited qualifying words (about, approx, minimum) found in quantity declaration.",
        message_hi="मात्रा घोषणा में कोई प्रतिबंधित अस्पष्ट शब्द (लगभग, न्यूनतम) नहीं पाया गया।",
        quoted_rule_text=quoted_text,
        severity="MINOR"
    )
