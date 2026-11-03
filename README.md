# InvoiceFlow

An invoice-to-purchase-order reconciliation prototype built with Python, FastAPI, and SQLAlchemy.

InvoiceFlow checks whether a supplier invoice agrees with its purchase order and returns structured discrepancies for review. It separates input validation, vendor identification, purchase-order ownership checks, and financial reconciliation into independently testable components.

The public demo uses three synthetic invoices to demonstrate the workflow without accepting private documents or making paid AI requests.

## Try the demo

The demo includes three scenarios:

| Scenario | What it demonstrates |
|---|---|
| Matching invoice | Vendor and purchase order match, with no issues found by the implemented checks |
| Quantity mismatch | An invoice quantity differs from the purchase order; the resulting total difference is also reported |
| Unit-price mismatch | An invoice unit price differs from the purchase order; the resulting total difference is also reported |

Each result is computed when the application instance starts. Clicking a sample retrieves that result—it does not submit a new invoice.

> This is a portfolio demonstration, not an accounting or payment-approval system. A `matched` status does not mean an invoice is approved or safe to pay.

## The problem

Invoice review involves more than comparing two totals. An invoice may reference the wrong vendor, contain an incorrect purchase-order reference, charge a different unit price, or include inconsistent line arithmetic.

InvoiceFlow breaks that review into explicit steps:

1. Validate the invoice’s structure and required values.
2. Identify the vendor using normalized names and explicit aliases.
3. Find the purchase order and verify that it belongs to the matched vendor.
4. Compare invoice lines and totals against the purchase order.
5. Return structured results describing any discrepancies.

The goal is to make the decision path understandable and testable rather than hide it inside a single automation script.

## What it checks

### Input validation

- Required invoice fields.
- Field types and allowed values.
- Required line-item fields.
- Positive quantities and nonnegative monetary values.
- Duplicate invoice item codes.
- Line-total arithmetic.

### Matching

- Vendor canonical names and explicit aliases.
- Case and surrounding-whitespace normalization for supplier names.
- Unmatched and ambiguous vendor outcomes.
- Purchase-order lookup by reference.
- Purchase-order ownership verification.

### Reconciliation

- Invoice items with no matching purchase-order line.
- Ambiguous purchase-order line matches.
- Quantity differences.
- Unit-price differences.
- Purchase-order items missing from the invoice.
- Invoice line-total inconsistencies.
- Invoice total inconsistencies.
- Invoice-to-purchase-order total differences.

Monetary values are represented as integer cents throughout the processing workflow.

## Architecture

```text
Public demo
    │
    ▼
Allowlisted synthetic sample
    │
    ▼
Input validation
    │
    ▼
Vendor matching
    │
    ▼
Purchase-order lookup and ownership check
    │
    ▼
Reconciliation
    │
    ▼
Structured result
    │
    ▼
Browser display
```

At startup, the demo:

1. Creates an in-memory SQLite database.
2. Seeds synthetic vendors and purchase orders from project fixtures.
3. Processes the three sample invoices.
4. Stores their results for subsequent sample requests.

The database is disposable and recreated for each application instance. Repeated clicks do not create additional processing records.

### Key components

| Component | Responsibility |
|---|---|
| `app/demo_api.py` | Public sample-only API and application initialization |
| `app/demo_limits.py` | Instance-local request limiting |
| `app/validation.py` | Invoice input validation |
| `app/matching.py` | Vendor and purchase-order matching |
| `app/reconciliation.py` | Line-item and total comparisons |
| `app/invoice_processing.py` | Workflow orchestration and structured processing results |
| `app/reference_data.py` | Shared fixture-seeding logic |
| `static/demo/` | Public demo interface |

## Engineering decisions

### Deterministic business rules

Vendor matching and financial checks use explicit rules rather than asking an AI model to decide whether an invoice is acceptable.

Ambiguous matches and discrepancies are reported instead of silently resolved.

### Separation of concerns

Validation, matching, reconciliation, persistence, and presentation have separate responsibilities. The interface displays results; it does not implement financial rules.

### Structured outcomes

Failures are part of the workflow, not just exceptions. Results distinguish invalid invoices, unmatched vendors, ambiguous vendors, incorrect purchase-order ownership, currency mismatches, and completed reconciliation.

A processing status and a discrepancy list answer different questions: processing can complete successfully while still finding financial issues.

### Restricted public deployment

The public application is intentionally smaller than the local prototype. It accepts only allowlisted sample identifiers and does not expose arbitrary invoice submission, PDF upload, or record lookup by database ID.

### Testable external-service boundaries

The local prototype’s PDF-extraction tests use fake extractors rather than live OpenAI requests. Those tests verify integration behavior without requiring API credentials or incurring model costs; they do not establish real-world extraction accuracy.

## Public demo vs. local prototype

The repository’s development work includes a broader local prototype with JSON ingestion, duplicate detection, processing-result persistence, and text-based PDF draft extraction.

Those capabilities are not enabled on the public website.

| Capability | Public demo | Local prototype |
|---|---|---|
| Synthetic reconciliation examples | Yes | Yes |
| Validation, matching, and reconciliation | Yes | Yes |
| Arbitrary JSON invoice submission | No | Implemented locally |
| Text-based PDF draft extraction | No | Implemented locally |
| OpenAI requests | No | Used for PDF draft extraction |
| Lookup of arbitrary saved results | No | Available in the local API |
| Persistent customer-data storage | No | Not a production customer-data service |

The deployed entry point is:

```text
app.demo_api:app
```

The local prototype entry point is separate:

```text
app.api:app
```

The local prototype is unauthenticated and must not be exposed publicly as-is.

## Technology

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- Plain HTML, CSS, and JavaScript
- pytest

The local PDF prototype additionally uses PyMuPDF and the OpenAI API. Neither is required by the public demo runtime.

## Run the demo locally

Use Python 3.12 from the repository root:

```bash
python3.12 -m venv .venv-demo
.venv-demo/bin/pip install -r requirements-demo.lock

PYTHONPATH=. .venv-demo/bin/uvicorn app.demo_api:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1
```

Open:

```text
http://127.0.0.1:8000/
```

Check initialization:

```bash
curl http://127.0.0.1:8000/health
```

No API key is required. The demo does not load `.env` or use the developer’s `invoiceflow.db`.

`requirements.txt` is for the broader local prototype, not the demo installation.

## Tests

With the project’s test dependencies installed:

```bash
PYTHONPATH=. python -m pytest tests/test_demo.py -p no:cacheprovider -v
```

The demo tests cover:

- Homepage and static assets.
- Expected results for all three sample scenarios.
- Rejection of unsupported samples and unexpected request fields.
- Unavailability of the original upload, lookup, and documentation routes.
- Startup without an OpenAI API key.
- Isolation from PDF and OpenAI modules.
- Rate-limit responses.
- Oversized request rejection.
- Bounded database record counts.
- Security headers.
- Health and initialization behavior.

Run the broader suite in the full local-prototype environment:

```bash
PYTHONPATH=. python -m pytest tests/ -p no:cacheprovider -v
```

The broader suite requires the local prototype’s dependencies. Passing mocked PDF tests is not equivalent to verifying live extraction against real documents.

## Deploy on Vercel

The project uses Vercel’s native FastAPI runtime.

| Setting | Value |
|---|---|
| Root directory | Repository root |
| Framework preset | FastAPI |
| Python version | 3.12 |
| Install command | Default |
| Build command | Default |
| Output directory | Default |

Deploy a branch containing the public-demo configuration. The initial release branch is `release/public-demo`.

`pyproject.toml` explicitly selects the application:

```toml
[tool.vercel]
entrypoint = "app.demo_api:app"
```

Do not configure a Docker build, Uvicorn start command, or OpenAI API key for the native Vercel deployment.

The Vercel upload configuration excludes the local prototype’s dependency file, PDF modules, private test files, environment files, and developer databases.

After deployment, verify:

- `/` loads the demo.
- `/health` reports successful initialization.
- All three scenarios return the expected results.
- `/docs` and `/processing-results/1` are unavailable.
- No arbitrary invoice form or PDF upload is exposed.

## Safety and limitations

### Synthetic data only

The public demo does not accept real invoices, private documents, or user-provided invoice fields. It makes no live AI requests.

### Not payment authorization

`matched` means the vendor and purchase order were found and processing completed. It does not mean the invoice is approved, financially correct in every respect, or safe to pay.

A clean result means:

> No issues found by the implemented checks.

It is not a guarantee that every possible invoice problem has been detected.

### Instance-local rate limiting

The demo allows 30 sample requests per minute per client address, using process memory.

On Vercel, counters are separate for each running instance and reset with the instance lifecycle. This is not a global site quota, distributed rate limiter, or DDoS protection. Client-address behavior also depends on deployment proxy configuration.

### Privacy

Only curated synthetic invoice data is processed by the public application. Hosting infrastructure may process request metadata, including IP addresses and access logs.

The absence of document uploads does not imply anonymous browsing or zero infrastructure retention.

### Intentional scope

This project does not implement a production customer invoicing service, human approval workflow, payment execution, scanned-document OCR, or multi-tenant access controls.

## Project status

The public release is a sample-only portfolio demo designed to demonstrate the workflow and engineering decisions.

The broader local prototype is a development implementation, not a service ready to accept live customer invoices.

## Dependency notices

See `THIRD_PARTY_NOTICES.md` for notices covering the public demo’s dependencies.

The separate local PDF implementation has additional dependencies and licensing considerations. Excluding those dependencies from the public demo does not determine the licensing obligations for distributing the broader prototype.

No open-source license for the original project code is granted by this README.
