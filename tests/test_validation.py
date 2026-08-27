from decimal import Decimal

from invoice_extraction.domain.models import BankDetails, ExtractedInvoice, LineItem
from invoice_extraction.validation import reconcile_invoice


def test_reconciliation_reports_arithmetic_mismatch() -> None:
    invoice = ExtractedInvoice(
        subtotal=Decimal("100"), tax=Decimal("10"), total=Decimal("115")
    )
    assert "invoice charges do not reconcile to total" in reconcile_invoice(invoice).warnings


def test_reconciliation_accepts_rounding_tolerance() -> None:
    invoice = ExtractedInvoice(
        subtotal=Decimal("100"), tax=Decimal("10.01"), total=Decimal("110")
    )
    assert reconcile_invoice(invoice).warnings == []


def test_reconciliation_includes_sop_charges_and_bank_formats() -> None:
    invoice = ExtractedInvoice(
        subtotal=Decimal("100"),
        tax=Decimal("10"),
        discount=Decimal("5"),
        freight=Decimal("3"),
        insurance=Decimal("2"),
        total=Decimal("110"),
        bank_details=BankDetails(iban="GB82 WEST 1234 5698 7654 32", swift="DEUTDEFF"),
        line_items=[
            LineItem(
                description="Service",
                quantity=Decimal("2"),
                unit_price=Decimal("50"),
                amount=Decimal("100"),
            )
        ],
    )
    assert reconcile_invoice(invoice).warnings == []
