# Synthetic v1 development baseline

- Run date: 2026-08-28
- Dataset: 9 deterministic, non-sensitive one-page invoices (3 digital, 3 clean scans, 3 degraded scans)
- Runtime: Windows CPU, 8 logical processors, PaddleOCR 3.7.0, PaddlePaddle 3.2.2, OneDNN enabled
- Pipeline: Node.js API -> Node.js processor -> PaddleOCR -> deterministic heuristic mapper

## Results

| Measure | Result | Required gate | Status |
|---|---:|---:|---|
| Completed invoices | 9 / 9 | No failures | Pass |
| End-to-end p95 latency | 7,751 ms | <15,000 ms | Pass |
| Throughput, concurrency 1 | 988.154 invoices/hour | >=200 | Pass |
| Scalar-field accuracy | 25.00% | >=95% | Fail |
| Critical-field accuracy | 66.67% | >=98% release gate | Fail |
| Line-item F1 | 0.00% | Reported separately | Fail |

The hardest degraded scan produced 1,027 recognized characters at 0.9737 mean OCR confidence. Direct OCR latency was 10.070 seconds on cold model initialization and 4.419 seconds warm.

## Interpretation

This run validates the real OCR, low-quality preprocessing, asynchronous API, persistence, latency, throughput and strict scoring paths. It intentionally does **not** validate mapping accuracy: `IES_MAPPING_PROVIDER=heuristic` was used because the Qwen model was not installed on this host. The heuristic mapper covers only a small scalar subset and does not map line items, so the evaluator correctly rejects the accuracy gates.

The next comparable run must use the frozen Qwen 2.5 7B mapping configuration. Neither this synthetic corpus nor any future synthetic-only score can substantiate production accuracy; final acceptance requires a representative, de-identified holdout that was not used for prompt or rule tuning.
