import os
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_PDF_EXTRACTION_MODEL = "gpt-4o-mini"

EXTRACTION_SYSTEM_PROMPT = """
Extract invoice fields that are explicitly present in the document.
Do not invent vendors, line items, quantities, or monetary amounts.
Return every monetary amount as an integer number of cents.
For example, 12.00 USD must be returned as 1200.
If a purchase-order reference is not present in the document, set po_reference to UNAVAILABLE.
If a line item has no printed item code, set item_code to a short uppercase token
derived only from that line's description (letters and digits, maximum 16 characters).
Do not add line items that are not in the document.
""".strip()


def _require_nonempty_string(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")

    stripped = value.strip()

    if stripped == "":
        raise ValueError("must be a nonempty string")

    return stripped


class ExtractedInvoiceLine(BaseModel):
    item_code: str
    description: str
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)
    stated_line_total_cents: int = Field(ge=0)

    @field_validator("item_code", "description")
    @classmethod
    def validate_nonempty_strings(cls, value: str) -> str:
        return _require_nonempty_string(value)


class ExtractedInvoice(BaseModel):
    invoice_number: str
    vendor_name: str
    po_reference: str
    currency: str
    stated_total_cents: int = Field(ge=0)
    line_items: list[ExtractedInvoiceLine] = Field(min_length=1)

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


def _extraction_issues(message: str, field: str | None = None) -> list[dict]:
    issue = {
        "code": "EXTRACTION_FAILED",
        "message": message,
    }
    if field is not None:
        issue["field"] = field
    return [issue]


def _pdf_extraction_model() -> str:
    return os.environ.get("PDF_EXTRACTION_MODEL") or DEFAULT_PDF_EXTRACTION_MODEL


def extract_pdf_text(file_bytes: bytes) -> tuple[str | None, str | None]:
    document = None

    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception:
        return None, "The PDF could not be read."

    try:
        if document.is_encrypted:
            authenticated = False
            try:
                authenticated = bool(document.authenticate(""))
            except Exception:
                authenticated = False

            if not authenticated:
                return None, "The PDF is encrypted and cannot be opened."

        page_text = []
        for page in document:
            page_text.append(page.get_text() or "")

        combined_text = "\n".join(page_text)

        if combined_text.strip() == "":
            return (
                None,
                "The PDF appears to be scanned or image-only and has no "
                "extractable text.",
            )

        return combined_text, None
    except Exception:
        return None, "The PDF could not be read."
    finally:
        if document is not None:
            document.close()


def extract_invoice_from_text(
    raw_text: str,
    client: OpenAI | None = None,
) -> tuple[dict | None, list[dict] | None]:
    if not isinstance(raw_text, str) or raw_text.strip() == "":
        return None, _extraction_issues(
            "No invoice text was provided for extraction."
        )

    try:
        if client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return None, _extraction_issues("OPENAI_API_KEY is not set.")
            client = OpenAI(api_key=api_key)

        completion = client.chat.completions.parse(
            model=_pdf_extraction_model(),
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format=ExtractedInvoice,
        )
        message = completion.choices[0].message

        if getattr(message, "refusal", None):
            return None, _extraction_issues(
                "The model did not extract an invoice from the PDF text."
            )

        parsed = getattr(message, "parsed", None)
        if parsed is None:
            return None, _extraction_issues(
                "The model returned an empty extraction result."
            )

        if isinstance(parsed, ExtractedInvoice):
            return parsed.model_dump(), None

        extracted = ExtractedInvoice.model_validate(parsed)
        return extracted.model_dump(), None
    except ValidationError as exc:
        issues = []
        for error in exc.errors():
            field = ".".join(str(part) for part in error.get("loc", ()))
            issues.append(
                {
                    "code": "EXTRACTION_FAILED",
                    "field": field or None,
                    "message": error.get(
                        "msg",
                        "The extracted invoice failed validation.",
                    ),
                }
            )
        if issues:
            return None, issues
        return None, _extraction_issues(
            "The extracted invoice failed validation."
        )
    except Exception:
        return None, _extraction_issues(
            "The invoice could not be extracted from the PDF text."
        )
