"""Deidentified layout regressions; never include private invoice files here."""
import json

import httpx
import pytest

from app import mapper
from app.models import ExtractedField, Invoice, LineItem


def test_trading_name_and_delivery_table_total():
    invoice = mapper.heuristic_map("""EXAMPLE GEMS & EXCHANGE
10 Example Road
Bank: Example Bank
Beneficiary: EXAMPLE GEMS & EXCHANGE, 10 Example Road
Buyer Shipping Pte. Ltd.
VESSEL NAME
DELIVERY
AMOUNT
TOTAL
1
30/06/2026
TEST VESSEL
Terminal
SGD
150.00
150.00
Total SGD Amount


150.00
""")
    assert invoice.vendor.name.value == "EXAMPLE GEMS & EXCHANGE"
    assert invoice.billTo.entity.value == "Buyer Shipping Pte. Ltd"
    assert invoice.amounts.total.value == 150
    assert invoice.lineItems[0].amount.value == 150
    assert invoice.bankDetails.bankName.value == "Example Bank"


def test_total_does_not_cross_unrelated_headings():
    assert mapper.heuristic_map("TOTAL\nDelivery date\n1").amounts.total.value is None


def test_wrapped_fuel_total_and_care_of_buyer_are_not_supplier():
    invoice = mapper.heuristic_map("""Bill to
Master and Owners of TEST VESSEL
C/O Customer Shipping (Pte)
Ltd
Example Marine Limited An Example Subsidiary
Total
Amount (Excl Tax)
250.00 USD
Total
VAT/GST/IGIC
0.00 USD
Total
Amount
250.00 USD
""")
    assert invoice.vendor.name.value == "Example Marine Limited"
    assert invoice.amounts.total.value == 250


def test_service_rows_bill_to_and_multiline_po():
    invoice = mapper.heuristic_map("""Example Services Limited
Bill To : Customer Shipping (PTE) LTD
PO No. :
TEST-202600001
Item
Qty.
Rate
Amount
1
Operational Service Charges
Service Delivery from Example
3.00
100.00
300.00
2
Technology Service Charges
1.00
50.00
50.00
Grand Total
350.00
Favouring Example Services Limited
""")
    assert invoice.billTo.entity.value == "Customer Shipping (PTE) LTD"
    assert invoice.header.poReference.value == "TEST-202600001"
    assert len(invoice.lineItems) == 2
    assert invoice.lineItems[0].amount.value == 300


def test_inspection_rows_wrapped_buyer_and_account_currency():
    invoice = mapper.heuristic_map("""Example Testing Singapore Pte Ltd
CUSTOMER SHIPPING (PTE)
LTD
Purchase Order Ref.
TEST-100-1
UoM
Tax Code
Amount
65241
Bunker Inspection
1
Ea
450.00
450.00
Zero%
450.00
Account Number : (USD) 144-00000000
Total Amount USD
450.00
""")
    assert invoice.billTo.entity.value == "CUSTOMER SHIPPING (PTE) LTD"
    assert invoice.header.poReference.value == "TEST-100-1"
    assert invoice.bankDetails.accountNumber.value == "144-00000000"
    assert invoice.lineItems[0].chargeCode.value == "65241"
    assert invoice.lineItems[0].amount.value == 450


def test_qwen_sparse_fields_are_marked_and_invalid_page_rejected(monkeypatch):
    content = {"header": {"invoiceNumber": {"value": "TEST-100", "confidence": 0.9, "page": 1}}}

    def response(*args, **kwargs):
        assert "source" not in kwargs["json"]["format"]["$defs"]["ExtractedField"]["properties"]
        return httpx.Response(200, request=httpx.Request("POST", "http://test"),
                              json={"message": {"content": json.dumps(content)}, "done_reason": "stop"})

    monkeypatch.setattr(mapper.httpx, "post", response)
    invoice = mapper._qwen("--- PAGE 1 ---\nInvoice No TEST-100")
    assert invoice.header.invoiceNumber.source == "qwen"
    content["header"]["invoiceNumber"]["page"] = 2
    with pytest.raises(ValueError, match="invalid page"):
        mapper._qwen("--- PAGE 1 ---\nInvoice No TEST-100")
    content.clear()
    with pytest.raises(ValueError, match="empty extraction"):
        mapper._qwen("--- PAGE 1 ---\nInvoice No TEST-100")


def test_partial_qwen_rows_merge_by_unique_description_not_position():
    def row(description, amount=None):
        return LineItem(description=ExtractedField(value=description), amount=ExtractedField(value=amount))

    primary = Invoice(lineItems=[row("Service B"), row("Service A")])
    fallback = Invoice(lineItems=[row("Service A", 100), row("Service B", 200)])
    merged = mapper._fill_missing(primary, fallback)
    assert [item.amount.value for item in merged.lineItems] == [200, 100]

    ambiguous = Invoice(lineItems=[row("Service A"), row("Service A")])
    assert all(item.amount.value is None for item in mapper._fill_missing(ambiguous, fallback).lineItems)


def test_missing_description_requires_unique_row_number_and_amount():
    qwen = Invoice(lineItems=[LineItem(lineNumber=ExtractedField(value="1"), amount=ExtractedField(value=120))])
    evidence = Invoice(lineItems=[LineItem(lineNumber=ExtractedField(value="1"), amount=ExtractedField(value=120),
                                          description=ExtractedField(value="Delivery service"))])
    assert mapper._fill_missing(qwen, evidence).lineItems[0].description.value == "Delivery service"
