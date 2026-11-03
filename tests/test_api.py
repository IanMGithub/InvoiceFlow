import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import app, get_session
from app.db import Base
from app.models import (
    InvoiceProcessingResult,
    PurchaseOrder,
    PurchaseOrderLine,
    Vendor,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def client(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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


def _valid_invoice_payload():
    return {
        "invoice_number": "INV-API-001",
        "vendor_name": "Cedar Ridge Office Supply",
        "po_reference": "PO-API-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "description": "A4 paper cases",
                "quantity": 10,
                "unit_price_cents": 12000,
                "stated_line_total_cents": 120000,
            }
        ],
    }


def _seed_matching_vendor_and_po(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-API-001",
        name="Cedar Ridge Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-API-001",
        total_cents=120000,
    )
    _insert_po_line(
        session,
        purchase_order_id=purchase_order.id,
        item_code="PAPER-A4",
        quantity=10,
        unit_price_cents=12000,
    )
    return vendor, purchase_order


def _processing_result_count(session):
    return len(session.scalars(select(InvoiceProcessingResult)).all())


def test_successful_invoice_submission_returns_200_and_processing_result(
    client,
    session,
):
    vendor, purchase_order = _seed_matching_vendor_and_po(session)

    response = client.post("/invoices", json=_valid_invoice_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ingested"
    assert body["ingestion_id"] is not None
    assert body["processing_result_id"] is not None
    assert body["processing_result"] == {
        "id": body["processing_result_id"],
        "invoice_number": "INV-API-001",
        "vendor_id": vendor.id,
        "purchase_order_id": purchase_order.id,
        "status": "matched",
        "issues": [],
    }


def test_duplicate_invoice_content_returns_409_and_does_not_reprocess(
    client,
    session,
):
    _seed_matching_vendor_and_po(session)
    payload = _valid_invoice_payload()

    first_response = client.post("/invoices", json=payload)
    second_response = client.post("/invoices", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    body = second_response.json()
    assert body["code"] == "DUPLICATE_INVOICE"
    assert body["status"] == "duplicate"
    assert body["detail"] == "Invoice content has already been ingested."
    assert body["ingestion_id"] == first_response.json()["ingestion_id"]
    assert (
        body["processing_result_id"]
        == first_response.json()["processing_result_id"]
    )
    assert _processing_result_count(session) == 1


def test_invalid_invoice_field_returns_422(client):
    payload = _valid_invoice_payload()
    payload["line_items"][0]["quantity"] = 0

    response = client.post("/invoices", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_REQUEST"
    assert "detail" in body


def test_unknown_processing_result_id_returns_404(client):
    response = client.get("/processing-results/99999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Processing result not found.",
        "code": "NOT_FOUND",
    }


def test_unknown_invoice_source_id_returns_404(client):
    response = client.get("/invoices/sources/99999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Invoice source not found.",
        "code": "NOT_FOUND",
    }
