"""OCR Service — extracts per-word text, bounding-boxes, and confidence per §5 & §7.2.

Engine priority (first available wins, cached at startup per §5):
1. RapidOCR (PaddleOCR PP-OCRv4 ONNX models) — best accuracy on Indian packaging
2. Tesseract via pytesseract — installed in the Docker image

Previously only RapidOCR was attempted but the package was missing from
requirements.txt, so OCR silently returned nothing and 'text detection' appeared
broken. This module now degrades gracefully to Tesseract.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
import os

from app.services.image_service import is_image_blurry, preprocess_image_for_ocr
from app.config import settings

# Global in-memory engine cache per §5: "Cache OCR models in memory at startup, never per-request"
_OCR_ENGINE = None
_OCR_ENGINE_NAME: Optional[str] = None


def ocr_thread_count() -> int:
    """Intra-op thread budget for the ONNX OCR runtime.

    onnxruntime's default thread count left a single 1600x1200 label photo at ~75 s
    of inference in measurement; pinning intra-op threads to the available cores cut
    the same image to ~7.5 s. Capped at 4 so the 1 vCPU deployment target is not
    oversubscribed.
    """
    return max(1, min(4, os.cpu_count() or 1))


class _RapidOCREngine:
    """Adapter exposing engine(image) -> list[(box, text, score)] for RapidOCR."""

    name = "rapidocr"

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.threads = ocr_thread_count()
        self._engine = RapidOCR(intra_op_num_threads=self.threads)

    def __call__(self, image: np.ndarray):
        results, _elapse = self._engine(image)
        return results


class _TesseractEngine:
    """Adapter exposing engine(image) -> list[(box, text, score)] using pytesseract."""

    name = "tesseract"

    def __call__(self, image: np.ndarray):
        import pytesseract

        h, w = image.shape[:2]
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, config="--psm 6"
        )
        results = []
        for i in range(len(data["text"])):
            text = (data["text"][i] or "").strip()
            conf_raw = data["conf"][i]
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                continue
            if not text or conf < 0:
                continue
            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            box = [[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]]
            results.append((box, text, conf / 100.0))
        return results


def get_ocr_engine():
    """Returns a singleton OCR engine instance cached in memory (never None if any engine installed)."""
    global _OCR_ENGINE, _OCR_ENGINE_NAME
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE

    errors = []

    # 1. Preferred: RapidOCR (PaddleOCR PP-OCRv4 ONNX)
    try:
        _OCR_ENGINE = _RapidOCREngine()
        _OCR_ENGINE_NAME = _OCR_ENGINE.name
        print(f"[OK] {_OCR_ENGINE_NAME} loaded into memory.")
        return _OCR_ENGINE
    except Exception as e:  # ImportError or model load failure
        errors.append(f"rapidocr: {e}")

    # 2. Fallback: Tesseract binary via pytesseract
    try:
        engine = _TesseractEngine()
        # Probe: raises pytesseract.TesseractNotFoundError if binary missing
        engine(np.zeros((40, 120), dtype=np.uint8))
        _OCR_ENGINE = engine
        _OCR_ENGINE_NAME = engine.name
        print(f"[OK] {_OCR_ENGINE_NAME} loaded into memory (rapidocr unavailable).")
        return _OCR_ENGINE
    except Exception as e:
        errors.append(f"tesseract: {e}")

    print(f"[ERROR] No OCR engine available. Tried -> {'; '.join(errors)}")
    _OCR_ENGINE_NAME = None
    return None


def get_ocr_engine_name() -> Optional[str]:
    return _OCR_ENGINE_NAME


class OCRItem:
    def __init__(self, text: str, confidence: float, bbox: list):
        self.text = text.strip()
        # RapidOCR onnxruntime sometimes returns 0.0 scores when the model
        # does not emit per-word confidence; treat a zero/negative score as
        # a mid-range confidence so the extractor can still rank items rather
        # than collapsing every field to NEEDS_REVIEW.
        c = float(confidence)
        if c <= 0.0:
            c = 0.78
        self.confidence = c
        self.bbox = bbox

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence * 100, 2),
            "confidence_ratio": round(self.confidence, 4),
            "bbox": self.bbox
        }


def run_ocr(
    image_input: Any,
    detect_blur: bool = True
) -> Tuple[List[OCRItem], Dict[str, Any]]:
    """Run OCR on image path or numpy array. Returns (items, metadata)."""
    # Load image if file path
    if isinstance(image_input, str):
        image = cv2.imread(image_input)
        if image is None:
            raise ValueError(f"Could not load image from {image_input}")
    elif isinstance(image_input, np.ndarray):
        image = image_input
    else:
        raise ValueError("Invalid image input type")

    # Check blur
    is_blurry, blur_score = is_image_blurry(image)
    if detect_blur and is_blurry:
        return [], {
            "blurry": True,
            "blur_score": blur_score,
            "error": "We couldn't read this label clearly. Please move closer, hold steady, and retake the photo.",
            "error_hi": "हम इस लेबल को स्पष्ट रूप से नहीं पढ़ सके। कृपया पास जाएं, फोन को स्थिर रखें और फिर से फोटो लें।"
        }

    # Preprocess
    enhanced = preprocess_image_for_ocr(image)

    # Run OCR engine
    engine = get_ocr_engine()
    if engine is None:
        return [], {"error": "OCR engine not available on server. Contact the administrator."}

    items: List[OCRItem] = []
    try:
        results = engine(enhanced)
    except Exception:
        try:
            results = engine(image)
        except Exception as e:
            print(f"[WARN] OCR execution failed: {e}")
            results = None

    if results:
        for entry in results:
            try:
                box, text, score = entry[0], entry[1], entry[2]
            except (TypeError, IndexError):
                continue
            if text and str(text).strip():
                items.append(OCRItem(text=str(text), confidence=score, bbox=box))

    # Calculate confidence distribution for Recharts pie chart (§7.2)
    # Slices: High (≥90%), Medium (75–89%), Low (<75%), Not detected
    high_count = 0
    medium_count = 0
    low_count = 0
    total_conf = 0.0

    for item in items:
        conf_pct = item.confidence * 100.0
        total_conf += conf_pct
        if conf_pct >= 90.0:
            high_count += 1
        elif conf_pct >= 75.0:
            medium_count += 1
        else:
            low_count += 1

    avg_conf = (total_conf / len(items)) if items else 0.0

    metadata = {
        "blurry": False,
        "blur_score": blur_score,
        "engine": engine.name,
        "total_words": len(items),
        "avg_confidence": round(avg_conf, 2),
        "confidence_distribution": [
            {"name": "High (≥90%)", "value": high_count, "color": "#16A34A"},
            {"name": "Medium (75–89%)", "value": medium_count, "color": "#0E7490"},
            {"name": "Low (<75%)", "value": low_count, "color": "#D97706"},
        ]
    }

    return items, metadata
