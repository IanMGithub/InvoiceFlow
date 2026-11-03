# InvoiceFlow demo

InvoiceFlow checks a supplier invoice against a purchase order. This public demo runs those checks on three synthetic invoices: one that matches, one quantity mismatch, and one unit-price mismatch. A click shows the result computed when the process started. It does not submit a new invoice, upload a file, or call a model.

The local prototype, including PDF draft extraction, stays in this repository. Vercel does not run it. The deployed application is `app.demo_api:app`.

## Run the demo locally

Use Python 3.11 or 3.12 from the repository root:

```bash
python3.12 -m venv .venv-demo
.venv-demo/bin/pip install -r requirements-demo.lock
PYTHONPATH=. .venv-demo/bin/uvicorn app.demo_api:app --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000/ . No API key is required. This command does not read `.env` and does not use `invoiceflow.db`.

`requirements.txt` is only for the local prototype. Do not install it for the demo.

## Deploy on Vercel

Import the Git repository with these settings:

| Setting | Value |
| --- | --- |
| Branch | `release/public-demo` |
| Root Directory | repository root (`.`) |
| Framework Preset | FastAPI |
| Python | 3.12, from `.python-version` and `requires-python` |
| Install | default, using `pyproject.toml` |
| Build Command | empty |
| Output Directory | empty |

Leave the install command empty so Vercel does not run `pip install -r requirements.txt`. The demo dependencies are `fastapi==0.143.0` and `sqlalchemy==2.0.54` in `pyproject.toml`. `[tool.vercel]` sets the entrypoint to `app.demo_api:app`.

Do not set a Docker build, a start command, or an Uvicorn command. Vercel’s native FastAPI runtime loads that entrypoint. `.vercelignore` keeps `.env`, developer databases, `test_files/`, `requirements.txt`, and the PDF modules out of the upload. The three sample invoices, `fixtures/vendors.json`, `fixtures/purchase_orders.json`, and `static/demo/` are included.

The demo keeps its SQLite database in memory, so startup does not write to the read-only function filesystem.

## Limitations

The invoices, vendors, and purchase orders are synthetic. Visitors cannot submit their own invoice fields or upload PDFs. The deployment does not call OpenAI. A status of matched means the vendor and purchase order were found and the checks ran. It does not mean the invoice is approved or safe to pay.

## Architecture and tests

At startup the demo loads the fixture vendors and purchase orders, then runs `fixtures/invoices/valid_invoice.json`, `quantity_mismatch.json`, and `price_mismatch.json` through the existing validation, matching, and reconciliation code. The page asks for one of those sample ids and renders the stored result.

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_demo.py -p no:cacheprovider
```

## Rate limit

The demo allows 30 sample requests per minute in process memory. On Vercel that limit applies separately to each running instance. It is not a global quota for the site.
