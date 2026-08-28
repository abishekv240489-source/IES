import numpy as np

from app.preprocessing import estimate_quality, prepare_for_ocr


def test_quality_score_is_bounded() -> None:
    image = np.full((100, 100, 3), 128, dtype=np.uint8)
    assert 0 <= estimate_quality(image) <= 1
    prepared = prepare_for_ocr(image)
    assert 0 <= prepared.quality_score <= 1
    assert prepared.image.ndim == 3
    assert prepared.image.shape[2] == 3
