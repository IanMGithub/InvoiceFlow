import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.invoice_processing import process_invoice
from app.models import (
    InvoiceProcessingResult,
    PurchaseOrder,
    PurchaseOrderLine,
    Vendor,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def _insert_vendor(session, vendor_code, name, aliases=None):
    vendor = Vendor(
        vendor_code=vendor_code,
        name=name,
        normalized_name=name.strip().casefold(),
        aliases=[] if aliases is None else aliases,
    )
    session.add(vendor)
    session.flush()
    return vendor


def _insert_purchase_order(
    session,
    vendor_id,
    po_number,
    currency="USD",
    total_cents=210000,
):
    purchase_order = PurchaseOrder(
        vendor_id=vendor_id,
        po_number=po_number,
        currency=currency,
        total_cents=total_cents,
    )
    session.add(purchase_order)
    session.flush()
    return purchase_order


def _insert_po_line(
    session,
    purchase_order_id,
    item_code,
    quantity,
    unit_price_cents,
    description="Test item",
):
    line = PurchaseOrderLine(
        purchase_order_id=purchase_order_id,
        item_code=item_code,
        description=description,
        quantity=quantity,
        unit_price_cents=unit_price_cents,
        line_total_cents=quantity * unit_price_cents,
    )
    session.add(line)
    session.flush()
    return line


def test_matching_invoice_and_po_returns_matched_with_reconciliation_issues(
    session,
):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-IP-MATCH-001",
        name="Cedar Ridge Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-TEST-IP-001",
        total_cents=120000,
    )
    _insert_po_line(
        session,
        purchase_order_id=purchase_order.id,
        item_code="PAPER-A4",
        quantity=10,
        unit_price_cents=12000,
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-001",
        "vendor_name": "Cedar Ridge Office Supply",
        "po_reference": "PO-TEST-IP-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
            }
        ],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-001",
        "vendor_id": vendor.id,
        "purchase_order_id": purchase_order.id,
        "status": "matched",
        "issues": [],
    }


def test_unmatched_vendor_returns_vendor_unmatched(session):
    _insert_vendor(
        session,
        vendor_code="TEST-IP-UNKNOWN-001",
        name="Pine Valley Supply",
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-UNKNOWN-001",
        "vendor_name": "Unknown Supplier",
        "po_reference": "PO-TEST-IP-UNKNOWN-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-UNKNOWN-001",
        "vendor_id": None,
        "purchase_order_id": None,
        "status": "vendor_unmatched",
        "issues": [],
    }


def test_ambiguous_vendor_returns_vendor_ambiguous(session):
    _insert_vendor(
        session,
        vendor_code="TEST-IP-AMBIG-A-001",
        name="Riverbend Supplies",
    )
    _insert_vendor(
        session,
        vendor_code="TEST-IP-AMBIG-B-001",
        name="Riverbend Wholesale",
        aliases=["Riverbend Supplies"],
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-AMBIG-001",
        "vendor_name": "Riverbend Supplies",
        "po_reference": "PO-TEST-IP-AMBIG-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-AMBIG-001",
        "vendor_id": None,
        "purchase_order_id": None,
        "status": "vendor_ambiguous",
        "issues": [],
    }


def test_unknown_po_returns_po_unmatched(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-IP-POUNK-001",
        name="Lakeside Office Supply",
    )
    _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-TEST-IP-KNOWN-001",
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-POUNK-001",
        "vendor_name": "Lakeside Office Supply",
        "po_reference": "PO-DOES-NOT-EXIST",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-POUNK-001",
        "vendor_id": vendor.id,
        "purchase_order_id": None,
        "status": "po_unmatched",
        "issues": [],
    }


def test_po_owned_by_different_vendor_returns_po_vendor_mismatch(session):
    owner = _insert_vendor(
        session,
        vendor_code="TEST-IP-OWNER-001",
        name="Harbor Mill Supply",
    )
    invoice_vendor = _insert_vendor(
        session,
        vendor_code="TEST-IP-OTHER-001",
        name="Summit Paper Company",
    )
    _insert_purchase_order(
        session,
        vendor_id=owner.id,
        po_number="PO-TEST-IP-OWNED-001",
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-OWNED-001",
        "vendor_name": "Summit Paper Company",
        "po_reference": "PO-TEST-IP-OWNED-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-OWNED-001",
        "vendor_id": invoice_vendor.id,
        "purchase_order_id": None,
        "status": "po_vendor_mismatch",
        "issues": [],
    }


def test_currency_mismatch_returns_currency_mismatch(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-IP-CURRENCY-001",
        name="Northstar Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-TEST-IP-CURRENCY-001",
        currency="EUR",
        total_cents=120000,
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-CURRENCY-001",
        "vendor_name": "Northstar Office Supply",
        "po_reference": "PO-TEST-IP-CURRENCY-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-CURRENCY-001",
        "vendor_id": vendor.id,
        "purchase_order_id": purchase_order.id,
        "status": "currency_mismatch",
        "issues": [],
    }


def test_reconciliation_issue_is_returned_without_stopping_processing(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-IP-QTY-001",
        name="Southstar Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-TEST-IP-QTY-001",
        total_cents=90000,
    )
    _insert_po_line(
        session,
        purchase_order_id=purchase_order.id,
        item_code="TONER-BK",
        quantity=6,
        unit_price_cents=15000,
    )

    invoice = {
        "invoice_number": "INV-TEST-IP-QTY-001",
        "vendor_name": "Southstar Office Supply",
        "po_reference": "PO-TEST-IP-QTY-001",
        "currency": "USD",
        "stated_total_cents": 90000,
        "line_items": [
            {
                "item_code": "TONER-BK",
                "quantity": 5,
                "unit_price_cents": 15000,
            }
        ],
    }

    result = process_invoice(session, invoice)
    saved = session.get(InvoiceProcessingResult, result["id"])

    assert saved is not None
    assert result == {
        "id": saved.id,
        "invoice_number": "INV-TEST-IP-QTY-001",
        "vendor_id": vendor.id,
        "purchase_order_id": purchase_order.id,
        "status": "matched",
        "issues": [
            {
                "code": "QUANTITY_MISMATCH",
                "item_code": "TONER-BK",
                "expected_quantity": 6,
                "observed_quantity": 5,
                "difference_quantity": -1,
            }
        ],
    }
