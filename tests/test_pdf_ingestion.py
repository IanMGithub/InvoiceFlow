import hashlib

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import app, get_session
from app.db import Base
from app.ingestion import ingest_invoice_pdf
from app.models import (
    InvoiceProcessingResult,
    InvoiceSource,
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
    total_cents=120000,
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


def _valid_extracted_invoice():
    return {
        "invoice_number": "INV-PDF-001",
        "vendor_name": "Cedar Ridge Office Supply",
        "po_reference": "PO-PDF-001",
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
        vendor_code="TEST-PDF-001",
        name="Cedar Ridge Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-PDF-001",
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


def _make_text_pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def _make_empty_pdf() -> bytes:
    document = pymupdf.open()
    document.new_page()
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def _successful_extractor(_raw_text):
    return _valid_extracted_invoice(), None


def _failing_extractor(_raw_text):
    return None, [
        {
            "code": "EXTRACTION_FAILED",
            "message": "The model could not extract an invoice.",
        }
    ]


def _invalid_extracted_invoice_extractor(_raw_text):
    invoice = _valid_extracted_invoice()
    invoice["currency"] = "usd"
    return invoice, None


def _processing_result_count(session):
    return len(session.scalars(select(InvoiceProcessingResult)).all())


def _source_count(session):
    return len(session.scalars(select(InvoiceSource)).all())


def test_valid_pdf_invoice_is_extracted_and_processed(session):
    vendor, purchase_order = _seed_matching_vendor_and_po(session)
    pdf_bytes = _make_text_pdf("Invoice INV-PDF-001 for Cedar Ridge Office Supply")
    expected_hash = hashlib.sha256(pdf_bytes).hexdigest()

    result = ingest_invoice_pdf(
        session,
        "invoice.pdf",
        pdf_bytes,
        extractor=_successful_extractor,
    )

    assert result["status"] == "ingested"
    assert result["source_type"] == "pdf_file"
    assert result["source_reference"] == "invoice.pdf"
    assert result["content_hash"] == expected_hash
    assert result["ingestion_id"] is not None
    assert result["processing_result_id"] is not None
    assert result["extraction_issues"] is None
    assert result["processing_result"] == {
        "id": result["processing_result_id"],
        "invoice_number": "INV-PDF-001",
        "vendor_id": vendor.id,
        "purchase_order_id": purchase_order.id,
        "status": "matched",
        "issues": [],
    }
    assert _processing_result_count(session) == 1
    assert _source_count(session) == 1


def test_duplicate_pdf_content_is_not_processed_twice(session):
    _seed_matching_vendor_and_po(session)
    pdf_bytes = _make_text_pdf("Invoice INV-PDF-001")

    first_result = ingest_invoice_pdf(
        session,
        "invoice.pdf",
        pdf_bytes,
        extractor=_successful_extractor,
    )
    second_result = ingest_invoice_pdf(
        session,
        "invoice-copy.pdf",
        pdf_bytes,
        extractor=_failing_extractor,
    )

    assert first_result["status"] == "ingested"
    assert second_result["status"] == "duplicate"
    assert second_result["content_hash"] == first_result["content_hash"]
    assert second_result["ingestion_id"] == first_result["ingestion_id"]
    assert second_result["processing_result"] is None
    assert second_result["extraction_issues"] is None
    assert _processing_result_count(session) == 1
    assert _source_count(session) == 1


def test_non_pdf_file_is_rejected(session):
    result = ingest_invoice_pdf(
        session,
        "invoice.txt",
        b"not a pdf",
        extractor=_successful_extractor,
    )

    assert result["status"] == "extraction_failed"
    assert result["ingestion_id"] is None
    assert result["processing_result_id"] is None
    assert result["processing_result"] is None
    assert result["extraction_issues"][0]["code"] == "UNSUPPORTED_FILE"
    assert _processing_result_count(session) == 0
    assert _source_count(session) == 0


def test_unreadable_or_empty_pdf_returns_extraction_failed(session):
    unreadable_result = ingest_invoice_pdf(
        session,
        "broken.pdf",
        b"this is not a valid pdf file",
        extractor=_successful_extractor,
    )
    empty_result = ingest_invoice_pdf(
        session,
        "empty.pdf",
        _make_empty_pdf(),
        extractor=_successful_extractor,
    )

    for result in (unreadable_result, empty_result):
        assert result["status"] == "extraction_failed"
        assert result["ingestion_id"] is not None
        assert result["processing_result_id"] is None
        assert result["processing_result"] is None
        assert result["extraction_issues"][0]["code"] == (
            "PDF_TEXT_EXTRACTION_FAILED"
        )

    assert "scanned or image-only" in empty_result["extraction_issues"][0][
        "message"
    ]
    assert _processing_result_count(session) == 0
    assert _source_count(session) == 2


def test_extractor_failure_returns_extraction_failed(session):
    pdf_bytes = _make_text_pdf("Invoice text that cannot be extracted")

    result = ingest_invoice_pdf(
        session,
        "invoice.pdf",
        pdf_bytes,
        extractor=_failing_extractor,
    )

    assert result["status"] == "extraction_failed"
    assert result["ingestion_id"] is not None
    assert result["processing_result_id"] is None
    assert result["processing_result"] is None
    assert result["extraction_issues"][0]["code"] == "EXTRACTION_FAILED"
    assert _processing_result_count(session) == 0
    assert _source_count(session) == 1


def test_extracted_invoice_validation_failure_is_processed_through_existing_pipeline(
    session,
):
    _seed_matching_vendor_and_po(session)
    pdf_bytes = _make_text_pdf("Invoice with an invalid extracted currency")

    result = ingest_invoice_pdf(
        session,
        "invoice.pdf",
        pdf_bytes,
        extractor=_invalid_extracted_invoice_extractor,
    )

    assert result["status"] == "ingested"
    assert result["processing_result_id"] is not None
    assert result["processing_result"]["status"] == "invalid_invoice"
    assert result["processing_result"]["issues"]
    assert result["extraction_issues"] is None
    assert _processing_result_count(session) == 1
    assert _source_count(session) == 1


def test_pdf_api_endpoint_accepts_pdf_upload(client, session, monkeypatch):
    vendor, purchase_order = _seed_matching_vendor_and_po(session)
    monkeypatch.setattr(
        "app.ingestion.extract_invoice_from_text",
        _successful_extractor,
    )
    pdf_bytes = _make_text_pdf("Invoice INV-PDF-001")

    response = client.post(
        "/invoices/pdf",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ingested"
    assert body["source_type"] == "pdf_file"
    assert body["processing_result_id"] is not None
    assert body["processing_result"]["vendor_id"] == vendor.id
    assert body["processing_result"]["purchase_order_id"] == purchase_order.id
    assert body["processing_result"]["status"] == "matched"


def test_pdf_api_endpoint_rejects_non_pdf_upload(client):
    response = client.post(
        "/invoices/pdf",
        files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 415
    body = response.json()
    assert body["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert body["detail"] == "Only PDF files are accepted."


def test_pdf_api_endpoint_rejects_oversized_file(client):
    oversized = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/invoices/pdf",
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "PAYLOAD_TOO_LARGE"
    assert "10 MB" in body["detail"]
