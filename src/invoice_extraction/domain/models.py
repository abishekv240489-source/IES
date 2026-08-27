from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CandidateKind(str, Enum):
    INVOICE_NUMBER = "invoice_number"
    INVOICE_DATE = "invoice_date"
    DUE_DATE = "due_date"
    PURCHASE_ORDER = "purchase_order"
    BOOKING_NUMBER = "booking_number"
    CURRENCY = "currency"
    SUBTOTAL = "subtotal"
    TAX = "tax"
    DISCOUNT = "discount"
    FREIGHT = "freight"
    INSURANCE = "insurance"
    TOTAL = "total"
    AMOUNT_DUE = "amount_due"
    SUPPLIER_NAME = "supplier_name"
    CUSTOMER_NAME = "customer_name"
    PAYMENT_TERMS = "payment_terms"
    BANK_NAME = "bank_name"
    ACCOUNT_NAME = "account_name"
    ACCOUNT_NUMBER = "account_number"
    IBAN = "iban"
    SWIFT = "swift"


class OcrToken(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    page: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float


class FieldCandidate(BaseModel):
    kind: CandidateKind
    raw_value: str
    normalized_value: str
    confidence: float = Field(ge=0, le=1)
    page: int = Field(ge=1)
    evidence: str = Field(max_length=500)


class MoneyValue(BaseModel):
    amount: Decimal
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class Party(BaseModel):
    name: str | None = None
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_id: str | None = None


class BankDetails(BaseModel):
    bank_name: str | None = None
    account_name: str | None = None
    account_number: str | None = None
    iban: str | None = None
    swift: str | None = None


class LineItem(BaseModel):
    description: str
    item_code: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    tax_rate: Decimal | None = None
    discount: Decimal | None = None
    amount: Decimal | None = None


class ExtractedInvoice(BaseModel):
    supplier: Party = Field(default_factory=Party)
    customer: Party = Field(default_factory=Party)
    supplier_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    purchase_order: str | None = None
    booking_number: str | None = None
    payment_terms: str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    discount: Decimal | None = None
    freight: Decimal | None = None
    insurance: Decimal | None = None
    total: Decimal | None = None
    amount_due: Decimal | None = None
    bank_details: BankDetails = Field(default_factory=BankDetails)
    line_items: list[LineItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
