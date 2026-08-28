# Acceptance test plan

## Required gates

| Gate | Definition | Pass condition |
|---|---|---:|
| Field accuracy | Correct normalized values / labelled required values | >= 95% |
| Critical-field accuracy | Invoice number, vendor, date, currency, total, bank account | >= 98% recommended |
| Throughput | Completed invoices in a sustained one-hour run | >= 200/hour |
| Latency | Upload accepted to extraction completed | < 15s p95 |
| Batch reliability | Completed or deterministically routed to review | >= 99.5% |
| Low-quality recovery | Accuracy on a separately labelled degraded-scan subset | Reported and >= agreed pilot threshold |

## Dataset protocol

- Use a frozen holdout set that was never used to tune prompts, rules or models.
- Stratify by vendor, layout, language, page count, digital/scanned origin and quality band.
- Remove or tokenize personal and bank information in non-production test copies.
- Keep ground truth outside Git in access-controlled storage.
- Report missing labels separately; do not count them as correct blanks.
- Count every missing prediction as incorrect. Never skip a document because processing failed or no prediction file exists.
- Keep synthetic results separate from the representative holdout result; synthetic data validates mechanics and regression behavior, not production accuracy.

## Metrics

- Exact match and normalized match per field
- Precision/recall/F1 for line items
- Full-invoice success rate
- OCR character/word error rate on a labelled subset
- p50/p95/p99 latency by pipeline stage
- Throughput at worker counts 1, 2, 4 and 8
- Human-review rate and correction rate

## Reproducible benchmark commands

Generate a privacy-safe synthetic dataset (the output path is ignored by Git):

```powershell
python evaluation/generate_synthetic.py --output-root data/benchmarks/synthetic-v1 --count 30
```

Run it through a started API and write predictions outside Git:

```powershell
python evaluation/run_benchmark.py --dataset data/benchmarks/synthetic-v1/dataset.json `
  --predictions data/benchmarks/synthetic-v1/predictions --concurrency 4
```

Create the acceptance report. `--require-performance` makes missing latency or throughput measurements fail the gate:

```powershell
python evaluation/evaluate.py `
  --truth data/benchmarks/synthetic-v1/ground_truth `
  --predictions data/benchmarks/synthetic-v1/predictions `
  --output reports/generated/synthetic-v1.json `
  --require-performance
```

For production acceptance, replace the synthetic dataset with an access-controlled, frozen holdout set and retain the same directory contract.
