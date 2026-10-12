import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.matching import match_vendor
from app.models import Vendor


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


def test_exact_canonical_name_returns_matched(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-VM-CANONICAL-001",
        name="Cedar Ridge Office Supply",
    )

    result = match_vendor(session, "Cedar Ridge Office Supply")

    assert result == {
        "status": "matched",
        "vendor_id": vendor.id,
    }


def test_explicit_alias_returns_matched(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-VM-ALIAS-001",
        name="Lakeside Office Supply",
        aliases=["Lakeside Office Supply LLC"],
    )

    result = match_vendor(session, "Lakeside Office Supply LLC")

    assert result == {
        "status": "matched",
        "vendor_id": vendor.id,
    }


def test_case_and_outer_whitespace_returns_matched(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-VM-CASEFOLD-001",
        name="Northstar Office Supply",
    )

    result = match_vendor(session, "  NORTHSTAR OFFICE SUPPLY  ")

    assert result == {
        "status": "matched",
        "vendor_id": vendor.id,
    }


def test_unknown_supplier_returns_unmatched(session):
    _insert_vendor(
        session,
        vendor_code="TEST-VM-UNKNOWN-001",
        name="Pine Valley Supply",
    )

    result = match_vendor(session, "Unknown Supplier")

    assert result == {
        "status": "unmatched",
        "vendor_id": None,
    }


def test_two_distinct_vendors_matching_name_returns_ambiguous(session):
    _insert_vendor(
        session,
        vendor_code="TEST-VM-AMBIG-A-001",
        name="Riverbend Supplies",
    )
    _insert_vendor(
        session,
        vendor_code="TEST-VM-AMBIG-B-001",
        name="Riverbend Wholesale",
        aliases=["Riverbend Supplies"],
    )

    result = match_vendor(session, "Riverbend Supplies")

    assert result == {
        "status": "ambiguous",
        "vendor_id": None,
    }


def test_single_vendor_name_and_alias_match_returns_matched_once(session):
    vendor = _insert_vendor(
        session,
        vendor_code="TEST-VM-BOTH-001",
        name="Summit Paper Company",
        aliases=["Summit Paper Company"],
    )

    result = match_vendor(session, "Summit Paper Company")

    assert result == {
        "status": "matched",
        "vendor_id": vendor.id,
    }
