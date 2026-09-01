# Node/PaddleOCR synthetic v2 development baseline

- Run date: 2026-09-01
- Dataset: 9 deterministic, privacy-safe one-page invoices
- Quality mix: 3 digital PDFs, 3 clean scans and 3 degraded scans
- Runtime: Windows CPU, Node.js API and processor microservices, PostgreSQL 15, PaddleOCR, deterministic evidence-preserving mapper
- Concurrency: 4 processor slots

## Warm steady-state result

| Measure | Result | Required gate | Status |
|---|---:|---:|---|
| Completed invoices | 9 / 9 | No failures | Pass |
| Scalar-field accuracy | 98.48% | >=95% | Pass |
| Critical-field accuracy | 100.00% | >=98% | Pass |
| Line-item F1 | 98.11% | Reported separately | Pass |
| End-to-end p95 latency | 12,324 ms | <15,000 ms | Pass |
| Throughput | 1,357.038 invoices/hour | >=200/hour | Pass |

The cold-start run reached 98.86% scalar-field accuracy and 1,141.626 invoices/hour but recorded 15,537 ms p95 latency while PaddleOCR initialized. Production readiness should warm OCR models before traffic and measure cold starts separately.

## Interpretation

This result demonstrates that the Node API, PostgreSQL durable queue, concurrent Node processor, low-quality PaddleOCR path, structured mapping, persistence and strict evaluator work together and can clear the configured regression gates. The mapper never fills values that are absent from the document; the v2 generator visibly prints discount and exchange-rate fields so the labels are evidence-backed.

This dataset is synthetic and was used during development. It must not be treated as evidence of production accuracy. Release authorization still requires a frozen, representative, de-identified holdout set that has not been used to tune OCR, patterns, prompts or validation rules. Qwen 2.5 7B remains the preferred semantic mapper for vendor/layout diversity beyond deterministic labelled formats.
