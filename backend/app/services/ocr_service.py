"""OCR Service utilizing PaddleOCR PP-OCRv4 ONNX model cached at startup.
Extracts per-word text, bounding-boxes, and confidence percentages per §5 & §7.2.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
import os

from app.services.image_service import is_image_blurry, preprocess_image_for_ocr
from app.config import settings

# Global in-memory model cache per §5: "Cache OCR models in memory at startup, never per-request"
_OCR_ENGINE = None


def get_ocr_engine():
    """Returns singleton OCR engine instance cached in memory."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _OCR_ENGINE = RapidOCR()
            print("[OK] RapidOCR (PaddleOCR PP-OCRv4) loaded into memory.")
        except Exception as e:
            print(f"[WARN] Failed to load RapidOCR: {e}. Attempting fallback.")
            _OCR_ENGINE = None
    return _OCR_ENGINE


class OCRItem:
    def __init__(self, text: str, confidence: float, bbox: list):
        self.text = text.strip()
        self.confidence = float(confidence)
        self.bbox = bbox

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence * 100, 2) if self.confidence <= 1.0 else round(self.confidence, 2),
            "confidence_ratio": round(self.confidence / 100.0 if self.confidence > 1.0 else self.confidence, 4),
            "bbox": self.bbox
        }


def run_ocr(
    image_input: Any,
    detect_blur: bool = True
) -> Tuple[List[OCRItem], Dict[str, Any]]:
    """Run OCR on image path or numpy array.
    Returns (items, metadata).
    """
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
        return [], {"error": "OCR engine not available"}

    try:
        results, elapse = engine(enhanced)
    except Exception as e:
        results, elapse = engine(image)

    items: List[OCRItem] = []
    if results:
        for box, text, score in results:
            if text and text.strip():
                items.append(OCRItem(text=text, confidence=score, bbox=box))

    # Calculate confidence distribution for Recharts pie chart (§7.2)
    # Slices: High (≥90%), Medium (75–89%), Low (<75%), Not detected
    high_count = 0
    medium_count = 0
    low_count = 0
    total_conf = 0.0

    for item in items:
        conf_pct = item.confidence * 100 if item.confidence <= 1.0 else item.confidence
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
        "total_words": len(items),
        "avg_confidence": round(avg_conf, 2),
        "confidence_distribution": [
            {"name": "High (≥90%)", "value": high_count, "color": "#16A34A"},
            {"name": "Medium (75–89%)", "value": medium_count, "color": "#0E7490"},
            {"name": "Low (<75%)", "value": low_count, "color": "#D97706"},
        ]
    }

    return items, metadata
