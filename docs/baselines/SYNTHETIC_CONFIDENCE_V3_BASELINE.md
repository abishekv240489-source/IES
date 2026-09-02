# PaddleOCR confidence-fusion synthetic v3 baseline

- Run date: 2026-09-01
- Dataset: 9 newly generated, deterministic, privacy-safe one-page invoices
- Quality mix: 3 digital PDFs, 3 clean scans and 3 degraded scans
- Runtime: Windows CPU, Node.js API/processor, PostgreSQL 15, PaddleOCR and hybrid mapper
- Client concurrency: 2, matched to one local CPU AI-worker
- Confidence method: page-aware weighted harmonic mean (60% mapping, 40% OCR/text evidence)

## Warm steady-state result

| Measure | Result | Required gate | Status |
|---|---:|---:|---|
| Completed invoices | 9 / 9 | No failures | Pass |
| Scalar-field accuracy | 98.86% | >=95% | Pass |
| Degraded-scan scalar accuracy | 96.55% | >=95% | Pass |
| Critical-field accuracy | 100.00% | >=98% release gate | Pass |
| Line-item F1 | 96.30% | Reported separately | Pass |
| End-to-end p95 latency | 12,271 ms | <15,000 ms | Pass |
| Throughput | 905.651 invoices/hour | >=200/hour | Pass |

## Mapping and latency decision

Qwen 2.5 7B Instruct Q4_K_M was installed in the local Ollama store. On this CPU-only host, a
schema-constrained mapping request did not complete within either a 10-second or a 120-second budget.
Running Qwen for every invoice therefore violates the latency requirement and starves concurrent OCR.

The `hybrid` policy uses the deterministic evidence mapper when invoice number, date, currency, vendor,
total, line items and at least 20 populated fields are present. Ambiguous or incomplete invoices are sent
to Qwen; successful Qwen output may be completed from deterministic evidence, but populated Qwen values
are never overwritten. Production synchronous Qwen 7B requires a benchmarked GPU-backed inference tier.

## Remaining errors and interpretation

The three scalar misses were note text on degraded scans (`remittance`/`invoice` character errors). Critical
fields were unaffected. One degraded line-item record failed exact matching. These errors were not patched
with phrase-specific corrections because doing so would overfit the synthetic generator.

This dataset is synthetic and was created by the repository generator. It validates regression behavior,
PaddleOCR routing, low-quality handling, confidence fusion, persistence and performance mechanics only. It
does **not** establish production accuracy. Release authorization still requires a frozen, representative,
de-identified holdout set that was not used to tune OCR, patterns, prompts, thresholds or validation rules.
