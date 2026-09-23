"""Hindi OCR tests (Phase 1 completion): eng+hin language configuration.

The tesseract fallback engine must request English + Hindi language packs
(tesseract-ocr-hin is in the Docker image) and degrade to English-only when
a pack is missing — never fail the scan. Devanagari text flows into the same
deterministic field extractors; a Hindi-only label routes to NEEDS_REVIEW
(fail-closed), never a fabricated verdict.
"""


from app.config import settings
from app.services import ocr_service
from app.services.field_extractors import extract_fields_from_ocr
from app.services.ocr_service import OCRItem


def _make_engine(langs: str) -> ocr_service._TesseractEngine:
    engine = ocr_service._TesseractEngine()
    engine.langs = langs
    return engine


def test_tesseract_engine_defaults_to_english_plus_hindi():
    engine = ocr_service._TesseractEngine()
    assert "eng" in engine.langs
    assert "hin" in engine.langs


def test_ocr_languages_setting_is_respected():
    assert settings.OCR_LANGUAGES == "eng+hin"


def test_missing_hindi_pack_falls_back_to_english(monkeypatch):
    """tesseract raises when a configured pack is absent -> retry with eng."""
    import pytesseract

    engine = _make_engine("eng+hin")
    calls = []

    def _fake_image_to_data(image, output_type=None, config=None, lang=None):
        calls.append(lang)
        if lang == "eng+hin":
            raise pytesseract.TesseractError("missing", "Failed loading language 'hin'")
        # English-only call succeeds: return the DICT shape pytesseract uses.
        return {
            "text": ["MRP", "Rs.", "25.00"],
            "conf": [90, 90, 92],
            "left": [10, 60, 100],
            "top": [10, 10, 10],
            "width": [40, 30, 50],
            "height": [12, 12, 12],
        }

    monkeypatch.setattr(pytesseract, "image_to_data", _fake_image_to_data)
    import numpy as np

    results = engine(np.full((40, 160, 3), 255, dtype=np.uint8))
    assert calls == ["eng+hin", "eng"]
    assert len(results) == 3
    assert results[0][1] == "MRP"


def test_devanagari_items_flow_through_extractors():
    """Devanagari OCR items are accepted by the extractors (no crash, no loss)."""
    items = [
        OCRItem(text="अधिकतम", confidence=0.9, bbox=[[0, 0], [10, 0], [10, 10], [0, 10]]),
        OCRItem(text="खुदरा", confidence=0.88, bbox=[[12, 0], [22, 0], [22, 10], [12, 10]]),
        OCRItem(text="मूल्य", confidence=0.91, bbox=[[24, 0], [34, 0], [34, 10], [24, 10]]),
        OCRItem(text="MRP Rs. 25.00 incl. of all taxes", confidence=0.95, bbox=[[0, 14], [60, 14], [60, 24], [0, 24]]),
    ]
    data = extract_fields_from_ocr(items)
    d = data.to_dict()
    # The English MRP declaration on the label is still found despite the
    # Devanagari header; the Hindi text itself does not crash extraction.
    assert "mrp" in d
    assert d["mrp"]["value"] == 25.0


def test_hindi_only_label_yields_needs_review_fields_not_fabrication():
    """A label with no readable Rule 6(1) declarations simply yields no fields —
    the rule engine then routes NEEDS_REVIEW (fail-closed), never COMPLIANT."""
    items = [
        OCRItem(text="अधिकतम", confidence=0.9, bbox=[[0, 0], [10, 0], [10, 10], [0, 10]]),
        OCRItem(text="खुदरा", confidence=0.85, bbox=[[12, 0], [22, 0], [22, 10], [12, 10]]),
        OCRItem(text="मूल्य", confidence=0.87, bbox=[[24, 0], [34, 0], [34, 10], [24, 10]]),
    ]
    data = extract_fields_from_ocr(items)
    d = data.to_dict()
    assert d.get("mrp", {}).get("value") in (None, "")
    assert d.get("net_quantity_value", {}).get("value") in (None, "")
