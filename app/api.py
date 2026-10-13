import hashlib
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, engine
from app.invoice_processing import process_invoice
from app.models import InvoiceProcessingResult, InvoiceSource

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


app = FastAPI(
    title="InvoiceFlow API",
    description="Local development API for JSON invoice ingestion.",
)


def get_session():
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _require_nonempty_string(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")

    stripped = value.strip()

    if stripped == "":
        raise ValueError("must be a nonempty string")

    return stripped


class InvoiceLineRequest(BaseModel):
    item_code: str
    description: str
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)
    stated_line_total_cents: int = Field(ge=0)

    @field_validator("item_code", "description")
    @classmethod
    def validate_nonempty_strings(cls, value: str) -> str:
        return _require_nonempty_string(value)


class InvoiceRequest(BaseModel):
    invoice_number: str
    vendor_name: str
    po_reference: str
    currency: str
    stated_total_cents: int = Field(ge=0)
    line_items: list[InvoiceLineRequest] = Field(min_length=1)

    @field_validator("invoice_number", "vendor_name", "po_reference")
    @classmethod
    def validate_nonempty_strings(cls, value: str) -> str:
        return _require_nonempty_string(value)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        stripped = _require_nonempty_string(value)
        is_three_uppercase_letters = (
            len(stripped) == 3
            and stripped.isascii()
            and stripped.isalpha()
            and stripped.isupper()
        )

        if not is_three_uppercase_letters:
            raise ValueError(
                "currency must be exactly three uppercase "
                "alphabetic characters"
            )

        return stripped


def _canonical_content_hash(invoice_data: dict) -> str:
    canonical = json.dumps(
        invoice_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _error_response(status_code: int, detail: str, code: str, **extra):
    content = {"detail": detail, "code": code}
    content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "code": "INVALID_REQUEST",
        },
    )


@app.post("/invoices")
def submit_invoice(invoice: InvoiceRequest, session: SessionDep):
    invoice_data = invoice.model_dump()
    content_hash = _canonical_content_hash(invoice_data)

    existing_source = session.scalar(
        select(InvoiceSource).where(
            InvoiceSource.content_hash == content_hash
        )
    )

    if existing_source is not None:
        return _error_response(
            409,
            "Invoice content has already been ingested.",
            "DUPLICATE_INVOICE",
            ingestion_id=existing_source.id,
            processing_result_id=existing_source.processing_result_id,
            status="duplicate",
            processing_result=None,
        )

    processing_result = process_invoice(session, invoice_data)

    source = InvoiceSource(
        source_type="json_api",
        source_reference=invoice.invoice_number,
        content_hash=content_hash,
        invoice_number=processing_result.get("invoice_number"),
        status="ingested",
        processing_result_id=processing_result.get("id"),
    )
    session.add(source)
    session.commit()

    return {
        "ingestion_id": source.id,
        "processing_result_id": processing_result.get("id"),
        "status": source.status,
        "processing_result": processing_result,
    }


@app.get("/processing-results/{processing_result_id}")
def get_processing_result(processing_result_id: int, session: SessionDep):
    record = session.get(InvoiceProcessingResult, processing_result_id)

    if record is None:
        return _error_response(
            404,
            "Processing result not found.",
            "NOT_FOUND",
        )

    return {
        "id": record.id,
        "invoice_number": record.invoice_number,
        "vendor_id": record.vendor_id,
        "purchase_order_id": record.purchase_order_id,
        "status": record.status,
        "issues": record.issues,
        "created_at": record.created_at.isoformat(),
    }


@app.get("/invoices/sources/{ingestion_id}")
def get_invoice_source(ingestion_id: int, session: SessionDep):
    record = session.get(InvoiceSource, ingestion_id)

    if record is None:
        return _error_response(
            404,
            "Invoice source not found.",
            "NOT_FOUND",
        )

    return {
        "id": record.id,
        "source_type": record.source_type,
        "source_reference": record.source_reference,
        "content_hash": record.content_hash,
        "invoice_number": record.invoice_number,
        "status": record.status,
        "processing_result_id": record.processing_result_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@app.get("/")
def serve_ui():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
