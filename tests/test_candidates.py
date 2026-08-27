import json

from invoice_extraction.domain.models import CandidateKind, OcrToken
from invoice_extraction.extraction import build_evidence_package, extract_candidates


def _token(text: str, x0: float, x1: float, *, y: float = 10) -> OcrToken:
    return OcrToken(text=text, confidence=0.97, page=1, x0=x0, y0=y, x1=x1, y1=y + 10)


def test_extracts_label_adjacent_candidates_without_a_template() -> None:
    candidates = extract_candidates(
        [
            _token("Invoice No", 10, 70),
            _token("INV-1042", 90, 150),
            _token("Total", 10, 50, y=40),
            _token("USD 1,250.00", 90, 170, y=40),
        ]
    )
    by_kind = {candidate.kind: candidate for candidate in candidates}
    assert by_kind[CandidateKind.INVOICE_NUMBER].normalized_value == "INV-1042"
    assert by_kind[CandidateKind.TOTAL].normalized_value == "1250.00"


def test_evidence_package_is_bounded_and_machine_readable() -> None:
    candidates = extract_candidates([_token("Total", 10, 50), _token("100.00", 90, 140)])
    evidence = build_evidence_package(candidates, max_chars=500)
    assert len(evidence) <= 500
    assert json.loads(evidence)["candidates"][0]["kind"] == "total"


def test_extracts_sop_banking_and_charge_fields() -> None:
    candidates = extract_candidates(
        [
            _token("SWIFT", 10, 50),
            _token("ABCDINBB", 90, 150),
            _token("Freight", 10, 60, y=40),
            _token("USD 25.00", 90, 155, y=40),
        ]
    )
    by_kind = {candidate.kind: candidate for candidate in candidates}
    assert by_kind[CandidateKind.SWIFT].normalized_value == "ABCDINBB"
    assert by_kind[CandidateKind.FREIGHT].normalized_value == "25.00"
