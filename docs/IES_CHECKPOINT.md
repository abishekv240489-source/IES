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
