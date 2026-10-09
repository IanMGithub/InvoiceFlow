from app.reconciliation import compare_totals


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
