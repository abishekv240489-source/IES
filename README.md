# Invoice Extraction System (IES)

Cloud-agnostic invoice ingestion, OCR, structured extraction, validation, and human review. This repository is a clean-room rebuild based on the supplied solution design and the recovered IES feature set.

## Demo scope

- Batch upload for PDF, PNG, JPEG and TIFF invoices
- Safe filenames, MIME/magic-byte validation, size/page limits and SHA-256 duplicate detection
- Asynchronous job lifecycle with source-document retention and audit events
- Embedded PDF text fast path plus low-quality image preprocessing and PaddleOCR adapter
- Qwen 2.5 7B mapping through an Ollama-compatible endpoint, with a deterministic demo fallback
- Structured header, vendor, bill-to, vessel, amount, bank and line-item fields
- Deterministic validation, confidence flags and reviewer corrections
- React/MUI operational dashboard and invoice review cockpit
- Versioned PostgreSQL schema with normalized extraction, audit, benchmark and durable task tables
- Accuracy, latency and throughput benchmark harnesses (targets are measured, never assumed)

## Architecture

```text
React 18 + MUI
      |
Node.js 22 + Fastify API microservice
      |--- PostgreSQL (transactional state + audit + durable task queue)
      `--- shared encrypted/object document storage
                    |
Node.js 22 processor microservice
      |--- horizontally concurrent task leasing
      |
Python AI worker
      |--- embedded-text detection
      |--- low-quality preprocessing
      |--- PaddleOCR / PaddleX
      `--- Qwen 2.5 7B via Ollama-compatible API
```

The backend is now split into independently deployable Node.js microservices. The API owns HTTP ingestion, review and query endpoints; the processor leases durable tasks from PostgreSQL and owns asynchronous OCR/mapping orchestration. The Python AI runtime remains isolated because PaddleOCR is Python-native.

## One-command container demo

Prerequisites: Docker Desktop or Docker Engine with Compose.

1. Copy `.env.example` to `.env` and replace the example database password with a strong local value.
2. Build and start the complete stack:

   ```powershell
   docker compose up --build -d
   ```

3. Open `http://127.0.0.1:8088`. The API is also available at `http://127.0.0.1:8080`; API and processor readiness endpoints are `/actuator/health/readiness` and `http://127.0.0.1:8081/ready`.
4. Pull the preferred Qwen model when the machine has enough memory/disk:

   ```powershell
   docker compose --profile models run --rm ollama-model
   ```

Until Qwen is pulled, `IES_AI_DEMO_FALLBACK=true` keeps the workflow usable and labels the mapping engine accordingly. PaddleOCR is included in the AI-worker image. `docker compose down` stops the demo while retaining database, model and invoice volumes; do not use `down -v` if those local artifacts must be preserved.

## Local developer mode

Prerequisites: PostgreSQL 15+, Node 22+ with pnpm 11, and Python 3.11+.

1. Start dependencies: `docker compose up -d postgres ollama`.
2. Start the AI worker from `ai-worker`: `uvicorn app.main:app --port 8090`.
3. From `backend`, run `pnpm install --frozen-lockfile`, `pnpm migrate`, then start `pnpm dev:api` and `pnpm dev:processor` in separate terminals.
4. Start the UI from `frontend`: `pnpm install --frozen-lockfile && pnpm run dev`.

Every runtime uses PostgreSQL; there is no H2-only schema. Local and container demos default to authentication-off, while production deployment must enable OIDC/JWT.

## Kubernetes

The Kustomize baseline in [`deploy/k8s`](deploy/k8s/README.md) uses non-root containers, health probes, resource limits, default-deny network policies and autoscaling for the AI-worker tier. Stateful dependencies remain external so each environment can use approved managed or in-house services.

## Accuracy and performance gates

The requirements `>=95% field accuracy`, `>=200 invoices/hour`, and `<15s latency` are acceptance targets. They are not claimed until the benchmark set contains labelled, representative invoices and the generated report passes all gates. See [docs/ACCEPTANCE_TEST_PLAN.md](docs/ACCEPTANCE_TEST_PLAN.md).

The repository includes a deterministic synthetic invoice generator, degraded-scan variants, an API benchmark runner, strict missing-document penalties, line-item metrics and quality/layout breakdowns. See [docs/BENCHMARKING.md](docs/BENCHMARKING.md). Synthetic results are regression evidence only and are never presented as production accuracy.

The current Node/PaddleOCR synthetic regression passes all configured gates at 98.48% scalar-field accuracy, 100% critical-field accuracy, 98.11% line-item F1, 1,357 invoices/hour and 12.324s p95 latency after model warm-up. See [the Node v2 baseline](docs/baselines/SYNTHETIC_NODE_V2_BASELINE.md) for scope and limitations.

## Confidential GitHub workflow

Do not push invoice samples, OCR text, extracted JSON, model weights, database dumps, tokens, or `.env` files. Before every push:

```powershell
./scripts/security-check.ps1
git status --short
git diff --cached
```

Use a hardware-backed SSH key or GitHub credential manager, enable 2FA, branch protection, secret scanning/push protection, Dependabot, and least-privilege collaborator access.
