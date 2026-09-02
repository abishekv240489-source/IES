from app.mapper import _fill_missing, _ready_for_fast_path, heuristic_map
from app.models import ExtractedField, Invoice


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


def test_hybrid_fast_path_requires_complete_evidence() -> None:
    incomplete = heuristic_map("Invoice No: INV-100")
    assert not _ready_for_fast_path(incomplete)


def test_evidence_merge_only_fills_missing_qwen_values() -> None:
    qwen = Invoice()
    qwen.header.invoiceNumber = ExtractedField(value="QWEN-100", confidence=0.8, source="qwen", page=1)
    evidence = Invoice()
    evidence.header.invoiceNumber = ExtractedField(value="RULE-100", confidence=0.7, source="heuristic")
    evidence.header.currency = ExtractedField(value="USD", confidence=0.75, source="heuristic")

    merged = _fill_missing(qwen, evidence)

    assert merged.header.invoiceNumber.value == "QWEN-100"
    assert merged.header.invoiceNumber.source == "qwen"
    assert merged.header.currency.value == "USD"
    assert merged.header.currency.source == "heuristic"


def test_heuristic_mapper_handles_multiline_service_invoice() -> None:
    invoice = heuristic_map("""
        ALPHA THAI ENTERPRISES LTD.
        5/F, TEST PLAZA, HONG KONG.
        INVOICE
        Customer:
        Date:
        9-Jul-26
        OCEAN EXPRESS LINES PTE LTD
        INV#
        20260701
        Description
        Currency
        Amount
        Service fee for Apr/May/Jun 2026
        USD
        3,225.00
        Total:
        3,225.00
        Name of Bank :
        Example Banking Corporation Limited
        Name of Account:
        Alpha Thai Enterprises Limited
        Account No.:
        HSBC/USD/SA#808-190458-274
        Swift Code
        HSBCHKHHHKH
    """)

    assert invoice.vendor.name.value == "ALPHA THAI ENTERPRISES LTD"
    assert invoice.billTo.entity.value == "OCEAN EXPRESS LINES PTE LTD"
    assert invoice.header.invoiceDate.value == "2026-07-09"
    assert invoice.header.invoiceNumber.value == "20260701"
    assert invoice.amounts.total.value == 3225.0
    assert invoice.bankDetails.bankName.value == "Example Banking Corporation Limited"
    assert invoice.bankDetails.beneficiary.value == "Alpha Thai Enterprises Limited"
    assert invoice.bankDetails.accountNumber.value == "HSBC/USD/SA#808-190458-274"
    assert invoice.lineItems[0].description.value == "Service fee for Apr/May/Jun 2026"
    assert invoice.lineItems[0].amount.value == 3225.0


def test_heuristic_mapper_handles_multicolumn_fuel_invoice_text() -> None:
    invoice = heuristic_map("""
        INVOICE
        SELLER VAT NO. : GB239088635
        Sold to
        Master and Owners of KOTA TEST IMO 1081843
        Invoice No 31106259
        Invoice Date 03 Jul 2026
        Due date 31 Aug 2026
        CUSTOMER ORDER REFERENCE: ELN-202600058-1
        Port: SHANGHAI MUNICIPALITY SHIPYARDS
        Invoice currency USD
        18 Jun 2026 GMB MARINE OIL M420 BULK EX-IBC 1000 Bulk 13,000.000 L 190.00 24,700.00 5A
        Agency/Call/Customs 177.00
        Total Amount 24,877.00 USD
        Example Marine Limited An Example Subsidiary
        SWIFT code: BOFAGB22
        Account Number: 64313043
        IBAN Number
        GB09 BOFA 1650 5064 3130 43
    """)

    assert invoice.vendor.name.value == "Example Marine Limited"
    assert invoice.vendor.taxRegistration.value == "GB239088635"
    assert invoice.billTo.entity.value == "Master and Owners of KOTA TEST IMO 1081843"
    assert invoice.header.invoiceDate.value == "2026-07-03"
    assert invoice.header.dueDate.value == "2026-08-31"
    assert invoice.header.poReference.value == "ELN-202600058-1"
    assert invoice.vessel.name.value == "KOTA TEST"
    assert invoice.vessel.imo.value == "1081843"
    assert invoice.amounts.total.value == 24877.0
    assert invoice.lineItems[0].quantity.value == 13000.0
    assert invoice.lineItems[0].amount.value == 24700.0
    assert invoice.lineItems[1].amount.value == 177.0


def test_heuristic_mapper_handles_columnar_scanned_invoice_text() -> None:
    invoice = heuristic_map("""
        TRITON MARINE INDUSTRY PTE LTD
        TAX INVOICE
        INVOICE NO :
        COMPANY :
        TRM26091/06/26
        PACIFIC INTERNATIONAL LINES (PTE) LTD
        DATE :
        25/06/2026
        VESSEL NAME:
        KOTA KARIM
        YOUR P/O NO:
        TERMS:
        WITHIN 60 DAYS
        KRM-202600454-1
        QTY
        DESCRIPTION
        UNIT
        AMOUNT
        ITEM
        NO.
        PRICE
        4.80
        9.60
        1
        2
        PCS
        V-BELT A-44
        2.80
        84.00
        2
        30 PCS
        LAMP SINGLE LED BLUE
        SUB TOTAL S$
        93.60
        10% DISC. S$
        9.36
        TOTAL
        S$
        84.24
    """)

    assert invoice.header.invoiceNumber.value == "TRM26091/06/26"
    assert invoice.header.invoiceDate.value == "2026-06-25"
    assert invoice.header.currency.value == "SGD"
    assert invoice.header.poReference.value == "KRM-202600454-1"
    assert invoice.vessel.name.value == "KOTA KARIM"
    assert invoice.amounts.total.value == 84.24
    assert invoice.amounts.discount.value == 9.36
    assert len(invoice.lineItems) == 2
    assert invoice.lineItems[0].description.value == "V-BELT A-44"
    assert invoice.lineItems[1].amount.value == 84.0
