import hashlib
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.ingestion import ingest_invoice_file
from app.models import (
    InvoiceProcessingResult,
    InvoiceSource,
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


def _valid_invoice():
    return {
        "invoice_number": "INV-INGEST-001",
        "vendor_name": "Cedar Ridge Office Supply",
        "po_reference": "PO-INGEST-001",
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
        vendor_code="TEST-ING-001",
        name="Cedar Ridge Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-INGEST-001",
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


def _write_json(tmp_path, filename, payload):
    path = tmp_path / filename
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    elif isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
    return path


def _processing_result_count(session):
    return len(session.scalars(select(InvoiceProcessingResult)).all())


def _source_count(session):
    return len(session.scalars(select(InvoiceSource)).all())


def test_valid_json_invoice_is_ingested_and_processed(session, tmp_path):
    vendor, purchase_order = _seed_matching_vendor_and_po(session)
    invoice_path = _write_json(tmp_path, "invoice.json", _valid_invoice())
    expected_hash = hashlib.sha256(invoice_path.read_bytes()).hexdigest()

    result = ingest_invoice_file(session, invoice_path)

    assert result["status"] == "ingested"
    assert result["source_type"] == "json_file"
    assert result["source_reference"] == "invoice.json"
    assert result["content_hash"] == expected_hash
    assert result["ingestion_id"] is not None
    assert result["processing_result_id"] is not None
    assert result["processing_result"] == {
        "id": result["processing_result_id"],
        "invoice_number": "INV-INGEST-001",
        "vendor_id": vendor.id,
        "purchase_order_id": purchase_order.id,
        "status": "matched",
        "issues": [],
    }
    assert _processing_result_count(session) == 1
    assert _source_count(session) == 1


def test_same_invoice_content_is_not_processed_twice(session, tmp_path):
    _seed_matching_vendor_and_po(session)
    invoice_path = _write_json(tmp_path, "invoice.json", _valid_invoice())

    first_result = ingest_invoice_file(session, invoice_path)
    second_result = ingest_invoice_file(session, invoice_path)

    assert first_result["status"] == "ingested"
    assert second_result["status"] == "duplicate"
    assert second_result["content_hash"] == first_result["content_hash"]
    assert second_result["processing_result"] is None
    assert _processing_result_count(session) == 1
    assert _source_count(session) == 1


def test_invalid_json_returns_invalid_json_and_does_not_process(
    session,
    tmp_path,
):
    invoice_path = _write_json(tmp_path, "broken.json", "{not json")

    result = ingest_invoice_file(session, invoice_path)

    assert result["status"] == "invalid_json"
    assert result["ingestion_id"] is None
    assert result["processing_result_id"] is None
    assert result["processing_result"] is None
    assert _processing_result_count(session) == 0
    assert _source_count(session) == 0


def test_non_dictionary_json_returns_invalid_payload_and_does_not_process(
    session,
    tmp_path,
):
    invoice_path = _write_json(tmp_path, "list.json", [1, 2, 3])

    result = ingest_invoice_file(session, invoice_path)

    assert result["status"] == "invalid_payload"
    assert result["ingestion_id"] is None
    assert result["processing_result_id"] is None
    assert result["processing_result"] is None
    assert _processing_result_count(session) == 0
    assert _source_count(session) == 0


def test_missing_file_returns_clear_error(session, tmp_path):
    missing_path = tmp_path / "does-not-exist.json"

    result = ingest_invoice_file(session, missing_path)

    assert result["status"] == "missing_file"
    assert result["ingestion_id"] is None
    assert result["processing_result_id"] is None
    assert result["processing_result"] is None
    assert "does not exist or is not a regular file" in result["error"]
    assert _processing_result_count(session) == 0
    assert _source_count(session) == 0
