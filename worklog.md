Built:
- Deterministic reconciliation with eleven passing tests.
- Persistent vendors, purchase orders, and PO lines in SQLite.
- Seed and verification scripts.

Learned:
- Fixture data differs from saved database records.
- Foreign keys reference database primary-key IDs.
- Flush obtains IDs without committing the transaction.
- Matching reference data is separate from checking an invoice.

Problems solved:
- Import/file-placement errors.
- Incorrect fixture item code.
- Missing quantities in test inputs.
- Misspelled foreign-key table reference.

Unfinished:
- Incoming invoices are not stored yet.
- No invoice-processing API, AI extraction, or review workflow yet.

Next task:
- Match an invoice fixture to saved vendor/PO records and reconcile it.