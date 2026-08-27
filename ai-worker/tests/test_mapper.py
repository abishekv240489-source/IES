from app.mapper import confidence, heuristic_map


def test_heuristic_mapper_extracts_core_fields() -> None:
    invoice = heuristic_map("""
        Supplier: Harbor Services Pte Ltd
        Invoice No: INV-2026-1042
        Invoice Date: 20/08/2026
        PO No: PO-80019
        Currency USD
        Subtotal: 1,000.00
        Tax: 90.00
        Grand Total: 1,090.00
        Account Number: 072-140318-8
        SWIFT: DBSSSGSG
    """)
    assert invoice.header.invoiceNumber.value == "INV-2026-1042"
    assert invoice.header.invoiceDate.value == "2026-08-20"
    assert invoice.amounts.total.value == 1090.0
    assert invoice.bankDetails.accountNumber.value == "072-140318-8"
    assert confidence(invoice, 0.9) > 0.6


def test_missing_values_are_not_invented() -> None:
    invoice = heuristic_map("unrelated page")
    assert invoice.header.invoiceNumber.value is None
    assert invoice.amounts.total.value is None
