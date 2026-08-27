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

## Metrics

- Exact match and normalized match per field
- Precision/recall/F1 for line items
- Full-invoice success rate
- OCR character/word error rate on a labelled subset
- p50/p95/p99 latency by pipeline stage
- Throughput at worker counts 1, 2, 4 and 8
- Human-review rate and correction rate
