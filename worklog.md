Built:
- Vendor matching by exact normalized canonical name or explicit alias, with unmatched and ambiguous outcomes.
- Purchase-order matching by PO number, including ownership verification against the matched vendor.
- Invoice processing service (`process_invoice`) that validates headers, matches vendor and PO, checks currency, and reconciles the invoice.
- JSON file ingestion and a local FastAPI JSON API, both persisting `InvoiceSource` plus `InvoiceProcessingResult`.
- Local single-page UI for JSON invoice submission, PDF upload, result inspection, and processing-result lookup.
- PDF ingestion for text-based PDFs: extract text with PyMuPDF, draft-extract fields with an LLM using OPENAI_API_KEY from `.env`, then run the existing validation/matching/reconciliation pipeline.

Tests:
- Isolated in-memory SQLite tests covering matching, validation, reconciliation, JSON ingestion, the JSON API, the UI shell, and PDF ingestion. PDF tests use a fake extractor and do not call OpenAI.

Unfinished:
- Scanned or image-only PDFs are not supported; they need OCR or another extraction approach.
- LLM extraction is draft extraction only and still depends on validation, matching, and reconciliation.
- No authentication, review workflow, or production deployment path.
