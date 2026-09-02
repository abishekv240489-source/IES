# IES architecture decisions

## Boundaries

| Boundary | Technology | Responsibility |
|---|---|---|
| Web client | React 18, TypeScript, MUI | Upload, queue visibility, review, correction and audit views |
| System API | Node.js 22, TypeScript, Fastify | Security, ingestion, review, query and audit endpoints |
| Processor | Node.js 22, TypeScript | Durable task leasing, concurrent orchestration, validation and retry/dead-letter handling |
| Batch | PostgreSQL-backed batches and task queue | Atomic submission, controlled reprocessing and horizontal consumption |
| AI worker | Python, PaddleOCR/PaddleX, OpenCV | OCR and low-quality document recovery |
| Semantic mapper | Qwen 2.5 7B via Ollama-compatible API | Map OCR text into the fixed invoice schema |
| Persistence | PostgreSQL | Jobs, invoice records, fields, corrections and immutable audit events |
| Work queue | PostgreSQL | Transactional task enqueue, leasing, retries and crash recovery without dual-write gaps |
| Integration events | Kafka-compatible extension point | Optional downstream enterprise event publication after the core transaction commits |
| Reports | JasperReports/Thymeleaf integration point | Operational and compliance exports |
| Workflow/rules | Drools/Camunda integration point | Configurable enterprise rules and approval workflow |

## Processing flow

1. The API streams an upload to a generated document path while calculating SHA-256.
2. It validates filename, extension, content type, magic bytes, size and duplicate hash. Duplicate content is labelled for traceability but remains a distinct job in the requested batch.
3. A job and audit event are committed before processing begins.
4. The AI worker uses embedded PDF text page-by-page when sufficiently complete and sends sparse or image-only pages through rendering, preprocessing and PaddleOCR, including mixed PDFs.
5. Digital PDFs use their native text layer when it is sufficiently complete; scanned PDFs and image
   invoices must pass through PaddleOCR. `IES_PADDLEOCR_REQUIRED=true` prevents a silent empty-text OCR
   fallback. PaddleOCR returns text and page-level OCR confidence.
6. A deterministic evidence mapper handles complete labelled invoices. Ambiguous or incomplete mappings are
   sent to Qwen 2.5 7B at temperature zero and validated against the versioned JSON schema; deterministic
   evidence may fill missing Qwen fields but never overwrite a populated Qwen value. Set
   `IES_MAPPING_PROVIDER=ollama` to require Qwen for every invoice, or `hybrid` for the latency-aware path.
7. The Node processor applies authoritative rules: mandatory fields, amount reconciliation, currency/date sanity, confidence thresholds and bank/PO checks.
8. The UI presents source and extracted values side-by-side. Corrections are audited and become evaluation labels only after approval.
9. An authorized reviewer can stream an invoice or complete batch audit ZIP. Packages preserve the original source, exact extraction, page-level OCR text/confidence evidence, validation, revision and event records, plus a structured correction template for accuracy analysis.

## Performance model

`200 invoices/hour` equals 3.33 invoices/minute. A 15-second per-document ceiling requires at least one continuously utilized worker; bursts, multi-page documents and tail latency require parallel workers. The target topology starts with four OCR/mapping worker slots and measures p50/p95/p99 latency separately.

## Deployment model

- The local Compose topology exposes every port on loopback only and places the browser behind a same-origin Nginx proxy.
- API, processor, AI-worker and web images run without application-level root privileges and use health probes plus explicit memory bounds.
- Kubernetes scales the CPU-heavy AI-worker tier independently from the API and UI.
- PostgreSQL, Ollama/Qwen, optional Kafka integration, ingress and secrets remain environment services rather than cloud-vendor-specific manifests.
- The baseline keeps one API and one processor replica because source documents use a `ReadWriteOnce` volume. Horizontal scaling requires encrypted shared storage or an object-storage implementation.

## Accuracy model

Accuracy is calculated at field level on a frozen, labelled holdout set. Required-field exact/normalized match, line-item F1 and full-document success are reported separately. Confidence is a routing signal, not a substitute for measured accuracy.

Each populated extracted field receives a page-aware confidence score using a weighted harmonic mean:
60% Qwen/mapping confidence and 40% PaddleOCR confidence from the evidence page (or the document mean
when the page is unknown). The conservative harmonic mean prevents a strong component from hiding a weak
one. The API response and audit event retain the method, weights, component averages and populated-field
count. Document confidence is capped by the fused confidence of the five required fields, so strong OCR on
optional populated fields cannot conceal a missing vendor, invoice number/date, currency or total.
Human-reviewed fields keep their reviewer-assigned confidence.

## Security model

- Production authentication is OIDC/JWT (Microsoft Entra ID compatible).
- Uploaded names never become storage paths.
- Original documents and derived PII are excluded from Git.
- Application secrets come from environment variables or an external secret manager.
- Logs use identifiers and timings, not OCR text or bank-account values.
- Every state transition and reviewer correction emits an append-only audit event.
- Audit downloads are tenant-scoped, available only after processing finishes, recorded as events, marked private/no-store and streamed without persisting duplicate audit artifacts.
