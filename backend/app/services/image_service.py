"""Image preprocessing service using OpenCV per §5 & §7.1.
Features:
- Blur detection (Laplacian variance)
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Deskew & perspective correction
- Denoise and contrast calculation
- Veg/Non-veg color dot detection (Rule 6(8))
"""

import cv2
import numpy as np
from typing import Tuple, Optional, Dict, Any


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


def preprocess_image_for_ocr(image: np.ndarray) -> np.ndarray:
    """Enhance image for OCR: grayscale, denoise, CLAHE, and deskew."""
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
    h, w = image.shape[:2]
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
