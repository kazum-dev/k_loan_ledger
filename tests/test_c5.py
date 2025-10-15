from datetime import date
import csv
from pathlib import Path
import io
from modules.loan_module import (
    calc_overdue_days, calc_late_fee, compute_recovery_amount,
    calculate_total_repaid_by_loan_id, display_unpaid_loans,
)

def test_overdue_with_grace_threshold():
    # due=2025-10-10, grace=5 → 閾値=10/15
    assert calc_overdue_days(date(2025,10,15), "2025-10-10", 5) == 0
    assert calc_overdue_days(date(2025,10,16), "2025-10-10", 5) == 1

def test_recovery_total_formula():
    info = compute_recovery_amount(
        repayment_expected=1100, total_repaid=0,
        today=date(2025,10,15), due_date_str="2025-10-05", grace_period_days=0,
        late_fee_rate_percent=10.0, late_base_amount=1000
    )
    # overdue_days = 10, late_fee = 1000 * 10% * (10/30) = 33.333.. → 33円
    assert info["remaining"] == 1100
    assert info["late_fee"] == 33
    assert info["recovery_total"] == 1133

def test_late_fee_zero_when_not_overdue():
    fee = calc_late_fee(late_base_amount=1000, late_fee_rate_percent=10.0, overdue_days=0)
    assert fee == 0.0

def test_empty_repayments_returns_zero(tmp_path: Path):
    # 空の repayments.csv を用意
    rep = tmp_path / "repayments.csv"
    rep.write_text("loan_id,customer_id,repayment_amount,repayment_date\n", encoding="utf-8")
    assert calculate_total_repaid_by_loan_id(str(rep), "ANY") == 0

def test_repayments_header_aliases_supported(tmp_path: Path):
    # ヘッダの表記ゆれ repayed_amount / repay_amount を吸収
    rep = tmp_path / "repayments.csv"
    with rep.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["loanid","payer","repay_amount","date"])
        w.writerow(["L001","CUST001","500","2025-10-01"])
    assert calculate_total_repaid_by_loan_id(str(rep), "L001") == 500

def test_invalid_due_date_row_is_handled(tmp_path: Path, monkeypatch):
    # loan_v3.csv に不正な due_date を持つ未返済1件を用意
    loans = tmp_path / "loan_v3.csv"
    with loans.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "loan_id","customer_id","loan_amount","loan_date","due_date",
            "interest_rate_percent","repayment_expected","repayment_method",
            "grace_period_days","late_fee_rate_percent","late_base_amount"
        ])
        w.writerow(["L_BADDATE","CUST999","1000","2025-10-01","BAD_DATE",
                    "10.0","1100","CASH","0","10.0","1000"])
    reps = tmp_path / "repayments.csv"
    reps.write_text("loan_id,customer_id,repayment_amount,repayment_date\n", encoding="utf-8")

    rows = display_unpaid_loans(
        "CUST999", loan_file=str(loans), repayment_file=str(reps),
        filter_mode="all", today=date(2025,10,15)
    )
    assert rows and rows[0]["status"] == "DATE_ERR"
