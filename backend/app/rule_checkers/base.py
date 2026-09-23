"""Base classes and data models for deterministic Legal Metrology rule checkers."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.models.scan import Verdict


@dataclass
class CheckResult:
    field: str
    status: Verdict  # COMPLIANT, NON_COMPLIANT, NEEDS_REVIEW
    confidence: float
    rule_ref: str
    message_en: str
    message_hi: str
    suggested_fix: Optional[str] = None
    quoted_rule_text: Optional[str] = None
    severity: str = "MAJOR"  # MAJOR or MINOR
    bbox: Optional[list] = None
    extracted_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "status": self.status.value,
            "confidence": round(self.confidence, 2),
            "rule_ref": self.rule_ref,
            "message_en": self.message_en,
            "message_hi": self.message_hi,
            "suggested_fix": self.suggested_fix,
            "quoted_rule_text": self.quoted_rule_text,
            "severity": self.severity,
            "bbox": self.bbox,
            "extracted_value": self.extracted_value
        }
