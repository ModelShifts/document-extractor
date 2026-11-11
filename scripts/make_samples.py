"""Generate the synthetic sample documents in ``samples/``.

Every company, address and number in these files is invented. Nothing here is
real data. Run from the repository root:

    python scripts/make_samples.py

Each PDF gets a ``<name>.truth.json`` file next to it with the expected field
values, used by the tests and the accuracy check in ``scripts/evaluate.py``.
"""

from __future__ import annotations

import io
import json
import random
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "samples"
INK = HexColor("#1c1a17")
RUST = HexColor("#8a3a24")
PAPER = HexColor("#f3efe6")
GREY = HexColor("#6b665e")

rng = random.Random(20260311)


def money(x: float) -> str:
    return f"{x:,.2f}"


def make_items(n: int, catalogue: list[str], lo: float, hi: float) -> list[tuple[str, int, float, float]]:
    items = []
    for desc in rng.sample(catalogue, n):
        qty = rng.randint(1, 12)
        unit = round(rng.uniform(lo, hi), 2)
        items.append((desc, qty, unit, round(qty * unit, 2)))
    return items


def totals(items, rate: float) -> tuple[float, float, float]:
    sub = round(sum(i[3] for i in items), 2)
    tax = round(sub * rate, 2)
    return sub, tax, round(sub + tax, 2)


def write_truth(name: str, schema: str, fields: dict) -> None:
    (OUT / f"{name}.truth.json").write_text(
        json.dumps({"file": f"{name}.pdf", "schema": schema, "fields": fields}, indent=2) + "\n"
    )


PARTS = [
    "Hex bolt M8 x 40, zinc",
    "Bearing 6204-2RS",
    "Timing belt HTD 5M-450",
    "Aluminium extrusion 20x20, 1 m",
    "Shaft coupling 8 mm to 10 mm",
    "Linear rail MGN12, 400 mm",
    "Stepper driver board",
    "Cable chain 10x15, 1 m",
    "Proximity sensor, inductive",
    "Spring washer M8, pack of 100",
]
SERVICES = [
    "Pallet storage, per week",
    "Last-mile delivery, zone B",
    "Customs documentation",
    "Cross-dock handling",
    "Shrink wrapping, per pallet",
    "Forklift hire, per hour",
    "Container unloading",
    "Labelling service",
]


# --------------------------------------------------------------------------- #
# Invoice 1: classic layout, seller top-left, totals bottom-right
# --------------------------------------------------------------------------- #
def invoice_classic(path: Path) -> dict:
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    w, h = A4
    items = make_items(5, PARTS, 2.5, 180)
    sub, tax, total = totals(items, 0.09)

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 70, "Northwind Parts Pte. Ltd.")
    c.setFont("Helvetica", 9)
    c.drawString(50, h - 86, "12 Example Road, #04-01, Singapore 000000")
    c.drawString(50, h - 98, "GST Reg. No. 000000000X (sample)")

    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(RUST)
    c.drawRightString(w - 50, h - 70, "TAX INVOICE")
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 50, h - 92, "Invoice No: NWP-2026-0412")
    c.drawRightString(w - 50, h - 106, "Invoice Date: 14 March 2026")
    c.drawRightString(w - 50, h - 120, "Due Date: 13 April 2026")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, h - 150, "Bill To")
    c.setFont("Helvetica", 10)
    c.drawString(50, h - 164, "Example Logistics Pte. Ltd.")
    c.drawString(50, h - 177, "88 Sample Avenue, Singapore 000001")

    y = h - 220
    c.setFillColor(PAPER)
    c.rect(45, y - 6, w - 90, 20, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Description")
    c.drawRightString(360, y, "Qty")
    c.drawRightString(450, y, "Unit price")
    c.drawRightString(w - 50, y, "Amount")
    c.setFont("Helvetica", 9)
    for desc, qty, unit, amt in items:
        y -= 20
        c.drawString(50, y, desc)
        c.drawRightString(360, y, str(qty))
        c.drawRightString(450, y, money(unit))
        c.drawRightString(w - 50, y, money(amt))
    y -= 14
    c.line(300, y, w - 50, y)
    c.setFont("Helvetica", 10)
    for label, val in (("Subtotal", sub), ("GST 9%", tax)):
        y -= 18
        c.drawString(330, y, label)
        c.drawRightString(w - 50, y, f"SGD {money(val)}")
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    c.drawString(330, y, "Total Due")
    c.drawRightString(w - 50, y, f"SGD {money(total)}")

    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawString(50, 60, "Synthetic sample document generated for testing. All names and figures are fictional.")
    c.save()
    return {
        "invoice_number": "NWP-2026-0412",
        "invoice_date": "2026-03-14",
        "due_date": "2026-04-13",
        "seller_name": "Northwind Parts Pte. Ltd.",
        "buyer_name": "Example Logistics Pte. Ltd.",
        "currency": "SGD",
        "subtotal": sub,
        "tax": tax,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# Invoice 2: banner header, two-column parties, different labels
# --------------------------------------------------------------------------- #
def invoice_banner(path: Path) -> dict:
    c = canvas.Canvas(str(path), pagesize=letter, invariant=1)
    w, h = letter
    items = make_items(4, SERVICES, 40, 900)
    sub, tax, total = totals(items, 0.07)

    c.setFillColor(INK)
    c.rect(0, h - 90, w, 90, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, h - 55, "Example Logistics")
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 40, h - 45, "INVOICE")
    c.drawRightString(w - 40, h - 60, "Bill No. EL/INV/7731")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, h - 120, "FROM")
    c.drawString(w / 2, h - 120, "TO")
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 135, "Example Logistics Inc.")
    c.drawString(40, h - 148, "400 Placeholder Street, Springfield 00000")
    c.drawString(w / 2, h - 135, "Sample Robotics Ltd.")
    c.drawString(w / 2, h - 148, "7 Demo Park, Unit 3, Testville 00000")

    c.setFont("Helvetica", 10)
    c.drawString(40, h - 180, "Issued: 2026-05-02")
    c.drawString(200, h - 180, "Payment due: 2026-06-01")
    c.drawString(380, h - 180, "Currency: USD")

    y = h - 220
    c.setStrokeColor(INK)
    c.line(40, y + 14, w - 40, y + 14)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Service")
    c.drawRightString(400, y, "Units")
    c.drawRightString(480, y, "Rate")
    c.drawRightString(w - 40, y, "Line total")
    c.line(40, y - 6, w - 40, y - 6)
    c.setFont("Helvetica", 9)
    for desc, qty, unit, amt in items:
        y -= 20
        c.drawString(40, y, desc)
        c.drawRightString(400, y, str(qty))
        c.drawRightString(480, y, money(unit))
        c.drawRightString(w - 40, y, money(amt))

    y -= 40
    c.setFillColor(PAPER)
    c.rect(330, y - 60, w - 370, 80, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawString(340, y, "Net amount")
    c.drawRightString(w - 50, y, money(sub))
    c.drawString(340, y - 18, "Sales tax (7%)")
    c.drawRightString(w - 50, y - 18, money(tax))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(340, y - 44, "Amount Due (USD)")
    c.drawRightString(w - 50, y - 44, money(total))

    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawString(40, 50, "Synthetic sample document generated for testing. All names and figures are fictional.")
    c.save()
    return {
        "invoice_number": "EL/INV/7731",
        "invoice_date": "2026-05-02",
        "due_date": "2026-06-01",
        "seller_name": "Example Logistics Inc.",
        "buyer_name": "Sample Robotics Ltd.",
        "currency": "USD",
        "subtotal": sub,
        "tax": tax,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# Invoice 3: compact European style, key-value block on the right, EUR
# --------------------------------------------------------------------------- #
def invoice_compact(path: Path) -> dict:
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    w, h = A4
    items = make_items(3, PARTS, 10, 400)
    sub, tax, total = totals(items, 0.19)

    c.setFillColor(RUST)
    c.rect(0, 0, 14, h, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Times-Bold", 16)
    c.drawString(50, h - 60, "Demo Freight GmbH")
    c.setFont("Times-Roman", 9)
    c.drawString(50, h - 74, "Beispielweg 1, 00000 Musterstadt")

    c.setFont("Times-Roman", 10)
    c.drawString(50, h - 130, "Customer:")
    c.drawString(50, h - 144, "Northwind Parts Pte. Ltd.")
    c.drawString(50, h - 157, "12 Example Road, Singapore 000000")

    kv = [
        ("Invoice number", "DF-88213"),
        ("Invoice date", "03.02.2026"),
        ("Payable by", "05.03.2026"),
        ("Currency", "EUR"),
    ]
    y = h - 130
    for k, v in kv:
        c.setFont("Times-Bold", 10)
        c.drawString(340, y, k)
        c.setFont("Times-Roman", 10)
        c.drawRightString(w - 50, y, v)
        y -= 15

    y = h - 220
    c.setFont("Times-Bold", 10)
    c.drawString(50, y, "Pos.")
    c.drawString(85, y, "Article")
    c.drawRightString(380, y, "Qty")
    c.drawRightString(460, y, "Price")
    c.drawRightString(w - 50, y, "Total")
    c.setFont("Times-Roman", 10)
    for i, (desc, qty, unit, amt) in enumerate(items, 1):
        y -= 18
        c.drawString(50, y, str(i))
        c.drawString(85, y, desc)
        c.drawRightString(380, y, str(qty))
        c.drawRightString(460, y, money(unit))
        c.drawRightString(w - 50, y, money(amt))
    y -= 30
    c.drawString(360, y, "Net total")
    c.drawRightString(w - 50, y, f"{money(sub)} EUR")
    y -= 15
    c.drawString(360, y, "VAT 19%")
    c.drawRightString(w - 50, y, f"{money(tax)} EUR")
    y -= 18
    c.setFont("Times-Bold", 11)
    c.drawString(360, y, "Gross total")
    c.drawRightString(w - 50, y, f"{money(total)} EUR")

    c.setFont("Times-Roman", 8)
    c.setFillColor(GREY)
    c.drawString(50, 50, "Synthetic sample document generated for testing. All names and figures are fictional.")
    c.save()
    return {
        "invoice_number": "DF-88213",
        "invoice_date": "2026-02-03",
        "due_date": "2026-03-05",
        "seller_name": "Demo Freight GmbH",
        "buyer_name": "Northwind Parts Pte. Ltd.",
        "currency": "EUR",
        "subtotal": sub,
        "tax": tax,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# Invoice 4: two pages, long item list, totals on page 2
# --------------------------------------------------------------------------- #
def invoice_two_page(path: Path) -> dict:
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    w, h = A4
    catalogue = [f"{p} (batch {k})" for p in PARTS for k in ("A", "B", "C")]
    items = make_items(30, catalogue, 1.2, 60)
    sub, tax, total = totals(items, 0.09)

    def header(page: int) -> float:
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, h - 60, "Placeholder Supplies Pte. Ltd.")
        c.setFont("Helvetica", 9)
        c.drawRightString(w - 50, h - 60, f"Page {page} of 2")
        c.drawRightString(w - 50, h - 72, "Ref: PS-INV-30027")
        return h - 100

    y = header(1)
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Invoice to: Sample Robotics Ltd.")
    c.drawString(50, y - 14, "Date of issue: 20/01/2026")
    c.drawString(50, y - 28, "Terms: Net 30, due 19/02/2026")
    y -= 60
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Item")
    c.drawRightString(380, y, "Qty")
    c.drawRightString(460, y, "Unit (SGD)")
    c.drawRightString(w - 50, y, "Amount (SGD)")
    c.setFont("Helvetica", 9)
    for n, (desc, qty, unit, amt) in enumerate(items):
        if n == 22:
            c.showPage()
            y = header(2) - 10
            c.setFont("Helvetica", 9)
        y -= 17
        c.drawString(50, y, desc)
        c.drawRightString(380, y, str(qty))
        c.drawRightString(460, y, money(unit))
        c.drawRightString(w - 50, y, money(amt))
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(340, y, "Sub-total")
    c.drawRightString(w - 50, y, money(sub))
    c.drawString(340, y - 16, "GST @ 9%")
    c.drawRightString(w - 50, y - 16, money(tax))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(340, y - 36, "TOTAL SGD")
    c.drawRightString(w - 50, y - 36, money(total))
    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawString(50, 50, "Synthetic sample document generated for testing. All names and figures are fictional.")
    c.save()
    return {
        "invoice_number": "PS-INV-30027",
        "invoice_date": "2026-01-20",
        "due_date": "2026-02-19",
        "seller_name": "Placeholder Supplies Pte. Ltd.",
        "buyer_name": "Sample Robotics Ltd.",
        "currency": "SGD",
        "subtotal": sub,
        "tax": tax,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #
def paragraph(c: canvas.Canvas, text: str, x: float, y: float, width: float, font="Times-Roman", size=10.5, lead=14) -> float:
    c.setFont(font, size)
    words, line = text.split(), ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font, size) > width:
            c.drawString(x, y, line)
            y -= lead
            line = word
        else:
            line = trial
    if line:
        c.drawString(x, y, line)
        y -= lead
    return y - 6


def contract(path: Path, title: str, intro: str, clauses: list[tuple[str, str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    w, h = A4
    c.setFillColor(INK)
    c.setFont("Times-Bold", 16)
    c.drawCentredString(w / 2, h - 70, title)
    y = paragraph(c, intro, 60, h - 110, w - 120)
    for heading, body in clauses:
        if y < 140:
            c.showPage()
            c.setFillColor(INK)
            y = h - 70
        c.setFont("Times-Bold", 11)
        c.drawString(60, y, heading)
        y = paragraph(c, body, 60, y - 16, w - 120)
    y -= 20
    c.setFont("Times-Roman", 10)
    c.drawString(60, y, "Signed for and on behalf of each party by an authorised signatory.")
    c.setFont("Times-Roman", 8)
    c.setFillColor(GREY)
    c.drawString(60, 50, "Synthetic sample document generated for testing. All names and terms are fictional.")
    c.save()


def contract_services(path: Path) -> dict:
    contract(
        path,
        "MASTER SERVICES AGREEMENT",
        "This Master Services Agreement is made on 1 July 2026 (the Effective Date) between "
        "Northwind Parts Pte. Ltd. (the Customer) and Example Logistics Pte. Ltd. (the Provider).",
        [
            ("1. Services", "The Provider will supply warehousing and delivery services as described in each "
             "statement of work agreed in writing by both parties."),
            ("2. Term", "This Agreement starts on the Effective Date and continues for a period of 24 months, "
             "unless terminated earlier under clause 6."),
            ("3. Fees and Payment", "The Customer will pay each undisputed invoice within 30 days of the invoice "
             "date. Fees are stated in Singapore dollars and exclude goods and services tax."),
            ("4. Service Levels", "The Provider will use reasonable efforts to meet the delivery windows set out "
             "in the applicable statement of work."),
            ("5. Confidentiality", "Each party will keep the other party's confidential information private and "
             "use it only to perform this Agreement."),
            ("6. Termination", "Either party may terminate this Agreement for convenience by giving not less than "
             "sixty (60) days written notice to the other party. The notice period starts on the day the notice "
             "is received."),
            ("7. Governing Law", "This Agreement is governed by the laws of Singapore."),
        ],
    )
    return {
        "contract_title": "Master Services Agreement",
        "party_a": "Northwind Parts Pte. Ltd.",
        "party_b": "Example Logistics Pte. Ltd.",
        "effective_date": "2026-07-01",
        "term_months": 24,
        "notice_period_days": 60,
        "payment_terms_days": 30,
        "governing_law": "Singapore",
    }


def contract_supply(path: Path) -> dict:
    contract(
        path,
        "SUPPLY AGREEMENT",
        "This Supply Agreement is entered into as of 15 September 2026 by and between "
        "Sample Robotics Ltd. (the Buyer) and Demo Freight GmbH (the Supplier).",
        [
            ("1. Supply of Goods", "The Supplier agrees to supply the components listed in Schedule 1 against "
             "purchase orders issued by the Buyer."),
            ("2. Duration", "This Agreement shall remain in force for twelve (12) months from the date above and "
             "renews automatically for further periods of twelve months."),
            ("3. Price and Payment", "Prices are fixed for the duration of the Agreement. Invoices are payable "
             "within 45 days of receipt."),
            ("4. Delivery", "Delivery is made to the Buyer's nominated site. Risk passes on delivery."),
            ("5. Termination", "Either party may end this Agreement by giving ninety (90) days prior written "
             "notice. Notice is effective from the date of dispatch."),
            ("6. Law and Jurisdiction", "This Agreement shall be governed by and construed in accordance with "
             "the laws of England and Wales."),
        ],
    )
    return {
        "contract_title": "Supply Agreement",
        "party_a": "Sample Robotics Ltd.",
        "party_b": "Demo Freight GmbH",
        "effective_date": "2026-09-15",
        "term_months": 12,
        "notice_period_days": 90,
        "payment_terms_days": 45,
        "governing_law": "England and Wales",
    }


# --------------------------------------------------------------------------- #
# Scanned-style invoice: rendered to an image, slightly rotated, image-only PDF
# --------------------------------------------------------------------------- #
def invoice_scanned(path: Path) -> dict:
    import pypdfium2 as pdfium
    from PIL import Image, ImageFilter

    tmp = io.BytesIO()
    c = canvas.Canvas(tmp, pagesize=A4, invariant=1)
    w, h = A4
    items = make_items(3, SERVICES, 50, 500)
    sub, tax, total = totals(items, 0.09)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(60, h - 80, "Acme Example Services Pte. Ltd.")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, h - 130, "INVOICE")
    c.setFont("Helvetica", 12)
    rows = [
        ("Invoice No.", "AES-5120"),
        ("Date", "8 June 2026"),
        ("Due", "8 July 2026"),
        ("Billed to", "Northwind Parts Pte. Ltd."),
    ]
    y = h - 160
    for k, v in rows:
        c.drawString(60, y, k)
        c.drawString(180, y, v)
        y -= 20
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "Description")
    c.drawRightString(w - 60, y, "Amount (SGD)")
    c.setFont("Helvetica", 12)
    for desc, qty, unit, amt in items:
        y -= 22
        c.drawString(60, y, desc)
        c.drawRightString(w - 60, y, money(amt))
    y -= 40
    for label, val in (("Subtotal", sub), ("GST 9%", tax), ("Total SGD", total)):
        c.drawString(330, y, label)
        c.drawRightString(w - 60, y, money(val))
        y -= 22
    c.save()

    page = pdfium.PdfDocument(tmp.getvalue())[0]
    img = page.render(scale=150 / 72).to_pil().convert("L")
    img = img.rotate(0.6, resample=Image.BICUBIC, expand=False, fillcolor=255)
    import numpy as np

    noise_rng = np.random.default_rng(7)
    noise = Image.fromarray(noise_rng.normal(128, 18, (img.height, img.width)).clip(0, 255).astype("uint8"))
    img = Image.blend(img, noise, 0.08).filter(ImageFilter.GaussianBlur(0.4))
    img = img.point(lambda p: min(255, int(p * 1.04) + 6))

    out = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    out.drawImage(ImageReader(buf), 0, 0, width=w, height=h)
    out.save()
    return {
        "invoice_number": "AES-5120",
        "invoice_date": "2026-06-08",
        "due_date": "2026-07-08",
        "seller_name": "Acme Example Services Pte. Ltd.",
        "buyer_name": "Northwind Parts Pte. Ltd.",
        "currency": "SGD",
        "subtotal": sub,
        "tax": tax,
        "total": total,
    }


DOCS = [
    ("invoice-northwind-classic", "invoice", invoice_classic),
    ("invoice-example-logistics-banner", "invoice", invoice_banner),
    ("invoice-demo-freight-compact", "invoice", invoice_compact),
    ("invoice-placeholder-two-page", "invoice", invoice_two_page),
    ("contract-master-services", "contract", contract_services),
    ("contract-supply", "contract", contract_supply),
    ("invoice-acme-scanned", "invoice", invoice_scanned),
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, schema, fn in DOCS:
        fields = fn(OUT / f"{name}.pdf")
        write_truth(name, schema, fields)
        print(f"wrote samples/{name}.pdf")


if __name__ == "__main__":
    main()
