from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from evaluation.import_audit_reviews import _ensure_private_output, convert


def _field(value):
    return {"value": value, "confidence": 0.9, "source": "paddleocr", "page": 1}


def _audit(tmp_path: Path, *, outcome: str = "INCORRECT", corrected="INV-002") -> Path:
    source = b"private invoice bytes"
    extraction = {
        "header": {"invoiceNumber": _field("INV-OO2"), "currency": _field("USD")},
        "lineItems": [{"description": _field("Agency service"), "amount": _field(100)}],
    }
    reviews = [
        {"fieldPath": "header.invoiceNumber", "extractedValue": "INV-OO2", "outcome": outcome,
         "correctedValue": corrected, "notes": ""},
        {"fieldPath": "header.currency", "extractedValue": "USD", "outcome": "CORRECT",
         "correctedValue": None, "notes": ""},
        {"fieldPath": "lineItems.0.description", "extractedValue": "Agency service", "outcome": "CORRECT",
         "correctedValue": None, "notes": ""},
        {"fieldPath": "lineItems.0.amount", "extractedValue": 100, "outcome": "CORRECT",
         "correctedValue": None, "notes": ""},
    ]
    manifest = {
        "invoice": {"jobId": "job-1", "sourceSha256": hashlib.sha256(source).hexdigest(),
                    "status": "COMPLETED", "extractionEngine": "paddleocr", "overallConfidence": 0.9},
        "files": {"sourceInvoice": "invoices/001/source/invoice.pdf"},
    }
    archive = tmp_path / "audit.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("invoices/001/source/invoice.pdf", source)
        output.writestr("invoices/001/manifest.json", json.dumps(manifest))
        output.writestr("invoices/001/extracted-fields.json", json.dumps(extraction))
        output.writestr("invoices/001/review-template.json", json.dumps({
            "schemaVersion": "ies.audit-review.v1", "fieldReviews": reviews,
        }))
    return archive


def test_completed_review_becomes_private_benchmark(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    summary = convert(_audit(tmp_path), output, "scan_clean", "services")
    assert summary == {"documents": 1, "correct": 3, "incorrect": 1, "notApplicable": 0}
    truth = json.loads((output / "ground_truth/job-1.json").read_text())
    assert truth["header"]["invoiceNumber"] == "INV-002"
    assert truth["lineItems"][0]["amount"] == 100
    assert (output / "documents/job-1.pdf").read_bytes() == b"private invoice bytes"
    assert json.loads((output / "dataset.json").read_text())["release_holdout"] is False


def test_incomplete_review_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not completely reviewed"):
        convert(_audit(tmp_path, outcome="UNREVIEWED"), tmp_path / "output", "digital", "freight")


def test_incorrect_review_requires_correction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires correctedValue"):
        convert(_audit(tmp_path, corrected=None), tmp_path / "output", "digital", "freight")


def test_altered_extracted_value_is_rejected(tmp_path: Path) -> None:
    archive = _audit(tmp_path)
    extracted = tmp_path / "expanded"
    with zipfile.ZipFile(archive) as source:
        source.extractall(extracted)
    review_path = extracted / "invoices/001/review-template.json"
    review = json.loads(review_path.read_text())
    review["fieldReviews"][0]["extractedValue"] = "tampered"
    review_path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="altered"):
        convert(extracted, tmp_path / "output", "digital", "freight")


def test_confidential_output_cannot_enter_tracked_repository_path() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="Git-ignored data"):
        _ensure_private_output(repository_root / "reports" / "confidential-benchmark")
    _ensure_private_output(repository_root / "data" / "benchmarks" / "private")
