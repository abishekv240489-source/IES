from __future__ import annotations

import asyncio
import threading

import httpx

from app import main
from app.models import Invoice, OcrPage


def test_health_remains_responsive_during_ocr(monkeypatch) -> None:
    pipeline_started = threading.Event()
    release_pipeline = threading.Event()

    def slow_ocr(_target):
        pipeline_started.set()
        assert release_pipeline.wait(timeout=2)
        return [OcrPage(page=1, text="Invoice", confidence=0.9, quality_score=0.9,
                        used_preprocessing=False)], "paddleocr", []

    monkeypatch.setattr(main, "extract_document", slow_ocr)
    monkeypatch.setattr(main, "map_invoice", lambda _text: (Invoice(), "test-mapper", []))

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            extraction = asyncio.create_task(client.post(
                "/v1/extract",
                data={"document_id": "test-document"},
                files={"file": ("invoice.pdf", b"%PDF-test", "application/pdf")},
            ))
            assert await asyncio.to_thread(pipeline_started.wait, 1)
            health = await asyncio.wait_for(client.get("/health"), timeout=0.5)
            assert health.status_code == 200
            release_pipeline.set()
            response = await extraction
            assert response.status_code == 200

    asyncio.run(exercise())
