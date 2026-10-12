import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.matching import match_purchase_order
from app.models import PurchaseOrder, Vendor


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


def test_existing_po_for_matching_vendor_returns_matched(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-POM-MATCH-001",
        name="Cedar Ridge Office Supply",
    )
    purchase_order = _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-TEST-POM-001",
    )

    result = match_purchase_order(
        session,
        "PO-TEST-POM-001",
        vendor.id,
    )

    assert result == {
        "status": "matched",
        "purchase_order_id": purchase_order.id,
    }


def test_unknown_po_reference_returns_unmatched(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-POM-UNKNOWN-001",
        name="Pine Valley Supply",
    )
    _insert_purchase_order(
        session,
        vendor_id=vendor.id,
        po_number="PO-TEST-POM-KNOWN-001",
    )

    result = match_purchase_order(
        session,
        "PO-DOES-NOT-EXIST",
        vendor.id,
    )

    assert result == {
        "status": "unmatched",
        "purchase_order_id": None,
    }


def test_existing_po_for_different_vendor_returns_vendor_mismatch(session):
    owner = _insert_vendor(
        session,
        vendor_code="TEST-POM-OWNER-001",
        name="Riverbend Supplies",
    )
    other_vendor = _insert_vendor(
        session,
        vendor_code="TEST-POM-OTHER-001",
        name="Riverbend Wholesale",
    )
    _insert_purchase_order(
        session,
        vendor_id=owner.id,
        po_number="PO-TEST-POM-OWNED-001",
    )

    result = match_purchase_order(
        session,
        "PO-TEST-POM-OWNED-001",
        other_vendor.id,
    )

    assert result == {
        "status": "vendor_mismatch",
        "purchase_order_id": None,
    }
