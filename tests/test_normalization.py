from decimal import Decimal

from invoice_extraction.normalization import normalize_date, normalize_identifier, normalize_money


def test_normalizes_international_money_formats() -> None:
    assert normalize_money("USD 1,234.56") == (Decimal("1234.56"), "USD")
    assert normalize_money("€ 1.234,56") == (Decimal("1234.56"), "EUR")
    assert normalize_money("(2,500.00)") == (Decimal("-2500.00"), None)


def test_normalizes_dates_and_rejects_invalid_date() -> None:
    assert normalize_date("27/08/2026") == "2026-08-27"
    assert normalize_date("2026-08-27") == "2026-08-27"
    assert normalize_date("27 Aug 26") == "2026-08-27"
    assert normalize_date("31/02/2026") is None


def test_identifier_preserves_meaningful_punctuation() -> None:
    assert normalize_identifier(" Inv- 001 / A ") == "INV-001/A"
