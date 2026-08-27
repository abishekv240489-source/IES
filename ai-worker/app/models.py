from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractedField(BaseModel):
    value: Any | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Literal["embedded-text", "paddleocr", "qwen", "heuristic", "review"] = "heuristic"
    page: int | None = None


class Header(BaseModel):
    invoiceNumber: ExtractedField = ExtractedField()
    invoiceDate: ExtractedField = ExtractedField()
    dueDate: ExtractedField = ExtractedField()
    currency: ExtractedField = ExtractedField()
    poReference: ExtractedField = ExtractedField()


class Vendor(BaseModel):
    name: ExtractedField = ExtractedField()
    address: ExtractedField = ExtractedField()
    country: ExtractedField = ExtractedField()
    taxRegistration: ExtractedField = ExtractedField()
    contact: ExtractedField = ExtractedField()


class BillTo(BaseModel):
    entity: ExtractedField = ExtractedField()
    address: ExtractedField = ExtractedField()
    businessUnit: ExtractedField = ExtractedField()
    accountingReference: ExtractedField = ExtractedField()


class Vessel(BaseModel):
    name: ExtractedField = ExtractedField()
    voyage: ExtractedField = ExtractedField()
    imo: ExtractedField = ExtractedField()
    port: ExtractedField = ExtractedField()


class Amounts(BaseModel):
    subtotal: ExtractedField = ExtractedField()
    tax: ExtractedField = ExtractedField()
    discount: ExtractedField = ExtractedField()
    shipping: ExtractedField = ExtractedField()
    total: ExtractedField = ExtractedField()
    exchangeRate: ExtractedField = ExtractedField()


class BankDetails(BaseModel):
    bankName: ExtractedField = ExtractedField()
    beneficiary: ExtractedField = ExtractedField()
    accountNumber: ExtractedField = ExtractedField()
    iban: ExtractedField = ExtractedField()
    swiftBic: ExtractedField = ExtractedField()


class LineItem(BaseModel):
    lineNumber: ExtractedField = ExtractedField()
    description: ExtractedField = ExtractedField()
    quantity: ExtractedField = ExtractedField()
    unitPrice: ExtractedField = ExtractedField()
    amount: ExtractedField = ExtractedField()
    chargeCode: ExtractedField = ExtractedField()


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    header: Header = Header()
    vendor: Vendor = Vendor()
    billTo: BillTo = BillTo()
    vessel: Vessel = Vessel()
    amounts: Amounts = Amounts()
    bankDetails: BankDetails = BankDetails()
    lineItems: list[LineItem] = []
    notes: ExtractedField = ExtractedField()


class OcrPage(BaseModel):
    page: int
    text: str
    confidence: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    used_preprocessing: bool


class ExtractionResponse(BaseModel):
    document_id: str
    invoice: Invoice
    overall_confidence: float = Field(ge=0, le=1)
    engine: str
    schema_version: str = "1.0"
    ocr_pages: int
    processing_ms: int
    warnings: list[str] = []
