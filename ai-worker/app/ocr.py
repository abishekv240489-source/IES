from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pymupdf as fitz

from .config import settings
from .models import OcrPage
from .preprocessing import prepare_for_ocr


def extract_document(path: Path) -> tuple[list[OcrPage], str, list[str]]:
    warnings: list[str] = []
    if path.suffix.lower() == ".pdf":
        embedded = _embedded_pdf_text(path)
        if sum(len(page.text.strip()) for page in embedded) >= settings.embedded_text_min_chars:
            return embedded, "embedded-text", warnings
        images = _pdf_images(path)
    else:
        images = [_load_image(path)]

    try:
        pages = [_paddle_page(image, index + 1) for index, image in enumerate(images)]
        return pages, "paddleocr", warnings
    except (ImportError, RuntimeError) as exc:
        if settings.paddle_required or not settings.demo_fallback:
            raise
        warnings.append(f"OCR engine unavailable; demo text fallback used ({type(exc).__name__})")
        pages = [OcrPage(page=i + 1, text="", confidence=0, quality_score=0, used_preprocessing=False) for i in range(len(images))]
        return pages, "ocr-demo-fallback", warnings


def _embedded_pdf_text(path: Path) -> list[OcrPage]:
    pages: list[OcrPage] = []
    with fitz.open(path) as document:
        if document.page_count > settings.max_pages:
            raise ValueError(f"Document exceeds {settings.max_pages} pages")
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            density = min(len(text) / 600.0, 1.0)
            pages.append(OcrPage(page=index + 1, text=text, confidence=0.98 if text else 0,
                                 quality_score=density, used_preprocessing=False))
    return pages


def _pdf_images(path: Path) -> list[np.ndarray]:
    images: list[np.ndarray] = []
    with fitz.open(path) as document:
        if document.page_count > settings.max_pages:
            raise ValueError(f"Document exceeds {settings.max_pages} pages")
        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
            images.append(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n))
    return images


def _load_image(path: Path) -> np.ndarray:
    from PIL import Image
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


@lru_cache(maxsize=1)
def _paddle_engine():
    from paddleocr import PaddleOCR

    model_kwargs: dict[str, object] = {}
    if settings.paddle_detection_model:
        model_kwargs["text_detection_model_name"] = settings.paddle_detection_model
    if settings.paddle_recognition_model:
        model_kwargs["text_recognition_model_name"] = settings.paddle_recognition_model
    if not model_kwargs:
        model_kwargs["lang"] = settings.paddle_language
    return PaddleOCR(
        **model_kwargs,
        text_recognition_batch_size=settings.paddle_recognition_batch_size,
        text_det_limit_side_len=settings.paddle_detection_limit_side,
        text_det_limit_type=settings.paddle_detection_limit_type,
        use_doc_orientation_classify=settings.paddle_use_orientation,
        use_doc_unwarping=settings.paddle_use_unwarping,
        use_textline_orientation=settings.paddle_use_textline_orientation,
        enable_mkldnn=settings.paddle_enable_mkldnn,
    )


def _paddle_page(image: np.ndarray, page_number: int) -> OcrPage:
    prepared = prepare_for_ocr(image)
    result = _paddle_engine().predict(prepared.image)
    texts: list[str] = []
    scores: list[float] = []
    for item in result:
        payload = getattr(item, "json", item)
        if callable(payload):
            payload = payload()
        data = payload.get("res", payload) if isinstance(payload, dict) else {}
        texts.extend(str(value) for value in data.get("rec_texts", []) if str(value).strip())
        scores.extend(float(value) for value in data.get("rec_scores", []))
    confidence = sum(scores) / len(scores) if scores else 0.0
    return OcrPage(page=page_number, text="\n".join(texts), confidence=confidence,
                   quality_score=prepared.quality_score, used_preprocessing=prepared.transformed)
