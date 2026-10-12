from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching import match_vendor, match_purchase_order
from app.models import (
    InvoiceProcessingResult,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.reconciliation import reconcile_invoice


def _save_result(
    session: Session,
    invoice_number: str,
    vendor_id: int | None,
    purchase_order_id: int | None,
    status: str,
    issues: list,
) -> dict:
    record = InvoiceProcessingResult(
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        purchase_order_id=purchase_order_id,
        status=status,
        issues=issues,
    )
    session.add(record)
    session.commit()

    return {
        "id": record.id,
        "invoice_number": invoice_number,
        "vendor_id": vendor_id,
        "purchase_order_id": purchase_order_id,
        "status": status,
        "issues": issues,
    }


def process_invoice(session: Session, invoice: dict) -> dict:
    invoice_number = invoice["invoice_number"]

    vendor_result = match_vendor(session, invoice["vendor_name"])

    if vendor_result["status"] != "matched":
        if vendor_result["status"] == "ambiguous":
            status = "vendor_ambiguous"
        else:
            status = "vendor_unmatched"

        return _save_result(
            session,
            invoice_number=invoice_number,
            vendor_id=vendor_result["vendor_id"],
            purchase_order_id=None,
            status=status,
            issues=[],
        )

    po_result = match_purchase_order(
        session,
        invoice["po_reference"],
        vendor_result["vendor_id"],
    )

    if po_result["status"] != "matched":
        if po_result["status"] == "vendor_mismatch":
            status = "po_vendor_mismatch"
        else:
            status = "po_unmatched"

        return _save_result(
            session,
            invoice_number=invoice_number,
            vendor_id=vendor_result["vendor_id"],
            purchase_order_id=po_result["purchase_order_id"],
            status=status,
            issues=[],
        )

    purchase_order = session.get(
        PurchaseOrder,
        po_result["purchase_order_id"],
    )

    if purchase_order is None:
        return _save_result(
            session,
            invoice_number=invoice_number,
            vendor_id=vendor_result["vendor_id"],
            purchase_order_id=po_result["purchase_order_id"],
            status="po_not_found",
            issues=[],
        )

    po_lines = session.scalars(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.purchase_order_id == purchase_order.id)
        .order_by(PurchaseOrderLine.id)
    ).all()

    if invoice["currency"] != purchase_order.currency:
        return _save_result(
            session,
            invoice_number=invoice_number,
            vendor_id=vendor_result["vendor_id"],
            purchase_order_id=purchase_order.id,
            status="currency_mismatch",
            issues=[],
        )

    po = {
        "total_cents": purchase_order.total_cents,
        "line_items": [
            {
                "item_code": line.item_code,
                "quantity": line.quantity,
                "unit_price_cents": line.unit_price_cents,
            }
            for line in po_lines
        ],
    }

    issues = reconcile_invoice(invoice, po)

    return _save_result(
        session,
        invoice_number=invoice_number,
        vendor_id=vendor_result["vendor_id"],
        purchase_order_id=purchase_order.id,
        status="matched",
        issues=issues,
    )
