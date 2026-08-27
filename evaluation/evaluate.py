"""Field-level accuracy evaluator for frozen IES holdout datasets.

Expected layout (kept outside Git):
  ground_truth/<document-id>.json
  predictions/<document-id>.json
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

CRITICAL_FIELDS = {
    "header.invoiceNumber",
    "header.invoiceDate",
    "header.currency",
    "vendor.name",
    "amounts.total",
    "bankDetails.accountNumber",
}


@dataclass
class Counts:
    labelled: int = 0
    correct: int = 0
    critical_labelled: int = 0
    critical_correct: int = 0
    documents: int = 0
    complete_documents: int = 0


def leaf_values(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict) and "value" in value:
        return {prefix: value["value"]}
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else key
            output.update(leaf_values(nested, path))
        return output
    return {}


def normalize(path: str, value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip().casefold()
    if path.endswith(("accountNumber", "iban", "swiftBic")):
        return re.sub(r"[^a-z0-9]", "", text)
    if path.startswith("amounts.") or path.endswith(("quantity", "unitPrice", "amount")):
        try:
            return str(Decimal(text.replace(",", "")).quantize(Decimal("0.01")))
        except InvalidOperation:
            return text
    return text


def evaluate(truth_dir: Path, prediction_dir: Path) -> tuple[Counts, dict[str, dict[str, int]]]:
    counts = Counts()
    per_field: dict[str, dict[str, int]] = {}
    for truth_file in sorted(truth_dir.glob("*.json")):
        prediction_file = prediction_dir / truth_file.name
        if not prediction_file.exists():
            continue
        truth = leaf_values(json.loads(truth_file.read_text(encoding="utf-8")))
        prediction = leaf_values(json.loads(prediction_file.read_text(encoding="utf-8")))
        counts.documents += 1
        document_ok = True
        for path, expected in truth.items():
            if expected is None:
                continue
            actual = prediction.get(path)
            matched = normalize(path, expected) == normalize(path, actual)
            field = per_field.setdefault(path, {"labelled": 0, "correct": 0})
            field["labelled"] += 1
            counts.labelled += 1
            if path in CRITICAL_FIELDS:
                counts.critical_labelled += 1
            if matched:
                counts.correct += 1
                field["correct"] += 1
                if path in CRITICAL_FIELDS:
                    counts.critical_correct += 1
            else:
                document_ok = False
        counts.complete_documents += int(document_ok)
    return counts, per_field


def ratio(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-field-accuracy", type=float, default=0.95)
    args = parser.parse_args()
    counts, per_field = evaluate(args.truth, args.predictions)
    report = {
        "documents": counts.documents,
        "field_accuracy": ratio(counts.correct, counts.labelled),
        "critical_field_accuracy": ratio(counts.critical_correct, counts.critical_labelled),
        "complete_document_rate": ratio(counts.complete_documents, counts.documents),
        "labelled_fields": counts.labelled,
        "per_field": {path: {**value, "accuracy": ratio(value["correct"], value["labelled"])} for path, value in per_field.items()},
        "gate": {"minimum": args.min_field_accuracy, "passed": ratio(counts.correct, counts.labelled) >= args.min_field_accuracy},
    }
    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if report["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
