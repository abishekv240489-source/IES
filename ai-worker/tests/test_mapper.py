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


def test_heuristic_mapper_extracts_full_labelled_layout_and_line_items() -> None:
    invoice = heuristic_map("""
        INVOICE
        SYN-2026-1000
        Invoice Date: 2026-08-01
        Due Date: 2026-08-31
        SUPPLIER
        BILL TO
        Supplier: Harbor Services Pte Ltd
        Pacific International Lines (Private) Limited
        18 Keppel Road, Singapore 089055
        140 Cecil Street, Singapore 069540
        Country: Singapore
        Business Unit: Marine Operations
        Tax Registration: SG201938475K
        Accounting Ref: ACCT-6100
        Contact: billing@harbor.example
        PO No: PO-84000
        Vessel: Kota Lestari
        Voyage: V260E
        IMO: 9320100
        Port: Singapore
        AMOUNT
        1
        Marine spare parts
        Charge Code: SPARES
        4.0
        187.25
        749.00
        Subtotal
        749.00
        Tax Amount
        67.41
        Shipping
        0.00
        Discount
        0.00
        Exchange Rate
        1.00
        TOTAL USD
        816.41
        Bank Name: DBS Bank
        Beneficiary: Harbor Services Pte Ltd
        Account Number: 072-140318-8
        SWIFT: DBSSSGSG
        Payment due within 30 days. Quote the invoice number with remittance.
    """)
    assert invoice.header.invoiceNumber.value == "SYN-2026-1000"
    assert invoice.vendor.address.value == "18 Keppel Road, Singapore 089055"
    assert invoice.billTo.entity.value == "Pacific International Lines (Private) Limited"
    assert invoice.vessel.imo.value == "9320100"
    assert invoice.amounts.exchangeRate.value == 1.0
    assert invoice.bankDetails.beneficiary.value == "Harbor Services Pte Ltd"
    assert invoice.lineItems[0].description.value == "Marine spare parts"
    assert invoice.lineItems[0].amount.value == 749.0


def test_heuristic_mapper_handles_degraded_ocr_line_item_order() -> None:
    invoice = heuristic_map("""
        IMO 9320102
        DESCRIPTION CHARGE CODE
        QTY
        UNIT PRICE
        AMOUNT
        .
        Port agency services
        1.0
        1,250.00
        1,250.00
        1
        Charge Code: AGENCY
        Subtotal
        1,250.00
    """)
    assert invoice.vessel.imo.value == "9320102"
    assert invoice.lineItems[0].lineNumber.value == "1"
    assert invoice.lineItems[0].quantity.value == 1.0
    assert invoice.lineItems[0].chargeCode.value == "AGENCY"
