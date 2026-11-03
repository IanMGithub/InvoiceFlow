# Fixture expectations

## What the code stores

The public demo and the local processor store `matched` for the three curated fixtures below, because the vendor and purchase order match. They do not store `ready_for_review` or `needs_review`. Issue codes are stored on that result.

Verified outcomes:

- `valid_invoice.json`: no issues.
- `quantity_mismatch.json`: `QUANTITY_MISMATCH` on `TONER-BK` (expected quantity 6, observed 5) and `PO_TOTAL_MISMATCH` (expected 210000 cents, observed 195000 cents).
- `price_mismatch.json`: `UNIT_PRICE_MISMATCH` on `PAPER-A4` (expected 12000 cents, observed 15000 cents) and `PO_TOTAL_MISMATCH` (expected 210000 cents, observed 240000 cents).

Line arithmetic inside the mismatch invoices agrees, so those files reach reconciliation. There is no separate internal line-total or invoice-total issue for them.

The status names in the older notes below (`ready_for_review`, `needs_review`) are target language, not stored values. Idempotency keys are not implemented. The local prototype dedupes identical JSON content by hash. The public demo computes each curated example once at startup.

## Valid invoice
Input: invoices/valid_invoice.json
Target status language: ready_for_review
Implemented status: matched
Issues: none

## Price mismatch
Input: invoices/price_mismatch.json
Target status language: needs_review
Implemented status: matched
Issues:
- UNIT_PRICE_MISMATCH on PAPER-A4
- PO_TOTAL_MISMATCH: expected 210000 cents, observed 240000 cents
No line-arithmetic or internal invoice-total mismatch.

## Quantity mismatch
Input: invoices/quantity_mismatch.json
Target status language: needs_review
Implemented status: matched
Issues:
- QUANTITY_MISMATCH on TONER-BK
- PO_TOTAL_MISMATCH: expected 210000 cents, observed 195000 cents
No line-arithmetic or internal invoice-total mismatch.

## Duplicate submission
Input: invoices/valid_invoice.json, submitted twice
Target: an idempotency key returns the original record. That key is not implemented.
Local prototype behavior: the same canonical JSON hash returns the original ingestion and does not create a second processing result.
Public demo behavior: the example is processed once at startup, and later clicks do not insert rows.

## Missing invoice number
Input: invoices/missing_invoice_number.json
Target status language: needs_review
Implemented status: invalid_invoice
Issues:
- MISSING_FIELD for invoice_number

## Unmatched PO
Input: invoices/unmatched_po.json
Target status language: needs_review
Implemented status: po_unmatched
Issues:
- no PO comparison issues, because matching stops before reconciliation
Do not run PO-dependent comparisons without a matched PO.