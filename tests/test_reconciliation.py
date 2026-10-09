from app.reconciliation import compare_totals, compare_line_items


def test_matching_totals_return_no_issues():
    issues = compare_totals(
        invoice_total_cents=210000,
        po_total_cents=210000,
    )

    assert issues == []


def test_different_totals_return_mismatch_issue():
    issues = compare_totals(
        invoice_total_cents=240000,
        po_total_cents=210000,
    )

    assert issues == [
        {
            "code": "PO_TOTAL_MISMATCH",
            "expected_cents": 210000,
            "observed_cents": 240000,
            "difference_cents": 30000,
        }
    ]


def test_different_totals_return_negative_difference():
    issues = compare_totals(
        invoice_total_cents=195000,
        po_total_cents=210000,
    )

    assert issues == [
        {
            "code": "PO_TOTAL_MISMATCH",
            "expected_cents": 210000,
            "observed_cents": 195000,
            "difference_cents": -15000,
        }
    ]


def test_unmatched_item_does_not_stop_other_price_checks():
    invoice_lines = [
        {
            "item_code": "UNKNOWN-ITEM",
            "quantity": 1,
            "unit_price_cents": 1000
        },
        {
            "item_code": "PAPER-A4",
            "quantity": 1,
            "unit_price_cents": 15000
        },
    ]

    po_lines = [
        {
            "item_code": "PAPER-A4",
            "quantity": 1,
            "unit_price_cents": 12000
        },
    ]

    issues = compare_line_items(invoice_lines, po_lines)

    assert issues == [
        {
            "code": "ITEM_UNMATCHED",
            "item_code": "UNKNOWN-ITEM",
        },
        {
            "code": "UNIT_PRICE_MISMATCH",
            "item_code": "PAPER-A4",
            "expected_cents": 12000,
            "observed_cents": 15000,
            "difference_cents": 3000,
        },
    ]


def test_multiple_po_matches_return_ambiguity_issue():
    invoice_lines = [
        {"item_code": "PAPER-A4", "unit_price_cents": 12000},
    ]

    po_lines = [
        {"item_code": "PAPER-A4", "unit_price_cents": 12000},
        {"item_code": "PAPER-A4", "unit_price_cents": 13000},
    ]

    issues = compare_line_items(invoice_lines, po_lines)

    assert issues == [
        {
            "code": "ITEM_MATCH_AMBIGUOUS",
            "item_code": "PAPER-A4",
            "match_count": 2,
        }
    ]
