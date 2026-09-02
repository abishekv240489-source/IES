from __future__ import annotations

import hashlib
import logging
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .confidence import MAPPING_WEIGHT, METHOD, OCR_WEIGHT, fuse_invoice_confidence
from .config import settings
from .mapper import map_invoice
from .models import ConfidenceBreakdown, ExtractionResponse
from .ocr import extract_document

logger = logging.getLogger("ies.ai-worker")
app = FastAPI(title="IES AI Worker", version="0.1.0", docs_url="/docs")
REQUIRED_FORM = Form(...)
REQUIRED_FILE = File(...)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "UP",
        "mapping_provider": settings.mapping_provider,
        "ocr_engine": "paddleocr",
        "paddle_required": settings.paddle_required,
    }


@app.post("/v1/extract", response_model=ExtractionResponse)
async def extract(document_id: str = REQUIRED_FORM, file: UploadFile = REQUIRED_FILE) -> ExtractionResponse:
    started = time.perf_counter()
    suffix = Path(file.filename or "invoice").suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise HTTPException(status_code=415, detail="Unsupported invoice type")

    byte_count = 0
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix="ies-") as temp_dir:
        target = Path(temp_dir) / f"document{suffix}"
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                byte_count += len(chunk)
                if byte_count > settings.max_file_bytes:
                    raise HTTPException(status_code=413, detail="Invoice exceeds size limit")
                digest.update(chunk)
                output.write(chunk)
        try:
            pages, ocr_engine, ocr_warnings = extract_document(target)
            text = "\n\n".join(f"--- PAGE {page.page} ---\n{page.text}" for page in pages)
            invoice, mapping_engine, mapping_warnings = map_invoice(text)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            logger.exception("Extraction failed document_id=%s sha256_prefix=%s", document_id, digest.hexdigest()[:12])
            raise HTTPException(status_code=502, detail="Extraction pipeline failed") from error

    confidence = fuse_invoice_confidence(invoice, pages)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    return ExtractionResponse(
        document_id=document_id,
        invoice=invoice,
        overall_confidence=confidence.overall,
        engine=f"{ocr_engine}+{mapping_engine}",
        ocr_pages=len(pages),
        processing_ms=elapsed_ms,
        confidence_breakdown=ConfidenceBreakdown(
            method=METHOD,
            mapping_weight=MAPPING_WEIGHT,
            ocr_weight=OCR_WEIGHT,
            mapping_confidence=confidence.mapping,
            ocr_confidence=confidence.ocr,
            populated_fields=confidence.populated_fields,
        ),
        warnings=ocr_warnings + mapping_warnings,
    )
