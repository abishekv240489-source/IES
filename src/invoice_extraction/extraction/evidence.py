from __future__ import annotations

import json
from collections.abc import Iterable

from invoice_extraction.domain.models import FieldCandidate


def build_evidence_package(
    candidates: Iterable[FieldCandidate], *, max_candidates: int = 40, max_chars: int = 8_000
) -> str:
    """Create a bounded Qwen input containing candidates rather than full OCR text."""
    ranked = sorted(candidates, key=lambda candidate: candidate.confidence, reverse=True)
    candidate_payloads: list[dict[str, object]] = [
        candidate.model_dump(mode="json") for candidate in ranked[:max_candidates]
    ]
    payload = {
        "instruction": (
            "Map supplied evidence to the invoice schema. Do not repair OCR or infer values."
        ),
        "candidates": candidate_payloads,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) <= max_chars:
        return encoded
    while candidate_payloads and len(encoded) > max_chars:
        candidate_payloads.pop()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encoded
