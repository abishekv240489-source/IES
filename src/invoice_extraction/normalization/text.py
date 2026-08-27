from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

_SPACE_RE = re.compile(r"[\t\u00a0 ]+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MONEY_RE = re.compile(
    r"(?P<sign>[-(])?\s*(?P<currency>[A-Z]{3}|[$€£₹])?\s*"
    r"(?P<number>\d[\d.,' ]*)\s*(?P<close>\))?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"^(\d{1,4})[./\-](\d{1,2})[./\-](\d{1,4})$")

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def normalize_text(value: str) -> str:
    """Normalize Unicode and spacing without inventing document content."""
    value = unicodedata.normalize("NFKC", value)
    value = _CONTROL_RE.sub("", value)
    lines = [_SPACE_RE.sub(" ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_identifier(value: str) -> str:
    """Normalize an identifier while preserving meaningful punctuation."""
    value = normalize_text(value).upper().strip(" :#")
    return re.sub(r"\s+", "", value)


def _decimal_separator(number: str) -> str | None:
    dot = number.rfind(".")
    comma = number.rfind(",")
    if dot >= 0 and comma >= 0:
        return "." if dot > comma else ","
    separator = "." if dot >= 0 else "," if comma >= 0 else None
    if separator and len(number) - number.rfind(separator) - 1 in (1, 2):
        return separator
    return None


def normalize_money(value: str) -> tuple[Decimal, str | None] | None:
    """Parse common international money formats without locale guessing by the LLM."""
    cleaned = normalize_text(value).upper()
    match = _MONEY_RE.search(cleaned)
    if not match:
        return None
    currency_raw = match.group("currency")
    currency = _CURRENCY.get(currency_raw, currency_raw) if currency_raw else None
    number = match.group("number").replace("'", "").replace(" ", "")
    decimal_separator = _decimal_separator(number)
    if decimal_separator:
        thousands_separator = "," if decimal_separator == "." else "."
        number = number.replace(thousands_separator, "")
        number = number.replace(decimal_separator, ".")
    else:
        number = number.replace(",", "").replace(".", "")
    try:
        amount = Decimal(number)
    except InvalidOperation:
        return None
    if match.group("sign") in {"-", "("} or match.group("close") == ")":
        amount = -abs(amount)
    return amount, currency


def normalize_date(value: str, *, day_first: bool = True) -> str | None:
    """Convert unambiguous/common invoice dates to ISO-8601."""
    cleaned = normalize_text(value).strip(" ,")
    numeric = _DATE_RE.match(cleaned)
    if numeric:
        first, second, third = (int(part) for part in numeric.groups())
        if first > 999:
            year, month, day = first, second, third
        else:
            year = third + 2000 if third < 100 else third
            if first > 12:
                day, month = first, second
            elif second > 12:
                month, day = first, second
            elif day_first:
                day, month = first, second
            else:
                month, day = first, second
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    words = re.match(r"^(\d{1,2})[ ,/-]+([A-Za-z]{3,9})[ ,/-]+(\d{2,4})$", cleaned)
    if words:
        day = int(words.group(1))
        word_month = _MONTHS.get(words.group(2)[:3].lower())
        year = int(words.group(3))
        year = year + 2000 if year < 100 else year
        if word_month:
            try:
                return date(year, word_month, day).isoformat()
            except ValueError:
                return None
    return None
