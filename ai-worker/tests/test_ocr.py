from pathlib import Path

import numpy as np

from app import ocr
from app.models import OcrPage


def test_mixed_pdf_uses_embedded_text_and_ocrs_only_sparse_pages(monkeypatch) -> None:
    embedded = [
        OcrPage(page=1, text="A" * 200, confidence=0.98, quality_score=1.0, used_preprocessing=False),
        OcrPage(page=2, text="", confidence=0.0, quality_score=0.0, used_preprocessing=False),
    ]
    requested: list[int] = []

    monkeypatch.setattr(ocr, "_embedded_pdf_text", lambda _path: embedded)

    def images(_path, page_numbers):
        requested.extend(page_numbers)
        return [(2, np.zeros((10, 10, 3), dtype=np.uint8))]

    monkeypatch.setattr(ocr, "_pdf_images", images)
    monkeypatch.setattr(
        ocr,
        "_paddle_page",
        lambda _image, page: OcrPage(
            page=page, text="scanned page text", confidence=0.91, quality_score=0.8, used_preprocessing=True
        ),
    )

    pages, engine, warnings = ocr.extract_document(Path("mixed.pdf"))

    assert requested == [2]
    assert engine == "embedded-text+paddleocr"
    assert warnings == []
    assert pages[0].text == "A" * 200
    assert pages[1].text == "scanned page text"
