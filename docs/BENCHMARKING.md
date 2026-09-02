# Accuracy and performance benchmarking

The benchmark tooling is deliberately separate from application runtime data. Invoice documents, labels, predictions and generated reports are excluded from Git.

## Dataset contract

`dataset.json` lists each document, ground-truth file, quality band and layout. Ground-truth JSON follows the fixed IES invoice schema with an optional `_meta` object. Truth leaves may be plain values; prediction leaves may be plain values or `{value, confidence, source, page}` objects.

Required quality bands for a representative holdout are:

- digital PDF
- clean scan
- degraded scan (blur, skew, compression, low contrast or noise)

Stratify further by vendor, layout, language, page count and invoice complexity. Production invoices must be de-identified or retained only in approved encrypted storage with least-privilege access.

## Scoring behavior

- Missing prediction files are scored as incorrect for every labelled field.
- Failed/rejected jobs remain in the denominator.
- Field accuracy excludes unlabelled `null` truth values.
- Critical-field accuracy is reported independently.
- Line-item exact precision/recall/F1 and aligned cell accuracy are separate from scalar fields.
- Quality and layout strata expose regressions hidden by an aggregate score.
- Latency uses the nearest-rank p95. Throughput comes from the complete benchmark run wall time.
- Performance gates are mandatory only when `--require-performance` is supplied.

## Interpretation

Synthetic invoices are useful for regression, failure-path and degraded-image testing. They cannot substantiate the `>=95%` production accuracy requirement because their layouts and vocabulary are generated from known templates. Only a frozen representative holdout can approve that gate.

Never tune prompts, regexes or normalization rules against the holdout. Use a separate training/development set, freeze the model and configuration, then run the holdout once for the release candidate.

## Turning completed audit reviews into a benchmark

Keep the audit ZIP and generated dataset under `data/`; both locations are excluded from Git. In every `review-template.json`, review every field as `CORRECT`, `INCORRECT` (with `correctedValue`) or `NOT_APPLICABLE`. The importer rejects incomplete reviews, altered extracted values, unsafe archive paths, oversized entries and source hash mismatches.

```powershell
python evaluation/import_audit_reviews.py `
  --audit "C:\private\batch-audit-reviewed.zip" `
  --output-root data/benchmarks/reviewed-development `
  --quality scan_clean `
  --layout services

python evaluation/evaluate.py `
  --truth data/benchmarks/reviewed-development/ground_truth `
  --predictions data/benchmarks/reviewed-development/reviewed_predictions `
  --output reports/generated/reviewed-development.json `
  --report-only
```

The generated report includes `improvement_priorities`, ranked by observed field errors. The imported dataset is marked `release_holdout: false`: it is development evidence because its reviewed results have already been seen. A separate frozen representative holdout remains mandatory for the production accuracy claim.

The checked-in [synthetic v1 development baseline](baselines/SYNTHETIC_V1_BASELINE.md) demonstrates the expected report and records the current OCR/runtime measurements without storing invoice documents or predictions in Git.
