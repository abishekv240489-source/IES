import pytest

from app.confidence import fuse_invoice_confidence, weighted_harmonic
from app.models import Invoice, OcrPage


def page(number: int, confidence: float) -> OcrPage:
    return OcrPage(
        page=number,
        text="invoice text",
        confidence=confidence,
        quality_score=0.9,
        used_preprocessing=False,
    )


def test_weighted_harmonic_uses_both_signals_conservatively() -> None:
    assert weighted_harmonic(0.8, 0.9) == pytest.approx(0.8372)
    assert weighted_harmonic(0.99, 0.2) < 0.5
    assert weighted_harmonic(0.0, 0.9) == 0.0


def test_fusion_is_page_aware_and_penalizes_missing_required_fields() -> None:
    invoice = Invoice()
    invoice.header.invoiceNumber.value = "INV-100"
    invoice.header.invoiceNumber.confidence = 0.9
    invoice.header.invoiceNumber.source = "qwen"
    invoice.header.invoiceNumber.page = 2
    invoice.header.currency.value = "USD"
    invoice.header.currency.confidence = 0.9
    invoice.header.currency.source = "qwen"
    invoice.header.currency.page = 1

    result = fuse_invoice_confidence(invoice, [page(1, 0.95), page(2, 0.50)])

    assert invoice.header.invoiceNumber.confidence < invoice.header.currency.confidence
    assert invoice.header.dueDate.confidence == 0.0
    assert result.mapping == 0.9
    assert result.ocr == pytest.approx(0.725)
    assert result.populated_fields == 2
    expected_required = (invoice.header.invoiceNumber.confidence + invoice.header.currency.confidence) / 5
    assert result.required == pytest.approx(expected_required, abs=0.0001)
    assert result.required_present == 2
    assert result.overall == pytest.approx(expected_required, abs=0.0001)


def test_reviewed_confidence_is_not_reduced_by_ocr() -> None:
    invoice = Invoice()
    invoice.notes.value = "confirmed"
    invoice.notes.confidence = 1.0
    invoice.notes.source = "review"

    result = fuse_invoice_confidence(invoice, [page(1, 0.1)])

    assert invoice.notes.confidence == 1.0
    assert result.overall == 0.0
