Supported invoices

One invoice references one purchase order.

The invoice bills the entire purchase order.

USD only.

Positive integer quantities.

Unit prices have at most two decimal places.

No tax, freight, discounts, partial billing, or credit notes.

No verification that goods were received.

Matching rules

Match the vendor by an exact normalized name or an explicitly defined alias.

Match the purchase order by its PO number.

Verify that the purchase order belongs to the matched vendor.

Match invoice lines to PO lines by item code.

Never silently choose between ambiguous matches.

Unmatched or ambiguous records require review.

Reconciliation rules

Check that:

Required fields are present.

Every expected PO item appears exactly once.

No unexpected invoice items appear.

Quantities match.

Unit prices match.

Each stated line total equals quantity × unit price.

The stated invoice total equals the sum of its line totals.

The stated invoice total equals the PO total.

Record each failed check as an issue rather than silently correcting the data.

Review rules

Passing automated checks does not mean human approval.

Missing information and discrepancies require review.

Corrections must trigger validation and reconciliation again.

Approval is blocked while unresolved issues remain.

Review decisions and changes are saved.

Approval never triggers payment.

Duplicate rules

A repeated request with the same idempotency key and payload returns the original record.

Reusing that key with a different payload produces a conflict.

A repeated document or vendor/invoice-number combination is flagged as a possible business duplicate