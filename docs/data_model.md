# InvoiceFlow Data Model

## vendors
One row represents one known supplier.

Primary key:
- id

Fields:
- vendor_code
- name
- normalized_name
- aliases

## purchase_orders
One row represents one purchase order issued to a vendor.

Primary key:
- id

Foreign keys:
- vendor_id → vendors.id

Fields:
- po_number
- currency
- total_cents

## purchase_order_lines
One row represents one item ordered on a purchase order.

Primary key:
- id

Foreign keys:
- purchase_order_id → purchase_orders.id

Fields:
- item_code
- description
- quantity
- unit_price_cents
- line_total_cents

## invoices
One row represents one submitted invoice and its current processing state.

Primary key:
- id

Foreign keys:
- vendor_id → vendors.id; may be null
- purchase_order_id → purchase_orders.id; may be null

Fields:
- invoice_number; may be null
- extracted_vendor_name; may be null
- extracted_po_reference; may be null
- currency; may be null
- stated_total_cents; may be null
- status
- raw_extraction; may be null
- source_hash
- idempotency_key
- processing_error; may be null
- created_at
- updated_at

## invoice_lines
One row represents one item stated on an invoice.

Primary key:
- id

Foreign keys:
- invoice_id → invoices.id
- purchase_order_line_id → purchase_order_lines.id; may be null

Fields:
- item_code; may be null
- description; may be null
- quantity; may be null
- unit_price_cents; may be null
- stated_line_total_cents; may be null

## invoice_issues
One row represents one problem identified during invoice processing.

Primary key:
- id

Foreign keys:
- invoice_id → invoices.id
- invoice_line_id → invoice_lines.id; may be null

Fields:
- code
- field_name; may be null
- expected_value; may be null
- observed_value; may be null
- resolved_at; may be null

## review_events
One row represents one saved human review action.

Primary key:
- id

Foreign keys:
- invoice_id → invoices.id

Fields:
- reviewer_label
- action
- reason
- changes
- created_at

# Relationships

- One vendor can have many purchase orders.
- One purchase order can have many purchase-order lines.
- One vendor can have many matched invoices.
- One purchase order can have many submitted invoice records.
- One invoice can have many invoice lines.
- One invoice can have many issues.
- One invoice can have many review events.
- An invoice may not yet have a matched vendor or purchase order.
- An invoice line may not yet have a matched purchase-order line.

Valid Fixture Example Tracing:
Before processing begins, our database contains the Northstar Office Supply vendor record, purchase order PO-1001, and its two purchase-order lines.

InvoiceFlow receives the structured invoice fixture INV-1001. Because this input is JSON, its fields and line items are already available; no AI extraction is needed.

The system checks that the required invoice data is present and usable.

It uses the invoice’s supplier name to find Northstar Office Supply. It uses the PO reference to find PO-1001, then verifies that the PO belongs to Northstar.

It matches each invoice line to a purchase-order line using the item code.

It compares quantities, unit prices, line totals, and the invoice total under our defined business rules.

Because this invoice matches and has no issues, the system saves its data and relationships with the status ready_for_review.

A human has not approved it yet. Approval will be a separate saved review action, and it will not trigger payment.

1. An invoice should be saved even if it has no matched PO because the invoice still exists. If it is deleted a review cannot investigate or correct it. It could be due to an incorrect PO reference on the invoice. An extraction mistake, or a PO that has not yet been added to the prototype'ds database.

2. The supplier name should be retained after matching a vendor because if you only keep the matched vendor id you lose the original name. It makes it harder to investigate.

3. Review events need to be seperateed from current status because review_events preserves past actions while invoice record preserrves the latest state.