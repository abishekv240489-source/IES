# IES architecture decisions

## Boundaries

| Boundary | Technology | Responsibility |
|---|---|---|
| Web client | React 18, TypeScript, MUI | Upload, queue visibility, review, correction and audit views |
| System API | Java 21, Spring Boot 3.5 | Security, ingestion, orchestration, business state, validation and integrations |
| Batch | Spring Batch-compatible design | Controlled reprocessing and large batch orchestration |
| AI worker | Python, PaddleOCR/PaddleX, OpenCV | OCR and low-quality document recovery |
| Semantic mapper | Qwen 2.5 7B via Ollama-compatible API | Map OCR text into the fixed invoice schema |
| Persistence | PostgreSQL | Jobs, invoice records, fields, corrections and immutable audit events |
| Cache | Redis | Idempotency, hot job status and distributed coordination |
| Messaging | Kafka | Durable processing events and horizontal worker scaling |
| Reports | JasperReports/Thymeleaf integration point | Operational and compliance exports |
| Workflow/rules | Drools/Camunda integration point | Configurable enterprise rules and approval workflow |

## Processing flow

1. The API streams an upload to a generated document path while calculating SHA-256.
2. It validates filename, extension, content type, magic bytes, size and duplicate hash.
3. A job and audit event are committed before processing begins.
4. The AI worker uses embedded PDF text when sufficiently complete; otherwise it renders and preprocesses pages for OCR.
5. PaddleOCR returns text, regions and OCR confidence.
6. Qwen maps text to a versioned JSON schema. Temperature is zero and JSON is validated before acceptance.
7. Java applies authoritative rules: mandatory fields, amount reconciliation, currency/date sanity, confidence thresholds and bank/PO checks.
8. The UI presents source and extracted values side-by-side. Corrections are audited and become evaluation labels only after approval.

## Performance model

`200 invoices/hour` equals 3.33 invoices/minute. A 15-second per-document ceiling requires at least one continuously utilized worker; bursts, multi-page documents and tail latency require parallel workers. The target topology starts with four OCR/mapping worker slots and measures p50/p95/p99 latency separately.

## Accuracy model

Accuracy is calculated at field level on a frozen, labelled holdout set. Required-field exact/normalized match, line-item F1 and full-document success are reported separately. Confidence is a routing signal, not a substitute for measured accuracy.

## Security model

- Production authentication is OIDC/JWT (Microsoft Entra ID compatible).
- Uploaded names never become storage paths.
- Original documents and derived PII are excluded from Git.
- Application secrets come from environment variables or an external secret manager.
- Logs use identifiers and timings, not OCR text or bank-account values.
- Every state transition and reviewer correction emits an append-only audit event.
