# Architecture Migration Context
- Deprecate HTTP/IPC calls to the Python `ai-worker` microservice.
- Implement direct VLM document extraction inside `backend/src/services/processor/ai-client.ts`.
- Engine: Google Gemini Flash (`gemini-1.5-flash` or `gemini-2.0-flash`) using `@google/genai`.
- Input: Invoice PDF or rendered page images.
- Output: Strictly typed JSON adhering to PIL shipping schema with per-field confidence scores.