"""Generate deterministic, non-sensitive invoice PDFs and labelled truth data."""
from __future__ import annotations

import argparse
import io
import json
import random
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymupdf as fitz
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

VENDORS = [
    ("Harbor Services Pte Ltd", "18 Keppel Road, Singapore 089055", "Singapore", "SG201938475K", "billing@harbor.example", "DBS Bank", "072-140318-8", "DBSSSGSG"),
    ("Bluewater Marine GmbH", "Seestrasse 41, 20457 Hamburg, Germany", "Germany", "DE319284756", "accounts@bluewater.example", "Commerzbank", "DE89370400440532013000", "COBADEFFXXX"),
    ("Coastal Supply India Pvt Ltd", "47 Port Link Road, Chennai 600001, India", "India", "33AACCC1042M1ZX", "finance@coastal.example", "HDFC Bank", "50200018475021", "HDFCINBB"),
]
LINE_CATALOG = [
    ("Port agency services", "AGENCY", Decimal(1), Decimal("1250.00")),
    ("Fresh water supply", "WATER", Decimal(12), Decimal("42.50")),
    ("Mooring assistance", "MOORING", Decimal(2), Decimal("325.00")),
    ("Marine spare parts", "SPARES", Decimal(4), Decimal("187.25")),
    ("Customs documentation", "CUSTOMS", Decimal(1), Decimal("280.00")),
]
PALETTES = [("#073B4C", "#118AB2"), ("#263238", "#546E7A"), ("#3D405B", "#81B29A")]


def field_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def make_invoice(index: int, rng: random.Random, quality: str, layout: str) -> dict[str, Any]:
    vendor = VENDORS[index % len(VENDORS)]
    invoice_date = date(2026, 8, 1) + timedelta(days=index)
    selected = rng.sample(LINE_CATALOG, k=3)
    lines = []
    for line_number, (description, charge_code, quantity, unit_price) in enumerate(selected, 1):
        amount = quantity * unit_price
        lines.append({
            "lineNumber": str(line_number),
            "description": description,
            "quantity": field_value(quantity),
            "unitPrice": field_value(unit_price),
            "amount": field_value(amount),
            "chargeCode": charge_code,
        })
    subtotal = sum((Decimal(str(line["amount"])) for line in lines), Decimal(0))
    tax = (subtotal * Decimal("0.09")).quantize(Decimal("0.01"))
    shipping = Decimal("75.00") if index % 2 else Decimal("0.00")
    total = subtotal + tax + shipping
    account = vendor[6]
    return {
        "_meta": {
            "synthetic": True,
            "quality": quality,
            "layout": layout,
            "language": "en",
            "pages": 1,
        },
        "header": {
            "invoiceNumber": f"SYN-2026-{1000 + index}",
            "invoiceDate": invoice_date.isoformat(),
            "dueDate": (invoice_date + timedelta(days=30)).isoformat(),
            "currency": "USD",
            "poReference": f"PO-{84000 + index}",
        },
        "vendor": {
            "name": vendor[0],
            "address": vendor[1],
            "country": vendor[2],
            "taxRegistration": vendor[3],
            "contact": vendor[4],
        },
        "billTo": {
            "entity": "Pacific International Lines (Private) Limited",
            "address": "140 Cecil Street, Singapore 069540",
            "businessUnit": "Marine Operations",
            "accountingReference": f"ACCT-{6100 + index}",
        },
        "vessel": {
            "name": ["Kota Lestari", "Kota Singa", "Kota Cahaya"][index % 3],
            "voyage": f"V{260 + index}E",
            "imo": f"9{320100 + index}",
            "port": ["Singapore", "Chennai", "Hamburg"][index % 3],
        },
        "amounts": {
            "subtotal": field_value(subtotal),
            "tax": field_value(tax),
            "discount": 0.0,
            "shipping": field_value(shipping),
            "total": field_value(total),
            "exchangeRate": 1.0,
        },
        "bankDetails": {
            "bankName": vendor[5],
            "beneficiary": vendor[0],
            "accountNumber": account,
            "iban": account if account.startswith("DE") else None,
            "swiftBic": vendor[7],
        },
        "lineItems": lines,
        "notes": "Payment due within 30 days. Quote the invoice number with remittance.",
    }


def _money(value: Any) -> str:
    return f"{Decimal(str(value)):,.2f}"


def draw_invoice(path: Path, invoice: dict[str, Any], palette_index: int = 0) -> None:
    width, height = A4
    primary, accent = (colors.HexColor(value) for value in PALETTES[palette_index % len(PALETTES)])
    canvas = Canvas(str(path), pagesize=A4, pageCompression=1)
    canvas.setTitle(str(invoice["header"]["invoiceNumber"]))
    canvas.setAuthor("IES Synthetic Benchmark")

    canvas.setFillColor(primary)
    canvas.rect(0, height - 105, width, 105, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 25)
    canvas.drawString(42, height - 55, "INVOICE")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(42, height - 76, "Privacy-safe synthetic benchmark document")
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawRightString(width - 42, height - 51, str(invoice["header"]["invoiceNumber"]))
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(width - 42, height - 70, f"Invoice Date: {invoice['header']['invoiceDate']}")
    canvas.drawRightString(width - 42, height - 86, f"Due Date: {invoice['header']['dueDate']}")

    left = 42
    right = width / 2 + 12
    top = height - 132
    canvas.setFillColor(primary)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(left, top, "SUPPLIER")
    canvas.drawString(right, top, "BILL TO")
    canvas.setFillColor(colors.HexColor("#20262E"))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(left, top - 18, f"Supplier: {invoice['vendor']['name']}")
    canvas.drawString(right, top - 18, str(invoice["billTo"]["entity"]))
    canvas.setFont("Helvetica", 8.5)
    supplier_lines = [
        invoice["vendor"]["address"],
        f"Country: {invoice['vendor']['country']}",
        f"Tax Registration: {invoice['vendor']['taxRegistration']}",
        f"Contact: {invoice['vendor']['contact']}",
    ]
    bill_lines = [
        invoice["billTo"]["address"],
        f"Business Unit: {invoice['billTo']['businessUnit']}",
        f"Accounting Ref: {invoice['billTo']['accountingReference']}",
        f"PO No: {invoice['header']['poReference']}",
    ]
    for row, (supplier, bill) in enumerate(zip(supplier_lines, bill_lines)):
        y = top - 34 - row * 14
        canvas.drawString(left, y, str(supplier))
        canvas.drawString(right, y, str(bill))

    shipment_y = top - 104
    canvas.setFillColor(colors.HexColor("#EEF3F6"))
    canvas.roundRect(left, shipment_y - 35, width - 84, 48, 5, fill=1, stroke=0)
    canvas.setFillColor(primary)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(left + 10, shipment_y - 2, "VESSEL / SERVICE")
    canvas.setFillColor(colors.HexColor("#20262E"))
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(left + 10, shipment_y - 20, f"Vessel: {invoice['vessel']['name']}")
    canvas.drawString(left + 145, shipment_y - 20, f"Voyage: {invoice['vessel']['voyage']}")
    canvas.drawString(left + 270, shipment_y - 20, f"IMO: {invoice['vessel']['imo']}")
    canvas.drawString(left + 380, shipment_y - 20, f"Port: {invoice['vessel']['port']}")

    table_top = shipment_y - 62
    columns = [left, left + 34, left + 252, left + 320, left + 400, width - 42]
    canvas.setFillColor(accent)
    canvas.rect(left, table_top - 20, width - 84, 20, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    headings = ["#", "DESCRIPTION / CHARGE CODE", "QTY", "UNIT PRICE", "AMOUNT"]
    for index, heading in enumerate(headings):
        canvas.drawString(columns[index] + 5, table_top - 14, heading)
    canvas.setStrokeColor(colors.HexColor("#CFD8DC"))
    canvas.setFillColor(colors.HexColor("#20262E"))
    canvas.setFont("Helvetica", 8.5)
    row_height = 28
    for row, item in enumerate(invoice["lineItems"]):
        y_top = table_top - 20 - row * row_height
        if row % 2:
            canvas.setFillColor(colors.HexColor("#F7F9FA"))
            canvas.rect(left, y_top - row_height, width - 84, row_height, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#20262E"))
        canvas.line(left, y_top - row_height, width - 42, y_top - row_height)
        canvas.drawString(columns[0] + 5, y_top - 18, str(item["lineNumber"]))
        canvas.drawString(columns[1] + 5, y_top - 12, str(item["description"]))
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawString(columns[1] + 5, y_top - 23, f"Charge Code: {item['chargeCode']}")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(columns[3] - 6, y_top - 18, str(item["quantity"]))
        canvas.drawRightString(columns[4] - 6, y_top - 18, _money(item["unitPrice"]))
        canvas.drawRightString(columns[5] - 6, y_top - 18, _money(item["amount"]))

    totals_top = table_top - 20 - len(invoice["lineItems"]) * row_height - 18
    label_x = width - 185
    value_x = width - 48
    canvas.setFont("Helvetica", 8.5)
    total_rows = [
        ("Subtotal", invoice["amounts"]["subtotal"]),
        ("Tax Amount", invoice["amounts"]["tax"]),
        ("Shipping", invoice["amounts"]["shipping"]),
    ]
    for row, (label, value) in enumerate(total_rows):
        y = totals_top - row * 17
        canvas.drawString(label_x, y, label)
        canvas.drawRightString(value_x, y, _money(value))
    total_y = totals_top - 58
    canvas.setFillColor(primary)
    canvas.roundRect(label_x - 10, total_y - 7, 147, 25, 4, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(label_x, total_y + 1, f"TOTAL {invoice['header']['currency']}")
    canvas.drawRightString(value_x, total_y + 1, _money(invoice["amounts"]["total"]))

    bank_y = total_y - 44
    canvas.setFillColor(primary)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(left, bank_y, "BANK DETAILS")
    canvas.setFillColor(colors.HexColor("#20262E"))
    canvas.setFont("Helvetica", 8.5)
    bank = invoice["bankDetails"]
    canvas.drawString(left, bank_y - 17, f"Bank Name: {bank['bankName']}")
    canvas.drawString(left, bank_y - 32, f"Beneficiary: {bank['beneficiary']}")
    canvas.drawString(left, bank_y - 47, f"Account Number: {bank['accountNumber']}")
    canvas.drawString(left + 280, bank_y - 17, f"SWIFT: {bank['swiftBic']}")
    if bank["iban"]:
        canvas.drawString(left + 280, bank_y - 32, f"IBAN: {bank['iban']}")
    canvas.setFillColor(colors.HexColor("#607D8B"))
    canvas.setFont("Helvetica-Oblique", 7.5)
    canvas.drawString(left, 45, str(invoice["notes"]))
    canvas.drawRightString(width - 42, 27, "Page 1 of 1")
    canvas.save()


def rasterize_pdf(source: Path, target: Path, quality: str) -> None:
    with fitz.open(source) as document:
        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("L")
    if quality == "scan_clean":
        image = image.filter(ImageFilter.GaussianBlur(radius=0.25))
    elif quality == "scan_degraded":
        image = image.rotate(0.65, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=245)
        image = ImageEnhance.Contrast(image).enhance(0.72)
        image = image.filter(ImageFilter.GaussianBlur(radius=0.75))
        noise = Image.effect_noise(image.size, 9).convert("L")
        image = Image.blend(image, noise, 0.06)
        encoded = io.BytesIO()
        image.save(encoded, format="JPEG", quality=48, optimize=True)
        image = Image.open(io.BytesIO(encoded.getvalue())).convert("L")
    encoded = io.BytesIO()
    image.save(encoded, format="PNG", optimize=True)
    output = fitz.open()
    page = output.new_page(width=A4[0], height=A4[1])
    page.insert_image(page.rect, stream=encoded.getvalue())
    output.save(target, deflate=True, garbage=4)
    output.close()


def generate_dataset(output_root: Path, count: int, seed: int) -> None:
    if count < 3:
        raise ValueError("count must be at least 3 so every quality band is represented")
    documents_dir = output_root / "documents"
    truth_dir = output_root / "ground_truth"
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty benchmark directory: {output_root}")
    documents_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    qualities = ["digital", "scan_clean", "scan_degraded"]
    layouts = ["freight", "services", "supplies"]
    manifest: dict[str, Any] = {"schema_version": "1.0", "synthetic": True, "seed": seed, "documents": []}
    with tempfile.TemporaryDirectory(prefix="ies-synthetic-") as temp_dir:
        temp_root = Path(temp_dir)
        for index in range(count):
            quality = qualities[index % len(qualities)]
            layout = layouts[index % len(layouts)]
            document_id = f"synthetic-{index + 1:04d}"
            invoice = make_invoice(index, rng, quality, layout)
            document_path = documents_dir / f"{document_id}.pdf"
            vector_path = temp_root / f"{document_id}-vector.pdf"
            draw_invoice(vector_path, invoice, index)
            if quality == "digital":
                document_path.write_bytes(vector_path.read_bytes())
            else:
                rasterize_pdf(vector_path, document_path, quality)
            truth_path = truth_dir / f"{document_id}.json"
            truth_path.write_text(json.dumps(invoice, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest["documents"].append({
                "id": document_id,
                "path": f"documents/{document_path.name}",
                "truth": f"ground_truth/{truth_path.name}",
                "quality": quality,
                "layout": layout,
            })
    (output_root / "dataset.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=260828)
    parser.add_argument("--reference-output", type=Path)
    args = parser.parse_args()
    if bool(args.output_root) == bool(args.reference_output):
        parser.error("choose exactly one of --output-root or --reference-output")
    if args.reference_output:
        args.reference_output.parent.mkdir(parents=True, exist_ok=True)
        reference = make_invoice(0, random.Random(args.seed), "digital", "freight")
        draw_invoice(args.reference_output, reference, 0)
        print(args.reference_output)
        return 0
    try:
        generate_dataset(args.output_root, args.count, args.seed)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
