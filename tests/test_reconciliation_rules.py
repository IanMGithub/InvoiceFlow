from app.reconciliation import compare_line_items, reconcile_invoice


def test_po_item_absent_from_invoice_returns_po_item_missing():
    invoice_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 10,
            "unit_price_cents": 12000,
        }
    ]
    po_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 10,
            "unit_price_cents": 12000,
        },
        {
            "item_code": "TONER-BK",
            "quantity": 6,
            "unit_price_cents": 15000,
        },
    ]

    issues = compare_line_items(invoice_lines, po_lines)

    assert issues == [
        {
            "code": "PO_ITEM_MISSING_FROM_INVOICE",
            "item_code": "TONER-BK",
        }
    ]


def test_incorrect_stated_line_total_returns_invoice_line_total_mismatch():
    invoice = {
        "stated_total_cents": 1,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
                "stated_line_total_cents": 1,
            }
        ],
    }
    po = {
        "total_cents": 1,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
            }
        ],
    }

    issues = reconcile_invoice(invoice, po)

    assert issues == [
        {
            "code": "INVOICE_LINE_TOTAL_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_cents": 120000,
            "observed_cents": 1,
            "difference_cents": -119999,
        }
    ]


def test_stated_total_not_equal_to_line_sum_returns_invoice_total_mismatch():
    invoice = {
        "stated_total_cents": 99999,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
                "stated_line_total_cents": 120000,
            }
        ],
    }
    po = {
        "total_cents": 99999,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
            }
        ],
    }

    issues = reconcile_invoice(invoice, po)

    assert issues == [
        {
            "code": "INVOICE_TOTAL_MISMATCH",
            "expected_cents": 120000,
            "observed_cents": 99999,
            "difference_cents": -20001,
        }
    ]


def test_valid_invoice_and_po_return_no_issues():
    invoice = {
        "stated_total_cents": 210000,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
                "stated_line_total_cents": 120000,
            },
            {
                "item_code": "TONER-BK",
                "quantity": 6,
                "unit_price_cents": 15000,
                "stated_line_total_cents": 90000,
            },
        ],
    }
    po = {
        "total_cents": 210000,
        "line_items": [
            {
                "item_code": "PAPER-A4",
                "quantity": 10,
                "unit_price_cents": 12000,
            },
            {
                "item_code": "TONER-BK",
                "quantity": 6,
                "unit_price_cents": 15000,
            },
        ],
    }

    issues = reconcile_invoice(invoice, po)

    assert issues == []


def test_quantity_and_unit_price_mismatch_on_same_line_both_returned():
    invoice_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 5,
            "unit_price_cents": 15000,
        }
    ]
    po_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 6,
            "unit_price_cents": 12000,
        }
    ]

    issues = compare_line_items(invoice_lines, po_lines)

    assert issues == [
        {
            "code": "QUANTITY_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_quantity": 6,
            "observed_quantity": 5,
            "difference_quantity": -1,
        },
        {
            "code": "UNIT_PRICE_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_cents": 12000,
            "observed_cents": 15000,
            "difference_cents": 3000,
        },
    ]


def test_missing_po_item_does_not_prevent_other_line_checks():
    invoice_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 5,
            "unit_price_cents": 15000,
        }
    ]
    po_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 10,
            "unit_price_cents": 12000,
        },
        {
            "item_code": "TONER-BK",
            "quantity": 6,
            "unit_price_cents": 15000,
        },
    ]

    issues = compare_line_items(invoice_lines, po_lines)

    assert issues == [
        {
            "code": "QUANTITY_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_quantity": 10,
            "observed_quantity": 5,
            "difference_quantity": -5,
        },
        {
            "code": "UNIT_PRICE_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_cents": 12000,
            "observed_cents": 15000,
            "difference_cents": 3000,
        },
        {
            "code": "PO_ITEM_MISSING_FROM_INVOICE",
            "item_code": "TONER-BK",
        },
    ]
