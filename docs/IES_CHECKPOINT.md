# Current IES checkpoint

- Rebuild location: `C:\Users\User\Desktop\Projects\Inv_VIT`
- Authoritative scope: user requirements + supplied design document + supplied stack screenshot
- Recovered legacy features: ingestion, OCR fast path, scanned OCR, Qwen mapping, normalization, validation, corrections, history/audit, PostgreSQL, batch evaluation and synthetic variation work
- Current milestone: Node.js microservice backend plus production-grade PostgreSQL schema and representative accuracy qualification
- Deployment status: Node API/processor, UI and AI images; full-stack Compose; non-root runtime controls; health probes; network policies; and AI-worker autoscaling implemented
- Database status: all 13 SOP tables and fields implemented by a forward PostgreSQL migration, with choice constraints, five seeded SOP validation rules, existing-data backfill, transactional synchronization, immutable audit, durable processing queue and benchmark evidence integration-tested
- Synthetic accuracy/throughput status: all configured regression gates pass (98.48% scalar accuracy, 100% critical accuracy, 98.11% line-item F1, 1,357 invoices/hour, 12.324s warm p95)
- Production acceptance status: not yet proven on a representative labelled holdout; synthetic results cannot authorize production release
- Review qualification status: completed audit packages can now be validated and converted into Git-ignored development benchmarks with ranked field-level improvement priorities
- Next validation input needed: fully reviewed representative audit templates for development tuning, followed by a separate frozen holdout kept outside Git

## 2026-09-03 audit-driven correction pass

- Fixed overlapping processor claims and AI-worker request backlog. Busy workers return 503; durable retries refund busy attempts. Native OCR cancellation retains its file and exclusive slot safely.
- Accuracy-first settings: one local processor slot, Qwen enabled without the heuristic shortcut, 300-second mapping ceiling, 900-second pipeline ceiling and leases above that ceiling.
- Corrected trading-name supplier selection, explicit bill-to mapping, wrapped PO references, bounded total labels, inspection/service/delivery tables, and unique-evidence merging for incomplete Qwen rows.
- Missing lines/descriptions/amounts, fallback warnings, party-role conflicts, ambiguous prices and mapper disagreements now require review.
- Offline checks against the five available OCR snapshots recovered their known totals and line counts. This is development regression evidence, not full-field scoring.
- Two fresh live uploads both produced persisted Qwen extractions with no timeout (about 144 and 178 seconds), including a previously failed scanned invoice. Review gates correctly caught residual field gaps; subsequent matching refinements have automated regression coverage.
- The original eight-document batch remains unchanged. The other two previously failed documents, including the 19-page packet, still need full end-to-end replay. Do not claim all eight now pass or that 95% accuracy is established.
- All customer documents, audit ZIPs, OCR text, extracted values and live IDs remain outside version control. The repository contains only code, deidentified regression fixtures and aggregate observations.
