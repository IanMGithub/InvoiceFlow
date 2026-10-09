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
