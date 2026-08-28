from __future__ import annotations

import json
from pathlib import Path

from evaluation.evaluate import build_report, evaluate, normalize


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def truth_payload(quality: str = "digital") -> dict:
    return {
        "_meta": {"quality": quality, "layout": "freight"},
        "header": {"invoiceNumber": "INV-001", "invoiceDate": "2026-08-20", "currency": "USD"},
        "vendor": {"name": "Harbor Services"},
        "amounts": {"total": 1090.0},
        "bankDetails": {"accountNumber": "072-140318-8"},
        "lineItems": [
            {"lineNumber": "1", "description": "Agency service", "quantity": 1, "unitPrice": 1000, "amount": 1000}
        ],
    }


def wrapped_prediction() -> dict:
    field = lambda value: {"value": value, "confidence": 0.9, "source": "qwen"}
    return {
        "header": {"invoiceNumber": field("inv-001"), "invoiceDate": field("20/08/2026"), "currency": field("usd")},
        "vendor": {"name": field("Harbor   Services")},
        "amounts": {"total": field("1,090.00")},
        "bankDetails": {"accountNumber": field("072 140318 8")},
        "lineItems": [
            {"lineNumber": field("1"), "description": field("Agency service"), "quantity": field(1),
             "unitPrice": field(1000.0), "amount": field("1,000.00")}
        ],
        "_meta": {"status": "COMPLETED", "latency_ms": 2000},
    }


def test_normalization_handles_dates_amounts_and_accounts() -> None:
    assert normalize("header.invoiceDate", "20/08/2026") == "2026-08-20"
    assert normalize("amounts.total", "$1,090") == "1090.00"
    assert normalize("bankDetails.accountNumber", "072 140-318 8") == "0721403188"


def test_wrapped_prediction_scores_exactly(tmp_path: Path) -> None:
    truth = tmp_path / "truth"
    predictions = tmp_path / "predictions"
    write_json(truth / "one.json", truth_payload())
    write_json(predictions / "one.json", wrapped_prediction())
    result, extras = evaluate(truth, predictions)
    report = build_report(result, extras, predictions, 0.95, 0.98, 15000, 200, False)
    assert report["fields"]["accuracy"] == 1
    assert report["line_items"]["f1"] == 1
    assert report["by_quality"]["digital"]["field_accuracy"] == 1


def test_missing_prediction_is_counted_as_incorrect(tmp_path: Path) -> None:
    truth = tmp_path / "truth"
    predictions = tmp_path / "predictions"
    write_json(truth / "one.json", truth_payload("scan_degraded"))
    predictions.mkdir()
    result, _ = evaluate(truth, predictions)
    assert result.documents == 1
    assert result.missing_predictions == 1
    assert result.fields.labelled == 6
    assert result.fields.correct == 0
    assert result.by_quality["scan_degraded"].missing_predictions == 1


def test_extra_line_item_reduces_precision(tmp_path: Path) -> None:
    truth = tmp_path / "truth"
    predictions = tmp_path / "predictions"
    prediction = wrapped_prediction()
    prediction["lineItems"].append(prediction["lineItems"][0])
    write_json(truth / "one.json", truth_payload())
    write_json(predictions / "one.json", prediction)
    result, extras = evaluate(truth, predictions)
    report = build_report(result, extras, predictions, 0.95, 0.98, 15000, 200, False)
    assert report["line_items"]["precision"] == 0.5
    assert report["line_items"]["recall"] == 1
