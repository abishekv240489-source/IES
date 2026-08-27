from __future__ import annotations

import json

import httpx

from invoice_extraction.domain.models import ExtractedInvoice


class OllamaMapper:
    """Use Qwen only to select/map already-normalized evidence into the schema."""

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float = 45) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def map(self, evidence_json: str) -> ExtractedInvoice:
        schema = ExtractedInvoice.model_json_schema()
        payload = {
            "model": self._model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": 4096},
            "prompt": (
                "Return one JSON object matching the schema. Select only values explicitly present "
                "in the candidate evidence. Use null when unsupported. Do not calculate, repair, "
                "or guess.\nEVIDENCE:\n" + evidence_json
            ),
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/generate", json=payload)
            response.raise_for_status()
        body = response.json()
        mapped = json.loads(body["response"])
        return ExtractedInvoice.model_validate(mapped)
