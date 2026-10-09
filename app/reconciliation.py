def compare_totals(
    invoice_total_cents: int,
    po_total_cents: int,
) -> list[dict]:
    if invoice_total_cents == po_total_cents:
        return []
    else:
        return [
            {
                "code": "PO_TOTAL_MISMATCH",
                "expected_cents": po_total_cents,
                "observed_cents": invoice_total_cents,
                "difference_cents": invoice_total_cents - po_total_cents
            }
        ]


def compare_line_items(
    invoice_lines: list[dict],
    po_lines: list[dict],
) -> list[dict]:
    issues = []
    for invoice_line in invoice_lines:
        item_code = invoice_line["item_code"]

        matching_po_lines = [
            po_line
            for po_line in po_lines
            if po_line["item_code"] == item_code
        ]

        if len(matching_po_lines) == 0:
            issues.append(
                {
                    "code": "ITEM_UNMATCHED",
                    "item_code": item_code
                }
            )
            continue

        if len(matching_po_lines) > 1:
            issues.append(
                {
                    "code": "ITEM_MATCH_AMBIGUOUS",
                    "item_code": item_code,
                    "match_count": len(matching_po_lines),
                }
            )
            continue

        po_line = matching_po_lines[0]
        invoice_quantity = invoice_line["quantity"]
        po_quantity = po_line["quantity"]

        if invoice_quantity != po_quantity:
            issues.append(
                {
                    "code": "QUANTITY_MISMATCH",
                    "item_code": item_code,
                    "expected_quantity": po_quantity,
                    "observed_quantity": invoice_quantity,
                    "difference_quantity": invoice_quantity - po_quantity,
                }
            )

        invoice_price = invoice_line["unit_price_cents"]
        po_price = po_line["unit_price_cents"]

        if invoice_price != po_price:
            issues.append(
                {
                    "code": "UNIT_PRICE_MISMATCH",
                    "item_code": item_code,
                    "expected_cents": po_price,
                    "observed_cents": invoice_price,
                    "difference_cents": invoice_price - po_price,
                }
            )
    return issues


def reconcile_invoice(
    invoice: dict,
    po: dict,
) -> list[dict]:
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

    return issues
