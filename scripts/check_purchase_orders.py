from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Vendor, PurchaseOrder, PurchaseOrderLine


def main():
    with Session(engine) as session:
        purchase_orders = session.scalars(
            select(PurchaseOrder).order_by(PurchaseOrder.po_number)
        ).all()

        for po in purchase_orders:
            vendor = session.get(Vendor, po.vendor_id)

            print(
                f"{po.po_number} | "
                f"vendor={vendor.vendor_code} | "
                f"total_cents={po.total_cents}"
            )

            lines = session.scalars(
                select(PurchaseOrderLine)
                .where(PurchaseOrderLine.purchase_order_id == po.id)
                .order_by(PurchaseOrderLine.item_code)
            ).all()

            for line in lines:
                print(
                    f"  {line.item_code} | "
                    f"quantity={line.quantity} | "
                    f"unit_price_cents={line.unit_price_cents}"
                )


if __name__ == "__main__":
    main()
