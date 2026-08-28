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
- PostgreSQL migrations; Redis/Kafka-ready local topology
- Accuracy, latency and throughput benchmark harnesses (targets are measured, never assumed)

## Architecture

```text
React 18 + MUI
      |
Spring Boot 3.5 / Java 21 API
      |--- PostgreSQL (transactional state + audit)
      |--- Redis (cache/idempotency; production profile)
      |--- Kafka (durable work events; production profile)
      |
Python AI worker
      |--- embedded-text detection
      |--- low-quality preprocessing
      |--- PaddleOCR / PaddleX
      `--- Qwen 2.5 7B via Ollama-compatible API
```

The screenshot's `Spring Boot 5.1.x` is interpreted as **Spring Batch 5.1.x**. Spring Boot itself is pinned to the supported 3.5 line for Java 21 compatibility. The AI runtime is isolated as a Python service because PaddleOCR is Python-native; the enterprise API, workflow and data boundary remain Java/Spring.

## One-command container demo

Prerequisites: Docker Desktop or Docker Engine with Compose.

1. Copy `.env.example` to `.env` and replace both example passwords with strong local values.
2. Build and start the complete stack:

   ```powershell
   docker compose up --build -d
   ```

3. Open `http://127.0.0.1:8088`. The API is also available at `http://127.0.0.1:8080` and Swagger UI at `http://127.0.0.1:8080/swagger-ui/index.html`.
4. Pull the preferred Qwen model when the machine has enough memory/disk:

   ```powershell
   docker compose --profile models run --rm ollama-model
   ```

Until Qwen is pulled, `IES_AI_DEMO_FALLBACK=true` keeps the workflow usable and labels the mapping engine accordingly. PaddleOCR is included in the AI-worker image. `docker compose down` stops the demo while retaining database, model and invoice volumes; do not use `down -v` if those local artifacts must be preserved.

## Local developer mode

Prerequisites: Java 21+, Maven 3.9+, Node 20+ and Python 3.11+.

1. Start dependencies: `docker compose up -d postgres redis kafka ollama`.
2. Start the AI worker from `ai-worker`: `uvicorn app.main:app --port 8090`.
3. Start the API from `backend`: `mvn spring-boot:run -Dspring-boot.run.profiles=local`.
4. Start the UI from `frontend`: `pnpm install && pnpm run dev`.

The local Spring profile uses H2 and disables authentication for fast development. The container topology uses PostgreSQL and still defaults to demo authentication-off; production deployment must enable OIDC/JWT.

## Kubernetes

The Kustomize baseline in [`deploy/k8s`](deploy/k8s/README.md) uses non-root containers, health probes, resource limits, default-deny network policies and autoscaling for the AI-worker tier. Stateful dependencies remain external so each environment can use approved managed or in-house services.

## Accuracy and performance gates

The requirements `>=95% field accuracy`, `>=200 invoices/hour`, and `<15s latency` are acceptance targets. They are not claimed until the benchmark set contains labelled, representative invoices and the generated report passes all gates. See [docs/ACCEPTANCE_TEST_PLAN.md](docs/ACCEPTANCE_TEST_PLAN.md).

## Confidential GitHub workflow

Do not push invoice samples, OCR text, extracted JSON, model weights, database dumps, tokens, or `.env` files. Before every push:

```powershell
./scripts/security-check.ps1
git status --short
git diff --cached
```

Use a hardware-backed SSH key or GitHub credential manager, enable 2FA, branch protection, secret scanning/push protection, Dependabot, and least-privilege collaborator access.
