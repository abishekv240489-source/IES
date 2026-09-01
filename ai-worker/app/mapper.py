from __future__ import annotations

import json
import re
from datetime import date
from time import strptime
from typing import Any

import httpx

from .config import settings
from .models import ExtractedField, Invoice, LineItem

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
    invoice.header.invoiceNumber = _find(
        text,
        [
            (
                r"(?m)^\s*(?:invoice\s*(?:no\.?|number|#)|inv\s*#)\s*[:#-]?\s*"
                r"((?=[A-Z0-9/_-]*\d)[A-Z0-9][A-Z0-9/_-]+)\s*$"
            ),
            r"(?m)^\s*((?=[A-Z0-9/_-]*\d)[A-Z]{2,12}-[A-Z0-9/_-]{3,})\s*$",
        ],
        0.72,
    )
    invoice.header.poReference = _find(
        text,
        [(
            r"(?m)^\s*(?:purchase[ \t]+order|p\.?o\.?(?:[ \t]+no\.?)?)[ \t]*[:#-][ \t]*"
            r"([A-Z0-9][A-Z0-9/_-]+)[ \t]*$"
        )],
        0.68,
    )
    invoice.header.invoiceDate = _date(text, [r"invoice\s*date\s*[:#-]?\s*([^\n]+)", r"date\s*[:#-]?\s*([^\n]+)"])
    invoice.header.dueDate = _date(text, [r"due\s*date\s*[:#-]?\s*([^\n]+)"])
    invoice.header.currency = _find(
        text,
        [r"(?:currency|total)\s*[:#-]?\s*(USD|EUR|GBP|SGD|INR|AUD|CAD|JPY|CNY|AED|MYR)\b",
         r"\b(USD|EUR|GBP|SGD|INR|AUD|CAD|JPY|CNY|AED|MYR)\b"],
        0.75,
        upper=True,
    )
    invoice.vendor.name = _find(
        text, [r"(?m)^\s*(?:vendor|supplier|from)[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.58
    )
    invoice.vendor.country = _find(
        text, [r"(?m)^\s*country[ \t]*[:#-][ \t]*([^\n]{2,80})"], 0.68
    )
    invoice.vendor.taxRegistration = _find(
        text,
        [(
            r"(?m)^\s*(?:vat|gst|tax)[ \t]*(?:registration|reg|id|no\.?|#)[ \t]*"
            r"[:#-][ \t]*([A-Z0-9-]{5,30})"
        )],
        0.65,
    )
    invoice.vendor.contact = _find(
        text, [r"(?m)^\s*contact[ \t]*[:#-][ \t]*([^\n]{3,100})"], 0.66
    )
    invoice.billTo.businessUnit = _find(
        text, [r"(?m)^\s*business[ \t]+unit[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.68
    )
    invoice.billTo.accountingReference = _find(
        text,
        [r"(?m)^\s*accounting[ \t]+(?:reference|ref)[ \t]*[:#-][ \t]*([^\n]{2,80})"],
        0.68,
    )
    invoice.vessel.name = _find(
        text, [r"(?m)^\s*vessel[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.70
    )
    invoice.vessel.voyage = _find(
        text, [r"(?m)^\s*voyage[ \t]*[:#-][ \t]*([^\n]{2,50})"], 0.70
    )
    invoice.vessel.imo = _find(
        text, [r"(?m)^\s*imo[ \t]*(?:[:#-][ \t]*)?(\d{7})\b"], 0.72
    )
    invoice.vessel.port = _find(text, [r"(?m)^\s*port[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.68)
    invoice.amounts.subtotal = _label_amount(text, r"subtotal")
    invoice.amounts.tax = _label_amount(text, r"(?:tax|vat|gst)(?:[ \t]+amount)?")
    invoice.amounts.discount = _label_amount(text, r"discount")
    invoice.amounts.shipping = _label_amount(text, r"(?:shipping|freight)")
    invoice.amounts.total = _amount(
        text,
        [
            r"(?m)^\s*(?:grand\s*total|invoice\s*total|total\s*due|amount\s*due|total)\b(?:\s+[A-Z]{3})?\s*[: ]\s*[^\d-]*([\d,.]+)",
            r"(?m)^\s*total\s+[A-Z]{3}\s*$\s*([\d,.]+)",
        ],
        0.72,
    )
    invoice.amounts.exchangeRate = _label_amount(text, r"exchange[ \t]+rate", 0.66)
    invoice.bankDetails.bankName = _find(
        text, [r"(?m)^\s*bank[ \t]+name[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.55
    )
    invoice.bankDetails.beneficiary = _find(
        text, [r"(?m)^\s*beneficiary[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.65
    )
    invoice.bankDetails.accountNumber = _find(text, [r"(?:account|a/c)\s*(?:number|no\.?|#)\s*[:#-]?\s*([A-Z0-9 -]{5,40})"], 0.66)
    invoice.bankDetails.iban = _find(text, [r"\bIBAN\s*[:#-]?\s*([A-Z]{2}\d{2}[A-Z0-9 ]{10,32})"], 0.72, upper=True)
    invoice.bankDetails.swiftBic = _find(text, [r"(?:swift|bic)\s*(?:code)?\s*[:#-]?\s*([A-Z0-9]{8,11})"], 0.72, upper=True)
    invoice.notes = _find(
        text,
        [r"(?m)^\s*((?:payment|please|notes?|terms?)\b[^\n]{8,300})"],
        0.58,
    )
    _map_supplier_and_bill_to_block(invoice, text)
    invoice.lineItems = _line_items(text)
    return invoice


def _map_supplier_and_bill_to_block(invoice: Invoice, text: str) -> None:
    lines = _lines(text)
    supplier_index = next(
        (index for index, value in enumerate(lines) if re.match(r"(?i)^(?:supplier|vendor|from)\s*:", value)),
        None,
    )
    if supplier_index is None or supplier_index + 3 >= len(lines):
        return
    candidates = lines[supplier_index + 1:supplier_index + 4]
    if not any(":" in value for value in candidates):
        invoice.billTo.entity = _field(candidates[0], 0.62)
        invoice.vendor.address = _field(candidates[1], 0.60)
        invoice.billTo.address = _field(candidates[2], 0.60)


def _line_items(text: str) -> list[LineItem]:
    lines = _lines(text)
    header_end = next((index for index, value in enumerate(lines) if value.upper() == "AMOUNT"), None)
    subtotal = next(
        (index for index, value in enumerate(lines) if header_end is not None and index > header_end and
         re.match(r"(?i)^subtotal\b", value)),
        None,
    )
    if header_end is None or subtotal is None:
        return []
    body = lines[header_end + 1:subtotal]
    items: list[LineItem] = []
    index = 0
    while index + 5 < len(body):
        embedded_order = _line_number(body[index]) and body[index + 2].lower().startswith("charge code")
        ocr_order = _line_number(body[index + 1]) and body[index + 5].lower().startswith("charge code")
        degraded_ocr_order = _line_number(body[index + 4]) and body[index + 5].lower().startswith("charge code")
        if embedded_order:
            number, description, code, quantity, unit_price, amount = body[index:index + 6]
        elif ocr_order:
            description, number, quantity, unit_price, amount, code = body[index:index + 6]
        elif degraded_ocr_order:
            description, quantity, unit_price, amount, number, code = body[index:index + 6]
        else:
            index += 1
            continue
        parsed = [_number(quantity), _number(unit_price), _number(amount)]
        if any(value is None for value in parsed):
            index += 1
            continue
        items.append(LineItem(
            lineNumber=_field(number, 0.70),
            description=_field(description, 0.66),
            quantity=_field(parsed[0], 0.70),
            unitPrice=_field(parsed[1], 0.70),
            amount=_field(parsed[2], 0.70),
            chargeCode=_field(code.split(":", 1)[-1].strip(), 0.68),
        ))
        index += 6
    return items


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip() and
            not line.strip().startswith("--- PAGE")]


def _line_number(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}", value.strip()))


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def _field(value: Any, score: float) -> ExtractedField:
    return ExtractedField(value=value, confidence=score, source="heuristic")


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


def _label_amount(text: str, label: str, score: float = 0.68) -> ExtractedField:
    return _amount(
        text,
        [rf"(?m)^\s*{label}[ \t]*(?:[:#-][ \t]*|[ \t]*\n[ \t]*)([\d,.]+)[ \t]*$"],
        score,
    )


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
