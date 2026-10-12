InvoiceFlow is a local learning prototype that extracts synthetic invoice data, checks it against purchase orders, persists processing results, and supports human review through an API. It does not authorize or execute payments.

## Running locally

From the project root:

```bash
PYTHONPATH=. python scripts/check_invoice_matching.py
PYTHONPATH=. python -m pytest tests/ -v
```
