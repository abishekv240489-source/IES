from __future__ import annotations

from enum import Enum
from pathlib import Path


class DocumentFormat(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"


_EXTENSIONS = {
    ".pdf": DocumentFormat.PDF,
    ".png": DocumentFormat.PNG,
    ".jpg": DocumentFormat.JPEG,
    ".jpeg": DocumentFormat.JPEG,
    ".tif": DocumentFormat.TIFF,
    ".tiff": DocumentFormat.TIFF,
}


def _signature(data: bytes) -> DocumentFormat | None:
    if data.startswith(b"%PDF-"):
        return DocumentFormat.PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return DocumentFormat.PNG
    if data.startswith(b"\xff\xd8\xff"):
        return DocumentFormat.JPEG
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return DocumentFormat.TIFF
    return None


def validate_document(filename: str, data: bytes, *, max_bytes: int) -> DocumentFormat:
    """Validate size, extension, and magic bytes before decoding or OCR."""
    if not data:
        raise ValueError("Document is empty")
    if len(data) > max_bytes:
        raise ValueError(f"Document exceeds the {max_bytes}-byte upload limit")
    extension_format = _EXTENSIONS.get(Path(filename).suffix.lower())
    if extension_format is None:
        raise ValueError("Unsupported document extension")
    signature_format = _signature(data)
    if signature_format is None:
        raise ValueError("Unsupported or corrupt document signature")
    if extension_format != signature_format:
        raise ValueError("Document extension does not match its content")
    return signature_format
