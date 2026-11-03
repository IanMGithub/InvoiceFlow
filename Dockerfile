FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements-demo.lock requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.lock

COPY app/__init__.py \
    app/db.py \
    app/models.py \
    app/matching.py \
    app/validation.py \
    app/reconciliation.py \
    app/invoice_processing.py \
    app/reference_data.py \
    app/demo_limits.py \
    app/demo_api.py \
    app/
COPY fixtures/vendors.json fixtures/purchase_orders.json fixtures/
COPY fixtures/invoices/valid_invoice.json \
    fixtures/invoices/quantity_mismatch.json \
    fixtures/invoices/price_mismatch.json \
    fixtures/invoices/
COPY static/demo/index.html static/demo/styles.css static/demo/app.js static/demo/
COPY THIRD_PARTY_NOTICES.md ./

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]

CMD ["uvicorn", "app.demo_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
