from __future__ import annotations

import json
import re
from datetime import date
from time import strptime
from typing import Any

import httpx
from pydantic import BaseModel

from .config import settings
from .models import ExtractedField, Invoice, LineItem

SYSTEM_PROMPT = """You extract supplier invoice data. Return only JSON matching the supplied schema.
Never invent values. Use null when absent. Each leaf is {"value":...,"confidence":0..1,"source":"qwen","page":1}.
Set page to the 1-based PAGE marker containing the evidence, or null only when it cannot be identified.
Dates use YYYY-MM-DD, currency uses ISO 4217, amounts are numbers. Preserve account identifiers as strings.
The root keys are header, vendor, billTo, vessel, amounts, bankDetails, lineItems, notes."""


def map_invoice(text: str) -> tuple[Invoice, str, list[str]]:
    warnings: list[str] = []
    deterministic = heuristic_map(text)
    if settings.mapping_provider == "hybrid" and _ready_for_fast_path(deterministic):
        return deterministic, "evidence-mapper", warnings
    if settings.mapping_provider in {"hybrid", "ollama"} and text.strip():
        try:
            mapped = _fill_missing(_qwen(text), deterministic)
            return mapped, f"qwen:{settings.ollama_model}+evidence-merge", warnings
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            if not settings.demo_fallback:
                raise
            warnings.append(f"Qwen unavailable or invalid; heuristic fallback used ({type(exc).__name__})")
    return deterministic, "heuristic", warnings


def _ready_for_fast_path(invoice: Invoice) -> bool:
    required = (
        invoice.header.invoiceNumber,
        invoice.header.invoiceDate,
        invoice.header.currency,
        invoice.vendor.name,
        invoice.amounts.total,
    )
    return (
        all(field.value not in (None, "") for field in required)
        and bool(invoice.lineItems)
        and _populated_fields(invoice) >= settings.hybrid_min_populated_fields
    )


def _populated_fields(value: Any) -> int:
    if isinstance(value, ExtractedField):
        return int(value.value not in (None, ""))
    if isinstance(value, BaseModel):
        return sum(_populated_fields(getattr(value, name)) for name in type(value).model_fields)
    if isinstance(value, list):
        return sum(_populated_fields(item) for item in value)
    return 0


def _fill_missing(primary: Invoice, fallback: Invoice) -> Invoice:
    def merge(target: Any, evidence: Any) -> Any:
        if isinstance(target, ExtractedField) and isinstance(evidence, ExtractedField):
            if target.value in (None, "") and evidence.value not in (None, ""):
                return evidence.model_copy(deep=True)
            return target
        if isinstance(target, BaseModel) and isinstance(evidence, BaseModel):
            for name in type(target).model_fields:
                setattr(target, name, merge(getattr(target, name), getattr(evidence, name)))
            return target
        if isinstance(target, list) and isinstance(evidence, list) and not target:
            return [item.model_copy(deep=True) if isinstance(item, BaseModel) else item for item in evidence]
        return target

    return merge(primary, fallback)


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
            r"(?m)^\s*invoice\s*(?:no\.?|number|#)\s*:\s*$\s*(?:company\s*:\s*$\s*)?((?=[A-Z0-9/_-]*\d)[A-Z0-9][A-Z0-9/_-]+)\s*$",
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
        [r"(?m)^\s*customer\s+order\s+reference\s*[:#-]\s*([A-Z0-9][A-Z0-9/_-]+)\s*$", (
            r"(?m)^\s*(?:purchase[ \t]+order|p\.?o\.?(?:[ \t]+no\.?)?)[ \t]*[:#-][ \t]*"
            r"([A-Z0-9][A-Z0-9/_-]+)[ \t]*$"
        ), r"(?m)^\s*((?:PO|KRM|ELN)-[A-Z0-9][A-Z0-9/_-]+)\s*$"],
        0.68,
    )
    date_value = r"(\d{1,4}(?:[./-]\d{1,2}[./-]\d{1,4}|[ ./-][A-Za-z]{3,9}[ ./-]\d{2,4}))"
    invoice.header.invoiceDate = _date(
        text, [rf"invoice\s*date\s*[:#-]?\s*{date_value}", rf"(?m)^\s*date\s*[:#-]?\s*{date_value}"]
    )
    invoice.header.dueDate = _date(text, [rf"due\s*date\s*[:#-]?\s*{date_value}"])
    invoice.header.currency = _find(
        text,
        [r"(?:currency|total)\s*[:#-]?\s*(USD|EUR|GBP|SGD|INR|AUD|CAD|JPY|CNY|AED|MYR)\b",
         r"\b(USD|EUR|GBP|SGD|INR|AUD|CAD|JPY|CNY|AED|MYR)\b"],
        0.75,
        upper=True,
    )
    if invoice.header.currency.value is None and re.search(r"(?<!\w)S\$(?!\w)", text):
        invoice.header.currency = _field("SGD", 0.72)
    invoice.vendor.name = _find(
        text, [r"(?m)^\s*(?:vendor|supplier|from)[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.58
    )
    if invoice.vendor.name.value is None:
        company_names = _company_names(text)
        if company_names:
            invoice.vendor.name = _field(company_names[0], 0.72)
    invoice.vendor.country = _find(
        text, [r"(?m)^\s*country[ \t]*[:#-][ \t]*([^\n]{2,80})"], 0.68
    )
    invoice.vendor.taxRegistration = _find(
        text,
        [(
            r"(?m)^\s*(?:seller[ \t]+)?(?:vat|gst|tax)[ \t]*(?:registration|reg|id|no\.?|#)[ \t]*"
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
    invoice.billTo.entity = _find(
        text,
        [r"(?mi)^\s*(?:sold\s+to|bill\s+to)\s*:?[ \t]*\n[ \t]*([^\n]{3,120})"],
        0.70,
    )
    if invoice.billTo.entity.value is None:
        company_names = _company_names(text)
        if len(company_names) > 1:
            invoice.billTo.entity = _field(company_names[1], 0.66)
    invoice.vessel.name = _find(
        text, [r"(?mi)^\s*vessel\s+name[ \t]*:[ \t]*\n(?:[ \t]*delivery\s+no[ \t]*:[ \t]*\n[^\n]+\n)?[ \t]*([^\n]{2,100})",
               r"(?m)^\s*(?:vessel\s+name|vessel)[ \t]*[:#-][ \t]*([^\n]{2,100})",
               r"(?mi)^\s*master\s+and\s+owners\s+of\s+(.+?)\s+IMO\s+\d{7}\b"], 0.70
    )
    invoice.vessel.voyage = _find(
        text, [r"(?m)^\s*voyage[ \t]*[:#-][ \t]*([^\n]{2,50})"], 0.70
    )
    invoice.vessel.imo = _find(
        text, [r"(?m)^\s*imo[ \t]*(?:[:#-][ \t]*)?(\d{7})\b", r"(?i)\bIMO\s+(\d{7})\b"], 0.72
    )
    invoice.vessel.port = _find(text, [r"(?m)^\s*port[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.68)
    invoice.amounts.subtotal = _label_amount(text, r"sub[ \t]*total")
    invoice.amounts.tax = _label_amount(text, r"(?:tax|vat|gst)(?:[ \t]+amount)?")
    invoice.amounts.discount = _label_amount(
        text, r"(?:\d+(?:\.\d+)?%[ \t]+)?(?:disc\.?|discount)(?:[ \t]+S\$)?"
    )
    invoice.amounts.shipping = _label_amount(text, r"(?:shipping|freight)")
    invoice.amounts.total = _amount(
        text,
        [
            r"(?m)^\s*(?:grand\s*total|invoice\s*total|total\s*amount|total\s*due|amount\s*due|total)\b(?:\s+[A-Z]{3})?\s*:?\s*(?:\n\s*)?[^\d-]*([\d,.]+)",
            r"(?m)^\s*total\s+[A-Z]{3}\s*$\s*([\d,.]+)",
        ],
        0.72,
    )
    invoice.amounts.exchangeRate = _label_amount(text, r"exchange[ \t]+rate", 0.66)
    invoice.bankDetails.bankName = _find(
        text, [r"(?m)^\s*(?:bank[ \t]+name|name[ \t]+of[ \t]+bank)[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.55
    )
    if invoice.bankDetails.bankName.value is None:
        invoice.bankDetails.bankName = _following_label_value(text, [r"bank\s+name", r"name\s+of\s+bank"], 0.68)
    invoice.bankDetails.beneficiary = _find(
        text, [r"(?m)^\s*(?:beneficiary|name[ \t]+of[ \t]+account)[ \t]*[:#-][ \t]*([^\n]{2,100})"], 0.65
    )
    if invoice.bankDetails.beneficiary.value is None:
        invoice.bankDetails.beneficiary = _following_label_value(text, [r"beneficiary", r"name\s+of\s+account"], 0.68)
    invoice.bankDetails.accountNumber = _find(
        text, [r"(?:account|a/c)\s*(?:number|no\.?|#)\s*[:#-]?\s*([A-Z0-9/# -]{5,40})"], 0.66
    )
    if invoice.bankDetails.accountNumber.value is None:
        invoice.bankDetails.accountNumber = _following_label_value(
            text, [r"(?:account|a/c)\s*(?:number|no\.?|#)"], 0.68
        )
    invoice.bankDetails.iban = _find(text, [r"\bIBAN\s*[:#-]?\s*([A-Z]{2}\d{2}[A-Z0-9 ]{10,32})"], 0.72, upper=True)
    invoice.bankDetails.swiftBic = _find(text, [r"(?:swift|bic)\s*(?:code)?\s*[:#-]?\s*([A-Z0-9]{8,11})"], 0.72, upper=True)
    invoice.notes = _find(
        text,
        [r"(?m)^\s*((?:payment|please|notes?|terms?)\b[^\n]{8,300})"],
        0.58,
    )
    _map_supplier_and_bill_to_block(invoice, text)
    invoice.lineItems = _line_items(text) or _generic_line_items(text)
    return invoice


def _company_names(text: str) -> list[str]:
    pattern = re.compile(
        r"(?im)^\s*([A-Z][A-Z0-9&.,'() /-]{2,100}?\b(?:PRIVATE\s+LIMITED|PTE\.?\s+LTD\.?|LIMITED|LTD\.?|LLC|INC\.?|CORP(?:ORATION)?\.?))\b"
    )
    names: list[str] = []
    for match in pattern.finditer(text):
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        if value.upper() in {name.upper() for name in names}:
            continue
        names.append(value)
    return names


def _following_label_value(text: str, labels: list[str], confidence: float) -> ExtractedField:
    lines = _lines(text)
    label_pattern = re.compile(rf"(?:{'|'.join(labels)})\s*:?[ \t]*$", re.IGNORECASE)
    for index, line in enumerate(lines[:-1]):
        if not label_pattern.fullmatch(line):
            continue
        candidate = lines[index + 1].strip()
        if candidate and not candidate.endswith(":"):
            return _field(candidate, confidence)
    return ExtractedField()


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


def _generic_line_items(text: str) -> list[LineItem]:
    lines = _lines(text)
    columnar = _columnar_ocr_line_items(lines)
    if columnar:
        return columnar
    # Common service-invoice layout: Description / Currency / Amount followed by one row.
    try:
        description_header = next(index for index, line in enumerate(lines) if line.lower() == "description")
        amount_header = next(index for index in range(description_header + 1, len(lines)) if lines[index].lower() == "amount")
    except StopIteration:
        description_header = amount_header = -1
    if amount_header >= 0 and amount_header + 3 < len(lines):
        description, currency, amount = lines[amount_header + 1:amount_header + 4]
        parsed_amount = _number(amount)
        if len(description) > 3 and re.fullmatch(r"[A-Z]{3}", currency) and parsed_amount is not None:
            return [LineItem(
                lineNumber=_field("1", 0.68),
                description=_field(description, 0.70),
                amount=_field(parsed_amount, 0.72),
            )]

    # Common fuel invoice row containing delivery date, description, volume, UoM, price and value.
    row_pattern = re.compile(
        r"(?mi)^\s*\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+(.+?)\s+(?:Bulk\s+)?"
        r"([\d,]+\.\d{3})\s+([A-Za-z]+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+\w+\s*$"
    )
    match = row_pattern.search(text)
    if not match:
        return []
    items = [LineItem(
        lineNumber=_field("1", 0.68),
        description=_field(match.group(1), 0.70),
        quantity=_field(_number(match.group(2)), 0.72),
        unitPrice=_field(_number(match.group(4)), 0.72),
        amount=_field(_number(match.group(5)), 0.72),
    )]
    tail = text[match.end():]
    adjustment = re.search(r"(?mi)^\s*([A-Za-z][A-Za-z/() -]{3,80})\s+([\d,]+\.\d{2})\s*$", tail)
    if adjustment and adjustment.group(1).strip().upper() not in {"TOTAL AMOUNT", "NET AMOUNT"}:
        items.append(LineItem(
            lineNumber=_field("2", 0.66),
            description=_field(adjustment.group(1).strip(), 0.68),
            amount=_field(_number(adjustment.group(2)), 0.70),
        ))
    return items


def _columnar_ocr_line_items(lines: list[str]) -> list[LineItem]:
    try:
        start = next(index for index, line in enumerate(lines) if line.upper() == "PRICE") + 1
        end = next(index for index in range(start, len(lines)) if re.match(r"(?i)^sub\s*total\b", lines[index]))
    except StopIteration:
        return []
    body = lines[start:end]

    def is_money(value: str) -> bool:
        return bool(re.fullmatch(r"[\d,]+\.\d{2}", value.strip()))

    items: list[LineItem] = []
    index = 0
    while index + 2 < len(body):
        if not (is_money(body[index]) and is_money(body[index + 1]) and _line_number(body[index + 2])):
            index += 1
            continue
        next_index = index + 3
        while next_index + 2 < len(body) and not (
            is_money(body[next_index]) and is_money(body[next_index + 1]) and _line_number(body[next_index + 2])
        ):
            next_index += 1
        detail = body[index + 3:next_index if next_index + 2 < len(body) else len(body)]
        quantity: float | None = None
        description_start = 0
        if detail:
            combined = re.fullmatch(r"([\d,.]+)\s+PCS", detail[0], re.IGNORECASE)
            if combined:
                quantity = _number(combined.group(1))
                description_start = 1
            elif _number(detail[0]) is not None and len(detail) > 1 and detail[1].upper() == "PCS":
                quantity = _number(detail[0])
                description_start = 2
        description = " ".join(detail[description_start:]).strip()
        if description and quantity is not None:
            items.append(LineItem(
                lineNumber=_field(body[index + 2], 0.70),
                description=_field(description, 0.68),
                quantity=_field(quantity, 0.70),
                unitPrice=_field(_number(body[index]), 0.70),
                amount=_field(_number(body[index + 1]), 0.70),
            ))
        index = next_index if next_index > index else index + 1
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
    candidate = re.sub(r"\s+", " ", str(field.value)).strip(" .,:")
    for fmt in (
        "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%m/%d/%Y",
        "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y", "%d %b %y",
    ):
        try:
            parsed = strptime(candidate, fmt)
            field.value = date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
            return field
        except ValueError:
            continue
    field.value = candidate
    field.confidence = 0.35
    return field
