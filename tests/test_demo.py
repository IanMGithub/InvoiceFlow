import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.demo_api import create_app, read_bounded_body
from app.demo_limits import SlidingWindowLimiter, client_address
from app.models import InvoiceProcessingResult, InvoiceSource

PROJECT_DIR = Path(__file__).resolve().parent.parent


def _client(**kwargs):
    app = create_app(
        source_url=None,
        walkthrough_url=None,
        contact_url=None,
        **kwargs,
    )
    return app, TestClient(app)


def _count(engine, model) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model))


def test_homepage_and_assets_load():
    _app, client = _client()
    with client:
        page = client.get("/")
        css = client.get("/static/styles.css")
        script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "InvoiceFlow" in page.text
    assert "Try a sample" in page.text
    assert "Clean invoice" in page.text
    assert "Quantity mismatch" in page.text
    assert "Unit price mismatch" in page.text
    assert "No issues found by the implemented checks." in page.text
    assert "synthetic" in page.text.lower()
    assert "disabled on this public website" in page.text
    assert "safe to pay" in page.text
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert script.status_code == 200
    script_text = (PROJECT_DIR / "static" / "demo" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "innerHTML" not in script_text
    assert "insertAdjacentHTML" not in script_text
    assert "document.write" not in script_text


def test_allowlisted_examples_return_expected_issues():
    app, client = _client()
    with client:
        valid = client.post("/api/examples", json={"sample_id": "valid"})
        quantity = client.post(
            "/api/examples",
            json={"sample_id": "quantity-mismatch"},
        )
        price = client.post(
            "/api/examples",
            json={"sample_id": "price-mismatch"},
        )

    assert valid.status_code == 200
    valid_body = valid.json()
    assert valid_body["computed_at_startup"] is True
    assert valid_body["processing_result"]["invoice_number"] == "INV-1001"
    assert valid_body["processing_result"]["status"] == "matched"
    assert valid_body["processing_result"]["issues"] == []

    assert quantity.status_code == 200
    assert quantity.json()["processing_result"]["status"] == "matched"
    assert quantity.json()["processing_result"]["issues"] == [
        {
            "code": "QUANTITY_MISMATCH",
            "item_code": "TONER-BK",
            "expected_quantity": 6,
            "observed_quantity": 5,
            "difference_quantity": -1,
        },
        {
            "code": "PO_TOTAL_MISMATCH",
            "expected_cents": 210000,
            "observed_cents": 195000,
            "difference_cents": -15000,
        },
    ]

    assert price.status_code == 200
    assert price.json()["processing_result"]["status"] == "matched"
    assert price.json()["processing_result"]["issues"] == [
        {
            "code": "UNIT_PRICE_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_cents": 12000,
            "observed_cents": 15000,
            "difference_cents": 3000,
        },
        {
            "code": "PO_TOTAL_MISMATCH",
            "expected_cents": 210000,
            "observed_cents": 240000,
            "difference_cents": 30000,
        },
    ]
    assert _count(app.state.engine, InvoiceProcessingResult) == 3
    assert _count(app.state.engine, InvoiceSource) == 0


def test_unknown_sample_and_bad_payloads_are_rejected():
    _app, client = _client()
    with client:
        unknown = client.post("/api/examples", json={"sample_id": "other"})
        missing = client.post("/api/examples", json={})
        extra = client.post(
            "/api/examples",
            json={"sample_id": "valid", "invoice_number": "INV-9"},
        )
        arbitrary = client.post(
            "/api/examples",
            json={
                "invoice_number": "INV-9",
                "vendor_name": "Other Vendor",
                "po_reference": "PO-9",
                "currency": "USD",
                "stated_total_cents": 100,
                "line_items": [],
            },
        )

    assert unknown.status_code == 422
    assert unknown.json()["code"] == "UNKNOWN_SAMPLE"
    assert extra.status_code == 422
    assert extra.json()["code"] == "UNEXPECTED_FIELD"
    assert arbitrary.status_code == 422
    assert arbitrary.json()["code"] == "UNEXPECTED_FIELD"
    assert missing.status_code == 422
    assert missing.json()["code"] == "INVALID_REQUEST"
    assert "INV-9" not in unknown.text
    assert "INV-9" not in extra.text
    assert "Other Vendor" not in arbitrary.text


def test_original_api_routes_are_absent():
    _app, client = _client()
    paths = [
        "/invoices",
        "/invoices/pdf",
        "/processing-results/1",
        "/invoices/sources/1",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]
    with client:
        statuses = {path: client.get(path).status_code for path in paths}
        post_status = client.post("/invoices", json={"sample_id": "valid"}).status_code
        pdf_status = client.post(
            "/invoices/pdf",
            files={"file": ("invoice.pdf", b"%PDF", "application/pdf")},
        ).status_code

    assert statuses == {path: 404 for path in paths}
    assert post_status == 404
    assert pdf_status == 404


def test_repeated_clicks_do_not_insert_rows():
    app, client = _client()
    with client:
        before_results = _count(app.state.engine, InvoiceProcessingResult)
        before_sources = _count(app.state.engine, InvoiceSource)
        for _ in range(6):
            response = client.post("/api/examples", json={"sample_id": "valid"})
            assert response.status_code == 200
        after_results = _count(app.state.engine, InvoiceProcessingResult)
        after_sources = _count(app.state.engine, InvoiceSource)

    assert before_results == after_results == 3
    assert before_sources == after_sources == 0


def test_rate_limit_and_forwarded_header():
    _app, client = _client(rate_limit_per_minute=2, window_seconds=60)
    with client:
        first = client.post("/api/examples", json={"sample_id": "valid"})
        second = client.post("/api/examples", json={"sample_id": "valid"})
        third = client.post(
            "/api/examples",
            json={"sample_id": "valid"},
            headers={"x-forwarded-for": "198.51.100.20"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["code"] == "RATE_LIMITED"
    assert third.headers["retry-after"].isdigit()
    assert int(third.headers["retry-after"]) >= 1


def test_oversized_body_is_rejected_without_keeping_it():
    _app, client = _client(max_body_bytes=256)
    with client:
        response = client.post(
            "/api/examples",
            content=b'{"sample_id":"valid","padding":"' + (b"x" * 400) + b'"}',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"
    assert "x" * 40 not in response.text

    async def receive_huge():
        return {
            "type": "http.request",
            "body": b"y" * 100000,
            "more_body": False,
        }

    body, too_large = asyncio.run(read_bounded_body(receive_huge, 256))
    assert too_large is True
    assert body == b""


def test_security_headers_and_no_wildcard_cors():
    _app, client = _client()
    with client:
        response = client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    policy = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in policy
    assert "script-src 'self'" in policy
    assert "unsafe-inline" not in policy
    assert "*" not in policy
    assert "access-control-allow-origin" not in response.headers


def test_health_reflects_initialization():
    _app, client = _client()
    with client:
        ready = client.get("/health")

    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "demo_initialized": True}

    failed_app, failed_client = _client(project_dir=PROJECT_DIR / "missing-demo-fixtures")
    with failed_client:
        failed = failed_client.get("/health")
        action = failed_client.post("/api/examples", json={"sample_id": "valid"})

    assert failed.status_code == 503
    assert failed.json()["demo_initialized"] is False
    assert "missing-demo-fixtures" not in failed.text
    assert action.status_code == 503
    assert action.json()["code"] == "UNAVAILABLE"
    assert "missing-demo-fixtures" not in action.text


def test_configured_links_reject_unsafe_urls():
    app = create_app(
        source_url="https://example.com/invoiceflow",
        walkthrough_url="javascript:alert(1)",
        contact_url="http://127.0.0.1:8000/contact",
    )
    with TestClient(app) as client:
        response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "source_url": "https://example.com/invoiceflow",
        "walkthrough_url": None,
        "contact_url": "http://127.0.0.1:8000/contact",
    }


def test_limiter_bounds_memory_and_expires_keys():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, max_keys=2)
    assert limiter.check("a", now=0)[0] is True
    assert limiter.check("b", now=0)[0] is True
    assert limiter.check("c", now=0)[0] is True
    assert len(limiter._hits) <= 2
    assert limiter.check("a", now=10)[0] is True
    blocked, retry_after = limiter.check("a", now=10)
    assert blocked is False
    assert retry_after >= 1
    assert limiter.check("a", now=80)[0] is True


def test_client_address_ignores_forwarded_headers():
    scope = {
        "client": ("203.0.113.5", 4000),
        "headers": [(b"x-forwarded-for", b"198.51.100.8")],
    }
    assert client_address(scope) == "203.0.113.5"
    assert client_address({"client": None}) == "unknown"


def test_demo_requirements_exclude_pdf_and_openai():
    text = (PROJECT_DIR / "requirements-demo.txt").read_text(encoding="utf-8").lower()
    assert "pymupdf" not in text
    assert "openai" not in text
    assert "fastapi==" in text
    assert "sqlalchemy==" in text


def test_demo_import_does_not_load_openai_pdf_or_dotenv_key():
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("PDF_EXTRACTION_MODEL", None)
    env["PYTHONPATH"] = str(PROJECT_DIR)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = r"""
import os
import sys

if os.environ.get("OPENAI_API_KEY"):
    sys.stderr.write("key present before import\n")
    raise SystemExit(2)

import app.demo_api
from fastapi.testclient import TestClient

if os.environ.get("OPENAI_API_KEY"):
    sys.stderr.write("key present after import\n")
    raise SystemExit(3)

for name in ("openai", "pymupdf", "fitz", "app.pdf_extraction", "app.ingestion", "app.api"):
    if name in sys.modules:
        sys.stderr.write("loaded " + name + "\n")
        raise SystemExit(4)

with TestClient(app.demo_api.app) as client:
    response = client.get("/health")
    if response.status_code != 200:
        sys.stderr.write("health failed\n")
        raise SystemExit(5)
    if response.json().get("demo_initialized") is not True:
        sys.stderr.write("demo not initialized\n")
        raise SystemExit(6)
print("ok")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_validation_response_does_not_echo_raw_json_error():
    _app, client = _client()
    with client:
        response = client.post(
            "/api/examples",
            content=b"{",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_REQUEST"
    assert "loc" not in body
    assert json.dumps(body).count("{") == 1
