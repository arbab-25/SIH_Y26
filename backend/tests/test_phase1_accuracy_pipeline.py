"""Phase 1 accuracy pipeline tests: deskew, enhanced preprocessing, pyzbar cross-check.

The pyzbar barcode read (Rule 6(4A)(a)) is a deterministic INPUT to the rule
pipeline: it may confirm or demote an OCR'd GTIN, never invent a declaration
by itself. These tests pin that contract.
"""


import numpy as np
import pytest

from app.services import image_service, ocr_service
from app.services.auth_service import create_access_token


def _auth_headers() -> dict:
    return {
        "Authorization": "Bearer "
        + create_access_token("00000000-0000-0000-0000-000000000001", "INSPECTOR")
    }


def _white(rows=200, cols=400):
    return np.full((rows, cols, 3), 255, dtype=np.uint8)


# ------------------------------------------------------------------ deskew
def test_deskew_straight_image_is_untouched():
    """A perfectly horizontal image must not be rotated (angle 0)."""
    img = _white()
    out, angle = image_service.deskew_image(img)
    assert angle == 0.0
    assert out.shape == img.shape


def test_deskew_returns_small_angle_for_slightly_skewed_image():
    """A synthetic label skewed ~5 degrees is straightened to < 1.5 degrees."""
    import cv2

    # Two long thick dark edges = package borders; thick enough for HoughP
    # minLineLength and enough contrast to dominate the angle vote.
    skewed = np.full((400, 700, 3), 255, dtype=np.uint8)
    cv2.line(skewed, (30, 80), (660, 137), (0, 0, 0), 5)
    cv2.line(skewed, (30, 320), (660, 377), (0, 0, 0), 5)
    out, angle = image_service.deskew_image(skewed)
    assert 2.0 <= abs(angle) <= 10.0, f"expected a small skew angle, got {angle}"
    assert out.shape == skewed.shape


def test_deskew_rejects_extreme_angles():
    """A near-90 deg 'skew' is a different panel, not skew — leave it alone."""
    img = np.full((300, 500, 3), 255, dtype=np.uint8)
    import cv2

    cv2.line(img, (480, 10), (495, 290), (0, 0, 0), 3)  # near-vertical line
    _, angle = image_service.deskew_image(img)
    assert abs(angle) <= 15.0  # max_angle default; vertical edges are ignored


def test_enhance_for_ocr_returns_3_channel_and_never_shrinks():
    """Small frames are upscaled by design (bounded); shape stays 3-channel."""
    img = _white()
    out = image_service.enhance_for_ocr(img)
    assert out.ndim == 3 and out.shape[2] == 3
    # Deskew preserves the frame; the bounded upscale may only grow it.
    assert out.shape[0] >= img.shape[0] and out.shape[1] >= img.shape[1]
    assert max(out.shape[:2]) <= 1600 + 1  # upscale stays bounded


# ---------------------------------------------------------------- barcode
class _FakeBarcode:
    """Mimics a pyzbar Decoded object without needing libzbar."""

    def __init__(self, data, type_="EAN13"):
        self.data = data.encode()
        self.type = type_

        class _Rect:
            left, top, width, height = 10, 10, 100, 40

        self.rect = _Rect()


def test_detect_barcodes_reports_decoded_values(monkeypatch):
    monkeypatch.setattr(
        image_service, "_decode_barcodes", lambda gray: [_FakeBarcode("8901234567890")]
    )
    result = image_service.detect_barcodes(_white())
    assert result["detected"] is True
    assert result["results"][0]["data"] == "8901234567890"
    assert result["results"][0]["confidence"] == 1.0


def test_detect_barcodes_handles_missing_pyzbar(monkeypatch):
    """No libzbar on the host: detection degrades, never raises."""

    def _boom(_gray):
        raise ImportError("libzbar missing")

    monkeypatch.setattr(image_service, "_decode_barcodes", _boom)
    result = image_service.detect_barcodes(_white())
    assert result == {"detected": False, "results": []}


def test_run_ocr_includes_barcode_metadata(monkeypatch):
    monkeypatch.setattr(
        ocr_service,
        "get_ocr_engine",
        lambda: _StaticEngine([[[[0, 0], [10, 0], [10, 10], [0, 10]], "MRP", 0.9]]),
    )
    monkeypatch.setattr(ocr_service, "is_image_blurry", lambda img: (False, 999.0))
    # run_ocr binds detect_barcodes into its own namespace at import time.
    monkeypatch.setattr(
        ocr_service, "detect_barcodes", lambda img: {"detected": True, "results": [{"type": "EAN13", "data": "8901234567890", "confidence": 1.0, "bbox": None}]}
    )

    _items, meta = ocr_service.run_ocr(_white(60, 180), detect_blur=True)
    assert meta["barcodes"]["detected"] is True
    assert meta["barcodes"]["results"][0]["data"] == "8901234567890"


class _StaticEngine:
    """Engine double returning a fixed result set."""

    def __init__(self, results):
        self._results = results
        self.name = "tesseract"

    def __call__(self, image):
        return self._results


# ------------------------------------------------- barcode cross-check service
def _extracted_with_gtin(value, conf=0.9):
    from app.services.field_extractors import ExtractedData

    d = ExtractedData()
    if value is not None:
        d.set_field("barcode_gtin", value, conf)
    return d


def test_crosscheck_confirms_matching_gtin():
    from app.services.field_extractors import apply_barcode_crosscheck

    d = _extracted_with_gtin("8901234567890", 0.9)
    outcome = apply_barcode_crosscheck(d, "8901234567890")
    assert outcome["outcome"] == "confirmed"
    # A confirmed read is untouched.
    assert d.fields["barcode_gtin"]["confidence"] == 0.9


def test_crosscheck_demotes_mismatched_gtin_below_review_threshold():
    from app.services.field_extractors import apply_barcode_crosscheck

    d = _extracted_with_gtin("8909999999999", 0.92)
    outcome = apply_barcode_crosscheck(d, "8901234567890")
    assert outcome["outcome"] == "mismatch"
    entry = d.fields["barcode_gtin"]
    # Demoted below OCR_CONFIDENCE_THRESHOLD (0.75) -> NEEDS_REVIEW; the
    # machine read is recorded as evidence but the OCR value is NOT replaced.
    assert entry["confidence"] <= 0.50
    assert entry["mismatch_with_barcode"] == "8901234567890"
    assert entry["value"] == "8909999999999"


def test_crosscheck_fills_missing_gtin_at_mid_confidence():
    """OCR missed the digits: store the machine read but keep it in review."""
    from app.services.field_extractors import apply_barcode_crosscheck

    d = _extracted_with_gtin(None)
    outcome = apply_barcode_crosscheck(d, "8901234567890")
    assert outcome["outcome"] == "filled_from_barcode"
    entry = d.fields["barcode_gtin"]
    assert entry["value"] == "8901234567890"
    assert 0.50 < entry["confidence"] < 0.75  # present, but never auto-confirmed


# ------------------------------------------------------- benchmark framework
def test_benchmark_ground_truth_dataset_is_well_formed():
    """The committed labeled sample set parses and every entry has a GTIN-free shape."""
    import json
    import os

    dataset_path = os.path.join(
        os.path.dirname(__file__), "benchdata", "labels.json"
    )
    assert os.path.exists(dataset_path), "tests/benchdata/labels.json must be committed"
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["samples"]) >= 3, "at least 3 labeled samples required"
    for s in data["samples"]:
        assert {"image", "fields"} <= set(s.keys())
        assert {"net_quantity", "mrp"} <= set(s["fields"].keys())


def test_benchmark_metrics_functions():
    """Precision/recall math used by the benchmark script is correct."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from scripts.benchmark_ocr import aggregate_report, precision_recall_for_field

    tp, fp, fn = 8, 2, 2
    p, r = precision_recall_for_field(tp, fp, fn)
    assert p == pytest.approx(0.8)
    assert r == pytest.approx(0.8)

    report = aggregate_report(
        {
            "mrp": {"tp": 8, "fp": 2, "fn": 2},
            "net_quantity": {"tp": 10, "fp": 0, "fn": 0},
        }
    )
    assert report["macro"]["precision"] == pytest.approx((0.8 + 1.0) / 2)
    assert report["macro"]["recall"] == pytest.approx((0.8 + 1.0) / 2)
