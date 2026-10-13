from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching import match_vendor, match_purchase_order
from app.models import (
    InvoiceProcessingResult,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.reconciliation import (
    compare_line_items,
    compare_totals,
    reconcile_invoice,
)
from app.validation import validate_invoice


HEADER_VALIDATION_FIELDS = {
    "invoice",
    "invoice_number",
    "vendor_name",
    "po_reference",
    "currency",
    "stated_total_cents",
}


def _available_invoice_number(invoice):
    if not isinstance(invoice, dict):
        return None

    raw_invoice_number = invoice.get("invoice_number")

    if (
        isinstance(raw_invoice_number, str)
        and raw_invoice_number.strip() != ""
    ):
        return raw_invoice_number

    return None


def _has_header_validation_issues(issues):
    return any(
        issue.get("field") in HEADER_VALIDATION_FIELDS
        for issue in issues
    )


def _has_stated_line_totals(invoice):
    line_items = invoice.get("line_items")

    if not isinstance(line_items, list) or len(line_items) == 0:
        return False

    return all(
        isinstance(line, dict) and "stated_line_total_cents" in line
        for line in line_items
    )


def _save_result(
    session: Session,
    invoice_number: str | None,
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
    validation_issues = validate_invoice(invoice)

    if _has_header_validation_issues(validation_issues):
        return _save_result(
            session,
            invoice_number=_available_invoice_number(invoice),
            vendor_id=None,
            purchase_order_id=None,
            status="invalid_invoice",
            issues=validation_issues,
        )

    invoice_number = _available_invoice_number(invoice)

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

    if _has_stated_line_totals(invoice):
        issues = reconcile_invoice(invoice, po)
    else:
        issues = compare_line_items(
            invoice_lines=invoice["line_items"],
            po_lines=po["line_items"],
        )
        issues.extend(
            compare_totals(
                invoice_total_cents=invoice["stated_total_cents"],
                po_total_cents=po["total_cents"],
            )
        )

    return _save_result(
        session,
        invoice_number=invoice_number,
        vendor_id=vendor_result["vendor_id"],
        purchase_order_id=purchase_order.id,
        status="matched",
        issues=issues,
    )
