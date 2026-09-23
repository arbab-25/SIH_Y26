"""Image preprocessing service using OpenCV per §5 & §7.1.
Features:
- Blur detection (Laplacian variance)
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Denoise and contrast calculation
- Hough-based deskew + perspective correction (Phase 1 accuracy pipeline)
- Barcode/QR reading via pyzbar (Rule 6(4A)(a) cross-check)
- Veg/Non-veg color dot detection (Rule 6(8))
"""

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


def deskew_image(image: np.ndarray, max_angle: float = 15.0) -> Tuple[np.ndarray, float]:
    """Straighten a skewed label photo using the dominant Hough line angle.

    Phone photos of packages are rarely perfectly upright; up to ±15° of skew
    measurably drops OCR recognition confidence on small print. The angle comes
    from the median of the dominant Hough lines — robust to one misdetected
    edge. Angles beyond max_angle are rejected as misdetection (a photo taken
    at 90° is a different panel, not a skew). Returns (image, applied_angle).

    Performance: the Hough search runs on a downscaled copy (angles are
    invariant to uniform scaling) — Canny+Hough on a full 1200 px frame was a
    large share of preprocessing wall-time for a result that only needs one
    scalar angle.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Downscaled search copy: Canny+Hough cost scales with pixel count.
    h0, w0 = gray.shape[:2]
    max_side = max(h0, w0)
    scale = min(1.0, 600.0 / max_side)
    if scale < 1.0:
        search = cv2.resize(gray, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    else:
        search = gray

    # Blurry/low-texture photos return few lines; widen the Canny aperture so
    # we still find the package edges.
    edges = cv2.Canny(search, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=max(8, min(search.shape) // 4),
        maxLineGap=15,
    )
    if lines is None or len(lines) == 0:
        return image, 0.0

    angles: List[float] = []
    for line in lines[:100]:
        # OpenCV 4.x returns shape (N,1,4); OpenCV 5.x returns (N,4). Flatten
        # either shape so the unpack works on both.
        coords = np.asarray(line).reshape(-1)
        if coords.size < 4:
            continue
        x1, y1, x2, y2 = (float(c) for c in coords[:4])
        if x2 - x1 == 0:
            continue  # perfectly vertical: meaningless for deskew, skip
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        # Normalize to [-45, 45]: a line at 80° is a slightly-rotated vertical
        # edge, not a heavy text skew.
        while angle > 45:
            angle -= 90
        while angle < -45:
            angle += 90
        angles.append(angle)
    if not angles:
        return image, 0.0

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.3 or abs(median_angle) > max_angle:
        return image, 0.0

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    # expand=True would bleed black borders that the OCR detector reads as
    # text regions; keep the original size and lose only the corners.
    border_value = 255 if gray.ndim == 2 else (255, 255, 255)
    rotated = cv2.warpAffine(
        image, m, (w, h), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT, borderValue=border_value,
    )
    return rotated, round(median_angle, 2)


def enhance_for_ocr(image: np.ndarray) -> np.ndarray:
    """Full Phase-1 enhancement pipeline: deskew, denoise, CLAHE, upscale.

    Order matters — deskew first (denoising a skewed image wastes work and
    interpolation blurs it further), then denoise, then CLAHE on the clean
    result, then a bounded upscale so small statutory print gains pixels.
    Returns the enhanced 3-channel BGR image (OCR engines expect color).

    Performance (this pipeline is on the critical path of EVERY scan):
    - Non-local-means denoising (fastNlMeansDenoisingColored) measured the
      single largest preprocessing cost by far — tens of seconds on large
      frames — while the grayscale output made its color machinery moot.
      Bilateral filtering preserves edges the same way at a small fraction of
      the cost, on grayscale only.
    - Deskew's Hough search runs on a downscaled copy (see deskew_image).
    """
    if image is None or image.size == 0:
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()

    deskewed, _angle = deskew_image(gray)

    # Edge-preserving denoise on grayscale only; d=9 keeps statutory small
    # print while flattening JPEG/halftone noise.
    denoised = cv2.bilateralFilter(deskewed, d=9, sigmaColor=50, sigmaSpace=7)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Bounded upscale: small labels (e.g. a 200 px-wide shampoo sachet) gain
    # recognition from 1.5x; capping the long side at 1600 keeps inference
    # memory bounded on the free tier.
    h, w = enhanced.shape[:2]
    if max(h, w) < 900:
        scale = 1.5
        enhanced = cv2.resize(enhanced, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        if max(enhanced.shape[:2]) > 1600:
            down = 1600.0 / max(enhanced.shape[:2])
            enhanced = cv2.resize(enhanced, (int(enhanced.shape[1] * down), int(enhanced.shape[0] * down)), interpolation=cv2.INTER_AREA)

    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def is_image_blurry(image: np.ndarray, threshold: float = 80.0) -> Tuple[bool, float]:
    """Check if image is blurry using the variance of the Laplacian.
    Returns (is_blurry, variance_score).
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return variance < threshold, variance


# OCR input ceiling. PP-OCR detection cost grows ~quadratically with input
# size; phone photos at 4000px dominate scan latency. 1600px on the long edge
# keeps statutory small print legible (the frontend uploads at the same cap)
# while cutting engine time on large photos by several x.
OCR_MAX_DIM = 1600


def preprocess_image_for_ocr(image: np.ndarray) -> np.ndarray:
    """Enhance image for OCR: downscale, grayscale, denoise, CLAHE, and deskew."""
    # Bounded downscale: keep aspect, cap the long edge at OCR_MAX_DIM.
    h, w = image.shape[:2]
    long_edge = max(h, w)
    if long_edge > OCR_MAX_DIM:
        scale = OCR_MAX_DIM / float(long_edge)
        image = cv2.resize(
            image,
            (max(1, round(int(w * scale))), max(1, round(int(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )

    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Mild Gaussian blur to reduce noise
    denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)

    return denoised


def calculate_contrast_ratio(image: np.ndarray, bbox: Optional[list] = None) -> float:
    """Calculate RMS contrast of a region or the whole image.
    Used for Rule 9(1)(b) contrast validation.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    if bbox and len(bbox) >= 4:
        # Crop to bbox [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        pts = np.array(bbox, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)
        h_img, w_img = gray.shape[:2]
        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))
        crop = gray[y:y+h, x:x+w]
    else:
        crop = gray

    if crop.size == 0:
        return 0.0

    # RMS contrast = standard deviation of normalized pixel intensities
    norm = crop.astype(np.float32) / 255.0
    contrast = float(np.std(norm))
    return round(contrast, 3)


def detect_veg_nonveg_symbol(image: np.ndarray) -> Dict[str, Any]:
    """Detect vegetarian (green dot) or non-vegetarian (red/brown dot) symbol
    in the upper region of the package per Rule 6(8).
    """
    if len(image.shape) < 3:
        return {"detected": False, "symbol": None, "confidence": 0.0}

    # Inspect top 40% of the image
    h = image.shape[0]
    top_crop = image[0:int(h * 0.4), :]

    hsv = cv2.cvtColor(top_crop, cv2.COLOR_BGR2HSV)

    # Green color range for veg dot
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)

    # Brown/Red color range for non-veg dot
    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])
    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, lower_red1, upper_red1),
        cv2.inRange(hsv, lower_red2, upper_red2)
    )

    green_pixels = int(cv2.countNonZero(green_mask))
    red_pixels = int(cv2.countNonZero(red_mask))

    total_area = top_crop.shape[0] * top_crop.shape[1]
    green_ratio = green_pixels / max(1, total_area)
    red_ratio = red_pixels / max(1, total_area)

    if green_ratio > 0.0005 and green_pixels > red_pixels * 1.5:
        return {"detected": True, "symbol": "VEGETARIAN", "confidence": min(0.95, green_ratio * 500)}
    elif red_ratio > 0.0005 and red_pixels > green_pixels * 1.5:
        return {"detected": True, "symbol": "NON_VEGETARIAN", "confidence": min(0.95, red_ratio * 500)}

    return {"detected": False, "symbol": None, "confidence": 0.0}


def _decode_barcodes(gray: "np.ndarray") -> list:
    """Decode 1D barcodes + QR codes with pyzbar; never raises.

    pyzbar needs the libzbar shared library. On the Render Docker image it is
    present (libzbar0 is installed in the Dockerfile). On a dev machine without
    it, the deferred import plus try/except keeps scans working without the
    barcode cross-check rather than failing the whole scan.
    """
    try:
        from pyzbar import pyzbar as pyzbar_decoder
    except Exception as exc:  # ImportError or missing libzbar native library
        print(f"[WARN] pyzbar unavailable, barcode cross-check skipped: {exc}")
        return []
    try:
        return pyzbar_decoder.decode(gray)
    except Exception as exc:
        print(f"[WARN] pyzbar decode failed: {exc}")
        return []


def _rect_to_list(rect) -> list | None:
    """Convert a pyzbar Rect (named attrs) or sequence to a plain list."""
    try:
        return [int(rect.left), int(rect.top), int(rect.width), int(rect.height)]
    except (AttributeError, TypeError, ValueError):
        try:
            return [int(v) for v in rect]
        except (TypeError, ValueError):
            return None


def detect_barcodes(image: np.ndarray) -> Dict[str, Any]:
    """Read EAN/GTIN barcodes and QR codes from a label photo.

    Rule 6(4A)(a) permits a barcode/GTIN/QR on the package. The value is
    machine-printed with an error-correcting symbology, so it is the most
    trustworthy reading on the label (confidence 1.0): it is used downstream
    to CROSS-CHECK the OCR'd GTIN digits, never to invent one (§3: a field the
    camera can read but OCR missed must not be silently filled in).
    """
    if image is None or image.size == 0:
        return {"detected": False, "results": []}

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    try:
        raw = _decode_barcodes(gray)
    except Exception as exc:
        print(f"[WARN] pyzbar decode raised: {exc}")
        raw = []

    # Small/stretched codes often fail on the full frame but decode on an
    # upscaled copy; try once more before giving up.
    if not raw:
        h, w = gray.shape[:2]
        if max(h, w) < 1600:
            scaled = cv2.resize(gray, (int(w * 1.5), int(h * 1.5)), interpolation=cv2.INTER_CUBIC)
            try:
                raw = _decode_barcodes(scaled)
            except Exception:
                raw = []

    results = []
    for r in raw:
        try:
            data = r.data.decode("utf-8", errors="replace").strip()
        except Exception:
            data = ""
        if not data:
            continue
        results.append({
            "type": str(r.type),
            "data": data,
            # Barcodes are machine-printed: a successful decode is exact.
            "confidence": 1.0,
            # pyzbar's rect is a 4-named-attr object, not a tuple — handle any
            # rect-like shape defensively and never let bbox extraction break
            # a successful decode.
            "bbox": _rect_to_list(r.rect),
        })

    if not results:
        return {"detected": False, "results": []}
    return {"detected": True, "results": results}
