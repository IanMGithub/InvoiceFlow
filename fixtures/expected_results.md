# Fixture expectations

## Valid invoice
Input: invoices/valid_invoice.json
Status: ready_for_review
Issues: none

## Price mismatch
Input: invoices/price_mismatch.json
Status: needs_review
Issues:
- UNIT_PRICE_MISMATCH on PAPER-A4
- PO_TOTAL_MISMATCH: expected 210000 cents, observed 240000 cents
No line-arithmetic or internal invoice-total mismatch.

## Quantity mismatch
Input: invoices/quantity_mismatch.json
Status: needs_review
Issues:
- QUANTITY_MISMATCH on TONER-BK
- PO_TOTAL_MISMATCH: expected 210000 cents, observed 195000 cents
No line-arithmetic or internal invoice-total mismatch.

## Duplicate submission
Input: invoices/valid_invoice.json, submitted twice
Use the same idempotency key and identical payload.
Expected: return the same invoice record; do not create a second record.

## Missing invoice number
Input: invoices/missing_invoice_number.json
Status: needs_review
Issues:
- MISSING_FIELD for invoice_number

## Unmatched PO
Input: invoices/unmatched_po.json
Status: needs_review
Issues:
- PO_UNMATCHED
Do not run PO-dependent comparisons without a matched PO.