import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, PROJECT_DIR, engine
from app.models import Vendor, PurchaseOrder, PurchaseOrderLine


def main():
    Base.metadata.create_all(engine)

    fixture_path = PROJECT_DIR / "fixtures" / "vendors.json"

    with fixture_path.open(encoding="utf-8") as file:
        vendor_data = json.load(file)

    po_fixture_path = PROJECT_DIR / "fixtures" / "purchase_orders.json"

    with po_fixture_path.open(encoding="utf-8") as file:
        po_data = json.load(file)

    with Session(engine) as session:
        with session.begin():
            for data in vendor_data:
                existing_vendor = session.scalar(
                    select(Vendor).where(
                        Vendor.vendor_code == data["vendor_code"]
                    )
                )

                if existing_vendor is not None:
                    print(f"Already exists: {data['vendor_code']}")
                    continue

                vendor = Vendor(
                    vendor_code=data["vendor_code"],
                    name=data["name"],
                    normalized_name=data["name"].strip().casefold(),
                    aliases=data["aliases"],
                )

                session.add(vendor)
                print(f"Adding: {data['vendor_code']}")
            for data in po_data:
                existing_po = session.scalar(
                    select(PurchaseOrder).where(
                        PurchaseOrder.po_number == data["po_number"]
                    )
                )

                if existing_po is not None:
                    print(f"PO already exists: {data['po_number']}")
                    continue

                vendor = session.scalar(
                    select(Vendor).where(
                        Vendor.vendor_code == data["vendor_code"]
                    )
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
                    po_line = PurchaseOrderLine(
                        purchase_order_id=po.id,
                        item_code=line["item_code"],
                        description=line["description"],
                        quantity=line["quantity"],
                        unit_price_cents=line["unit_price_cents"],
                        line_total_cents=line["line_total_cents"],
                    )

                    session.add(po_line)

                print(f"Adding PO: {data['po_number']}")


if __name__ == "__main__":
    main()
