from __future__ import annotations

import json
import re
from datetime import date
from time import strptime
from typing import Any

import httpx

from .config import settings
from .models import ExtractedField, Invoice

SYSTEM_PROMPT = """You extract supplier invoice data. Return only JSON matching the supplied schema.
Never invent values. Use null when absent. Each leaf is {"value":...,"confidence":0..1,"source":"qwen","page":null}.
Dates use YYYY-MM-DD, currency uses ISO 4217, amounts are numbers. Preserve account identifiers as strings.
The root keys are header, vendor, billTo, vessel, amounts, bankDetails, lineItems, notes."""


def map_invoice(text: str) -> tuple[Invoice, str, list[str]]:
    warnings: list[str] = []
    if settings.mapping_provider == "ollama" and text.strip():
        try:
            return _qwen(text), f"qwen:{settings.ollama_model}", warnings
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            if not settings.demo_fallback:
                raise
            warnings.append(f"Qwen unavailable or invalid; heuristic fallback used ({type(exc).__name__})")
    return heuristic_map(text), "heuristic", warnings


def _qwen(text: str) -> Invoice:
    schema = Invoice.model_json_schema()
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": schema,
        "options": {"temperature": 0, "num_ctx": 16384},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:60000]},
        ],
    }
    response = httpx.post(f"{settings.ollama_base_url}/api/chat", json=payload,
                          timeout=settings.request_timeout_seconds)
    response.raise_for_status()
    content = response.json()["message"]["content"]
    return Invoice.model_validate_json(content)


def heuristic_map(text: str) -> Invoice:
    invoice = Invoice()
    invoice.header.invoiceNumber = _find(text, [r"(?:invoice\s*(?:no\.?|number|#)|inv\s*#)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]+)"], 0.72)
    invoice.header.poReference = _find(text, [r"(?:purchase\s*order|p\.?o\.?\s*(?:no\.?|#)?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]+)"], 0.68)
    invoice.header.invoiceDate = _date(text, [r"invoice\s*date\s*[:#-]?\s*([^\n]+)", r"date\s*[:#-]?\s*([^\n]+)"])
    invoice.header.dueDate = _date(text, [r"due\s*date\s*[:#-]?\s*([^\n]+)"])
    invoice.header.currency = _find(text, [r"\b(USD|EUR|GBP|SGD|INR|AUD|CAD|JPY|CNY|AED|MYR)\b"], 0.75, upper=True)
    invoice.vendor.name = _find(text, [r"(?:vendor|supplier|from)\s*[:#-]?\s*([^\n]{2,100})"], 0.58)
    invoice.vendor.taxRegistration = _find(text, [r"(?:vat|gst|tax)\s*(?:registration|reg|id|no\.?|#)?\s*[:#-]?\s*([A-Z0-9-]{5,30})"], 0.65)
    invoice.amounts.subtotal = _amount(text, [r"subtotal\s*[: ]\s*[^\d-]*([\d,.]+)"])
    invoice.amounts.tax = _amount(text, [r"(?:tax|vat|gst)\s*(?:amount)?\s*[: ]\s*[^\d-]*([\d,.]+)"])
    invoice.amounts.total = _amount(
        text,
        [r"(?m)^\s*(?:grand\s*total|invoice\s*total|total\s*due|amount\s*due|total)\b\s*[: ]\s*[^\d-]*([\d,.]+)"],
        0.72,
    )
    invoice.bankDetails.bankName = _find(text, [r"bank\s*(?:name)?\s*[:#-]?\s*([^\n]{2,100})"], 0.55)
    invoice.bankDetails.accountNumber = _find(text, [r"(?:account|a/c)\s*(?:number|no\.?|#)\s*[:#-]?\s*([A-Z0-9 -]{5,40})"], 0.66)
    invoice.bankDetails.iban = _find(text, [r"\bIBAN\s*[:#-]?\s*([A-Z]{2}\d{2}[A-Z0-9 ]{10,32})"], 0.72, upper=True)
    invoice.bankDetails.swiftBic = _find(text, [r"(?:swift|bic)\s*(?:code)?\s*[:#-]?\s*([A-Z0-9]{8,11})"], 0.72, upper=True)
    return invoice


def _find(text: str, patterns: list[str], confidence: float, upper: bool = False) -> ExtractedField:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" :-")
            return ExtractedField(value=value.upper() if upper else value, confidence=confidence, source="heuristic")
    return ExtractedField()


def _amount(text: str, patterns: list[str], confidence: float = 0.68) -> ExtractedField:
    field = _find(text, patterns, confidence)
    if field.value is None:
        return field
    raw = str(field.value).replace(",", "")
    try:
        field.value = float(raw)
    except ValueError:
        field.value = None
        field.confidence = 0
    return field


def _date(text: str, patterns: list[str]) -> ExtractedField:
    field = _find(text, patterns, 0.64)
    if field.value is None:
        return field
    candidate = str(field.value).split()[0].strip(".,")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%b-%Y"):
        try:
            parsed = strptime(candidate, fmt)
            field.value = date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
            return field
        except ValueError:
            continue
    field.value = candidate
    field.confidence = 0.35
    return field


def confidence(invoice: Invoice, ocr_confidence: float) -> float:
    values: list[float] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "value" in value and "confidence" in value and value["value"] not in (None, ""):
                values.append(float(value["confidence"]))
            else:
                for nested in value.values():
                    walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(invoice.model_dump())
    field_score = sum(values) / len(values) if values else 0
    return round(0.75 * field_score + 0.25 * ocr_confidence, 4)
