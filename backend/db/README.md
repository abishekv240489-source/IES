# PostgreSQL schema

`migrations/001_node_microservices.sql` is the authoritative schema for every environment. The Node API and processor both run pending migrations under a PostgreSQL advisory lock at startup; `pnpm migrate` is also available for deployment jobs.

## Tables

| Area | Tables |
|---|---|
| Tenancy and ingestion | `tenants`, `invoice_batches`, `invoice_jobs` |
| Versioned extraction | `extraction_revisions`, `extracted_fields`, `invoice_line_items` |
| Quality and review | `validation_issues`, `audit_events` |
| Durable processing | `processing_tasks` |
| Measured release evidence | `benchmark_runs`, `benchmark_document_results`, `benchmark_field_results` |

`release_accuracy_status` reports whether a completed representative holdout run has met the configured scalar-field accuracy, critical-field accuracy, line-item F1, p95 latency and throughput gates. A synthetic or incomplete run cannot pass the release gate.

## Operational behavior

- Upload metadata, the initial audit event and the processing task are committed atomically.
- Processors lease work with `FOR UPDATE SKIP LOCKED`, renew ownership by lease timestamp and recover expired leases after a crash.
- Extraction revisions are immutable snapshots; the active revision is referenced by the invoice job.
- Scalar fields and line items are normalized for reporting while the versioned JSON payload is retained for complete replay.
- Tenant keys, foreign keys, checks and queue indexes are defined in the migration rather than application-only code.

Run `pnpm verify` to execute the migration and full pipeline against an embedded PostgreSQL-compatible engine. For a deployed PostgreSQL database, set `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USERNAME` and `DATABASE_PASSWORD`, then run `pnpm migrate`.
