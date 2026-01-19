from modules.loan_module import get_unpaid_loans_rows

def test_unpaid_excludes_cancelled(tmp_path):
    loans = tmp_path / "loan_v3.csv"
    reps  = tmp_path / "repayments.csv"

    loans.write_text(
        "loan_id,customer_id,loan_amount,loan_date,interest_rate_percent,"
        "repayment_expected,repayment_method,grace_period_days,"
        "late_fee_rate_percent,late_base_amount,contract_status\n"
        "L1,C001,10000,2025-01-01,100,20000,CASH,0,10,10000,CANCELLED\n"
        "L2,C001,5000,2025-01-02,100,10000,CASH,0,10,5000,ACTIVE\n",
        encoding="utf-8"
    )

    reps.write_text(
        "loan_id,customer_id,repayment_amount,repayment_date,payment_type\n",
        encoding="utf-8"
    )

    rows = get_unpaid_loans_rows(
        "C001",
        loan_file=str(loans),
        repayment_file=str(reps),
    )

    assert len(rows) == 1
    assert rows[0]["loan_id"] == "L2"
