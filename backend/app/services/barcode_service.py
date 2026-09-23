"""Barcode / QR decoding service (pyzbar) with a deterministic GTIN cross-check.

Role in the pipeline (Rule 6(4A)(a)): a machine-decoded barcode is an
authoritative INPUT to the rule engine — it may CONFIRM or DEMOTE an OCR'd
GTIN, never invent a declaration by itself. Fail-closed semantics:

- OCR read == decoded digits  -> read confirmed, untouched.
- OCR read a DIFFERENT number -> confidence demoted below the NEEDS_REVIEW
  threshold and the mismatch recorded; never auto-corrected (the inspector
  decides which reading is right).
- OCR missed the digits       -> the machine read is stored at a deliberately
  mid confidence (0.60) so the field stays in NEEDS_REVIEW rather than
  passing as a confirmed declaration.
"""

import re
from typing import Any, Dict, List, Optional

# Confidence assigned when the barcode fills a field OCR never read: mid, so
# the value stays in NEEDS_REVIEW (threshold is 0.75) until an inspector agrees.
BARCODE_MISSING_READ_CONF = 0.60
# Maximum confidence left on an OCR value contradicted by the decode.
BARCODE_MISMATCH_MAX_CONF = 0.55

try:  # pyzbar needs the zbar shared library; degrade gracefully without it.
    from pyzbar.pyzbar import decode as _pyzbar_decode
    _PYZBAR_AVAILABLE = True
except Exception:  # pragma: no cover - depends on host libraries
    _pyzbar_decode = None
    _PYZBAR_AVAILABLE = False


def barcodes_available() -> bool:
    return _PYZBAR_AVAILABLE


def decode_barcodes(image_path: str) -> List[str]:
    """Decode 1D/2D symbologies from an image file. Returns raw data strings."""
    if not _PYZBAR_AVAILABLE:
        return []
    try:
        import cv2

        image = cv2.imread(image_path)
        if image is None:
            return []
        results = _pyzbar_decode(image)
        return [r.data.decode("utf-8", errors="replace") for r in results if r.data]
    except Exception as e:
        print(f"[WARN] Barcode decode failed for {image_path}: {e}")
        return []


def apply_barcode_crosscheck(extracted: Any, decoded_gtin: str) -> Dict[str, Any]:
    """Cross-check the OCR'd GTIN against a pyzbar-decoded barcode.

    Mutates `extracted` (an ExtractedData) per the fail-closed contract above
    and returns a JSON-serialisable outcome record for scan metadata.
    """
    entry = extracted.fields.get("barcode_gtin")
    if not isinstance(entry, dict):
        entry = {"value": None, "confidence": 0.0, "bbox": None, "source_text": None}
        extracted.fields["barcode_gtin"] = entry

    ocr_value = str(entry.get("value") or "")
    if ocr_value == decoded_gtin:
        return {"outcome": "confirmed", "decoded_gtin": decoded_gtin}
    if not ocr_value:
        entry["value"] = decoded_gtin
        entry["confidence"] = BARCODE_MISSING_READ_CONF
        entry["source"] = "barcode_decode"
        return {"outcome": "filled_from_barcode", "decoded_gtin": decoded_gtin}

    entry["confidence"] = min(float(entry.get("confidence") or 0.0), BARCODE_MISMATCH_MAX_CONF)
    entry["mismatch_with_barcode"] = decoded_gtin
    return {
        "outcome": "mismatch",
        "decoded_gtin": decoded_gtin,
        "ocr_gtin": ocr_value,
    }


def run_barcode_crosscheck(image_paths: List[str], extracted_data: Any) -> Optional[Dict[str, Any]]:
    """Decode barcodes across all uploaded panels and cross-check the OCR GTIN.

    Returns None when pyzbar is unavailable or nothing decodable was found;
    otherwise returns {"source": "pyzbar", **outcome} for scan metadata.
    """
    if not _PYZBAR_AVAILABLE:
        return None

    candidates: List[str] = []
    for path in image_paths:
        for data in decode_barcodes(path):
            if data not in candidates:
                candidates.append(data)

    decoded = next((c for c in candidates if re.fullmatch(r"\d{8,14}", c)), None)
    if not decoded:
        return None

    outcome = apply_barcode_crosscheck(extracted_data, decoded)
    print(f"[INFO] Barcode cross-check: {outcome}")
    return {"source": "pyzbar", **outcome}
