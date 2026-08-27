import pytest

from invoice_extraction.ingestion import DocumentFormat, validate_document


def test_validates_extension_and_magic_bytes() -> None:
    assert validate_document("invoice.pdf", b"%PDF-1.7\n", max_bytes=100) is DocumentFormat.PDF


def test_rejects_renamed_or_oversized_documents() -> None:
    with pytest.raises(ValueError, match="does not match"):
        validate_document("invoice.pdf", b"\x89PNG\r\n\x1a\n", max_bytes=100)
    with pytest.raises(ValueError, match="upload limit"):
        validate_document("invoice.pdf", b"%PDF-1.7\n", max_bytes=5)
