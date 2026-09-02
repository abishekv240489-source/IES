"""Convert completed IES audit reviews into a private benchmark dataset.

The output belongs under ``data/`` (which is excluded from Git). Review packages
are treated as untrusted data: archive paths, sizes, hashes and review values are
validated before any benchmark material is produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ENTRY_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
OUTCOMES = {"CORRECT", "INCORRECT", "NOT_APPLICABLE"}


def _ensure_private_output(output_root: Path) -> None:
    """Prevent confidential benchmark artifacts entering a tracked repo path."""
    repository_root = Path(__file__).resolve().parents[1]
    try:
        relative = output_root.resolve().relative_to(repository_root)
    except ValueError:
        return
    if not relative.parts or relative.parts[0].lower() != "data":
        raise ValueError("Output inside this repository must be under the Git-ignored data/ directory")


def _json(data: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON in {name}: {error}") from error
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object in {name}")
    return value


def _safe_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe audit entry path: {name}")
    return path.as_posix()


def load_entries(source: Path) -> dict[str, bytes]:
    """Read a ZIP or extracted audit directory into a validated entry map."""
    entries: dict[str, bytes] = {}
    total = 0
    if source.is_file():
        if not zipfile.is_zipfile(source):
            raise ValueError(f"Audit input is not a valid ZIP: {source}")
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = _safe_name(info.filename)
                if name in entries:
                    raise ValueError(f"Duplicate audit entry: {name}")
                if info.file_size > MAX_ENTRY_BYTES:
                    raise ValueError(f"Audit entry exceeds 25 MB: {name}")
                total += info.file_size
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("Expanded audit package exceeds 1 GB")
                data = archive.read(info)
                if len(data) != info.file_size:
                    raise ValueError(f"Audit entry size changed while reading: {name}")
                entries[name] = data
    elif source.is_dir():
        root = source.resolve()
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if path.is_symlink():
                raise ValueError(f"Symbolic links are not accepted: {path}")
            resolved = path.resolve()
            resolved.relative_to(root)
            name = _safe_name(path.relative_to(source).as_posix())
            size = path.stat().st_size
            if size > MAX_ENTRY_BYTES:
                raise ValueError(f"Audit entry exceeds 25 MB: {name}")
            total += size
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError("Audit directory exceeds 1 GB")
            entries[name] = path.read_bytes()
    else:
        raise FileNotFoundError(source)
    return entries


def _lookup(entries: dict[str, bytes], name: str, context: str) -> bytes:
    safe = _safe_name(name)
    try:
        return entries[safe]
    except KeyError as error:
        raise ValueError(f"Missing {context}: {safe}") from error


def _value_at_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise ValueError(f"Field path does not exist in extraction: {path}")
            current = current[index]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ValueError(f"Field path does not exist in extraction: {path}")
    if isinstance(current, dict) and "value" in current:
        return current.get("value")
    return current


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current: Any = root
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        next_is_index = not last and parts[index + 1].isdigit()
        if isinstance(current, list):
            if not part.isdigit():
                raise ValueError(f"Invalid array field path: {path}")
            position = int(part)
            while len(current) <= position:
                current.append(None)
            if last:
                current[position] = value
            else:
                if current[position] is None:
                    current[position] = [] if next_is_index else {}
                current = current[position]
        elif isinstance(current, dict):
            if last:
                current[part] = value
            else:
                if part not in current:
                    current[part] = [] if next_is_index else {}
                current = current[part]
        else:
            raise TypeError(f"Field path conflicts with another field: {path}")


def _document_id(job_id: Any, source_name: str) -> str:
    candidate = str(job_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", candidate):
        return candidate
    return hashlib.sha256(f"{candidate}\0{source_name}".encode()).hexdigest()[:32]


def _completed_truth(review: dict[str, Any], extraction: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    if review.get("schemaVersion") != "ies.audit-review.v1":
        raise ValueError("Unsupported review schema version")
    field_reviews = review.get("fieldReviews")
    if not isinstance(field_reviews, list) or not field_reviews:
        raise ValueError("Review contains no fields")
    truth: dict[str, Any] = {}
    counts = {"correct": 0, "incorrect": 0, "notApplicable": 0}
    seen: set[str] = set()
    for item in field_reviews:
        if not isinstance(item, dict):
            raise TypeError("Every field review must be an object")
        path = str(item.get("fieldPath", "")).strip()
        if not path or path in seen:
            raise ValueError(f"Missing or duplicate reviewed field path: {path or '<empty>'}")
        seen.add(path)
        outcome = str(item.get("outcome", "UNREVIEWED")).upper()
        if outcome not in OUTCOMES:
            raise ValueError(f"Field {path} is not completely reviewed")
        extracted = _value_at_path(extraction, path)
        if item.get("extractedValue") != extracted:
            raise ValueError(f"Extracted value was altered in review field {path}")
        if outcome == "NOT_APPLICABLE":
            counts["notApplicable"] += 1
            continue
        if outcome == "INCORRECT":
            corrected = item.get("correctedValue")
            if corrected is None:
                raise ValueError(f"Incorrect field {path} requires correctedValue")
            value = corrected
            counts["incorrect"] += 1
        else:
            value = extracted
            counts["correct"] += 1
        _set_path(truth, path, value)
    return truth, counts


def convert(source: Path, output_root: Path, quality: str, layout: str) -> dict[str, Any]:
    _ensure_private_output(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty output directory: {output_root}")
    entries = load_entries(source)
    review_names = sorted(name for name in entries if name.endswith("review-template.json"))
    if not review_names:
        raise ValueError("No review-template.json files found")

    prepared: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for review_name in review_names:
        prefix = review_name[: -len("review-template.json")]
        review = _json(entries[review_name], review_name)
        extraction_name = f"{prefix}extracted-fields.json"
        manifest_name = f"{prefix}manifest.json"
        extraction = _json(_lookup(entries, extraction_name, "extracted fields"), extraction_name)
        manifest = _json(_lookup(entries, manifest_name, "invoice manifest"), manifest_name)
        invoice = manifest.get("invoice")
        files = manifest.get("files")
        if not isinstance(invoice, dict) or not isinstance(files, dict):
            raise TypeError(f"Invalid invoice manifest: {manifest_name}")
        source_name = str(files.get("sourceInvoice", ""))
        source_bytes = _lookup(entries, source_name, "source invoice")
        expected_hash = str(invoice.get("sourceSha256", "")).lower()
        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or actual_hash != expected_hash:
            raise ValueError(f"Source invoice hash mismatch: {source_name}")
        document_id = _document_id(invoice.get("jobId"), source_name)
        if document_id in identifiers:
            raise ValueError(f"Duplicate invoice identifier: {document_id}")
        identifiers.add(document_id)
        truth, counts = _completed_truth(review, extraction)
        source_suffix = Path(PurePosixPath(source_name).name).suffix.lower() or ".bin"
        truth["_meta"] = {"quality": quality, "layout": layout, "reviewed": True}
        prediction = dict(extraction)
        prediction["_meta"] = {
            "quality": quality,
            "layout": layout,
            "status": invoice.get("status"),
            "engine": invoice.get("extractionEngine"),
            "confidence": invoice.get("overallConfidence"),
        }
        prepared.append({
            "id": document_id,
            "suffix": source_suffix,
            "source": source_bytes,
            "truth": truth,
            "prediction": prediction,
            "counts": counts,
        })

    documents_dir = output_root / "documents"
    truth_dir = output_root / "ground_truth"
    predictions_dir = output_root / "reviewed_predictions"
    documents_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir.mkdir(parents=True, exist_ok=True)
    manifest_documents = []
    total_counts = {"correct": 0, "incorrect": 0, "notApplicable": 0}
    for item in prepared:
        document_name = f"{item['id']}{item['suffix']}"
        (documents_dir / document_name).write_bytes(item["source"])
        (truth_dir / f"{item['id']}.json").write_text(
            json.dumps(item["truth"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (predictions_dir / f"{item['id']}.json").write_text(
            json.dumps(item["prediction"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for key in total_counts:
            total_counts[key] += item["counts"][key]
        manifest_documents.append({
            "id": item["id"],
            "path": f"documents/{document_name}",
            "truth": f"ground_truth/{item['id']}.json",
            "quality": quality,
            "layout": layout,
        })
    dataset = {
        "schema_version": "1.0",
        "synthetic": False,
        "reviewed": True,
        "release_holdout": False,
        "documents": manifest_documents,
    }
    summary = {"documents": len(prepared), **total_counts}
    (output_root / "dataset.json").write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    (output_root / "review-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True, help="Reviewed audit ZIP or extracted directory")
    parser.add_argument("--output-root", type=Path, required=True, help="Private output directory under data/")
    parser.add_argument("--quality", default="unspecified")
    parser.add_argument("--layout", default="unspecified")
    args = parser.parse_args()
    try:
        summary = convert(args.audit, args.output_root, args.quality, args.layout)
    except (OSError, TypeError, ValueError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
