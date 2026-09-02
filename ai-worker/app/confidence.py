from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .models import ExtractedField, Invoice, OcrPage

MAPPING_WEIGHT = 0.60
OCR_WEIGHT = 0.40
METHOD = "required-aware-page-harmonic-v2"


@dataclass(frozen=True)
class ConfidenceResult:
    overall: float
    mapping: float
    ocr: float
    populated_fields: int
    required: float
    required_present: int


def weighted_harmonic(mapping_confidence: float, ocr_confidence: float) -> float:
    """Combine independent confidence signals without letting either hide a weak signal."""
    mapping = _clamp(mapping_confidence)
    ocr = _clamp(ocr_confidence)
    if mapping == 0 or ocr == 0:
        return 0.0
    return round(1.0 / ((MAPPING_WEIGHT / mapping) + (OCR_WEIGHT / ocr)), 4)


def fuse_invoice_confidence(invoice: Invoice, pages: list[OcrPage]) -> ConfidenceResult:
    """Replace populated field confidence with page-aware OCR/mapping fusion scores."""
    page_scores = {page.page: _clamp(page.confidence) for page in pages}
    document_ocr = _mean(list(page_scores.values()))
    raw_mapping: list[float] = []
    fused: list[float] = []

    for field in _fields(invoice):
        if field.value in (None, ""):
            field.confidence = 0.0
            continue
        if field.source == "review":
            fused.append(_clamp(field.confidence))
            continue
        mapping_score = _clamp(field.confidence)
        ocr_score = page_scores.get(field.page, document_ocr)
        raw_mapping.append(mapping_score)
        field.confidence = weighted_harmonic(mapping_score, ocr_score)
        fused.append(field.confidence)

    required_fields = [
        invoice.header.invoiceNumber,
        invoice.header.invoiceDate,
        invoice.header.currency,
        invoice.vendor.name,
        invoice.amounts.total,
    ]
    required_scores = [field.confidence if field.value not in (None, "") else 0.0 for field in required_fields]
    required_confidence = _mean(required_scores)
    return ConfidenceResult(
        overall=round(min(_mean(fused), required_confidence), 4),
        mapping=round(_mean(raw_mapping), 4),
        ocr=round(document_ocr, 4),
        populated_fields=len(fused),
        required=round(required_confidence, 4),
        required_present=sum(field.value not in (None, "") for field in required_fields),
    )


def _fields(value: Any) -> Iterator[ExtractedField]:
    if isinstance(value, ExtractedField):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _fields(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from _fields(item)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
