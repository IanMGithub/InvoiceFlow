import json
from pathlib import Path

from app.reconciliation import (
    compare_totals,
    compare_line_items,
    reconcile_invoice
)

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


def test_valid_invoice_fixture_has_matching_unit_prices():
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

    reversed_po_lines = list(reversed(po["line_items"]))

    issues = compare_line_items(
        invoice_lines=invoice["line_items"],
        po_lines=reversed_po_lines,
    )

    assert issues == []


def test_price_mismatch_fixture_has_unit_price_issue():
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

    issues = compare_line_items(
        invoice_lines=invoice["line_items"],
        po_lines=po["line_items"],
    )

    assert issues == [
        {
            "code": "UNIT_PRICE_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_cents": 12000,
            "observed_cents": 15000,
            "difference_cents": 3000,
        }
    ]


def test_reconcile_quantity_mismatch_fixture_returns_all_issues():
    with (FIXTURES_DIR / "invoices" / "quantity_mismatch.json").open(
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

    issues = reconcile_invoice(invoice, po)

    assert issues == [
        {
            "code": "QUANTITY_MISMATCH",
            "item_code": "TONER-BK",
            "expected_quantity": 6,
            "observed_quantity": 5,
            "difference_quantity": -1,
        },
        {
            "code": "PO_TOTAL_MISMATCH",
            "expected_cents": 210000,
            "observed_cents": 195000,
            "difference_cents": -15000,
        },
    ]
