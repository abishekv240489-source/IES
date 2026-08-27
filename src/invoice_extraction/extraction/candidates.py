from __future__ import annotations

import re
from collections.abc import Iterable

from invoice_extraction.domain.models import CandidateKind, FieldCandidate, OcrToken
from invoice_extraction.normalization import normalize_date, normalize_identifier, normalize_money

_LABELS: tuple[tuple[CandidateKind, re.Pattern[str]], ...] = (
    (CandidateKind.SUPPLIER_NAME, re.compile(r"\b(?:supplier|vendor|from)\b", re.I)),
    (CandidateKind.CUSTOMER_NAME, re.compile(r"\b(?:customer|bill\s*to|sold\s*to)\b", re.I)),
    (CandidateKind.INVOICE_NUMBER, re.compile(r"\b(?:invoice|inv)\s*(?:no|number|#)\b", re.I)),
    (CandidateKind.INVOICE_DATE, re.compile(r"\b(?:invoice\s*)?date\b", re.I)),
    (CandidateKind.DUE_DATE, re.compile(r"\bdue\s*date\b", re.I)),
    (
        CandidateKind.PURCHASE_ORDER,
        re.compile(r"\b(?:purchase\s*order|p\.?o\.?)\s*(?:no|#)?\b", re.I),
    ),
    (CandidateKind.BOOKING_NUMBER, re.compile(r"\bbooking\s*(?:no|number|#)?\b", re.I)),
    (CandidateKind.AMOUNT_DUE, re.compile(r"\b(?:amount|balance)\s*due\b", re.I)),
    (CandidateKind.SUBTOTAL, re.compile(r"\bsub\s*total\b", re.I)),
    (CandidateKind.TAX, re.compile(r"\b(?:tax|vat|gst)\b", re.I)),
    (CandidateKind.DISCOUNT, re.compile(r"\bdiscount\b", re.I)),
    (CandidateKind.FREIGHT, re.compile(r"\b(?:freight|shipping)\b", re.I)),
    (CandidateKind.INSURANCE, re.compile(r"\binsurance\b", re.I)),
    (CandidateKind.TOTAL, re.compile(r"\b(?:grand\s*)?total\b", re.I)),
    (CandidateKind.PAYMENT_TERMS, re.compile(r"\bpayment\s*terms?\b", re.I)),
    (CandidateKind.BANK_NAME, re.compile(r"\bbank\s*(?:name)?\b", re.I)),
    (CandidateKind.ACCOUNT_NAME, re.compile(r"\baccount\s*name\b", re.I)),
    (CandidateKind.ACCOUNT_NUMBER, re.compile(r"\baccount\s*(?:no|number|#)\b", re.I)),
    (CandidateKind.IBAN, re.compile(r"\biban\b", re.I)),
    (CandidateKind.SWIFT, re.compile(r"\b(?:swift|bic)\b", re.I)),
)


def _same_line(left: OcrToken, right: OcrToken) -> bool:
    left_height = max(left.y1 - left.y0, 1.0)
    right_height = max(right.y1 - right.y0, 1.0)
    return abs((left.y0 + left.y1) / 2 - (right.y0 + right.y1) / 2) <= max(
        left_height, right_height
    )


def _normalize(kind: CandidateKind, value: str) -> str | None:
    if kind in {CandidateKind.INVOICE_DATE, CandidateKind.DUE_DATE}:
        return normalize_date(value)
    if kind in {
        CandidateKind.SUBTOTAL,
        CandidateKind.TAX,
        CandidateKind.DISCOUNT,
        CandidateKind.FREIGHT,
        CandidateKind.INSURANCE,
        CandidateKind.TOTAL,
        CandidateKind.AMOUNT_DUE,
    }:
        parsed = normalize_money(value)
        return format(parsed[0], "f") if parsed else None
    if kind in {
        CandidateKind.INVOICE_NUMBER,
        CandidateKind.PURCHASE_ORDER,
        CandidateKind.BOOKING_NUMBER,
        CandidateKind.ACCOUNT_NUMBER,
        CandidateKind.IBAN,
        CandidateKind.SWIFT,
    }:
        return normalize_identifier(value)
    return value.strip(" :")


def extract_candidates(tokens: Iterable[OcrToken]) -> list[FieldCandidate]:
    """Find label-adjacent values using OCR geometry, not vendor templates."""
    ordered = sorted(tokens, key=lambda token: (token.page, token.y0, token.x0))
    candidates: list[FieldCandidate] = []
    for index, label_token in enumerate(ordered):
        matching_kind = next(
            (kind for kind, pattern in _LABELS if pattern.search(label_token.text)), None
        )
        if matching_kind is None:
            continue
        nearby = [
            token
            for token in ordered[index + 1 : index + 8]
            if token.page == label_token.page
            and _same_line(label_token, token)
            and token.x0 >= label_token.x0
        ]
        for value_token in nearby:
            normalized = _normalize(matching_kind, value_token.text)
            if normalized:
                candidates.append(
                    FieldCandidate(
                        kind=matching_kind,
                        raw_value=value_token.text,
                        normalized_value=normalized,
                        confidence=min(label_token.confidence, value_token.confidence),
                        page=label_token.page,
                        evidence=f"{label_token.text}: {value_token.text}",
                    )
                )
                break
    return candidates
