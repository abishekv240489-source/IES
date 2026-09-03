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
            busy = await asyncio.wait_for(client.post(
                "/v1/extract", data={"document_id": "second"},
                files={"file": ("invoice.pdf", b"%PDF-test", "application/pdf")},
            ), timeout=0.5)
            assert busy.status_code == 503
            assert busy.json()["detail"] == "AI_WORKER_BUSY"
            release_pipeline.set()
            response = await extraction
            assert response.status_code == 200

    asyncio.run(exercise())


def test_cancelled_request_retains_file_and_exclusive_slot(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    paths = []

    def slow_pipeline(path):
        paths.append(path)
        started.set()
        assert release.wait(3)
        assert path.exists()
        return [], "test", [], Invoice(), "test", []

    monkeypatch.setattr(main, "_run_pipeline", slow_pipeline)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            task = asyncio.create_task(client.post("/v1/extract", data={"document_id": "cancel"},
                                                  files={"file": ("invoice.pdf", b"%PDF-test")}))
            assert await asyncio.to_thread(started.wait, 1)
            task.cancel()
            await asyncio.sleep(0.02)
            assert main.PIPELINE_SEMAPHORE.locked()
            assert paths[0].exists()
            release.set()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert not main.PIPELINE_SEMAPHORE.locked()
            assert not paths[0].exists()

    asyncio.run(exercise())
