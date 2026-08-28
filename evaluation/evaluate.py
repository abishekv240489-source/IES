"""Strict field, line-item, quality, latency and throughput evaluation for IES."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import strptime
from typing import Any

CRITICAL_FIELDS = {
    "header.invoiceNumber",
    "header.invoiceDate",
    "header.currency",
    "vendor.name",
    "amounts.total",
    "bankDetails.accountNumber",
}
TERMINAL_FAILURES = {"FAILED", "REJECTED"}


@dataclass
class Counter:
    labelled: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.labelled if self.labelled else 0.0

    def add(self, matched: bool) -> None:
        self.labelled += 1
        self.correct += int(matched)


@dataclass
class Stratum:
    documents: int = 0
    missing_predictions: int = 0
    complete_documents: int = 0
    fields: Counter = field(default_factory=Counter)


@dataclass
class Evaluation:
    documents: int = 0
    predictions_found: int = 0
    missing_predictions: int = 0
    failed_predictions: int = 0
    complete_documents: int = 0
    fields: Counter = field(default_factory=Counter)
    critical: Counter = field(default_factory=Counter)
    line_fields: Counter = field(default_factory=Counter)
    truth_line_items: int = 0
    predicted_line_items: int = 0
    exact_line_items: int = 0
    per_field: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    by_quality: dict[str, Stratum] = field(default_factory=lambda: defaultdict(Stratum))
    by_layout: dict[str, Stratum] = field(default_factory=lambda: defaultdict(Stratum))
    latencies_ms: list[float] = field(default_factory=list)


def _invoice_root(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("extraction", "invoice"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def _leaf_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def flatten_fields(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten scalar invoice fields while excluding metadata and line items."""
    if isinstance(value, dict) and "value" in value:
        return {prefix: value.get("value")}
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, nested in value.items():
            if key.startswith("_") or key == "lineItems":
                continue
            path = f"{prefix}.{key}" if prefix else key
            output.update(flatten_fields(nested, path))
        return output
    if isinstance(value, list) or not prefix:
        return {}
    return {prefix: value}


def line_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _invoice_root(payload).get("lineItems", [])
    if not isinstance(raw, list):
        return []
    output: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            output.append({key: _leaf_value(value) for key, value in item.items() if not key.startswith("_")})
    return output


def normalize(path: str, value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip().casefold()
    if path.endswith(("accountNumber", "iban", "swiftBic", "taxRegistration")):
        return re.sub(r"[^a-z0-9]", "", text)
    if path.endswith(("invoiceDate", "dueDate")):
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%b-%Y"):
            try:
                parsed = strptime(text, pattern)
                return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
            except ValueError:
                continue
    if path.startswith("amounts.") or path.endswith(("quantity", "unitPrice", "amount", "exchangeRate")):
        try:
            cleaned = re.sub(r"[^0-9.+-]", "", text.replace(",", ""))
            return str(Decimal(cleaned).quantize(Decimal("0.01")))
        except InvalidOperation:
            return text
    return text


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(math.ceil(quantile * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("_meta", {})
    return metadata if isinstance(metadata, dict) else {}


def _score_line_items(result: Evaluation, truth: list[dict[str, Any]], prediction: list[dict[str, Any]]) -> None:
    result.truth_line_items += len(truth)
    result.predicted_line_items += len(prediction)
    prediction_by_number = {
        normalize("lineNumber", item.get("lineNumber")): item
        for item in prediction
        if normalize("lineNumber", item.get("lineNumber"))
    }
    used_prediction_ids: set[int] = set()
    for index, expected_item in enumerate(truth):
        line_number = normalize("lineNumber", expected_item.get("lineNumber"))
        actual_item = prediction_by_number.get(line_number) if line_number else None
        if actual_item is None and index < len(prediction) and id(prediction[index]) not in used_prediction_ids:
            actual_item = prediction[index]
        if actual_item is not None:
            used_prediction_ids.add(id(actual_item))
        record_matches: list[bool] = []
        for key, expected in expected_item.items():
            if expected is None:
                continue
            actual = actual_item.get(key) if actual_item else None
            matched = normalize(key, expected) == normalize(key, actual)
            result.line_fields.add(matched)
            record_matches.append(matched)
        result.exact_line_items += int(bool(record_matches) and all(record_matches))


def _update_stratum(stratum: Stratum, labelled: int, correct: int, complete: bool, missing: bool) -> None:
    stratum.documents += 1
    stratum.missing_predictions += int(missing)
    stratum.complete_documents += int(complete)
    stratum.fields.labelled += labelled
    stratum.fields.correct += correct


def evaluate(truth_dir: Path, prediction_dir: Path) -> tuple[Evaluation, set[str]]:
    result = Evaluation()
    truth_files = [path for path in sorted(truth_dir.glob("*.json")) if not path.name.startswith("_")]
    if not truth_files:
        raise ValueError(f"No ground-truth JSON files found in {truth_dir}")
    truth_names = {path.name for path in truth_files}

    for truth_file in truth_files:
        truth_payload = json.loads(truth_file.read_text(encoding="utf-8"))
        truth_meta = _metadata(truth_payload)
        quality = str(truth_meta.get("quality", "unspecified"))
        layout = str(truth_meta.get("layout", "unspecified"))
        expected_fields = flatten_fields(_invoice_root(truth_payload))
        prediction_file = prediction_dir / truth_file.name
        missing = not prediction_file.exists()
        prediction_payload: dict[str, Any] = {}
        if missing:
            result.missing_predictions += 1
        else:
            prediction_payload = json.loads(prediction_file.read_text(encoding="utf-8"))
            result.predictions_found += 1
            prediction_meta = _metadata(prediction_payload)
            latency = prediction_meta.get("latency_ms", prediction_payload.get("latencyMs"))
            if isinstance(latency, (int, float)) and latency >= 0:
                result.latencies_ms.append(float(latency))
            status = str(prediction_meta.get("status", prediction_payload.get("status", ""))).upper()
            result.failed_predictions += int(status in TERMINAL_FAILURES)

        actual_fields = flatten_fields(_invoice_root(prediction_payload))
        document_labelled = 0
        document_correct = 0
        document_ok = not missing
        for path, expected in expected_fields.items():
            if expected is None:
                continue
            matched = normalize(path, expected) == normalize(path, actual_fields.get(path))
            result.fields.add(matched)
            result.per_field[path].add(matched)
            document_labelled += 1
            document_correct += int(matched)
            if path in CRITICAL_FIELDS:
                result.critical.add(matched)
            if not matched:
                document_ok = False

        _score_line_items(result, line_items(truth_payload), line_items(prediction_payload))
        result.documents += 1
        result.complete_documents += int(document_ok)
        _update_stratum(result.by_quality[quality], document_labelled, document_correct, document_ok, missing)
        _update_stratum(result.by_layout[layout], document_labelled, document_correct, document_ok, missing)

    prediction_names = {
        path.name for path in prediction_dir.glob("*.json") if not path.name.startswith("_")
    }
    return result, prediction_names - truth_names


def _counter_report(counter: Counter) -> dict[str, int | float]:
    return {"labelled": counter.labelled, "correct": counter.correct, "accuracy": round(counter.accuracy, 6)}


def _strata_report(strata: dict[str, Stratum]) -> dict[str, Any]:
    return {
        name: {
            "documents": value.documents,
            "missing_predictions": value.missing_predictions,
            "field_accuracy": round(value.fields.accuracy, 6),
            "complete_document_rate": round(value.complete_documents / value.documents, 6) if value.documents else 0,
        }
        for name, value in sorted(strata.items())
    }


def build_report(
    result: Evaluation,
    extra_predictions: set[str],
    prediction_dir: Path,
    min_field_accuracy: float,
    min_critical_accuracy: float,
    max_p95_latency_ms: float,
    min_throughput: float,
    require_performance: bool,
) -> dict[str, Any]:
    run_file = prediction_dir / "_run.json"
    run = json.loads(run_file.read_text(encoding="utf-8")) if run_file.exists() else {}
    throughput = run.get("invoices_per_hour")
    p95 = percentile(result.latencies_ms, 0.95)
    line_precision = result.exact_line_items / result.predicted_line_items if result.predicted_line_items else 0.0
    line_recall = result.exact_line_items / result.truth_line_items if result.truth_line_items else 0.0
    line_f1 = 2 * line_precision * line_recall / (line_precision + line_recall) if line_precision + line_recall else 0.0

    field_passed = result.fields.accuracy >= min_field_accuracy
    critical_passed = result.critical.accuracy >= min_critical_accuracy
    latency_measured = p95 is not None
    throughput_measured = isinstance(throughput, (int, float))
    latency_passed = latency_measured and p95 < max_p95_latency_ms
    throughput_passed = throughput_measured and float(throughput) >= min_throughput
    performance_passed = (latency_passed and throughput_passed) if require_performance else True

    return {
        "schema_version": "2.0",
        "documents": {
            "labelled": result.documents,
            "predictions_found": result.predictions_found,
            "missing_predictions": result.missing_predictions,
            "failed_predictions": result.failed_predictions,
            "extra_predictions": sorted(extra_predictions),
            "complete_document_rate": round(result.complete_documents / result.documents, 6),
        },
        "fields": _counter_report(result.fields),
        "critical_fields": _counter_report(result.critical),
        "line_items": {
            "truth_records": result.truth_line_items,
            "predicted_records": result.predicted_line_items,
            "exact_records": result.exact_line_items,
            "precision": round(line_precision, 6),
            "recall": round(line_recall, 6),
            "f1": round(line_f1, 6),
            "field_accuracy": round(result.line_fields.accuracy, 6),
        },
        "performance": {
            "samples": len(result.latencies_ms),
            "p50_latency_ms": percentile(result.latencies_ms, 0.50),
            "p95_latency_ms": p95,
            "p99_latency_ms": percentile(result.latencies_ms, 0.99),
            "invoices_per_hour": throughput,
        },
        "by_quality": _strata_report(result.by_quality),
        "by_layout": _strata_report(result.by_layout),
        "per_field": {path: _counter_report(counter) for path, counter in sorted(result.per_field.items())},
        "gates": {
            "field_accuracy": {"minimum": min_field_accuracy, "passed": field_passed},
            "critical_field_accuracy": {"minimum": min_critical_accuracy, "passed": critical_passed},
            "p95_latency": {"maximum_ms": max_p95_latency_ms, "measured": latency_measured, "passed": latency_passed},
            "throughput": {"minimum_invoices_per_hour": min_throughput, "measured": throughput_measured, "passed": throughput_passed},
            "performance_required": require_performance,
            "overall_passed": field_passed and critical_passed and performance_passed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-field-accuracy", type=float, default=0.95)
    parser.add_argument("--min-critical-accuracy", type=float, default=0.98)
    parser.add_argument("--max-p95-latency-ms", type=float, default=15_000)
    parser.add_argument("--min-throughput", type=float, default=200)
    parser.add_argument("--require-performance", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    try:
        result, extra_predictions = evaluate(args.truth, args.predictions)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    report = build_report(
        result,
        extra_predictions,
        args.predictions,
        args.min_field_accuracy,
        args.min_critical_accuracy,
        args.max_p95_latency_ms,
        args.min_throughput,
        args.require_performance,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if args.report_only or report["gates"]["overall_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
