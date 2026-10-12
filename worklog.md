Built:
- Vendor matching by exact normalized canonical name or explicit alias, with unmatched and ambiguous outcomes.
- Purchase-order matching by PO number, including ownership verification against the matched vendor.
- Invoice processing service (`process_invoice`) that matches vendor and PO, checks currency, and reconciles the invoice.
- Reconciliation integration: line-item and total checks run after a successful match; issues are returned without stopping processing.
- Result persistence: one `InvoiceProcessingResult` row per call, storing invoice number, nullable vendor/PO IDs, status, and issues JSON. The raw invoice payload is not saved yet.

Tests:
- 26 isolated tests: reconciliation (10), vendor matching (6), PO matching (3), and invoice processing (7).

Unfinished:
- Raw invoice payload is not stored.
- No invoice-processing API, AI extraction, or review workflow yet.
