from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PreparedImage:
    image: np.ndarray
    quality_score: float
    transformed: bool


def estimate_quality(image: np.ndarray) -> float:
    """Cheap, deterministic 0..1 quality estimate based on contrast and sharpness."""
    try:
        import cv2
    except ImportError:
        return 0.5
    gray = _gray(image, cv2)
    contrast = min(float(gray.std()) / 64.0, 1.0)
    sharpness = min(float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 900.0, 1.0)
    brightness = float(gray.mean()) / 255.0
    exposure = max(0.0, 1.0 - abs(brightness - 0.68) * 1.8)
    return round(max(0.0, min(1.0, 0.35 * contrast + 0.45 * sharpness + 0.20 * exposure)), 4)


def prepare_for_ocr(image: np.ndarray) -> PreparedImage:
    try:
        import cv2
    except ImportError:
        return PreparedImage(image=image, quality_score=0.5, transformed=False)
    original_score = estimate_quality(image)
    if original_score >= 0.68:
        return PreparedImage(image=image, quality_score=original_score, transformed=False)

    gray = _gray(image, cv2)
    if min(gray.shape[:2]) < 1200:
        gray = cv2.resize(gray, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, h=8, templateWindowSize=7, searchWindowSize=21)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gray = _deskew(gray, cv2)
    prepared_score = estimate_quality(gray)
    # PaddleOCR v3's document-orientation and unwarping stages require an HWC
    # three-channel image even when the enhanced content is monochrome.
    three_channel = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    return PreparedImage(image=three_channel, quality_score=max(original_score, prepared_score), transformed=True)


def _gray(image: np.ndarray, cv2: object) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def _deskew(gray: np.ndarray, cv2: object) -> np.ndarray:
    inverted = cv2.bitwise_not(gray)
    threshold = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(threshold > 0))
    if coords.size == 0:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.15 or abs(angle) > 12:
        return gray
    height, width = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
