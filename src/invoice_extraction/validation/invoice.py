from __future__ import annotations

import re
from decimal import Decimal

from invoice_extraction.domain.models import ExtractedInvoice

_SWIFT_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?$")


def _valid_iban(value: str) -> bool:
    compact = re.sub(r"\s+", "", value).upper()
    if not 15 <= len(compact) <= 34 or not compact.isalnum():
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(
        str(ord(character) - 55) if character.isalpha() else character
        for character in rearranged
    )
    return int(numeric) % 97 == 1


def reconcile_invoice(
    invoice: ExtractedInvoice, *, tolerance: Decimal = Decimal("0.02")
) -> ExtractedInvoice:
    """Add deterministic warnings without silently changing extracted values."""
    warnings = list(invoice.warnings)
    if invoice.subtotal is not None and invoice.total is not None:
        expected = invoice.subtotal
        expected += invoice.tax or Decimal("0")
        expected += invoice.freight or Decimal("0")
        expected += invoice.insurance or Decimal("0")
        expected -= invoice.discount or Decimal("0")
        difference = abs(expected - invoice.total)
        if difference > tolerance:
            warnings.append("invoice charges do not reconcile to total")
    if invoice.amount_due is not None and invoice.amount_due < 0:
        warnings.append("amount_due is negative")
    if invoice.invoice_date and invoice.due_date and invoice.due_date < invoice.invoice_date:
        warnings.append("due_date is before invoice_date")
    swift = invoice.bank_details.swift
    if swift and not _SWIFT_RE.fullmatch(re.sub(r"\s+", "", swift).upper()):
        warnings.append("swift has an invalid format")
    iban = invoice.bank_details.iban
    if iban and not _valid_iban(iban):
        warnings.append("iban checksum is invalid")
    for index, item in enumerate(invoice.line_items, start=1):
        if item.quantity is not None and item.unit_price is not None and item.amount is not None:
            expected_amount = item.quantity * item.unit_price - (item.discount or Decimal("0"))
            if abs(expected_amount - item.amount) > tolerance:
                warnings.append(f"line item {index} does not reconcile")
    return invoice.model_copy(update={"warnings": list(dict.fromkeys(warnings))})
