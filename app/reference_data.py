import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PurchaseOrder, PurchaseOrderLine, Vendor


def seed_reference_data(
    session: Session,
    project_dir: Path,
    *,
    echo: bool = False,
) -> None:
    """Load synthetic vendors and purchase orders into an existing session.

    The caller owns the transaction. Fixture paths are fixed project files,
    not visitor input.
    """

    def say(message: str) -> None:
        if echo:
            print(message)

    vendor_path = project_dir / "fixtures" / "vendors.json"
    po_path = project_dir / "fixtures" / "purchase_orders.json"

    with vendor_path.open(encoding="utf-8") as file:
        vendor_data = json.load(file)

    with po_path.open(encoding="utf-8") as file:
        po_data = json.load(file)

    for data in vendor_data:
        existing_vendor = session.scalar(
            select(Vendor).where(Vendor.vendor_code == data["vendor_code"])
        )

        if existing_vendor is not None:
            say(f"Already exists: {data['vendor_code']}")
            continue

        vendor = Vendor(
            vendor_code=data["vendor_code"],
            name=data["name"],
            normalized_name=data["name"].strip().casefold(),
            aliases=data["aliases"],
        )
        session.add(vendor)
        say(f"Adding: {data['vendor_code']}")

    for data in po_data:
        existing_po = session.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.po_number == data["po_number"]
            )
        )

        if existing_po is not None:
            say(f"PO already exists: {data['po_number']}")
            continue

        vendor = session.scalar(
            select(Vendor).where(Vendor.vendor_code == data["vendor_code"])
        )

        if vendor is None:
            raise ValueError(
                f"Cannot seed PO {data['po_number']}: "
                f"vendor {data['vendor_code']} does not exist"
            )

        po = PurchaseOrder(
            vendor_id=vendor.id,
            po_number=data["po_number"],
            currency=data["currency"],
            total_cents=data["total_cents"],
        )
        session.add(po)
        session.flush()

        for line in data["line_items"]:
            session.add(
                PurchaseOrderLine(
                    purchase_order_id=po.id,
                    item_code=line["item_code"],
                    description=line["description"],
                    quantity=line["quantity"],
                    unit_price_cents=line["unit_price_cents"],
                    line_total_cents=line["line_total_cents"],
                )
            )

        say(f"Adding PO: {data['po_number']}")
