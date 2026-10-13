from copy import deepcopy

from app.validation import validate_invoice


def _valid_invoice():
    return {
        "invoice_number": "INV-VAL-001",
        "vendor_name": "Cedar Ridge Office Supply",
        "po_reference": "PO-VAL-001",
        "currency": "USD",
        "stated_total_cents": 120000,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "description": "A4 paper cases",
                "quantity": 10,
                "unit_price_cents": 12000,
                "stated_line_total_cents": 120000,
            }
        ],
    }


def test_valid_invoice_returns_no_validation_issues():
    issues = validate_invoice(_valid_invoice())

    assert issues == []


def test_missing_invoice_number_returns_missing_field():
    invoice = _valid_invoice()
    invoice["invoice_number"] = None

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "MISSING_FIELD",
            "field": "invoice_number",
            "message": "invoice_number is required.",
        }
    ]


def test_blank_vendor_name_returns_invalid_value():
    invoice = _valid_invoice()
    invoice["vendor_name"] = "   "

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "INVALID_VALUE",
            "field": "vendor_name",
            "message": "vendor_name must be a nonempty string.",
        }
    ]


def test_invalid_currency_returns_invalid_value():
    invoice = _valid_invoice()
    invoice["currency"] = "usd"

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "INVALID_VALUE",
            "field": "currency",
            "message": (
                "currency must be exactly three uppercase "
                "alphabetic characters."
            ),
        }
    ]


def test_negative_stated_total_cents_returns_invalid_value():
    invoice = _valid_invoice()
    invoice["stated_total_cents"] = -1

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "INVALID_VALUE",
            "field": "stated_total_cents",
            "message": (
                "stated_total_cents must be greater than or equal to zero."
            ),
        }
    ]


def test_empty_line_items_returns_invalid_value():
    invoice = _valid_invoice()
    invoice["line_items"] = []

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "INVALID_VALUE",
            "field": "line_items",
            "message": "line_items must be a nonempty list.",
        }
    ]


def test_zero_quantity_returns_invalid_value():
    invoice = _valid_invoice()
    invoice["line_items"][0]["quantity"] = 0

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "INVALID_VALUE",
            "field": "quantity",
            "message": "quantity must be greater than zero.",
            "index": 0,
            "item_code": "PAPER-A4",
        }
    ]


def test_line_total_mismatch_returns_line_total_mismatch():
    invoice = _valid_invoice()
    invoice["line_items"][0]["stated_line_total_cents"] = 1

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "LINE_TOTAL_MISMATCH",
            "field": "stated_line_total_cents",
            "message": (
                "stated_line_total_cents must equal "
                "quantity multiplied by unit_price_cents."
            ),
            "index": 0,
            "item_code": "PAPER-A4",
        }
    ]


def test_duplicate_item_codes_return_duplicate_item_code():
    invoice = _valid_invoice()
    invoice["line_items"].append(deepcopy(invoice["line_items"][0]))
    invoice["stated_total_cents"] = 240000

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "DUPLICATE_ITEM_CODE",
            "field": "item_code",
            "message": "item_code must not appear more than once.",
            "index": 1,
            "item_code": "PAPER-A4",
        }
    ]


def test_non_integer_quantity_returns_invalid_type():
    invoice = _valid_invoice()
    invoice["line_items"][0]["quantity"] = 10.5

    issues = validate_invoice(invoice)

    assert issues == [
        {
            "code": "INVALID_TYPE",
            "field": "quantity",
            "message": "quantity must be an integer.",
            "index": 0,
            "item_code": "PAPER-A4",
        }
    ]
