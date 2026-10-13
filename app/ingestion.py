import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.invoice_processing import process_invoice
from app.models import InvoiceSource


def _ingestion_result(
    *,
    ingestion_id,
    source_reference,
    content_hash,
    status,
    processing_result_id=None,
    processing_result=None,
    error=None,
):
    result = {
        "ingestion_id": ingestion_id,
        "source_type": "json_file",
        "source_reference": source_reference,
        "content_hash": content_hash,
        "status": status,
        "processing_result_id": processing_result_id,
        "processing_result": processing_result,
    }

    if error is not None:
        result["error"] = error

    return result


def ingest_invoice_file(session: Session, file_path: Path) -> dict:
    source_reference = file_path.name

    if not file_path.exists() or not file_path.is_file():
        return _ingestion_result(
            ingestion_id=None,
            source_reference=source_reference,
            content_hash=None,
            status="missing_file",
            error=(
                "Invoice file does not exist or is not a regular file: "
                f"{file_path}"
            ),
        )

    raw_bytes = file_path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    existing_source = session.scalar(
        select(InvoiceSource).where(
            InvoiceSource.content_hash == content_hash
        )
    )

    if existing_source is not None:
        return _ingestion_result(
            ingestion_id=existing_source.id,
            source_reference=existing_source.source_reference,
            content_hash=existing_source.content_hash,
            status="duplicate",
            processing_result_id=existing_source.processing_result_id,
            processing_result=None,
        )

    try:
        text = raw_bytes.decode("utf-8")
        parsed_invoice = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _ingestion_result(
            ingestion_id=None,
            source_reference=source_reference,
            content_hash=content_hash,
            status="invalid_json",
        )

    if not isinstance(parsed_invoice, dict):
        return _ingestion_result(
            ingestion_id=None,
            source_reference=source_reference,
            content_hash=content_hash,
            status="invalid_payload",
        )

    processing_result = process_invoice(session, parsed_invoice)

    source = InvoiceSource(
        source_type="json_file",
        source_reference=source_reference,
        content_hash=content_hash,
        invoice_number=processing_result.get("invoice_number"),
        status="ingested",
        processing_result_id=processing_result.get("id"),
    )
    session.add(source)
    session.commit()

    return _ingestion_result(
        ingestion_id=source.id,
        source_reference=source_reference,
        content_hash=content_hash,
        status="ingested",
        processing_result_id=processing_result.get("id"),
        processing_result=processing_result,
    )
