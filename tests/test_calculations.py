from datetime import date


def test_calculate_total_repaid_map_excludes_late_fee():
    from app import calculate_total_repaid_map

    repayments = [
        {
            "loan_id": "LOAN-001",
            "repayment_amount": "30000",
            "payment_type": "REPAYMENT",
        },
        {
            "loan_id": "LOAN-001",
            "repayment_amount": "10000",
            "payment_type": "REPAYMENT",
        },
        {
            "loan_id": "LOAN-001",
            "repayment_amount": "5000",
            "payment_type": "LATE_FEE",
        },
    ]

    result = calculate_total_repaid_map(repayments)

    assert result["LOAN-001"] == 40000


def test_calculate_late_fee_paid_map_excludes_normal_repayment():
    from app import calculate_late_fee_paid_map

    repayments = [
        {
            "loan_id": "LOAN-001",
            "repayment_amount": "30000",
            "payment_type": "REPAYMENT",
        },
        {
            "loan_id": "LOAN-001",
            "repayment_amount": "2000",
            "payment_type": "LATE_FEE",
        },
        {
            "loan_id": "LOAN-001",
            "repayment_amount": "1000",
            "payment_type": "LATE_FEE",
        },
    ]

    result = calculate_late_fee_paid_map(repayments)

    assert result["LOAN-001"] == 3000


def test_calc_overdue_days_with_grace_period():
    from app import calc_overdue_days

    today = date(2026, 8, 31)

    overdue_days = calc_overdue_days(
        today=today,
        due_date_str="2026-08-20",
        grace_period_days=3,
    )

    assert overdue_days == 8

def test_build_unpaid_loan_rows_partial_repayment():
    from app import build_unpaid_loan_rows

    loans = [
        {
            "loan_id": "LOAN-PARTIAL",
            "customer_id": "CUST-001",
            "loan_amount": "100000",
            "loan_date": "2026-08-01",
            "due_date": "2026-12-31",
            "repayment_expected": "110000",
            "grace_period_days": "0",
            "late_fee_rate_percent": "5",
            "late_base_amount": "100000",
            "contract_status": "ACTIVE",
        }
    ]

    repayments = [
        {
            "loan_id": "LOAN-PARTIAL",
            "repayment_amount": "30000",
            "payment_type": "REPAYMENT",
        }
    ]

    rows = build_unpaid_loan_rows(loans, repayments)

    assert len(rows) == 1
    assert rows[0]["total_repaid"] == 30000
    assert rows[0]["remaining"] == 80000
    assert rows[0]["status"] == "UNPAID"


def test_build_unpaid_loan_rows_excludes_cancelled_loan():
    from app import build_unpaid_loan_rows

    loans = [
        {
            "loan_id": "LOAN-CANCELLED",
            "customer_id": "CUST-002",
            "loan_amount": "100000",
            "loan_date": "2026-08-01",
            "due_date": "2026-12-31",
            "repayment_expected": "110000",
            "grace_period_days": "0",
            "late_fee_rate_percent": "5",
            "late_base_amount": "100000",
            "contract_status": "CANCELLED",
        }
    ]

    rows = build_unpaid_loan_rows(loans, [])

    assert rows == []


def test_build_unpaid_loan_rows_marks_overdue():
    from app import build_unpaid_loan_rows

    loans = [
        {
            "loan_id": "LOAN-OVERDUE",
            "customer_id": "CUST-003",
            "loan_amount": "100000",
            "loan_date": "2026-07-01",
            "due_date": "2026-07-31",
            "repayment_expected": "110000",
            "grace_period_days": "0",
            "late_fee_rate_percent": "6",
            "late_base_amount": "100000",
            "contract_status": "ACTIVE",
        }
    ]

    rows = build_unpaid_loan_rows(loans, [])

    assert len(rows) == 1
    assert rows[0]["status"] == "OVERDUE"
    assert rows[0]["overdue_days"] > 0
    assert rows[0]["late_fee_amount"] > 0
    assert rows[0]["current_collect_amount"] > rows[0]["remaining"]


def test_build_unpaid_loan_rows_late_fee_only():
    from app import build_unpaid_loan_rows

    loans = [
        {
            "loan_id": "LOAN-LATE-ONLY",
            "customer_id": "CUST-004",
            "loan_amount": "100000",
            "loan_date": "2026-07-01",
            "due_date": "2026-07-31",
            "repayment_expected": "110000",
            "grace_period_days": "0",
            "late_fee_rate_percent": "6",
            "late_base_amount": "100000",
            "contract_status": "ACTIVE",
        }
    ]

    repayments = [
        {
            "loan_id": "LOAN-LATE-ONLY",
            "repayment_amount": "110000",
            "payment_type": "REPAYMENT",
        }
    ]

    rows = build_unpaid_loan_rows(loans, repayments)

    assert len(rows) == 1
    assert rows[0]["remaining"] == 0
    assert rows[0]["late_fee_remaining"] > 0
    assert rows[0]["status"] == "LATE_FEE_ONLY"