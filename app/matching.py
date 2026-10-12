from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Vendor, PurchaseOrder


def match_vendor(session: Session, supplier_name: str) -> dict:
    normalized_supplier_name = supplier_name.strip().casefold()

    vendors = session.scalars(select(Vendor)).all()

    matching_vendors = []

    for vendor in vendors:
        name_matches = (
            vendor.normalized_name == normalized_supplier_name
        )

        alias_matches = False

        for alias in vendor.aliases:
            normalized_alias = alias.strip().casefold()

            if normalized_alias == normalized_supplier_name:
                alias_matches = True
                break

        if name_matches or alias_matches:
            matching_vendors.append(vendor)

    if len(matching_vendors) == 0:
        return {
            "status": "unmatched",
            "vendor_id": None,
        }

    if len(matching_vendors) == 1:
        return {
            "status": "matched",
            "vendor_id": matching_vendors[0].id,
        }

    return {
        "status": "ambiguous",
        "vendor_id": None,
    }

def match_purchase_order(
    session: Session,
    po_reference: str,
    vendor_id: int,
) -> dict:
    po = session.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.po_number == po_reference
        )
    )

    if po is None:
        return {
            "status": "unmatched",
            "purchase_order_id": None,
        }

    if po.vendor_id != vendor_id:
        return {
            "status": "vendor_mismatch",
            "purchase_order_id": None,
        }

    return {
        "status": "matched",
        "purchase_order_id": po.id,
    }
    
