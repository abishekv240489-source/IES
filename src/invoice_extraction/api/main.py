from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile

from invoice_extraction import __version__
from invoice_extraction.config import get_settings
from invoice_extraction.ingestion import validate_document

app = FastAPI(title="Invoice Extraction System", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/v1/documents/validate")
async def validate_upload(file: Annotated[UploadFile, File()]) -> dict[str, str | int]:
    settings = get_settings()
    data = await file.read(settings.max_upload_bytes + 1)
    try:
        document_format = validate_document(
            file.filename or "unnamed", data, max_bytes=settings.max_upload_bytes
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"filename": file.filename or "unnamed", "bytes": len(data), "format": document_format}
