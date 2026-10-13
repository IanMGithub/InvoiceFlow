InvoiceFlow is a local learning prototype that extracts synthetic invoice data, checks it against purchase orders, persists processing results, and supports human review through an API. It does not authorize or execute payments.

## Running locally

From the project root:

```bash
PYTHONPATH=. python scripts/check_invoice_matching.py
PYTHONPATH=. python -m pytest tests/ -v
```

## Local development API

This is a local development API. It is not authenticated and is not intended for production use.

Install dependencies and start the server from the project root:

```bash
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/uvicorn app.api:app --reload
```

Open the local web interface at http://127.0.0.1:8000/ . It is a simple development page for submitting invoices and inspecting processing results. It is not production-ready.

Use **Load sample invoice** to fill the form with the data from `fixtures/invoices/valid_invoice.json`, then submit it through the UI.

Submit an invoice:

```bash
curl -sS -X POST http://127.0.0.1:8000/invoices \
  -H "Content-Type: application/json" \
  -d @fixtures/invoices/valid_invoice.json
```

Retrieve a processing result (replace `1` with the returned `processing_result_id`):

```bash
curl -sS http://127.0.0.1:8000/processing-results/1
```
