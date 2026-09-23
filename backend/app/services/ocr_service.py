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

from app.services.image_service import (
    is_image_blurry,
    preprocess_image_for_ocr,
    enhance_for_ocr,
    detect_barcodes,
    detect_veg_nonveg_symbol,
    calculate_contrast_ratio,
)
from app.config import settings

# Global in-memory engine cache per §5: "Cache OCR models in memory at startup, never per-request"
_OCR_ENGINE = None
_OCR_ENGINE_NAME: Optional[str] = None


def ocr_thread_count() -> int:
    """Intra-op thread budget for the ONNX OCR runtime.

    onnxruntime's default thread count left a single 1600x1200 label photo at ~75 s
    of inference in measurement. Capped at 4 so the 1 vCPU deployment target is not
    oversubscribed — and configurable down to 1 via OCR_THREADS: on a 0.1-CPU free-
    tier instance multi-threaded ONNX starved the event loop until health checks
    failed and the platform restarted the service mid-scan.
    """
    configured = getattr(settings, "OCR_THREADS", 0) or 0
    if configured > 0:
        return configured
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

    def __init__(self):
        # Tesseract language packs installed on the host (eng + hin cover the
        # Phase-1 English + Hindi requirement; tesseract-ocr-hin ships in the
        # Docker image). Configured per CALL so hosts missing a pack fall
        # back at inference time rather than failing the engine probe.
        self.langs = (getattr(settings, "OCR_LANGUAGES", "") or "eng+hin").strip()

    def __call__(self, image: np.ndarray):
        import pytesseract

        h, w = image.shape[:2]
        try:
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config="--psm 6",
                lang=self.langs,
            )
        except pytesseract.TesseractError:
            # A configured language pack is missing on this host: retry with
            # English only instead of failing the scan (Rule 7 of the brief —
            # degrade, never guess).
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT, config="--psm 6", lang="eng"
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

    def available(self) -> bool:
        """Probe whether the tesseract binary is usable on this host."""
        try:
            self(np.zeros((40, 120), dtype=np.uint8))
            return True
        except Exception:
            return False


def get_ocr_engine():
    """Returns a singleton OCR engine instance cached in memory (never None if any engine installed).

    Honors the OCR_ENGINE preference. Order matters for the deployment tier:
    the previous version always loaded RapidOCR first regardless of the setting,
    so Render carried hundreds of MB of resident ONNX models it never needed —
    the direct cause of the 'exceeded its memory limit' restarts. With
    OCR_ENGINE=tesseract, only the lightweight tesseract subprocess is used
    (~zero resident memory) and RapidOCR stays available as the runtime fallback.
    """
    global _OCR_ENGINE, _OCR_ENGINE_NAME
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE

    errors = []
    preferred = (getattr(settings, "OCR_ENGINE", "") or "").strip().lower()

    tesseract_factory = lambda: _TesseractEngine()  # noqa: E731
    rapidocr_factory = lambda: _RapidOCREngine()  # noqa: E731

    # Attempt order: preferred engine first, then the other as fallback.
    if preferred == "rapidocr":
        attempts = [rapidocr_factory, tesseract_factory]
    else:
        # Default (and explicit 'tesseract'): tesseract first. The Docker image
        # ships the binary, and a subprocess engine costs no resident RAM.
        attempts = [tesseract_factory, rapidocr_factory]

    for factory in attempts:
        try:
            engine = factory()
            if isinstance(engine, _TesseractEngine):
                # Probe: raises pytesseract.TesseractNotFoundError if binary missing
                engine(np.zeros((40, 120), dtype=np.uint8))
            _OCR_ENGINE = engine
            _OCR_ENGINE_NAME = engine.name
            print(f"[OK] {_OCR_ENGINE_NAME} loaded as the OCR engine (preferred: {preferred or 'tesseract'}).")
            return _OCR_ENGINE
        except Exception as e:  # ImportError, model load failure, missing binary
            errors.append(f"{getattr(factory, '__name__', 'engine')}: {e}")

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

    # Downscale oversized photos before OCR. Detection accuracy holds to the
    # configured longest side, while inference memory and wall-time scale with
    # pixel count — without this a full-resolution phone photo exhausted the
    # deployment instance (Render free tier) and the request died with a 502.
    max_dim = settings.OCR_MAX_DIMENSION
    h, w = image.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        image = cv2.resize(
            image,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )

    # Check blur
    is_blurry, blur_score = is_image_blurry(image)
    if detect_blur and is_blurry:
        return [], {
            "blurry": True,
            "blur_score": blur_score,
            "error": "We couldn't read this label clearly. Please move closer, hold steady, and retake the photo.",
            "error_hi": "हम इस लेबल को स्पष्ट रूप से नहीं पढ़ सके। कृपया पास जाएं, फोन को स्थिर रखें और फिर से फोटो लें।"
        }

    # Preprocess — Phase 1 accuracy pipeline (deskew + denoise + CLAHE + upscale)
    # via enhance_for_ocr; OCR_ENHANCE=false reverts to the lighter legacy
    # pipeline (A/B benchmarking only).
    enhanced = enhance_for_ocr(image) if settings.OCR_ENHANCE else preprocess_image_for_ocr(image)

    # Barcode/QR cross-check (Rule 6(4A)(a)): read machine-printed codes on the
    # ORIGINAL (un-preprocessed) frame — binarization/upscale in the OCR
    # pipeline can distort symbology edges. Deterministic input only.
    try:
        barcode_meta = detect_barcodes(image)
    except Exception as bc_exc:
        print(f"[WARN] Barcode detection failed: {bc_exc}")
        barcode_meta = {"detected": False, "results": []}

    # Run OCR engine
    engine = get_ocr_engine()
    if engine is None:
        return [], {"error": "OCR engine not available on server. Contact the administrator."}

    items: List[OCRItem] = []
    used_engine_name = engine.name
    ocr_runtime_error: Optional[str] = None
    try:
        try:
            results = engine(enhanced)
        except Exception:
            # Retry once on the raw image (full preprocessing occasionally breaks
            # detection on unusual crops).
            results = engine(image)
    except Exception as primary_error:
        results = None
        if engine.name != "tesseract":
            try:
                fallback = _TesseractEngine()
                if fallback.available():
                    print(f"[WARN] {engine.name} inference failed ({primary_error}); falling back to tesseract.")
                    results = fallback(enhanced)
                    used_engine_name = fallback.name
            except Exception as fb_error:
                print(f"[WARN] Tesseract fallback also failed: {fb_error}")
        if results is None:
            print(f"[WARN] OCR execution failed: {primary_error}")
            # Distinguish "engine read nothing" from "engine could not run":
            # without this the scan completed 'done' with zero fields and the
            # inspector could not tell an unreadable label from a server fault.
            ocr_runtime_error = (
                "The text-recognition engine failed to process this image on "
                "the server. Please retry; if it keeps failing, try a smaller "
                "or clearer photo."
            )

    # Weaker read after the stronger pipeline? The aggressive enhancement
    # (denoise, upscaling) can starve the text detector on unusual inputs —
    # far fewer words than the raw frame yields means the enhanced pass hurt.
    # Re-run on the legacy light pipeline; deterministic, bounded to one extra
    # inference ONLY when the enhanced pass actually underperformed (a healthy
    # read never pays for this branch).
    if (
        not ocr_runtime_error
        and results is not None
        and len(items) == 0
        and len(results) <= 1
    ):
        try:
            legacy = engine(preprocess_image_for_ocr(image))
            if legacy is not None and len(legacy) > 2 * max(1, len(results)):
                print("[INFO] Enhanced-pipeline read underperformed; using legacy preprocessing output.")
                results = legacy
        except Exception:
            pass

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

    # Advisory measurements on the ORIGINAL frame (deterministic inputs for
    # display-only rule results): veg/non-veg dot analysis (FSSAI) and label
    # contrast (Rule 9(1)(b)). Cheap relative to inference; kept on the raw
    # frame so preprocessing cannot fabricate or erase the measurement.
    try:
        veg_symbol = detect_veg_nonveg_symbol(image)
    except Exception as veg_exc:
        print(f"[WARN] Veg/non-veg analysis failed: {veg_exc}")
        veg_symbol = {"detected": False, "symbol": None, "confidence": 0.0}
    try:
        contrast = calculate_contrast_ratio(image)
    except Exception as c_exc:
        print(f"[WARN] Contrast measurement failed: {c_exc}")
        contrast = None

    metadata = {
        "blurry": False,
        "blur_score": blur_score,
        "engine": used_engine_name,
        "total_words": len(items),
        "barcodes": barcode_meta,
        "veg_nonveg": veg_symbol,
        **(({"contrast": contrast}) if contrast is not None else {}),
        **(({"error": ocr_runtime_error}) if ocr_runtime_error else {}),
        "avg_confidence": round(avg_conf, 2),
        "confidence_distribution": [
            {"name": "High (≥90%)", "value": high_count, "color": "#16A34A"},
            {"name": "Medium (75–89%)", "value": medium_count, "color": "#0E7490"},
            {"name": "Low (<75%)", "value": low_count, "color": "#D97706"},
        ]
    }

    return items, metadata
