import json
from pathlib import Path

from app.reconciliation import compare_totals

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_valid_invoice_fixture_has_matching_total():
    with (FIXTURES_DIR / "invoices" / "valid_invoice.json").open(
        encoding="utf-8"
    ) as file:
        invoice = json.load(file)

    with (FIXTURES_DIR / "purchase_orders.json").open(
        encoding="utf-8"
    ) as file:
        purchase_orders = json.load(file)

    po = next(
        po
        for po in purchase_orders
        if po["po_number"] == invoice["po_reference"]
    )

    issues = compare_totals(
        invoice_total_cents=invoice["stated_total_cents"],
        po_total_cents=po["total_cents"],
    )

    assert issues == []


def test_invalid_invoice_fixture_non_matching_total():
    with (FIXTURES_DIR / "invoices" / "price_mismatch.json").open(
        encoding="utf-8"
    ) as file:
        invoice = json.load(file)

    with (FIXTURES_DIR / "purchase_orders.json").open(
        encoding="utf-8"
    ) as file:
        purchase_orders = json.load(file)

    po = next(
        po
        for po in purchase_orders
        if po["po_number"] == invoice["po_reference"]
    )

    issues = compare_totals(
        invoice_total_cents=invoice["stated_total_cents"],
        po_total_cents=po["total_cents"],
    )

    assert issues == [
        {
            "code": "PO_TOTAL_MISMATCH",
            "expected_cents": 210000,
            "observed_cents": 240000,
            "difference_cents": 30000,
        }
    ]
