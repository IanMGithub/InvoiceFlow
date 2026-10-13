from fastapi.testclient import TestClient

from app.api import app


def test_root_serves_html_interface():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text
    assert 'id="invoice-form"' in response.text


def test_static_assets_are_served():
    with TestClient(app) as client:
        css_response = client.get("/static/styles.css")
        js_response = client.get("/static/app.js")

    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert js_response.status_code == 200
    assert js_response.text.strip() != ""


def test_root_page_contains_invoice_form_fields():
    with TestClient(app) as client:
        html = client.get("/").text

    for label in [
        "Invoice number",
        "Vendor name",
        "PO reference",
        "Currency",
        "Stated total in cents",
        "Item code",
        "Description",
        "Quantity",
        "Unit price in cents",
        "Stated line total in cents",
        "Add line item",
        "Submit invoice",
        "Load sample invoice",
    ]:
        assert label in html


def test_root_page_contains_result_and_lookup_sections():
    with TestClient(app) as client:
        html = client.get("/").text

    assert 'id="result-panel"' in html
    assert 'id="lookup-panel"' in html
    assert "Reconciliation issues" in html
    assert "Full JSON response" in html
    assert "Processing result ID" in html
    assert "Look up processing result" in html
